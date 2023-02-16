#!/bin/bash

# Backup is only needed to be enabled on prod, so this variable should be 1 only in the prod branch, unless it's used for testing purposes
export CONSENSUS_BACKUP_ENABLED=1
export GOOGLE_CLOUD_PROJECT_NAME="consensus-bot-377809"

# Set the project root directory to the parent directory of the script directory
export CONSENSUS_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONSENSUS_LOGS_DIR="$CONSENSUS_PROJECT_ROOT/logs"

