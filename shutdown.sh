#!/bin/bash

# Stop the bot
pm2 stop "eco-lazy-consensus-bot"

# Remove the bot from PM2's process list
pm2 delete "eco-lazy-consensus-bot"

# Save process list
pm2 save

