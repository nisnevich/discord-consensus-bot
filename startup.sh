#!/bin/bash

# Definition of some helper methods
print_section() {
  title="$1"
  color="\033[1;33m"
  reset_color="\033[0m"
  printf "\n\n${color}==========  %s  ==========${reset_color}\n\n" "$title"
}

# ===================
# Setup env variables
# ===================

print_section "Setting up env..."

# Set the project root directory to the parent directory of the script directory
export CONSENSUS_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Add project root to .bashrc
line="export CONSENSUS_PROJECT_ROOT=$CONSENSUS_PROJECT_ROOT"
# Check if it's already there
if grep -Fxq "$line" ~/.bashrc; then
    echo "Project root has already been added to .bashrc"
else
    # Add the line to .bashrc
    echo "$line" >> ~/.bashrc
    echo "Added project root to .bashrc"
fi

# Load the rest of the environmental variables
source env_vars.sh


# ============
# Setup Python
# ============

print_section "Verifying Python installation..."

# Install python3 if it's not already installed
if ! command -v python3 &> /dev/null; then
  echo "Installing python3..."
  apt-get update
  apt-get install python3 -y
  echo "Adding python3 to PATH..."
  export PATH=$PATH:/usr/bin/python3
else
  echo "Python is already installed."
fi
# Check if python is available in path, or drop error otherwise
if ! command -v python3 &> /dev/null; then
  echo "ERROR: Python3 not found in PATH!"
  exit 1
else
  echo "python3 is in the PATH."
fi
# Install pip3 if it's not already installed
if ! command -v pip3 &> /dev/null; then
  echo "Installing pip3..."
  apt-get update
  apt-get install python3-pip -y
else
  echo "pip3 is already installed."
fi


# ===========================================
# Setup PM2 (used for runtime sustainability)
# ===========================================

print_section "Verifying PM2 installation..."

# Install npm if it's not already installed
if ! command -v npm &> /dev/null; then
  curl -sL https://deb.nodesource.com/setup_12.x | sudo -E bash -
  sudo apt-get install -y nodejs
else
  echo "NodeJS is already installed."
fi
# Install pm2 if it is not already installed
if ! command -v pm2 &> /dev/null; then
  echo "Installing pm2..."
  npm install -g pm2
else
  echo "PM2 is already installed."
fi


# ==================================
# Setup DB backups to Google Storage
# ==================================

print_section "Verifying backup configuration..."

if [ $CONSENSUS_BACKUP_ENABLED -eq 1 ]; then
  # Install google-cloud-sdk (includes gsutil and gcloud) if it is not already installed
  if ! which gcloud &> /dev/null; then
    echo "Installing Google Cloud SDK..."
    # Add the Cloud SDK distribution URI as a package source
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | sudo tee -a /etc/apt/sources.list.d/google-cloud-sdk.list
    # Import the Google Cloud Platform public key
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
    # Update the package list
    sudo apt-get update
    # Install the Google Cloud SDK
    sudo apt-get install google-cloud-sdk
  else
    echo "Google Cloud SDK is already installed."
  fi
  
  # Initiate gcloud authentication (you'll need another machine that has a web browser)
  if [[ -n $(gcloud auth application-default print-access-token 2>/dev/null) ]]; then
    echo "Google Cloud authorization has already been made."
  else
    echo "Missing Google Cloud token, starting no-browser authorization..."
    # Initiate gcloud no-browser authentication (requires another machine with a browser to login)
    gcloud auth login --no-browser
    gcloud auth application-default login --no-browser
  fi

  # Verify the quota project has been set, and set the config otherwise
  if [[ -n $(gcloud config get-value core/project 2>/dev/null) ]]; then
    current_project=$(gcloud config get-value core/project)
    if [[ "$current_project" == "$GOOGLE_CLOUD_PROJECT_NAME" ]]; then
      echo "The quota project is already set to $GOOGLE_CLOUD_PROJECT_NAME"
    else
      echo "The quota project is set to $current_project. Setting it to $GOOGLE_CLOUD_PROJECT_NAME"
      gcloud auth application-default set-quota-project $GOOGLE_CLOUD_PROJECT_NAME
    fi
  else
    echo "The current project is not set. Setting it to $GOOGLE_CLOUD_PROJECT_NAME..."
    gcloud config set core/project $GOOGLE_CLOUD_PROJECT_NAME
    gcloud auth application-default set-quota-project $GOOGLE_CLOUD_PROJECT_NAME
  fi

  # ===========================
  # Setup cron jobs for backups
  # ===========================
  
  echo "Verifying cron entries for backup scripts..."

  # Cron entry for runtime DB
  cron_entry_runtime="$CRON_RUNTIME_DB_BACKUP_SCHEDULE CONSENSUS_PROJECT_ROOT=$CONSENSUS_PROJECT_ROOT /bin/bash $CONSENSUS_PROJECT_ROOT/backup_scripts/backup_runtime_db.sh >> $LOG_BACKUP_RUNTIME_FILE_PATH 2>&1"
  # Cron entry for history DB
  cron_entry_history="$CRON_HISTORY_DB_BACKUP_SCHEDULE CONSENSUS_PROJECT_ROOT=$CONSENSUS_PROJECT_ROOT /bin/bash $CONSENSUS_PROJECT_ROOT/backup_scripts/backup_history_db.sh >> $LOG_BACKUP_HISTORY_FILE_PATH 2>&1"

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
  echo "The crontab:"
  crontab -l
else
  echo "Backups are disabled."
fi


# ==================================
# Setup Python dependencies (wheels)
# ==================================

print_section "Enabling python dependencies..."

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

print_section "Running unit tests..."
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

print_section "Starting the bot..."

# Check if "pm2 startup" was already set up before running it
if ! command -v pm2 startup &> /dev/null; then
  echo "Enabling pm2 to run on reboot..."
  # Set up pm2 to run on reboot
  pm2 startup
else
  echo "PM2 on-reboot starup is already enabled."
fi

# Run main.py with pm2 (and log any output of this command in a bright color to distinguish it easily)
echo -e "\033[1;33m"
# Even though --auto-restart isn't available in pm2 free vesion, testing showed that the bot actually gets restarted whenever it crashes with exception or just exits
pm2 start main.py --interpreter python3 --name "eco-lazy-consensus-bot-beta" 
echo -e "\033[0m"

# Save the current process list to run on startup
pm2 save

# Some pm2 commands for monitoring:
# pm2 show eco-lazy-consensus-bot # show general usage information
# pm2 logs eco-lazy-consensus-bot [--lines 1000] # display logs
# pm2 env 0 # display environment variables
# pm2 monit # monitor CPU and Memory usage eco-lazy-consensus-bot
