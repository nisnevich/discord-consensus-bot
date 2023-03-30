import logging
import sys
import traceback

from bot.config.logging_config import log_handler, console_handler, DEFAULT_LOG_LEVEL
from bot.recovery import start_proposals_coroutines
from bot.utils.db_utils import DBUtil
from bot.utils.discord_utils import get_discord_client
from bot.utils.proposal_utils import (
    add_proposal,
    get_proposals_count,
)

# imports below are needed to make discord client aware of decorated methods
from bot.propose import (
    approve_proposal,
    command_propose_opened_voting,
    command_propose_anonymous_voting,
)
from bot.transact import free_funding_transact_command
from bot.vote import cancel_proposal, on_raw_reaction_add
from bot.help import help
from bot.export import export_command

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


def main():
    async def setup_hook(client, pending_grant_proposals):
        # This method should execute quickly, because it delays the startup - the bot will only get
        # active after this method will finish.

        # Run async event loop task to start approval coroutines
        client.loop.create_task(start_proposals_coroutines(client, pending_grant_proposals))

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
            # Voters will also be restored (thanks to a bidirectional relationship with voters)
            add_proposal(proposal)
        logger.info("Loaded %d pending grant proposal(s) from database", get_proposals_count())

        # Enabling setup hook to start proposal approving coroutines after the client will be initialised.
        # client.run call is required before approve_grant_proposal, because it starts Discord event loop.
        client.setup_hook = lambda: setup_hook(client, pending_grant_proposals)

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
