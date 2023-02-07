import logging

from discord import User
from discord.ext import commands
from discord.utils import find

import nltk
from nltk.corpus import words
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

from utils.logging_config import log_handler, console_handler
from utils.dev_utils import measure_time
from utils.formatting_utils import (
    get_amount_to_print,
    remove_special_symbols,
    remove_discord_mentions,
)
from utils.const import *

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

# Preparing ntlk to validate language of the proposal
nltk.download('averaged_perceptron_tagger')
nltk.download('punkt')
nltk.download('wordnet')
nltk.download('words')
# Saving set of words in lowercase to compare later
english_words = set(word.lower() for word in words.words())
wordnet_lemmatizer = WordNetLemmatizer()


@measure_time
def is_valid_language(text, threshold=MIN_ENGLISH_TEXT_DESCRIPTION_PROPORTION) -> bool:
    """
    Determines if the given text is in the English language, based on the proportion of English words it contains.

    :param text: The text to be evaluated.
    :param threshold: The minimum proportion of English words that the text must contain in order to be considered valid.
    :return: True if the text is considered to be in the English language, False otherwise.
    """
    if len(text) == 0:
        return False

    # Count all discord mentions as valid words by simply removing them from the text
    # Also removing all special symbols to avoid performance issues with nltk
    text = remove_special_symbols(remove_discord_mentions(text))
    logger.debug("Description without special characters and mentions: %s", text)
    words = word_tokenize(text)
    lemmatized_words = [wordnet_lemmatizer.lemmatize(word.lower()) for word in words]
    english_word_count = 0
    for word in lemmatized_words:
        if word.isalpha() and word in english_words:
            english_word_count += 1
            logger.debug(f"{word} is English")
        else:
            logger.debug(f"{word} is not English")
    result = english_word_count / float(len(words)) >= threshold
    logger.debug(
        "english_word_count=%d, len(words)=%d, result=%s", english_word_count, len(words), result
    )
    return result


async def validate_grant_message(original_message, amount: float, description: str) -> bool:
    """
    Validate grant message - mention, amount etc.
    Parameters:
        amount: The amount of the grant being proposed.

    Returns:
        bool: True if the grant proposal message is valid, False otherwise.
    """
    logger.debug(
        "Validation started.\nMentions: %s\nAmount: %s\nDescription: %s",
        original_message.mentions,
        amount,
        description,
    )

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
    # comparing the message and how it should look like while removing all spaces (to avoid issues with multiple spaces)
    stripped_content = original_message.content.replace(" ", "")
    if stripped_content[: len(command_and_mention.replace(" ", ""))] != command_and_mention.replace(
        " ", ""
    ):
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
    if amount != 0 and not amount:
        await original_message.reply(ERROR_MESSAGE_EMPTY_AMOUNT)
        logger.info("Amount not set. message_id=%d, invalid value=%s", original_message.id, amount)
        return False

    # Check if amount is float
    if not isinstance(amount, float):
        await original_message.reply(ERROR_MESSAGE_INVALID_AMOUNT)
        logger.info("Invalid amount. message_id=%d, invalid value=%s", original_message.id, amount)
        return False

    # Check if amount is a positive float
    if float(amount) <= 0:
        await original_message.reply(
            ERROR_MESSAGE_NEGATIVE_AMOUNT.format(amount=get_amount_to_print(amount))
        )
        logger.info(
            "Invalid amount, should be positive float. message_id=%d, invalid value=%s",
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
            MAX_DESCRIPTION_LENGTH,
            original_message.id,
            description,
        )
        return False

    # check if the proposal is written in English (or at least a part of it)
    if not is_valid_language(description):
        await original_message.reply(ERROR_MESSAGE_INCORRECT_DESCRIPTION_LANGUAGE)
        logger.info(
            "Less than %d%% of the English words in the description. message_id=%d, invalid value=%s",
            int(100 * MIN_ENGLISH_TEXT_DESCRIPTION_PROPORTION),
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


# The first run of is_valid_language always takes a few seconds (supposedly because of loading data into main memory), so we make a stub run when starting the application to avoid latency for users
is_valid_language("lorem ipsum")
