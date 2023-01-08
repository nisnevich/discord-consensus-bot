import os
import logging
from logging.handlers import RotatingFileHandler

from utils.const import LOG_FILE_SIZE, LOG_PATH

if not os.path.exists(LOG_PATH):
    os.makedirs(LOG_PATH)

log_handler = RotatingFileHandler(LOG_PATH, mode='a', maxBytes=LOG_FILE_SIZE, backupCount=5)

# Set the log level and format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(formatter)
