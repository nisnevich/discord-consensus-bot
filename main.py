import logging

from discord.ext import commands

# These imports are needed to make Discord client know about the implemented methods.
from grant_proposal import approve_grant_proposal
from utils import db_utils
from utils.logging_config import log_handler
from utils.grant_utils import get_grant_proposal, add_grant_proposal, get_grant_proposals_count

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)

conn = db_utils.connect_db()


def main():
    # Connect to SQLite database
    conn = db_utils.connect_db()

    # Create tables for grant proposals
    conn.execute(
        "CREATE TABLE IF NOT EXISTS grant_proposals (id INTEGER PRIMARY KEY, mention TEXT, amount INTEGER, description TEXT)"
    )

    # Create bot client
    client = commands.Bot(command_prefix='!')

    # Load pending grant proposals from database

    cursor = conn.execute(
        "SELECT id, mention, amount, description, timer, channel_id FROM grant_proposals"
    )
    for row in cursor:
        add_grant_proposal(row[0], row[5], row[1], row[2], row[3], row[4])
        # Start background task to approve grant proposals
        client.loop.create_task(approve_grant_proposal(row[0], row[5], row[1], row[2], row[3]))
    logger.info("Loaded %d pending grant proposals from database", len(get_grant_proposals_count))

    # Read token from file and start the bot
    with open("token", "r") as f:
        token = f.read().strip()
    client.run(token)
    logger.info("Bot is up.")


if __name__ == "__main__":
    main()
