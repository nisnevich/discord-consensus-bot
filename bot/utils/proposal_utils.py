import discord
import logging

# Function overloading
from multipledispatch import dispatch

from bot.utils.db_utils import DBUtil

from bot.config.logging_config import log_handler, console_handler
from bot.config.schemas import Proposals, Voters
from bot.config.const import DEFAULT_LOG_LEVEL

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


proposals = {}


async def get_voter(user_id, voting_message_id, db):
    query_results = await db.filter(
        Voters.user_id == user_id, Voters.voting_message_id == voting_message_id
    )
    logger.debug("get_voter query result: %s", query_results)
    return query_results if not query_results else query_results[0]


async def add_voter(proposal, voter, db):
    await db.add(voter)
    await db.append(proposal.voters, voter)


async def remove_voter(proposal, voter, db):
    await db.remove(proposal.voters, voter)
    await db.delete(voter)


def is_relevant_proposal(voting_message_id):
    return voting_message_id in proposals


def get_proposals_count():
    return len(proposals)


def get_proposal(voting_message_id):
    if voting_message_id in proposals:
        return proposals[voting_message_id]
    else:
        logger.critical(
            f"Unable to get the proposal {voting_message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {voting_message_id}")


def get_proposal_initiated_by(message_id):
    """
    Returns a proposal that was either initiated by a message with the given id, or the bot has replied with a message of given id to the initial proposer message (bot_response_message_id).Use case: to cover users who have reacted to a wrong message (this is helpful during onboarding).
    """
    if not proposals:
        return None
    for proposal in proposals.values():
        if proposal.message_id == message_id or proposal.bot_response_message_id == message_id:
            return proposal
    return None


async def remove_proposal(voting_message_id, db: DBUtil):
    if voting_message_id in proposals:
        logger.info("Removing data: %s", proposals[voting_message_id])
        # Removing from DB; the delete-orphan cascade will clean up the Voters table with the associated data
        await db.delete(proposals[voting_message_id])
        # Removing from dict
        del proposals[voting_message_id]
    else:
        logger.critical(
            f"Unable to remove the proposal {voting_message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {voting_message_id}")


def validate_grantless_proposal(new_proposal):
    # Some extra validation; it's helpful when the values of the ORM object were changed after it was created, and for debugging as it provides detailed error messages
    if not isinstance(new_proposal.message_id, int):
        raise ValueError(
            f"message_id should be an int, got {type(new_proposal.message_id)} instead: {new_proposal.message_id}"
        )
    if not isinstance(new_proposal.channel_id, int):
        raise ValueError(
            f"channel_id should be an int, got {type(new_proposal.channel_id)} instead: {new_proposal.channel_id}"
        )
    if not isinstance(new_proposal.author, (discord.User, str)):
        raise ValueError(
            f"author should be discord.User or str, got {type(new_proposal.author)} instead: {new_proposal.author}"
        )
    if not isinstance(new_proposal.voting_message_id, int):
        raise ValueError(
            f"voting_message_id should be an int, got {type(new_proposal.voting_message_id)} instead: {new_proposal.voting_message_id}"
        )
    if not isinstance(new_proposal.description, str):
        raise ValueError(
            f"description should be a string, got {type(new_proposal.description)} instead: {new_proposal.description}"
        )
    if not isinstance(new_proposal.is_grantless, bool):
        raise ValueError(
            f"is_grantless should be bool, got {type(new_proposal.is_grantless)} instead: {new_proposal.is_grantless}"
        )
    if not isinstance(new_proposal.timer, int):
        raise ValueError(
            f"timer should be an int, got {type(new_proposal.timer)} instead: {new_proposal.timer}"
        )
    if not isinstance(new_proposal.bot_response_message_id, int):
        raise ValueError(
            f"bot_response_message_id should be an int, got {type(new_proposal.bot_response_message_id)} instead: {new_proposal.bot_response_message_id}"
        )


def validate_proposal_with_grant(new_grant_proposal):
    # The validation of proposals with grant is the same as with grantless, with a couple of extra fields
    validate_grantless_proposal(new_grant_proposal)

    if not isinstance(new_grant_proposal.mention, (discord.User, discord.user.ClientUser, str)):
        raise ValueError(
            f"mention should be discord.User str, got {type(new_grant_proposal.mention)} instead: {new_grant_proposal.mention}"
        )
    if not isinstance(new_grant_proposal.amount, (float, int)):
        raise ValueError(
            f"amount should be a float or int, got {type(new_grant_proposal.amount)} instead: {new_grant_proposal.amount}"
        )


@dispatch(Proposals)
def add_proposal(new_proposal):
    """
    Add a new grant proposal to the database and to a dictionary.
    Parameters:
    new_proposal (Proposals): The new grant proposal object to be added.
    db (optional): The DBUtil object used to save a proposal. If this parameter is not specified,proposal will only be added to in-memory dict (use case: when restoring data from DB).
    """

    if new_proposal.is_grantless:
        validate_grantless_proposal(new_proposal)
    else:
        validate_proposal_with_grant(new_proposal)

    # Adding to dict
    proposals[new_proposal.voting_message_id] = new_proposal
    logger.info("Added proposal with voting_message_id=%s", new_proposal.voting_message_id)


@dispatch(Proposals, DBUtil)
async def add_proposal(new_proposal, db):
    """
    Overloaded add_proposal that also saves to DB, with one extra parameter - the DBUtil object used to save a proposal.
    """
    # Add to dict
    add_proposal(new_proposal)
    # Add to DB
    if db:
        await db.add(new_proposal)
        logger.info("Inserted proposal into DB: %s", new_proposal)
    else:
        raise Exception("Incorrect DB identifier was given.")
