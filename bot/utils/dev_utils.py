import time
import logging

from bot.config.const import DEFAULT_LOG_LEVEL
from bot.config.logging_config import log_handler, console_handler

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


def measure_time(func):
    """
    A function decorator that measures the time it takes for the decorated function to run and logs the result using the provided logger.

    Parameters:
        logger (logging.Logger): The custom logger object used to log the timing information.
        func (callable): The function to be decorated and have its running time measured.

    Returns:
        wrapper (function): The decorated function that measures and logs its running time.
    """

    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug("{} took {:.6f} seconds to run".format(func.__name__, end_time - start_time))
        return result

    return wrapper
