#!/bin/bash

export CONSENSUS_PROJECT_ROOT="$PWD"
export CONSENSUS_LOGS_DIR="$CONSENSUS_PROJECT_ROOT/logs"
# Backup is only needed to be enabled on prod, so this variable should be 1 only in the prod branch, unless it's used for testing purposes
export CONSENSUS_BACKUP_ENABLED=1

# ============
# Setup Python
# ============

# Install python3 if it's not already installed
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
# Install pip3 if it's not already installed
if ! command -v pip3 &> /dev/null; then
  echo "Installing pip3..."
  apt-get update
  apt-get install python3-pip -y
fi


# ===========================================
# Setup PM2 (used for runtime sustainability)
# ===========================================

# Install npm if it's not already installed
if ! command -v npm &> /dev/null; then
  curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
# Install pm2 if it is not already installed
if ! command -v pm2 &> /dev/null; then
  echo "Installing pm2..."
  npm install -g pm2
fi


# ==================================
# Setup DB backups to Google Storage
# ==================================

if [ $CONSENSUS_BACKUP_ENABLED -eq 1 ]; then
  # Install google-cloud-sdk (includes gsutil and gcloud) if it is not already installed
  if ! command -v google-cloud-sdk &> /dev/null; then
    # Add the Cloud SDK distribution URI as a package source
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
    # Import the Google Cloud Platform public key
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
    # Update the package list
    sudo apt-get update
    # Install the Google Cloud SDK
    sudo apt-get install google-cloud-sdk
  fi
  # Initiate gcloud authentication (you'll need another machine that has a web browser)
  gcloud auth application-default login --no-browser
  echo "Note that you need to add a project that will be billed by running 'gcloud auth application-default set-quota-project project-name' (replace 'project-name' with the relevant name)."
  echo "For other users (to run the bot on other evn), copy ~/.config/gcloud/ to their home dir"
  # # As per the above message, you also have to run this:
  # project_name='project-001'
  # gcloud auth application-default set-quota-project $project_name
  #
  # # If you have other users, copy the credential file to them:
  # username='prod'
  # sudo mkdir -p /home/$username/.config/gcloud/
  # sudo cp -R ~/.config/gcloud/ /home/$username/.config/gcloud/
  #
  # # Don't forget to change owner:
  # sudo chown -R $username:$username /home/$username/.config
fi


# ===========================
# Setup cron jobs for backups
# ===========================

# The cron entries to be added
# FIXME
# # Backup runtime DB every 30 mins
# cron_entry_runtime="30 * * * * $(pwd)/backup_scripts/backup_runtime_db.sh"
# # Backup history DB every day at midnight
# cron_entry_history="0 0 * * * $(pwd)/backup_scripts/backup_history_db.sh"
# Testing values
cron_entry_runtime="* * * * * $(pwd)/backup_scripts/backup_runtime_db.sh"
cron_entry_history="* * * * * $(pwd)/backup_scripts/backup_history_db.sh"

# Check if the cron entry for history db is already in the cron file
if ! crontab -l | grep "$cron_entry_history"; then
  # If not, add it
  (crontab -l; echo "$cron_entry_history") | crontab -
  # Confirm that the cron entry has been added
  echo "Successfully added cron entry: $cron_entry_history"
else
  # If the cron entry already exists, do nothing
  echo "Cron entry already exists: $cron_entry_history"
fi

# Check if the cron entry for runtime db is already in the cron file
if ! crontab -l | grep "$cron_entry_runtime"; then
  # If not, add it
  (crontab -l; echo "$cron_entry_runtime") | crontab -
  # Confirm that the cron entry has been added
  echo "Successfully added cron entry: $cron_entry_runtime"
else
  # If the cron entry already exists, do nothing
  echo "Cron entry already exists: $cron_entry_runtime"
fi

# Print logs
echo "The updated crontab:"
crontab -l


# ==================================
# Setup Python dependencies (wheels)
# ==================================

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


# =========
# Run tests
# =========

echo "Running unit tests..."
# Run unit tests
output=$(python3 -m unittest discover -s bot/tests -p test_*.py -v || exit 1)
# Check if any test failed
if echo "$output" | grep -q "FAILED"; then
  echo "Error: Unit tests failed."
  echo "$output"
  exit 1
fi


# ================
# Starting the bot
# ================

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
