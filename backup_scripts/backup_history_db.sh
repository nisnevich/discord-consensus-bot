#!/bin/bash

source $CONSENSUS_PROJECT_ROOT/env_vars.sh

# Current date and time
CURRENT_DATETIME="$(date +%Y-%m-%d-%H-%M-%S)"
# Name of the bucket
BUCKET="consensus-bot-dbs"
# Name of the database to backup
HISTORY_DB="consensus-bot-history.db"
# Log file
LOG_FILE_PATH="$CONSENSUS_LOGS_DIR/backup-history-db.log"
# Create log file if it's missing
mkdir -p "$(dirname "$LOG_FILE_PATH")"
touch "$LOG_FILE_PATH"

# Backups should only be made on prod
if [ "$CONSENSUS_BACKUP_ENABLED" -eq 0 ]; then
  echo "Backup is disabled, exiting." | tee -a "$LOG_FILE_PATH"
  exit 0
fi

echo "$CURRENT_DATETIME Copying history DB..." | tee -a "$LOG_FILE_PATH"
# Backup the runtime database to Google Cloud Storage
gsutil cp $CONSENSUS_PROJECT_ROOT/$HISTORY_DB gs://$BUCKET/$HISTORY_DB 2>&1 | tee -a "$LOG_FILE_PATH"
