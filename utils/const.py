from enum import Enum

# Log
LOG_PATH = "logs/lazy-consensus-bot.log"
TESTS_PATH = "tests/"
LOG_FILE_SIZE = 1024 * 1024 * 10

# Database
DB_NAME = "lazy-consensus-bot.db"
GRANT_PROPOSALS_TABLE_NAME = "grant_proposals"
VOTERS_TABLE_NAME = "voters"

GITHUB_PROJECT_URL = "https://github.com/nisnevich/eco-discord-lazy-consensus-bot"

# =====================
# Bot related constants
# =====================

# Invite link with required permissions
# https://discord.com/api/oauth2/authorize?client_id=1061680925425012756&permissions=277025467456&scope=bot

# FIXME change values back after testing
GRANT_PROPOSAL_TIMER_SECONDS = 20
GRANT_PROPOSAL_TIMER_SLEEP_SECONDS = 1
#  GRANT_PROPOSAL_TIMER_SECONDS = 259200  # 3 days
#  GRANT_PROPOSAL_TIMER_SLEEP_SECONDS = 60  # 1 minute
LAZY_CONSENSUS_THRESHOLD = 1

# L3 or Eco role
# FIXME: change roles back to Eco Discord when testing is done
ROLE_IDS_ALLOWED = (1063903240925749389,)
# ROLE_IDS_ALLOWED = (812675567438659624, 1038497110754086913)
VOTING_CHANNEL_ID = 1067119414731886645
GRANT_APPLY_CHANNEL_ID = 1067127829654937692

DISCORD_COMMAND_PREFIX = "!"
GRANT_PROPOSAL_COMMAND_NAME = 'propose'
GRANT_APPLY_COMMAND_NAME = 'grant'
HELP_COMMAND_NAME = 'help-lazy'
REACTION_ON_BOT_MENTION = "👋"  # wave
# When the proposal is accepted, the bot will
REACTION_ON_PROPOSAL_ACCEPTED = "✅"  # green tick
CANCEL_EMOJI_UNICODE = "❌"  # ❌ (:x: emoji), unicode: \U0000274C
EMOJI_HOORAY = "🎉"
RESPONSIBLE_MENTION = "<@703574259401883728>"  # Nickname of a person who's responsible for maintaining the bot (used in some error messages to ping).


class ProposalResult(Enum):
    ACCEPTED = 0
    CANCELLED_BY_REACHING_THRESHOLD = 1
    CANCELLED_BY_PROPOSER = 2


# ==============
# Messages texts
# ==============

# Validation error messages
GRANT_COMMAND_MESSAGE = """
{prefix}{grant_command} {mention} {amount} {description}. Voting: {voting_url}
"""
COMMAND_FORMAT_RESPONSE = """
Hey there, {author}! It looks like you're trying to use the !propose command, but something's not quite right with the syntax. No worries though, I've got you covered.

Here's how the command should look: `!propose @username amount reason`

- `@username`: the person you'd like to reward with points.
- `amount`: how many points you'd like to give.
- `reason`: a short explanation of why you're giving the grant. This message will be posted if the grant is applied.

Here are some examples to get you started:
`!propose @Cinderella 100 for saving the kingdom from the dragon`
`!propose @PrinceCharming 200 for taming the wild unicorn and bringing peace to the land`

Don't worry, we all make mistakes, just give it another try! To learn more in DM, type `!help-lazy`. And if you're still having trouble, feel free to reach out for help.
"""
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
ERROR_MESSAGE_INVALID_ROLE = "It's only for Layer 3 members, but don't worry if you're not quite there yet! Getting the Layer 3 role is like reaching the top of a mountain, but the view from the top is oh-so-worth it! Plus, think of all the cool features you'll have access to once you get there. Keep climbing, Eco-warrior! :mountain: :eco_heart:"

# Help messages
HELP_MESSAGE_NON_AUTHORIZED_USER = f"""
Listen up, my elite friend! This bot is for the exclusive use of the Layer 3 squad. It's like a secret handshake for making quick and easy decisions. Want to know more about it? Check out our top secret files on {GITHUB_PROJECT_URL}. But shhh, don't tell anyone else about it! 🤫
"""
HELP_MESSAGE_AUTHORIZED_USER = f"""
Hey there, are you ready to shake things up? Look no further, because the !propose command is here to save the day! 🎆

Here's how it works:

- Type anywhere: `!propose @username amount reason`. For example:
> !propose @JohnDoe 100 bucks for pizza party

- Your proposal will be sent straight to the `#L3-Voting` channel for all to see. And don't worry, you don't have to lift a finger after that - just make sure you explained your proposal clearly and let the magic happen! 🦥

- After {int(GRANT_PROPOSAL_TIMER_SECONDS / 60)} hours, if there's less than {LAZY_CONSENSUS_THRESHOLD} dissenters, BAM! The grant is automatically applied. 🚀 I will keep you all updated.

- If you disagree to any proposal, add the {CANCEL_EMOJI_UNICODE} reaction to it in #L3-Voting. Don't worry, you can change your mind later (unless it's too late). Bonus points if you tell us why you're against it! ⏱️

- Also, if you change your mind regarding your own proposal, just add {CANCEL_EMOJI_UNICODE} to it in #L3-Voting and poof! It's gone. Magic! 🎩

So, don't be shy and get those creative juices flowing! Let's make Eco the best it can be with some fresh ideas! 🌟

I'll just leave this here for contributors and the curious: {GITHUB_PROJECT_URL}
"""

# Proposal related public messages
NEW_PROPOSAL_SAME_CHANNEL_RESPONSE = """
Alright, let's make this happen! You're proposing to give {mention} {amount} points, but watch out! If {threshold} or more big wigs from Layer 3 vote against it, the deal's off. Anyone who objects can make their voices heard here: {voting_link}

Let your new idea sparkle like a diamond in the Eco-system! Wishing you all the best! :eco_angel:
"""
NEW_PROPOSAL_VOTING_CHANNEL_MESSAGE = """
:eco_kyep: :eco_rocket: **Active voting!**
{countdown} I will grant `{amount}` points to {mention}, unless {threshold} members react with {reaction} to this message (if you need help, type *!lazy-help*).
`Proposed by:` {author}
`Goal:` {description}
"""  # Another version: {author} proposed giving {amount} points to {mention}. {threshold} votes against will cancel it. Use {reaction} to vote before {date_finish}.
PROPOSAL_RESULT_VOTING_CHANNEL_EDITED_MESSAGE = """
The {amount} points proposal for {mention} by {author} has come to a close.
{result}
Goal: {description}
It was proposed here: {link_to_original_message}
"""
PROPOSAL_RESULT_VOTING_CHANNEL = {
    ProposalResult.ACCEPTED: "The grant has been given! :tada:",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "The proposal has been cancelled due to opposition from {threshold} members: {voters_list}",
    ProposalResult.CANCELLED_BY_PROPOSER: "The proposal has been cancelled by the proposer.",
}
PROPOSAL_RESULT_PROPOSER_RESPONSE = {
    ProposalResult.ACCEPTED: "Hooray! :tada: The grant has been given and {mention} is now richer by {amount} points!",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "Sorry, {author}, but it looks like {threshold} members weren't on board with your proposal: {voting_link}",
    ProposalResult.CANCELLED_BY_PROPOSER: "{author} has cancelled the proposal.",
}
