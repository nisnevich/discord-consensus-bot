import discord
import logging
from typing import Union
from typing import Optional

# Function overloading
from multipledispatch import dispatch

from utils.logging_config import log_handler, console_handler
from schemas.grant_proposals import GrantProposals
from utils.db_utils import DBUtil

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


grant_proposals = {}


def get_grant_proposal(voting_message_id):
    if voting_message_id in grant_proposals:
        return grant_proposals[voting_message_id]
    else:
        logger.critical(
            f"Unable to get the proposal {voting_message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {voting_message_id}")


def is_relevant_grant_proposal(voting_message_id):
    return voting_message_id in grant_proposals


def get_grant_proposals_count():
    return len(grant_proposals)


async def remove_grant_proposal(voting_message_id, db: DBUtil):
    if voting_message_id in grant_proposals:
        logger.info("Removing data: %s", grant_proposals[voting_message_id])
        # Removing from DB; the delete-orphan cascade will clean up the Voters table with the associated data
        await db.delete(grant_proposals[voting_message_id])
        # Removing from dict
        del grant_proposals[voting_message_id]
    else:
        logger.critical(
            f"Unable to remove the proposal {voting_message_id} - it couldn't be found in the list of active proposals."
        )
        raise ValueError(f"Invalid proposal ID: {voting_message_id}")


@dispatch(GrantProposals)
def add_grant_proposal(new_grant_proposal):
    """
    Add a new grant proposal to the database and to a dictionary.
    Parameters:
    new_grant_proposal (GrantProposals): The new grant proposal object to be added.
    db (optional): The DBUtil object used to save a proposal. If this parameter is not specified,proposal will only be added to in-memory dict (use case: when restoring data from DB).
    """

    # Some extra validation; it's helpful when the values of the ORM object were changed after it was created, and for debugging as it provides detailed error messages
    if not isinstance(new_grant_proposal.message_id, int):
        raise ValueError(
            f"message_id should be an int, got {type(new_grant_proposal.message_id)} instead: {new_grant_proposal.message_id}"
        )
    if not isinstance(new_grant_proposal.channel_id, int):
        raise ValueError(
            f"channel_id should be an int, got {type(new_grant_proposal.channel_id)} instead: {new_grant_proposal.channel_id}"
        )
    if not isinstance(new_grant_proposal.author, (discord.User, str)):
        raise ValueError(
            f"author should be discord.User or str, got {type(new_grant_proposal.author)} instead: {new_grant_proposal.author}"
        )
    if not isinstance(new_grant_proposal.voting_message_id, int):
        raise ValueError(
            f"voting_message_id should be an int, got {type(new_grant_proposal.voting_message_id)} instead: {new_grant_proposal.voting_message_id}"
        )
    if not isinstance(new_grant_proposal.mention, (discord.User, str)):
        raise ValueError(
            f"mention should be discord.User or str, got {type(new_grant_proposal.mention)} instead: {new_grant_proposal.mention}"
        )
    if not isinstance(new_grant_proposal.amount, int):
        raise ValueError(
            f"amount should be an int, got {type(new_grant_proposal.amount)} instead: {new_grant_proposal.amount}"
        )
    if not isinstance(new_grant_proposal.description, str):
        raise ValueError(
            f"description should be a string, got {type(new_grant_proposal.description)} instead: {new_grant_proposal.description}"
        )
    if not isinstance(new_grant_proposal.timer, int):
        raise ValueError(
            f"timer should be an int, got {type(new_grant_proposal.timer)} instead: {new_grant_proposal.timer}"
        )
    if not isinstance(new_grant_proposal.bot_response_message_id, int):
        raise ValueError(
            f"bot_response_message_id should be an int, got {type(new_grant_proposal.bot_response_message_id)} instead: {new_grant_proposal.bot_response_message_id}"
        )

    # Adding to dict
    grant_proposals[new_grant_proposal.voting_message_id] = new_grant_proposal
    logger.info("Added proposal with voting_message_id=%s", new_grant_proposal.voting_message_id)


@dispatch(GrantProposals, DBUtil)
async def add_grant_proposal(new_grant_proposal, db):
    """
    Overloaded add_grant_proposal that also saves to DB, with one extra parameter - the DBUtil object used to save a proposal.
    """
    # Add to dict
    add_grant_proposal(new_grant_proposal)
    # Add to DB
    if db:
        await db.add(new_grant_proposal)
        logger.info("Inserted proposal into DB: %s", new_grant_proposal)
    else:
        raise Exception("Incorrect DB identifier was given.")
