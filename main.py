import logging
import sys
import traceback
import asyncio

from grant_proposal import approve_grant_proposal
from utils.db_utils import DBUtil
from utils.logging_config import log_handler, console_handler
from utils.grant_utils import add_grant_proposal, get_grant_proposals_count
from utils.bot_utils import get_discord_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


def main():
    db = DBUtil()
    # Initialise the database, only needed to call once
    # Later the session object will be shared across coroutines using asyncronous awaits
    db.connect_db()

    try:
        # Create required tables that don't exist
        db.create_all_tables()
        # Create bot client
        client = get_discord_client()
        # Load pending proposals from database
        pending_grant_proposals = db.load_pending_grant_proposals()
        for proposal in pending_grant_proposals:
            add_grant_proposal(proposal)
        logger.info("Loaded %d pending grant proposals from database", get_grant_proposals_count())

        # Read token from file and start the bot
        with open("token", "r") as f:
            token = f.read().strip()
        logger.info("Running the bot...")
        # client.run is required before starting approve_grant_proposal coroutines, because it starts Discord event loop
        client.run(token)

        # Start background tasks to approve pending proposals
        for proposal in pending_grant_proposals:
            client.loop.create_task(approve_grant_proposal(proposal.id))
            logger.info("Added task to event loop to approve message_id=%d", ctx.message.id)
    except Exception as e:
        logger.error("An error occurred in main(): %s", e)
        raise
    finally:
        db.close_db()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Script crashed: %s", e, exc_info=True)
        traceback.print_exc()
        sys.exit(1)
