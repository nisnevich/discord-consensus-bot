import logging

from discord import User
from discord.ext import commands
from discord.utils import find

from utils.logging_config import log_handler
from utils.const import *

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)


async def validate_grant_message(original_message, amount: int, description: str) -> bool:
    """
    Validate grant message - mention, amount etc.
    Parameters:
        amount (str): The amount of the grant being proposed.

    Returns:
        bool: True if the grant proposal message is valid, False otherwise.
    """

    # check if there are mentions in the message
    if not original_message.mentions:
        await original_message.reply(ERROR_MESSAGE_NO_MENTIONS)
        logger.info(
            "No mentions found in the message. message_id=%d, invalid value=%s",
            original_message.id,
            original_message.content,
        )
        return False

    command = f"{DISCORD_COMMAND_PREFIX}{GRANT_PROPOSAL_COMMAND_NAME}"
    # take the first mention
    user = original_message.mentions[0]
    # check if the mention follows the "!propose" command
    command_and_mention = f"{DISCORD_COMMAND_PREFIX}{GRANT_PROPOSAL_COMMAND_NAME} {original_message.mentions[0].mention}"
    if original_message.content[: len(command_and_mention)] != command_and_mention:
        await original_message.reply(ERROR_MESSAGE_INVALID_COMMAND_FORMAT)
        logger.info(
            "Invalid command format. message_id=%d, invalid value=%s",
            original_message.id,
            original_message.content,
        )
        return False

    # Check if the mention is a valid user
    if user is None:
        await original_message.reply(ERROR_MESSAGE_INVALID_USER)
        logger.info(
            "Invalid mention. message_id=%d, invalid value=%s",
            original_message.id,
            original_message.content,
        )
        return False

    # Check if amount is set
    if not amount:
        await original_message.reply(ERROR_MESSAGE_EMPTY_AMOUNT)
        logger.info("Amount not set. message_id=%d, invalid value=%s", original_message.id, amount)
        return False

    # Check if amount is int
    if not isinstance(amount, int):
        await original_message.reply(ERROR_MESSAGE_INVALID_AMOUNT)
        logger.info("Invalid amount. message_id=%d, invalid value=%s", original_message.id, amount)
        return False

    # Check if amount is a positive integer
    if int(amount) <= 0:
        await original_message.reply(ERROR_MESSAGE_NEGATIVE_AMOUNT.format(amount=amount))
        logger.info(
            "Invalid amount, should be positive integer. message_id=%d, invalid value=%s",
            original_message.id,
            amount,
        )
        return False

    # check if the description is a non-empty string that has characters besides spaces
    if not description or not description.strip():
        await original_message.reply(ERROR_MESSAGE_INVALID_DESCRIPTION)
        logger.info(
            "Invalid description. message_id=%d, invalid value=%s", original_message.id, description
        )
        return False

    # check if the description is less than a certain amount of characters
    if len(description) > MAX_DESCRIPTION_LENGTH:
        await original_message.reply(ERROR_MESSAGE_LENGTHY_DESCRIPTION)
        logger.info(
            "Too long description, exceeds the limit of %s. message_id=%d, invalid value=%s",
            ERROR_MESSAGE_LENGTHY_DESCRIPTION,
            original_message.id,
            description,
        )
        return False

    return True


async def validate_roles(user: User) -> bool:
    """
    Validate roles of the user to check if user has the required role to use this command.
    Parameters:
        user (discord.User): The user whose roles are being validated.

    Returns:
        bool: True if the user has the required roles, False otherwise.
    """

    # Check if user has allowed role
    role = find(lambda r: r.id in ROLE_IDS_ALLOWED, user.roles)
    if role is None:
        return False
    return True
