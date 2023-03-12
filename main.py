import sys
import traceback
import logging
import asyncio

from bot.utils.db_utils import DBUtil
from bot.config.logging_config import log_handler, console_handler, DEFAULT_LOG_LEVEL
from bot.utils.proposal_utils import (
    add_proposal,
    get_proposals_count,
    is_relevant_proposal,
    get_voter,
    add_voter,
    remove_voter,
)
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.validation import validate_roles
from bot.config.const import (
    CANCEL_EMOJI_UNICODE,
    VOTING_CHANNEL_ID,
    SLEEP_BEFORE_RECOVERY_SECONDS,
    ProposalResult,
)
from bot.config.schemas import Voters
from bot.utils.dev_utils import measure_time_async

# imports below are needed to make discord client aware of decorated methods
from bot.propose import approve_proposal, propose_command
from bot.transact import free_funding_transact_command
from bot.vote import cancel_proposal, on_raw_reaction_add
from bot.help import help

logger = logging.getLogger(__name__)
logger.setLevel(DEFAULT_LOG_LEVEL)
logger.addHandler(log_handler)
logger.addHandler(console_handler)


async def sync_voters_db_with_discord(client, proposal):
    """
    Updates voters in the database based on the reactions on the voting message associated with the given proposal.
    Voters who have added cancel reaction but are not in the database are added to the database.
    Voters who are in the database but have not added cancel reaction are removed from the database.

    :param proposal: The proposal for which to update voters.
    """

    # Retrieve the voting message
    voting_message = await get_message(client, VOTING_CHANNEL_ID, proposal.voting_message_id)
    logger.info(
        "Recovery: synchronizing voters of voting_message_id=%d", proposal.voting_message_id
    )

    # Retrieve all users who added cancel reaction to the message
    x_reactions = [
        reaction
        for reaction in voting_message.reactions
        if str(reaction.emoji) == CANCEL_EMOJI_UNICODE
    ]
    logger.debug(f"Reactions count: {len(x_reactions)}")
    x_reactors_valid = []
    for x_reaction in x_reactions:
        # Retrieve all users who added the cancel reaction
        async for user in x_reaction.users():
            # Check if the user is a valid member to participate in voting
            if not await validate_roles(user):
                return False
            # Check if the user is the proposer himself, and then cancel
            if proposal.author == user.mention:
                # cancel_proposal will remove all voters, so we just run it and exit
                logger.debug("The proposer voted against, cancelling")
                await cancel_proposal(
                    proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message
                )
                return
            x_reactors_valid.append(user)

    # Remove voters whose cancel reaction is not found on the message
    for voter in proposal.voters:
        voter_reacted = False
        is_valid_voter = True
        for x_reaction in x_reactions:
            # Check if the voter reacted
            async for user in x_reaction.users():
                if user.id == voter.user_id:
                    logger.debug(
                        "Proposal author: %s, user mention: %s", proposal.author, user.mention
                    )

                    # Make sure the voter still has permissions to vote, otherwise remove
                    if not await validate_roles(user):
                        is_valid_voter = False
                    voter_reacted = True
                    break
            if voter_reacted:
                break

        if not voter_reacted or not is_valid_voter:
            logger.info(f"Removing voter {voter.user_id} from DB for proposal {proposal.id}")
            await remove_voter(proposal, voter)

    # Process each valid user who added the cancel reaction
    for reactor in x_reactors_valid:
        # Retrieve the user from DB
        voter = await get_voter(reactor.id, proposal.voting_message_id)

        if not voter:
            # If voter is not in DB, add it
            logger.info(
                f"Adding voter {reactor.id} to DB for proposal {proposal.voting_message_id}"
            )
            await add_voter(
                proposal,
                Voters(user_id=reactor.id, voting_message_id=proposal.voting_message_id),
            )

    # Check if the threshold is reached, and then cancel
    if len(proposal.voters) >= proposal.threshold:
        logger.debug("Threshold is reached, cancelling")
        await cancel_proposal(
            proposal, ProposalResult.CANCELLED_BY_REACHING_THRESHOLD, voting_message
        )


@measure_time_async
async def start_proposals_coroutines(client, pending_grant_proposals):
    """
    Restores and actualises all active proposals stored in DB. Should run after the client will be initialised.
    """
    logger.info("Running approval of the proposals...")

    # Check if there are any pending proposals
    if pending_grant_proposals.count() == 0:
        logger.info("Hooray - no DB recovery is needed!")
        return

    db = DBUtil()
    # Acquire the recovery lock to block accepting new proposals and voting
    async with db.recovery_lock:
        # Wait some time until the client will load (otherwise methods such as client.get_channel may fail)
        logger.info(
            "Sleeping for %s seconds so that Discord client will initialize...",
            SLEEP_BEFORE_RECOVERY_SECONDS,
        )
        await asyncio.sleep(SLEEP_BEFORE_RECOVERY_SECONDS)

        # Start background tasks to approve pending proposals
        for proposal in pending_grant_proposals:
            # Update voters that were added or removed during the downtime
            await sync_voters_db_with_discord(client, proposal)

            # If the proposal wasn't removed add approval coroutine to event loop
            if is_relevant_proposal(proposal.voting_message_id):
                client.loop.create_task(approve_proposal(proposal.voting_message_id))
                logger.info(
                    "Added task to event loop to approve voting_message_id=%d",
                    proposal.voting_message_id,
                )
                logger.debug("Loaded a proposal: %s", proposal)

        logger.info("Recovery has finished!")


def main():
    async def setup_hook(client, pending_grant_proposals):
        # This method should execute quickly, because it delays the startup - the bot will only get
        # active after this method will finish.

        # Run async event loop task to start approval coroutines
        client.loop.create_task(start_proposals_coroutines(client, pending_grant_proposals))

    try:
        db = DBUtil()
        # Initialise the database, only needed to call once
        # Later the ORM session object will be shared across coroutines using asyncronous awaits
        db.connect_db()
        # Create required tables that don't exist
        db.create_all_tables()
        # Create bot client
        client = get_discord_client()

        # Load pending proposals from database
        pending_grant_proposals = db.load_pending_grant_proposals()
        for proposal in pending_grant_proposals:
            # Adding proposal without db parameter to only keep it in primary memory (as it's already in db)
            # Voters will also be restored (thanks to a bidirectional relationship with voters)
            add_proposal(proposal)
        logger.info("Loaded %d pending grant proposal(s) from database", get_proposals_count())

        # Enabling setup hook to start proposal approving coroutines after the client will be initialised.
        # client.run call is required before approve_grant_proposal, because it starts Discord event loop.
        client.setup_hook = lambda: setup_hook(client, pending_grant_proposals)

        # Read token from the file and start the bot
        with open("token", "r") as f:
            token = f.read().strip()
        logger.info("Starting the bot...")
        client.run(token)

    except Exception as e:
        logger.error("An error occurred in main(): %s", e)
        raise
    finally:
        db.close_db()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Script crashed: %s", e, exc_info=True)
        traceback.print_exc()
        sys.exit(1)
