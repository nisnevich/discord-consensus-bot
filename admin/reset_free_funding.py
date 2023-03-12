import logging
import path
import sys

# directory reach
directory = path.Path(__file__).abspath()
# setting path
sys.path.append(directory.parent.parent)

from bot.utils.db_utils import DBUtil
from bot.config.const import FREE_FUNDING_LIMIT_PERSON_PER_SEASON
from bot.config.logging_config import log_handler, console_handler, DEFAULT_LOG_LEVEL
from bot.config.schemas import FreeFundingBalance

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


def reset_all_free_funding_balances():
    answer = input(
        f"""
Are you absolutely sure you want to reset ALL balances of each user in the database to
{FREE_FUNDING_LIMIT_PERSON_PER_SEASON}?

- Unless you have backups, the previous state of balances will be lost.
- Make sure the bot is shutdown to avoid concurrency errors.

Type 'RESET' to proceed.
        """
    )

    if answer == "RESET":
        db = DBUtil()
        db.connect_db()

        balances = db.session.query(FreeFundingBalance)
        for balance in balances:
            balance.balance = FREE_FUNDING_LIMIT_PERSON_PER_SEASON
        db.session.commit()

        logger.info(
            "Successfully reset balances of %d users to %d.",
            balances.count(),
            FREE_FUNDING_LIMIT_PERSON_PER_SEASON,
        )
    else:
        logger.info("Resetting was cancelled.")


if __name__ == "__main__":
    try:
        reset_all_free_funding_balances()
    except Exception as e:
        logger.error("Script crashed: %s", e, exc_info=True)
        traceback.print_exc()
        sys.exit(1)
