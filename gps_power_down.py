import os
import time
import logging
import yaml
import subprocess
from geopy.distance import geodesic
import gpsd

# === CONFIG ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "gps_power_down.yaml")
MIN_WAIT_MINS = 10
ONE_MINUTE = 60

# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("gps_power_down service")

shared = logging.getLogger("shared")
shared_handler = logging.FileHandler("/var/log/updown.log")
shared_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
shared.addHandler(shared_handler)
shared.setLevel(logging.INFO)
shared.propagate = False

# === HELPERS ===
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        log.error(f"Failed to load config from {CONFIG_PATH}: {e}")
        return {}

def shutdown():
    log.info("Initiating shutdown...")
    subprocess.run(["wall", "Shutting down now..."])
    subprocess.run(["sudo", "shutdown", "-h", "now"])

def get_current_position():
    try:
        packet = gpsd.get_current()
        if packet.mode >= 2:
            return (packet.lat, packet.lon)
    except Exception as e:
        log.warning(f"GPSD error: {e}")
    return None

# === MAIN LOOP ===
def run():
    log.info("Starting gps_power_down service")
    shared.info(f"system coming up")
    
    try:
        gpsd.connect()
    except Exception as e:
        log.error(f"Failed to connect to gpsd: {e}")
        return

    shutdown_minute_counter = None
    same_location_start_time = None
    last_position = None

    while True:
        config = load_config()
        dist_threshold_meters = config.get("dist_threshold_meters", 20)

        if not config.get("enable", True):
            log.info("gps_power_down disabled via config")
            shutdown_minute_counter = None
            same_location_start_time = None
            last_position = None
            time.sleep(ONE_MINUTE)
            continue

        max_secs_at_location = config.get("max_secs_at_location", 600)
        shutdown_wait_mins = max(config.get("shutdown_wait_mins", 10), MIN_WAIT_MINS)

        position = get_current_position()
        if not position:
            log.info("No GPS fix available")
            time.sleep(ONE_MINUTE)
            continue

        if last_position is None:
            last_position = position
            same_location_start_time = time.time()
            log.info(f"Tracking new location: {position}")
        else:
            dist = geodesic(last_position, position).meters
            if dist < dist_threshold_meters:
                secs_at_location = int(time.time() - same_location_start_time)
                log.info(f"secs at location: {secs_at_location}")
            else:
                log.info(f"Moved {dist:.1f}m — resetting location timer")
                last_position = position
                same_location_start_time = time.time()
                shutdown_minute_counter = None
                time.sleep(ONE_MINUTE)
                continue

            if secs_at_location >= max_secs_at_location:
                if shutdown_minute_counter is None:
                    log.info(f"secs at location: {secs_at_location}, shutdown in {shutdown_wait_mins} minutes if you remain here.")
                    subprocess.run(["wall", f"secs at location: {secs_at_location}, shutdown in {shutdown_wait_mins} minutes if you remain here."])
                    shutdown_minute_counter = 0
                elif shutdown_minute_counter < shutdown_wait_mins - 1:
                    shutdown_minute_counter += 1
                    log.info(f"Shutdown will occur in {shutdown_wait_mins - shutdown_minute_counter} minutes")
                    subprocess.run(["wall", f"Shutdown will occur in {shutdown_wait_mins - shutdown_minute_counter} minutes"])
                else:
                    log.info(f"Shutting down at location: {position}")
                    shared.info(f"gps_power_down at {position}")
                    subprocess.run(["wall", "Shutting down, Bye!"])
                    shutdown()
                    break
            else:
                if shutdown_minute_counter is not None:
                    log.info("Moved or time reset, cancelling shutdown countdown")
                    subprocess.run(["wall", "Moved or time reset, cancelling shutdown"])
                    shutdown_minute_counter = None

        time.sleep(ONE_MINUTE)

if __name__ == "__main__":
    run()
