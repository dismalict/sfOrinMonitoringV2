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
    
# Ensure other packages is installed
apt-get install -y nano
