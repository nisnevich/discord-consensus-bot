import logging

from discord.ext import commands

# These imports are needed to make Discord client know about the implemented methods.
from grant_proposal import approve_grant_proposal, grant_proposal
from utils import db_utils
from utils.logging_config import log_handler
from utils.grant_utils import get_grant_proposal, add_grant_proposal, get_grant_proposals_count
from utils.bot_utils import get_discord_client


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)


def main():
    # Connect to SQLite database
    conn = db_utils.connect_db()

    # Create tables for grant proposals
    conn.execute(
        "CREATE TABLE IF NOT EXISTS grant_proposals (id INTEGER PRIMARY KEY, message_id INTEGER, channel_id INTEGER, mention TEXT, amount INTEGER, description TEXT, timer INTEGER)"
    )
    conn.commit()

    # Create bot client
    client = get_discord_client()

    # Load pending grant proposals from database
    cursor = conn.execute(
        "SELECT message_id, channel_id, mention, amount, description, timer FROM grant_proposals"
    )
    for row in cursor:
        add_grant_proposal(row[0], row[1], row[2], row[3], row[4], row[5])
        # Start background task to approve grant proposals
        client.loop.create_task(approve_grant_proposal(row[0]))
    logger.info("Loaded %d pending grant proposals from database", get_grant_proposals_count())

    # Read token from file and start the bot
    with open("token", "r") as f:
        token = f.read().strip()
    logger.info("Running the bot...")
    client.run(token)


if __name__ == "__main__":
    main()
