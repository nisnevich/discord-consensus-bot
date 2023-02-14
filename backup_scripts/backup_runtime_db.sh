#!/bin/bash

# How long to keep the backups
BACKUP_MAX_LIFE_SECONDS=432000 # 5 days in seconds
# Current date and time for naming the backup
CURRENT_DATETIME="$(date +%Y-%m-%d-%H-%M-%S)"
# Name of the bucket
BUCKET="consensus-bot-dbs"
# Directory where the history database is stored on the cloud
RUNTIME_DB_DIR="runtime-db"
# Name of the database to backup
RUNTIME_DB="consensus-bot.db"
# Log file
LOG_FILE_PATH="$CONSENSUS_LOGS_DIR/backup-runtime-db.log"

# Backups should only be made on prod
if [ "$CONSENSUS_BACKUP_ENABLED" -eq 0 ]; then
  echo "Backup is disabled, exiting." | tee -a "$LOG_FILE_PATH"
  exit 0
fi

# Backup the runtime database to Google Cloud Storage
gsutil cp $CONSENSUS_PROJECT_ROOT/$RUNTIME_DB gs://$BUCKET/$RUNTIME_DB_DIR/$CURRENT_DATETIME-$RUNTIME_DB 2>&1 | tee -a "$LOG_FILE_PATH"

# Remove backups older than 72 hours
gsutil ls gs://$BUCKET/ | while read -r file; do
  created_time=$(gsutil ls -L "$file" | grep "Creation time" | awk '{print $3,$4}')
  current_time=$(date +%Y-%m-%d\ %H:%M:%S)
  created_timestamp=$(date -d "$created_time" +%s)
  current_timestamp=$(date -d "$current_time" +%s)
  diff_timestamp=$((current_timestamp-created_timestamp))

  if [ $diff_timestamp -gt $BACKUP_MAX_LIFE_SECONDS ]; then 
    gsutil rm "$file" 2>&1 | tee -a "$LOG_FILE_PATH"
  fi
done
