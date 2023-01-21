import logging
import sys
import traceback

# These imports are needed to make Discord client know about the implemented methods.
from grant_proposal import approve_grant_proposal
from utils.db_utils import DBUtil
from utils.logging_config import log_handler
from utils.grant_utils import add_grant_proposal, get_grant_proposals_count
from utils.bot_utils import get_discord_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)


def main():
    db = DBUtil()
    try:
        db.create_all_tables()
        # Create bot client
        client = get_discord_client()
        # Load pending grant proposals from database
        pending_grant_proposals = db.load_pending_grant_proposals()
        # Iterate through each pending grant proposal and start a background task to approve them
        for proposal in pending_grant_proposals:
            add_grant_proposal(proposal)
            # Start background task to approve grant proposals
            client.loop.create_task(approve_grant_proposal(proposal.id))
        logger.info("Loaded %d pending grant proposals from database", get_grant_proposals_count())

        # Read token from file and start the bot
        with open("token", "r") as f:
            token = f.read().strip()
        logger.info("Running the bot...")
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
        logger.error("Script crashed: %s", e)
        print("Script crashed:")
        traceback.print_exc()
        sys.exit(1)
