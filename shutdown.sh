#!/bin/bash

source env_vars.sh

# Stop the bot
pm2 stop "eco-lazy-consensus-bot-prod"

# Remove the bot from PM2's process list
pm2 delete "eco-lazy-consensus-bot-prod"

# Save process list
pm2 save

