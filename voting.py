import logging

import discord

from utils.grant_utils import (
    get_grant_proposal,
    add_grant_proposal,
    remove_grant_proposal,
    is_relevant_grant_proposal,
    add_voter,
    remove_voter,
    get_voter,
    get_proposal_initiated_by,
)
from utils.db_utils import DBUtil
from utils import db_utils
from utils.logging_config import log_handler, console_handler
from utils.validation import validate_roles
from utils.bot_utils import get_discord_client
from utils.server_utils import get_message
from utils.const import *
from utils.formatting_utils import get_amount_to_print
from schemas.grant_proposals import Voters, GrantProposals

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)

db = DBUtil()
client = get_discord_client()


async def is_valid_voting_reaction(payload):
    logger.debug("Verifying the reaction...")

    # Check if the reaction matches
    if payload.emoji.name != CANCEL_EMOJI_UNICODE:
        return False
    logger.debug("Emoji is correct")

    # Check if the user role matches
    guild = client.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)
    if not await validate_roles(member):
        return False
    logger.debug("Role is correct")

    reaction_channel = guild.get_channel(payload.channel_id)

    # When adding reaction, check if the user has attempted to vote on a wrong message - either the original proposer message, or the bots reply to it, associated with an active proposal though (in order to help onboard new users)
    if payload.event_type == "REACTION_ADD":
        incorrect_reaction_proposal = get_proposal_initiated_by(payload.message_id)
        if incorrect_reaction_proposal:
            # Remove reaction from the message, in order not to confuse other members
            reaction_message = await reaction_channel.fetch_message(payload.message_id)
            await reaction_message.remove_reaction(payload.emoji, member)

            # Retrieve the relevant voting message to send link to the user
            voting_message = await get_message(
                client, VOTING_CHANNEL_ID, incorrect_reaction_proposal.voting_message_id
            )
            # Send private message to user
            dm_channel = await member.create_dm()
            await dm_channel.send(
                HELP_MESSAGE_VOTED_INCORRECTLY.format(voting_link=voting_message.jump_url)
            )

    # Check if this is a voting channel
    if reaction_channel.id != VOTING_CHANNEL_ID:
        return False
    logger.debug("Channel is correct")

    # Check if the reaction message is a relevant lazy consensus voting
    if not is_relevant_grant_proposal(payload.message_id):
        return False
    logger.debug("Proposal is correct")
    return True


@client.event
async def on_raw_reaction_remove(payload):
    logger.debug("Removing a reaction: %s", payload.event_type)
    try:
        # Check if the reaction was made by valid user to a valid voting message
        if not await is_valid_voting_reaction(payload):
            return

        # Get the proposal (it was already validated that it exists)
        proposal = get_grant_proposal(payload.message_id)

        # Error handling - retrieve the voter object from the DB
        voter = await get_voter(payload.user_id, payload.message_id, db)
        if not voter:
            logger.warning(
                "Warning: Unable to find in the DB a user whose voting reaction was presented on active proposal. channel=%s, message=%s, user=%s, proposal=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
            )
            return

        # Remove the voter from the list of voters for the grant proposal
        await remove_voter(proposal, voter, db)

    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)
            await message.reply(
                f"An unexpected error occurred when handling reaction removal. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while removing vote (reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )


@client.event
async def on_raw_reaction_add(payload):
    """
    Cancel a grant proposal if a L3 member reacts with a :x: emoji to the original message or the confirmation message.
    Parameters:
        payload (discord.RawReactionActionEvent): The event containing data about the reaction.
    """

    async def cancel_proposal(proposal, reason, voting_message):
        # Extracting dynamic data to fill messages
        # Don't remove unused variables because messages text may change
        mention_author = proposal.author
        mention_receiver = proposal.mention
        amount_of_allocation = get_amount_to_print(proposal.amount)
        description_of_proposal = proposal.description
        list_of_voters = VOTERS_LIST_SEPARATOR.join(
            f"<@{voter.user_id}>" for voter in proposal.voters
        )
        original_message = await get_message(client, proposal.channel_id, proposal.message_id)
        link_to_voting_message = voting_message.jump_url
        link_to_initial_proposer_message = original_message.jump_url if original_message else None

        # Filling the messages
        if reason == ProposalResult.CANCELLED_BY_PROPOSER:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author
            )
            result_message = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format()
            log_message = "(by the proposer)"
        elif reason == ProposalResult.CANCELLED_BY_REACHING_THRESHOLD:
            response_to_proposer = PROPOSAL_RESULT_PROPOSER_RESPONSE[reason].format(
                author=mention_author,
                threshold=LAZY_CONSENSUS_THRESHOLD,
                voting_link=link_to_voting_message,
            )
            result_message = PROPOSAL_RESULT_VOTING_CHANNEL[reason].format(
                threshold=LAZY_CONSENSUS_THRESHOLD, voters_list=list_of_voters
            )
            log_message = "(by reaching threshold)"
        edit_in_voting_channel = PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE.format(
            result=result_message,
            amount=amount_of_allocation,
            mention=mention_receiver,
            author=mention_author,
            description=description_of_proposal,
            # TODO#9 if link_to_initial_proposer_message is None, message should be different
            link_to_original_message=link_to_initial_proposer_message,
        )

        if original_message:
            await original_message.add_reaction(REACTION_ON_PROPOSAL_CANCELLED)
        # Reply in the original channel, unless it's not the voting channel itself (then not replying to avoid unnecessary spam)
        if original_message and voting_message.channel.id != original_message.channel.id:
            await original_message.reply(response_to_proposer)
        # Edit the proposal in the voting channel
        await voting_message.edit(content=edit_in_voting_channel)
        # Remove the proposal
        await remove_grant_proposal(proposal.voting_message_id, db)
        logger.info(
            "Cancelled grant proposal %s. voting_message_id=%d",
            log_message,
            proposal.voting_message_id,
        )

    try:
        logger.debug("Adding a reaction: %s", payload.event_type)

        # Check if it's a valid voting reaction
        if not await is_valid_voting_reaction(payload):
            # If not, check if the reaction is a heart emoji, to double it (just for fun)
            if payload.emoji.name in HEART_EMOJI_LIST:
                message = await get_message(client, payload.channel_id, payload.message_id)
                await message.add_reaction(payload.emoji)
            return

        proposal = get_grant_proposal(payload.message_id)

        # The voting message is needed to format the replies of the bot later
        voting_message = await get_message(client, payload.channel_id, payload.message_id)

        #  Check whether the voter is the proposer himself, and then cancel the proposal
        if proposal.author == payload.member.mention:
            await cancel_proposal(proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message)
            return
        logger.debug("Author is not the same")

        # Error/fraud handling - check if the user has already voted for this proposal
        voter = await get_voter(payload.user_id, payload.message_id, db)
        logger.debug("Voter: %s", voter)
        if voter:
            logger.warning(
                "Warning: Somehow the same user has managed to vote twice on the same proposal: channel=%s, message=%s, user=%s, proposal=%s, voter=%s",
                payload.channel_id,
                payload.message_id,
                payload.user_id,
                proposal,
                voter,
            )
            return
        logger.debug("User hasn't voted before")

        # Add voter to DB and dict
        await add_voter(
            proposal,
            Voters(user_id=payload.user_id, voting_message_id=proposal.voting_message_id),
            db,
        )
        logger.info(
            "Added vote of user_id=%s, total %d voters against voting_message_id=%d",
            payload.user_id,
            len(proposal.voters),
            proposal.voting_message_id,
        )
        # Check if the threshold is reached
        if len(proposal.voters) >= LAZY_CONSENSUS_THRESHOLD:
            logger.debug("Threshold is reached, cancelling")
            await cancel_proposal(
                proposal, ProposalResult.CANCELLED_BY_REACHING_THRESHOLD, voting_message
            )

    except Exception as e:
        try:
            # Try replying in Discord
            message = await get_message(client, payload.channel_id, payload.message_id)

            await message.reply(
                f"An unexpected error occurred when handling reaction adding. cc {RESPONSIBLE_MENTION}"
            )
        except Exception as e:
            logger.critical("Unable to reply in the chat that a critical error has occurred.")

        logger.critical(
            "Unexpected error in %s while voting (adding reaction), channel=%s, message=%s, user=%s",
            __name__,
            payload.channel_id,
            payload.message_id,
            payload.user_id,
            exc_info=True,
        )
