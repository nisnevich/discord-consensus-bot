import logging

from discord import User
from discord.ext import commands
from discord.utils import find

from utils.logging_config import log_handler
from utils.const import ROLE_IDS_ALLOWED

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)


async def validate_grant_message(original_message, amount: str) -> bool:
    """
    Validate grant message - mention, amount etc.
    Parameters:
        amount (str): The amount of the grant being proposed.

    Returns:
        bool: True if the grant proposal message is valid, False otherwise.
    """
    # Check if mention is a valid user
    user = original_message.mentions[0]
    if user is None:
        await original_message.reply("Error: invalid mention, unable to resolve username.")
        logger.info("Invalid mention. message_id=%d", original_message.id)
        return False

    # Check if amount is a positive integer
    if not amount.isdigit() or int(amount) <= 0:
        await original_message.reply("Error: invalid amount, should be positive integer.")
        logger.info("Invalid amount. message_id=%d", original_message.id)
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
