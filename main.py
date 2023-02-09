import sys
import traceback
import logging

from bot.utils.db_utils import DBUtil
from bot.config.logging_config import log_handler, console_handler, DEFAULT_LOG_LEVEL
from bot.utils.proposal_utils import add_proposal, get_proposals_count
from bot.utils.discord_utils import get_discord_client

# imports below are needed to make discord client aware of decorated methods
from bot.propose import approve_proposal, propose_command
from bot.vote import on_raw_reaction_add
from bot.help import help

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


def main():
    # A function to run after the client will be initialised
    async def start_proposals_coroutines():
        logger.info("Running approval of the proposals...")
        # Start background tasks to approve pending proposals
        for proposal in pending_grant_proposals:
            client.loop.create_task(approve_proposal(proposal.voting_message_id))
            logger.info(
                "Added task to event loop to approve voting_message_id=%d",
                proposal.voting_message_id,
            )
            logger.debug("The proposal added: %s", proposal)

    try:
        db = DBUtil()
        # Initialise the database, only needed to call once
        # Later the ORM session object will be shared across coroutines using asyncronous awaits
        db.connect_db()
        # Create required tables that don't exist
        db.create_all_tables()
        # Create bot client
        client = get_discord_client()

        # Load pending proposals from database
        pending_grant_proposals = db.load_pending_grant_proposals()
        for proposal in pending_grant_proposals:
            # Adding proposal without db parameter to only keep it in primary memory (as it's already in db)
            add_proposal(proposal)
        logger.info(
            "Loaded %d pending grant proposal(s) from database", get_proposals_count()
        )
        # Enabling setup hook to start proposal approving coroutines after the client will be initialised
        # client.run call is required before approve_grant_proposal, because it starts Discord event loop
        client.setup_hook = start_proposals_coroutines

        # Read token from the file and start the bot
        with open("token", "r") as f:
            token = f.read().strip()
        logger.info("Starting the bot...")
        client.run(token)

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
