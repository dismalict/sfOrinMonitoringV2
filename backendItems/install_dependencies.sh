#!/bin/bash

# Check if the script is run as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root or with sudo"
  exit
fi

# Update package list
echo "Updating package list..."
apt-get update

# Install pip if not installed
if ! command -v pip &> /dev/null; then
    echo "pip not found, installing..."
    apt-get install -y python3-pip
fi

# Install required Python packages
pip3 install --upgrade \
    mysql-connector-python \
    jetson-stats \
    psutil \
    configparser \
    subprocess32

# Ensure other packages are installed
apt-get install -y nano

# -----------------------------
# Systemd service setup
# -----------------------------
SERVICE_FILE="/home/administrator/sfOrinMonitoringV2/backendItems/dismalOrinGather.service"
DEST="/etc/systemd/system/dismalOrinGather.service"

echo "Installing systemd service..."

# Copy the service file
cp "$SERVICE_FILE" "$DEST"

# Reload systemd, enable, and start the service
systemctl daemon-reload
systemctl enable dismalOrinGather.service
systemctl restart dismalOrinGather.service

echo "Service dismalOrinGather installed and started!"
