import logging
import time

import discord
from discord import client

from utils.grant_utils import get_grant_proposal, add_grant_proposal, remove_grant_proposal
from utils.db_utils import DBUtil
from utils.const import RESPONSIBLE_MENTION
from utils.logging_config import log_handler
from utils.bot_utils import get_discord_client

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)

db = DBUtil()
client = get_discord_client()


async def grant(message_id):
    """
    Approve a grant proposal by adding the amount to the mentioned user.

    Parameters:
    mention (str): The mention of the user to grant the amount to.
    amount (str): The amount to grant.
    description (str): The optional description of the grant.
    """
    try:
        grant_proposal = get_grant_proposal(message_id)
    except ValueError as e:
        logger.error("Grant proposal not found. message_id=%d", message_id)
        return

    mention = grant_proposal.mention
    amount = grant_proposal.amount
    description = grant_proposal.description
    channel_id = grant_proposal.channel_id

    channel = client.get_channel(channel_id)
    original_message = await channel.fetch_message(message_id)

    # Construct the grant message
    grant_message = f"!grant {mention} {amount}"
    if description:
        grant_message += f" {description}"

    # Try sending the grant message up to 2 times
    success = False
    for i in range(2):
        try:
            await original_message.reply(grant_message)
            success = True
            # TODO add "green tick" reaction to the original grant proposal message when succeed
            break
        except Exception:
            logger.critical("An error occurred while sending grant message", exc_info=True)
            # Waiting 5 seconds before retry
            time.sleep(5)
            pass

    # Send error message if grant message could not be sent
    if not success:
        await original_message.reply(
            f"Error: could not apply grant for {mention}. cc " + RESPONSIBLE_MENTION,
        )
        logger.error("Could not apply grant. message_id=%d", message_id)
        # TODO: add extra handling if grant message wasn't delivered for some reason, such as email
        return

    # Remove grant proposal from dictionary
    try:
        remove_grant_proposal(message_id)
    except ValueError as e:
        logger.critical(f"Error while removing grant proposal: {e}")
        return
    # Remove from database
    await db.delete(grant_proposal)
    logger.info("Successfully applied grant. message_id=%d", message_id)
