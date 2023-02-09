#!/bin/bash

# Install python3 and pip3 if they are not already installed
if ! command -v python3 &> /dev/null; then
  echo "Installing python3..."
  apt-get update
  apt-get install python3 -y
  echo "Adding python3 to PATH..."
  export PATH=$PATH:/usr/bin/python3
fi
# Check if python is available in path, or drop error otherwise
if ! command -v python3 &> /dev/null; then
  echo "ERROR: Python3 not found in PATH!"
  exit 1
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

# Check if requirements.txt packages are installed before installing them
if [ ! -f /requirements.txt ]; then 
  echo "Checking if required python packages are installed..."
  for package in $(cat requirements.txt); do
    if ! pip freeze | grep -q "$package"; then
      echo "Installing required python package: $package"
      pip3 install "$package"
    fi
  done
fi

echo "Running unit tests..."
# Run unit tests
output=$(python3 -m unittest discover -s tests -p test_*.py -v || exit 1)
# Check if any test failed
if echo "$output" | grep -q "FAILED"; then
  echo "Error: Unit tests failed."
  echo "$output"
  exit 1
else
  echo "Unit tests passed successfully!"
fi

# Check if "pm2 startup" was already set up before running it
if ! command -v pm2 startup &> /dev/null; then
    # Set up pm2 to run on reboot
    pm2 startup
fi

# Run main.py with pm2 (and log any output of this command in a bright color to distinguish it easily)
echo -e "\033[1;33m"
# Even though --auto-restart isn't available in pm2 free vesion, testing showed that the bot actually gets restarted whenever it crashes with exception or just exits
pm2 start main.py --interpreter python3 --name "eco-lazy-consensus-bot"
echo -e "\033[0m"

# Save the current process list to run on startup
pm2 save

# Some pm2 commands for monitoring:
# pm2 show eco-lazy-consensus-bot # show general usage information
# pm2 logs eco-lazy-consensus-bot [--lines 1000] # display logs
# pm2 env 0 # display environment variables
# pm2 monit # monitor CPU and Memory usage eco-lazy-consensus-bot
