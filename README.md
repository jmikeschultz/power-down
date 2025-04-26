# power-down
powers down the pi if it remains N minutes within X of a lat lon

# 2. Create the systemd service file
cp into /etc/systemd/system/gps_power_down.service


# 3. Reload systemd, enable and start service
sudo systemctl daemon-reload
sudo systemctl enable gps_power_down.service
sudo systemctl start gps_power_down.service

# 4. Check status (optional)
sudo systemctl status gps_power_down.service

# Logs will be in /var/log/gps_power_down.log
