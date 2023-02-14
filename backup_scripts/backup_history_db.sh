#!/bin/bash

# How long to keep the backups
BACKUP_MAX_LIFE_SECONDS = 2592000 # 30 days
# Current date and time for naming the backup
CURRENT_DATETIME="$(date +%Y-%m-%d-%H-%M-%S)"
# Name of the bucket
BUCKET="consensus-bot-dbs"
# Directory where the runtime database is stored on the cloud
HISTORY_DB_DIR="history-db"
# Name of the database to backup
HISTORY_DB="consensus-bot-history.db"
# Log file
LOG_FILE_PATH="$CONSENSUS_LOGS_DIR/backup-history-db.log"

# Backups should only be made on prod
if [ "$CONSENSUS_BACKUP_ENABLED" -eq 0 ]; then
  echo "Backup is disabled, exiting." | tee -a "$LOG_FILE_PATH"
  exit 0
fi

# Backup the runtime database to Google Cloud Storage
gsutil cp $CONSENSUS_PROJECT_ROOT/$HISTORY_DB gs://$BUCKET/$HISTORY_DB_DIR/$CURRENT_DATETIME-$HISTORY_DB 2>&1 | tee -a "$LOG_FILE_PATH"

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
