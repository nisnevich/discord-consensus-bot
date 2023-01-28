from enum import Enum

# Log
LOG_PATH = "logs/lazy-consensus-bot.log"
TESTS_PATH = "tests/"
LOG_FILE_SIZE = 1024 * 1024 * 10

# Database
DB_NAME = "lazy-consensus-bot.db"
GRANT_PROPOSALS_TABLE_NAME = "grant_proposals"
VOTERS_TABLE_NAME = "voters"

# =====================
# Bot related constants
# =====================

# FIXME change values back after testing
GRANT_PROPOSAL_TIMER_SECONDS = 20
GRANT_PROPOSAL_TIMER_SLEEP_SECONDS = 1
#  GRANT_PROPOSAL_TIMER_SECONDS = 259200  # 3 days
#  GRANT_PROPOSAL_TIMER_SLEEP_SECONDS = 60  # 1 minute
LAZY_CONSENSUS_THRESHOLD = 8

# L3 or Eco role
# FIXME: change roles back to Eco Discord when testing is done
ROLE_IDS_ALLOWED = (1063903240925749389,)
# ROLE_IDS_ALLOWED = (812675567438659624, 1038497110754086913)
VOTING_CHANNEL_ID = "1067119414731886645"
GRANT_APPLY_CHANNEL_ID = "1063886828052160522"

DISCORD_COMMAND_PREFIX = "!"
GRANT_PROPOSAL_COMMAND_NAME = 'propose'
GRANT_APPLY_COMMAND_NAME = 'grant'
REACTION_ON_BOT_MENTION = "👋"  # wave
# When the proposal is accepted, the bot will
REACTION_ON_PROPOSAL_ACCEPTED = "✅"  # green tick
CANCEL_EMOJI_UNICODE = "❌"  # ❌ (:x: emoji), unicode: \U0000274C
RESPONSIBLE_MENTION = "<@703574259401883728>"  # Nickname of a person who's responsible for maintaining the bot (used in some error messages to ping).


class ProposalResult(Enum):
    ACCEPTED = 0
    CANCELLED_BY_REACHING_THRESHOLD = 1
    CANCELLED_BY_PROPOSER = 2


# ==============
# Messages texts
# ==============

COMMAND_FORMAT_RESPONSE = """
Hi {author}! This command should look like:

`!propose @username amount description`

> @username - the user you would like to reward.
> amount - how many points you would like to give.
> description - a text that should explain for others what the grant is given for (this is required). If the grant will be applied, I'll post this message.

Some examples:
!propose {author} 100 for being awesome
!propose {author} 100 for using Lazy Consensus bot
"""
# validation.py error messages
ERROR_MESSAGE_NO_MENTIONS = (
    "No mentions found. Please mention the user you want to propose the grant to."
)
ERROR_MESSAGE_INVALID_COMMAND_FORMAT = (
    "The mention must follow after `!propose `. Example: `!propose @mention`."
)
ERROR_MESSAGE_INVALID_USER = "Unable to resolve username. Is the user on this Discord server?"
ERROR_MESSAGE_INVALID_AMOUNT = (
    "The amount must be a positive integer. Example: `!propose @mention 100`."
)
ERROR_MESSAGE_NEGATIVE_AMOUNT = "The amount must be a positive integer: {amount}"
ERROR_MESSAGE_INVALID_DESCRIPTION = (
    "Please provide a description of the grant, like this: `!propose @mention amount description`."
)
# Proposal related public messages
NEW_PROPOSAL_SAME_CHANNEL_RESPONSE = """
Alright, let's make this happen! You're proposing to give {mention} {amount} points, but watch out! If {threshold} or more big wigs (Layer 3) vote against it, the deal's off. Anyone who objects can make their voices heard here: {voting_link}
"""
NEW_PROPOSAL_VOTING_CHANNEL_MESSAGE = """
:rocket: {countdown} will grant {amount} points to {mention} as proposed by {author}, unless {threshold} members react with {reaction} to this message before {date_finish}.
Goal: {description}
"""  # Another version: {author} proposed giving {amount} points to {mention}. {threshold} votes against will cancel it. Use {reaction} to vote before {date_finish}.
PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE = """
The {amount} point proposal for {mention} by {author} has come to a close. {result}
Goal: {description}
The message where it was proposed: {link_to_original_message}
"""
PROPOSAL_RESULT_VOTING_CHANNEL = {
    ProposalResult.ACCEPTED: "The grant has been given!",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "The proposal has been cancelled due to opposition from {threshold} members: {voters_list}",
    ProposalResult.CANCELLED_BY_PROPOSER: "The proposal has been cancelled by the proposer.",
}
PROPOSAL_RESULT_PROPOSER_RESPONSE = {
    ProposalResult.ACCEPTED: "Hooray! The grant has been given and {mention} is now richer by {amount} points!",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "Sorry, {author}, but it looks like {threshold} members weren't on board with your proposal: {voting_link}",
    ProposalResult.CANCELLED_BY_PROPOSER: "Oh well, {author} has cancelled the proposal.",
}
