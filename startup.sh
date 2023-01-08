#!/bin/bash

# Install python3 and pip3 if they are not already installed
if ! command -v python3 &> /dev/null; then
  echo "Installing python3..."
  apt-get update
  apt-get install python3 -y
fi
if ! command -v pip3 &> /dev/null; then
  echo "Installing pip3..."
  apt-get update
  apt-get install python3-pip -y
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    # Install npm
    curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# Install pm2 if it is not already installed
if ! command -v pm2 &> /dev/null; then
  echo "Installing pm2..."
  npm install -g pm2
fi

# Install required python packages
echo "Installing required python packages..."
pip3 install -r requirements.txt

# Set up pm2 to run on reboot
pm2 startup

# Run main.py with pm2
pm2 start main.py --name "eco-lazy-consensus-bot"

# Save the current process list
pm2 save
