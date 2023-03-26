import re

import discord
import logging
import sys
import asyncio
import datetime
from typing import List
from sqlalchemy.orm.collections import InstrumentedList

# Function overloading
from multipledispatch import dispatch

from bot.utils.db_utils import DBUtil

from bot.utils.formatting_utils import get_nickname_by_id_or_mention
from bot.utils.discord_utils import get_discord_client, get_message
from bot.config.logging_config import log_handler, console_handler
from bot.config.schemas import Proposals, Voters, FinanceRecipients, ProposalHistory
from bot.config.const import (
    DEFAULT_LOG_LEVEL,
    Vote,
    VOTING_CHANNEL_ID,
    DB_ARRAY_COLUMN_SEPARATOR,
    COMMA_LIST_SEPARATOR,
    GRANT_APPLY_CHANNEL_ID,
    RESPONSIBLE_MENTION,
)

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

client = get_discord_client()
db = DBUtil()

proposals = {}
# The lock is used while cancelling or accepting a proposal. This way concurrency errors related to
# removing and adding DB items can be avoided
proposal_lock = asyncio.Lock()


def find_matching_voter(user_id, voting_message_id):
    """
    Returns either a single Voter object that matches the provided user_id and voting_message_id, or a list of Voter objects that match, which is usually empty but may contain multiple objects if there's an error in the system.
    """
    voters_found = []
    # Iterate through proposals and check for voters with matching ids
    for id in proposals:
        p = proposals[id]
        for v in p.voters:
            if v.user_id == user_id and v.voting_message_id == voting_message_id:
                voters_found.append(v)
    # If a single match is found, return it
    if len(voters_found) == 1:
        return voters_found[0]
    # Otherwise return the entire array (it should be empty most of the time, the case when there's
    # more than 1 match is erroneous, but may happen and should be handled accordingly)
    else:
        return voters_found


def get_voters_with_vote(proposal, vote: Vote):
    """
    Returns an array of proposal voters with a certain voting value (e.g. "yes" or "no).
    """
    voters = []
    for voter in proposal.voters:
        if int(voter.value) == vote.value:
            voters.append(voter)
    return voters


async def add_voter(proposal, voter):
    await db.add(voter)
    await db.append(proposal.voters, voter)


async def remove_voter(proposal, voter):
    await db.remove(proposal.voters, voter)
    await db.delete(voter)


async def add_finance_recipient(proposal, recipient):
    await db.add(recipient)
    await db.append(proposal.finance_recipients, recipient)


def is_relevant_proposal(voting_message_id):
    if not isinstance(voting_message_id, int):
        raise ValueError(
            f"voting_message_id should be an int, got {type(voting_message_id)} instead: {voting_message_id}"
        )
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
    if not isinstance(new_proposal.author_id, (discord.User, str, int)):
        raise ValueError(
            f"author should be discord.User or str or int, got {type(new_proposal.author_id)} instead: {new_proposal.author_id}"
        )
    if not isinstance(new_proposal.voting_message_id, int):
        raise ValueError(
            f"voting_message_id should be an int, got {type(new_proposal.voting_message_id)} instead: {new_proposal.voting_message_id}"
        )
    if not isinstance(new_proposal.description, str):
        raise ValueError(
            f"description should be a string, got {type(new_proposal.description)} instead: {new_proposal.description}"
        )
    if not isinstance(new_proposal.not_financial, bool):
        raise ValueError(
            f"not_financial should be bool, got {type(new_proposal.not_financial)} instead: {new_proposal.not_financial}"
        )
    if not isinstance(new_proposal.submitted_at, datetime.datetime):
        raise ValueError(
            f"submitted_at should be datetime.datetime, got {type(new_proposal.submitted_at)} instead: {new_proposal.submitted_at}"
        )
    if not isinstance(new_proposal.closed_at, datetime.datetime):
        raise ValueError(
            f"closed_at should be datetime.datetime, got {type(new_proposal.closed_at)} instead: {new_proposal.closed_at}"
        )
    if not isinstance(new_proposal.bot_response_message_id, int):
        raise ValueError(
            f"bot_response_message_id should be an int, got {type(new_proposal.bot_response_message_id)} instead: {new_proposal.bot_response_message_id}"
        )
    if not isinstance(new_proposal.threshold_negative, int):
        raise ValueError(
            f"threshold should be an int, got {type(new_proposal.threshold_negative)} instead: {new_proposal.threshold_negative}"
        )


def validate_proposal_with_grant(new_grant_proposal):
    # The validation of proposals with grant is the same as with grantless, with a couple of extra fields
    validate_grantless_proposal(new_grant_proposal)

    if not isinstance(new_grant_proposal.finance_recipients, InstrumentedList):
        raise ValueError(
            f"finance_recipients should be InstrumentedList, got {type(new_grant_proposal.finance_recipients)} instead: {new_grant_proposal.finance_recipients}"
        )


@dispatch(Proposals)
def add_proposal(new_proposal):
    """
    Add a new grant proposal to the database and to a dictionary.
    Parameters:
    new_proposal (Proposals): The new grant proposal object to be added.
    db (optional): The DBUtil object used to save a proposal. If this parameter is not specified,proposal will only be added to in-memory dict (use case: when restoring data from DB).
    """

    if new_proposal.not_financial:
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


async def save_proposal_to_history(db, proposal, result, remove_from_main_db=True):
    """
    Adds a proposal to the ProposalHistory table after it has been processed.

    Parameters:
    proposal (Proposals): The original proposal that needs to be added to the history.
    result (ProposalResult): The result of the proposal. This should be one of the enumerated values in `ProposalResult`.
    """

    def replace_mentions_with_nicknames(description, id_to_nickname_map):
        """
        Replaces all mentions in a proposal description with nicknames, based on the mapping provided in id_to_nickname_map.
        """

        def replace_mention(match):
            user_id = match.group(1)
            return id_to_nickname_map.get(user_id, f"<@{user_id}>")

        return re.sub(r"<@(\d+)>", replace_mention, description)

    try:
        # Copy all attributes from Proposals table (excluding some of them)
        proposal_dict = {
            key: value
            for key, value in proposal.__dict__.items()
            # Exclude id and _sa_instance_state because they're unique to each table
            if key != "_sa_instance_state" and key != "id"
            # Exclude voters and finance_recipients because they are attached to another ORM
            # session, and also we need to recreate them in the history DB with their unique ids
            and key != "voters" and key != "finance_recipients"
        }

        # Retrieving voting message to save URL
        voting_message = await get_message(client, VOTING_CHANNEL_ID, proposal.voting_message_id)
        # Create a history item
        history_item = ProposalHistory(
            **proposal_dict,
            result=result.value,
            voting_message_url=voting_message.jump_url,
            # Retrieve author nickname by ID, so it can be used quickly when exporting analytics
            author_nickname=await get_nickname_by_id_or_mention(proposal.author_id),
        )
        # Add a history item and flush the changes so to assign id to the history proposal and associate other objects with it later
        await db.add(history_item, is_history=True)

        # Make a copy of the voters
        copied_voters = []
        for voter in proposal.voters:
            copied_voter = Voters(
                user_id=voter.user_id,
                user_nickname=await get_nickname_by_id_or_mention(voter.user_id),
                value=voter.value,
                voting_message_id=voter.voting_message_id,
                proposal_id=history_item.id,
            )
            copied_voters.append(copied_voter)
        # Add the copied voters to the Voters table
        await db.add_all(copied_voters, is_history=True)

        # Make a copy of the recipients
        copied_recipients = []
        for recipient in proposal.finance_recipients:
            copied_recipient = FinanceRecipients(
                proposal_id=history_item.id,
                recipient_ids=recipient.recipient_ids,
                recipient_nicknames=recipient.recipient_nicknames,
                amount=recipient.amount,
            )
            copied_recipients.append(copied_recipient)
        # Add the copied recipients to the FinanceRecipients table
        await db.add_all(copied_recipients, is_history=True)

        # Create a mapping of ids to nicknames
        id_to_nickname_map = {}
        for recipient in copied_recipients:
            ids = recipient.recipient_ids.split(DB_ARRAY_COLUMN_SEPARATOR)
            nicknames = recipient.recipient_nicknames.split(COMMA_LIST_SEPARATOR)
            id_to_nickname_map.update(zip(ids, nicknames))
        # Replace all mentions in description with the actual nicknames
        # Once I faced a bug during recovery when cancelling proposals, that the description got empty for unknown reason, so we do null checks just in case
        if history_item.description and id_to_nickname_map:
            history_item.description = replace_mentions_with_nicknames(
                history_item.description, id_to_nickname_map
            )

        # Save the changes
        await db.save(is_history=True)
        logger.debug(
            "Added history item %s",
            history_item,
        )

        # Remove the proposal (it's done here under the lock, in order to ensure DB
        # consistency, otherwise concurrency errors occur)
        if remove_from_main_db:
            await remove_proposal(proposal.voting_message_id, db)
    except Exception as e:
        try:
            grant_channel = client.get_channel(GRANT_APPLY_CHANNEL_ID)
            await grant_channel.send(
                f"An unexpected error occurred when saving proposal history. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while saving proposal history, result=%s, proposal=%s",
            __name__,
            result,
            proposal,
            exc_info=True,
        )
