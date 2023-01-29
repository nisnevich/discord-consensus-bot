import os
import logging
from logging.handlers import RotatingFileHandler

from utils.const import LOG_FILE_SIZE, LOG_PATH, DEFAULT_LOG_LEVEL

if not os.path.exists(LOG_PATH):
    os.makedirs(os.path.dirname(LOG_PATH))

log_handler = RotatingFileHandler(LOG_PATH, mode='a', maxBytes=LOG_FILE_SIZE, backupCount=5)
log_handler.setLevel(DEFAULT_LOG_LEVEL)

console_handler = logging.StreamHandler()
console_handler.setLevel(DEFAULT_LOG_LEVEL)

# Set the log level and format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
log_handler.setFormatter(formatter)
