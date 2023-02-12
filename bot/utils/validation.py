from discord import User
from discord.utils import find

import nltk
from nltk.corpus import words
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

from bot.config.logging_config import log_handler, console_handler
from bot.config.const import *

from bot.utils.dev_utils import measure_time
from bot.utils.formatting_utils import (
    get_amount_to_print,
    remove_special_symbols,
    remove_discord_mentions,
)

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

# Preparing ntlk to validate language of the proposal
for dataset in NLTK_DATASETS:
    nltk.download(dataset, download_dir=NLTK_DATASETS_DIR)
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


async def validate_grantless_message(original_message, description: str) -> bool:
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


async def validate_grant_message(
    original_message, mention: str, amount: float, description: str
) -> bool:
    """
    Validate grant message sent in discord - mention, amount etc.
    Parameters:
        amount: The amount of the grant being proposed.
    Returns:
        bool: True if the grant proposal message is valid, False otherwise.
    """
    logger.debug(
        "Grant proposal validation started.\nPrimary mention: %s\nAmount: %s\nDescription: %s\nAll mentions: %s",
        mention,
        amount,
        description,
        original_message.mentions,
    )

    # Assume that the validation of the mention was done when parsing the command
    # Only do some basic check
    if mention is None:
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

    # The validation of proposals with grant is the same as with grantless, with some extra fields
    return validate_grantless_message(original_message, description)


# The first run of is_valid_language always takes a few seconds (supposedly because of loading data into main memory), so we make a stub run when starting the application to avoid latency for users
is_valid_language("Loading nltk data to main memory")
