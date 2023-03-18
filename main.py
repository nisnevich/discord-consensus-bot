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
    find_matching_voter,
    add_voter,
    remove_voter,
    get_voters_with_vote,
)
from bot.utils.discord_utils import get_discord_client, get_message
from bot.utils.validation import validate_roles
from bot.config.const import (
    EMOJI_VOTING_NO,
    EMOJI_VOTING_YES,
    VOTING_CHANNEL_ID,
    SLEEP_BEFORE_RECOVERY_SECONDS,
    ProposalResult,
    Vote,
    BOT_ID,
    THRESHOLD_DISABLED_DB_VALUE,
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


async def sync_voters_db_with_discord(voting_message, proposal, vote, emoji):
    """
    Updates voters in the database based on the reactions on the voting message associated with the given proposal.
    Voters who have added cancel reaction but are not in the database are added to the database.
    Voters who are in the database but have not added cancel reaction are removed from the database.
    Also, decisions are applied if the proposer voted against, or if lazy consensus dissenters
    threshold was reached. This could have been done directly in approve_proposal to make the code
    cleaner, but checking every 5-10 sec the entire set of proposals would dramatically increase CPU load.

    :param voting_message: The message on which the voting occurred.
    :param proposal: The proposal for which to update voters.
    :param vote: The value of the vote - e.g. Vote.YES, Vote.NO
    :param emoji: The emoji corresponding to the vote.
    """

    reaction_voting = None
    # Find the reaction on the message
    for reaction in voting_message.reactions:
        if str(reaction.emoji) == emoji:
            reaction_voting = reaction
            break
    # Extract all dissenters
    voters = get_voters_with_vote(proposal, vote)
    # If the voting reaction is not found, simply remove all voters from DB and exit
    if not reaction_voting:
        # Iterate through all voters
        for voter in proposal.voters:
            logger.info(f"Removing voter {voter.user_id} from DB for proposal {proposal.id}")
            # Remove voter from DB
            await remove_voter(proposal, voter)
        return
    # Otherwise, remove only voters whose reaction is not found on the message (i.e. was removed by the voter while the bot was down), and continue
    for voter in proposal.voters:
        # Assume the voter didn't react, unless proven so
        voter_reacted = False
        # Assume the voter still has permissions to vote, unless proven othewise
        is_valid_voter = True
        # For each voter in DB, iterate through the actual voting reactions on the message, to check if the voters reaction is still presented
        async for user in reaction_voting.users():
            # If the voter ID matches the user ID found on the message, keep it in DB and switch to the next voter
            if voter.user_id == user.id:
                # Mark as "reacted"
                voter_reacted = True
                # If the voter doesn't have permissions to vote, remove him from DB
                if not await validate_roles(user):
                    is_valid_voter = False
                break
        # If voter removed his reaction, or he doesn't have permissions to vote anymore, remove from DB
        if not voter_reacted or not is_valid_voter:
            logger.info(f"Removing voter {voter.user_id} from DB for proposal {proposal.id}")
            await remove_voter(proposal, voter)

    # Add new voters to DB
    async for reactor in reaction_voting.users():
        # Check if the reactor is allowed to participate in voting
        if not await validate_roles(reactor) or reactor.id == BOT_ID:
            continue
        # For objecting votes, cancel the proposal if the voter is the proposer himself
        if vote == Vote.NO and int(proposal.author) == reactor.id:
            # cancel_proposal will remove all voters, so we just run it and exit
            logger.debug("The proposer voted against, cancelling")
            await cancel_proposal(proposal, ProposalResult.CANCELLED_BY_PROPOSER, voting_message)
            return
        # For supporting votes, don't count the author if he has upvoted
        if vote == Vote.YES and proposal.author == reactor.id:
            logger.debug("The author has voted in his own favor, not counting")
            continue
        # Attempt to retrieve the voter from DB
        voter = find_matching_voter(reactor.id, proposal.voting_message_id)
        # If the voter is not found in DB, add it
        if not voter:
            logger.info(
                f"Adding voter {reactor.id} to DB for proposal {proposal.voting_message_id}"
            )
            # Add voter to DB
            await add_voter(
                proposal,
                Voters(
                    user_id=reactor.id,
                    voting_message_id=proposal.voting_message_id,
                    value=vote.value,
                ),
            )

    # When handling objecting votes, cancel the proposal if the threshold is reached
    if vote == Vote.NO:
        # Get list of dissenters again (after we added all that were missing in DB)
        voters_against = get_voters_with_vote(proposal, vote)
        # Check if the threshold is reached
        if len(voters_against) >= proposal.threshold:
            logger.debug("Threshold is reached, cancelling")
            # Cancel the proposal
            await cancel_proposal(
                proposal, ProposalResult.CANCELLED_BY_REACHING_NEGATIVE_THRESHOLD, voting_message
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
            # Retrieve the voting message
            voting_message = await get_message(
                client, VOTING_CHANNEL_ID, proposal.voting_message_id
            )
            logger.info(
                "Recovery: synchronizing voters of voting_message_id=%d", proposal.voting_message_id
            )
            # Update voters that were added or removed during the downtime
            # Update dissenters
            await sync_voters_db_with_discord(voting_message, proposal, Vote.NO, EMOJI_VOTING_NO)
            # Update supporters, if full consensus is enabled for the proposal
            if proposal.threshold_positive != THRESHOLD_DISABLED_DB_VALUE:
                await sync_voters_db_with_discord(
                    voting_message, proposal, Vote.YES, EMOJI_VOTING_YES
                )

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
