#!/bin/bash

# Backup is only needed to be enabled on prod, so this variable should be 1 only in the prod branch, unless it's used for testing purposes
export CONSENSUS_BACKUP_ENABLED=1
export GOOGLE_CLOUD_PROJECT_NAME="consensus-bot-377809"

# Backup runtime DB every hour
export CRON_RUNTIME_DB_BACKUP_SCHEDULE="0 * * * *"
# Backup history DB twice a day
export CRON_HISTORY_DB_BACKUP_SCHEDULE="0 0,12 * * *"

# Logs dir
export CONSENSUS_LOGS_DIR="$CONSENSUS_PROJECT_ROOT/logs"
# Runtime DB backup log file
export LOG_BACKUP_RUNTIME_FILE_PATH="$CONSENSUS_LOGS_DIR/backup-runtime-db.log"
# History DB backup file
export LOG_BACKUP_HISTORY_FILE_PATH="$CONSENSUS_LOGS_DIR/backup-history-db.log"

