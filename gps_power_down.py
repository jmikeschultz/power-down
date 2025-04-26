import os
import time
import json
import logging
import yaml
import subprocess
from geopy.distance import geodesic

# === CONFIG ===
GPS_PATH = "/home/mike/.cache/boat/current_position.json"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "gps_power_down.yaml")
MIN_WAIT_MINS = 10
ONE_MINUTE = 60
# === LOGGING ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
log = logging.getLogger("gps_power_down service")

# === HELPERS ===
def load_config():
    try:
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
            return config or {}
    except Exception as e:
        log.error(f"Failed to load config from {CONFIG_PATH}: {e}")
        return {}

def get_gps():
    try:
        with open(GPS_PATH) as f:
            data = json.load(f)
            return (data["lat"], data["lon"])
    except Exception as e:
        log.warning(f"No GPS: {e}")
        return None

def close_enough(current, target, max_miles):
    try:
        return geodesic(current, target).miles <= max_miles
    except:
        return False

def shutdown():
    log.info("Initiating shutdown...")
    subprocess.run(["wall", "Shutting down now..."])
    subprocess.run(["sudo", "shutdown", "-h", "now"])

# === MAIN LOOP ===
def run():
    log.info("Starting gps_power_down service")

    shutdown_minute_counter = None

    while True:
        config = load_config()

        if not config.get("enable", True):
            log.info("gps_power_down disabled via config")
            shutdown_timer_start = None
            time.sleep(10)
            continue

        shutdown_wait_mins = max(config.get("shutdown_wait_mins", 10), MIN_WAIT_MINS) # don't let be too small!
        max_miles = config.get("max_miles", 0.1)
        target_lat = config.get("target_lat")
        target_lon = config.get("target_lon")

        if target_lat is None or target_lon is None:
            log.error("Missing target lat/lon in config")
            time.sleep(check_interval_secs)
            continue

        gps = get_gps()
        if not gps:
            log.info("No GPS position available")
            time.sleep(check_interval_secs)
            continue

        target = (target_lat, target_lon)

        if close_enough(gps, target, max_miles):
            if shutdown_minute_counter is None:
                log.info(f"Near target, shutdown will occur in {shutdown_wait_mins} minutes if you remain here.")
                subprocess.run(["wall", f"Near target, shutdown will occur in {shutdown_wait_mins} minutes if you remain here."])
                shutdown_minute_counter = 0
            elif shutdown_minute_counter < shutdown_wait_mins-1:
                shutdown_minute_counter += 1
                log.info(f"Shutdown will occur in {shutdown_wait_mins-shutdown_minute_counter} minutes")
                subprocess.run(["wall", f"Shutdown will occur in {shutdown_wait_mins-shutdown_minute_counter} minutes"])
            else:
                log.info("Shutting down, Bye!")
                subprocess.run(["wall", "Shutting down, Bye!"])
                shutdown()
                break                

        else:
            if shutdown_timer_start is not None:
                log.info("Moved away from target, cancelling shutdown")
                subprocess.run(["wall", "Moved away from target, cancelling shutdown"])
                shutdown_timer_start = None

        time.sleep(ONE_MINUTE)

if __name__ == "__main__":
    run()
