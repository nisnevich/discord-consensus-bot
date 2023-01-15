import logging

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

# conn = db_utils.connect_db()
session = DBUtil().session
client = get_discord_client()


async def grant(
    client, channel_id, message_id, mention: discord.User, amount: int, *, description=""
):
    """
    Approve a grant proposal by adding the amount to the mentioned user.

    Parameters:
    mention (str): The mention of the user to grant the amount to.
    amount (str): The amount to grant.
    description (str): The optional description of the grant.
    """

    original_message = await client.get_channel(channel_id).fetch_message(message_id)

    try:
        grant_proposal = get_grant_proposal(message_id)
    except ValueError as e:
        await original_message.channel.send(
            "Error: grant proposal not found.", reply=original_message
        )
        logger.error("Grant proposal not found. message_id=%d", message_id)
        return

    # Construct the grant message
    grant_message = f"!grant {mention.mention} {amount}"
    if description:
        grant_message += f" {description}"

    # Try sending the grant message up to 2 times
    success = False
    for i in range(2):
        try:
            await original_message.channel.send(grant_message, reply=original_message)
            success = True
            # TODO add "green tick" reaction to the original grant proposal message when succeed
            break
        except Exception:
            logger.critical("An error occurred while sending grant message", exc_info=True)
            pass

    # Send error message if grant message could not be sent
    if not success:
        await original_message.channel.send(
            f"Error: could not apply grant for {mention.mention}. cc " + RESPONSIBLE_MENTION,
            reply=original_message,
        )
        logger.error("Could not apply grant. message_id=%d", message_id)
        # TODO: add extra handling if grant message wasn't delivered for some reason, such as email
        return

    # Remove grant proposal from dictionary and database
    try:
        grant_proposal = get_grant_proposal(message_id)
        remove_grant_proposal(message_id)
    except ValueError as e:
        logger.critical(f"Error while removing grant proposal: {e}")
        return
    session.delete(grant_proposal)
    session.commit()
    # conn.execute("DELETE FROM grant_proposals WHERE id = ?", (message_id,))
    # conn.commit()
    logger.info("Successfully applied grant. message_id=%d", message_id)
