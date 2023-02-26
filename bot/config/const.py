import logging
import os

from enum import Enum

PROJECT_ROOT = os.getcwd()

# Log
LOG_PATH = os.path.join(PROJECT_ROOT, "logs/consensus-bot.log")
LOG_FILE_SIZE = 1024 * 1024 * 10
DEFAULT_LOG_LEVEL = logging.DEBUG

# Database
DB_PATH = os.path.join(PROJECT_ROOT, "consensus-bot.db")
DB_HISTORY_PATH = os.path.join(PROJECT_ROOT, "consensus-bot-history.db")
GRANT_PROPOSALS_TABLE_NAME = "proposals"
VOTERS_TABLE_NAME = "voters"
PROPOSAL_HISTORY_TABLE_NAME = 'proposal_history'

# nltk datasets to download
NLTK_DATASETS_DIR = f"{PROJECT_ROOT}/nltk"
NLTK_DATASETS = ['averaged_perceptron_tagger', 'punkt', 'wordnet', 'words']

# urls
GITHUB_PROJECT_URL = "https://github.com/nisnevich/eco-discord-lazy-consensus-bot"

# =++===============
# Critical constants
# ====++============

# Required Discord permissions: 415538474048

# How long will each proposal be active
PROPOSAL_DURATION_SECONDS = 25  # 3 days is 259200
# Default lazy consensus threshold
LAZY_CONSENSUS_THRESHOLD = 1

ROLE_IDS_ALLOWED = (1063903240925749389,)
VOTING_CHANNEL_ID = 1067119414731886645
GRANT_APPLY_CHANNEL_ID = 1067127829654937692

# =====================
# Bot related constants
# =====================

# Invite link with required permissions
# https://discord.com/api/oauth2/authorize?client_id=1061680925425012756&permissions=277025467456&scope=bot

# Time interval between checking if it's time to approve a proposal
APPROVAL_SLEEP_SECONDS = 5
# Time interval between starting the bot and running the recovery; it's needed in order to make sure
#  the client methods will become available (otherwise methods such as client.get_channel may fail).
#  Recommended value based on observations - 5-10 sec. During this time (as well as while recovery runs),
#  the bot will reject all proposals and votes for the sake of data integrity.
SLEEP_BEFORE_RECOVERY_SECONDS = 7

DISCORD_COMMAND_PREFIX = "!"
GRANT_PROPOSAL_COMMAND_NAME = 'propose'
PROPOSAL_COMMAND_ALIASES = ['lazy', 'suggest', 'prop', 'consensus']
GRANT_APPLY_COMMAND_NAME = 'grant'
HELP_COMMAND_NAME = 'help-lazy'
HELP_COMMAND_ALIASES = ['lazy-help']
EXPORT_COMMAND_NAME = 'export'
VOTERS_LIST_SEPARATOR = ", "
RESPONSIBLE_MENTION = "<@703574259401883728>"  # Nickname of a person who's responsible for maintaining the bot (used in some error messages to ping).
MAX_DESCRIPTION_LENGTH = 1600  # 1600 is determined experimentally; Discord API has some limitations, and this way we can make sure the app will not crash with discord.errors.HTTPException
MIN_DESCRIPTION_LENGTH = 30  # just some common sense value
MAX_PROPOSAL_AMOUNT = 100000000
MIN_PROPOSAL_AMOUNT = 250
MIN_ENGLISH_TEXT_DESCRIPTION_PROPORTION = 0.35

STOP_ACCEPTING_PROPOSALS_FLAG_FILE_NAME = "stopcock"
EMPTY_ANALYTICS_VALUE = "n/a"

# Emoji
REACTION_ON_BOT_MENTION = "👋"  # wave
# When the proposal is accepted, the bot will
REACTION_ON_PROPOSAL_ACCEPTED = "✅"  # green tick
REACTION_ON_PROPOSAL_CANCELLED = "🍃"  # leaves
REACTION_VOTING_DEFAULT_POSITIVE = "👀"  # eyes
CANCEL_EMOJI_UNICODE = "❌"  # ❌ (:x: emoji), unicode: \U0000274C
EMOJI_HOORAY = "🎉"
HEART_EMOJI_LIST = [
    "❤️",
    "♥️",
    "🖤",
    "💙",
    "🤎",
    "💝",
    "💚",
    "🧡",
    "💜",
    "💞",
    "🥰",
    "💖",
    "💕",
    "🤍",
    "💛",
    "💓",
    "💗",
    "💘",
    "💌",
    "😍",
    "❣️",
    "😻",
    "🫶",
    "❤️‍🔥",
    "😘",
]


class ProposalResult(Enum):
    ACCEPTED = 0
    CANCELLED_BY_REACHING_THRESHOLD = 1
    CANCELLED_BY_PROPOSER = 2

    def __str__(self):
        if self.value == ProposalResult.ACCEPTED.value:
            return 'Accepted'
        elif self.value == ProposalResult.CANCELLED_BY_REACHING_THRESHOLD.value:
            return 'Cancelled by reaching threshold'
        elif self.value == ProposalResult.CANCELLED_BY_PROPOSER.value:
            return 'Cancelled by proposer'


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
ERROR_MESSAGE_NO_MENTIONS = "Where's the love?! You need to mention someone if you want to propose a grant! `!propose @mention 100 for a giant robot.`"
ERROR_MESSAGE_INVALID_COMMAND_FORMAT = "Oopsie! The command format is as important as the ingredients in a pizza. To make sure you got it right, type `!help-lazy`"
ERROR_MESSAGE_INVALID_USER = (
    "Hmmm, that user doesn't seem to be around here. Did you check under the couch?"
)
ERROR_MESSAGE_INVALID_AMOUNT = (
    "The amount must be a positive number. Example: `!propose @mention 100 for a giant robot.`"
)
ERROR_MESSAGE_NEGATIVE_AMOUNT = "Hold on, {amount} is not enough to even buy a pack of gum. The amount has to be positive, my friend."
ERROR_MESSAGE_OVERFLOW_AMOUNT = "Whoa there, looks like you're trying to request a whopper of a number! Better try again with a smaller amount before the numbers run away from us!"
ERROR_MESSAGE_LITTLE_AMOUNT = f"Whoa there, it looks like you're trying to vote for a pocket change. Minimum amount: {MIN_PROPOSAL_AMOUNT}."
ERROR_MESSAGE_EMPTY_AMOUNT = "The amount is like the cherry on top of a sundae, without it, your proposal just isn't sweet enough. `!propose @mention 100 for a unicorn farm.`"
ERROR_MESSAGE_INVALID_DESCRIPTION = "You know what they say, if you don't describe your grant proposal, how will anyone know how awesome it is? `!propose @mention 100 for a giant robot.`"
ERROR_MESSAGE_LENGTHY_DESCRIPTION = f"Please reduce the description length to less than {MAX_DESCRIPTION_LENGTH} characters. Like, who wants to read that much anyways?"
ERROR_MESSAGE_SHORTY_DESCRIPTION = f"Less is not always more, my friend. A tiny bit more detailed description would be greatly appreciated."
ERROR_MESSAGE_INCORRECT_DESCRIPTION_LANGUAGE = f"Looks like your proposal needs a little more time in English class. Let's make sure you described everything in the language of Shakespeare (English must be at least {100 * MIN_ENGLISH_TEXT_DESCRIPTION_PROPORTION}% of the text, but feel free to add a second language if you'd like. Just don't let it go over a total of {MAX_DESCRIPTION_LENGTH} characters, okay?)."
ERROR_MESSAGE_INVALID_ROLE = "Sorry, you need Layer 3 role to use this command. Type `!help-lazy` to learn more about the bot in DM."
ERROR_MESSAGE_PROPOSAL_WITH_GRANT_VOTING_LINK_REMOVED = "The {amount} grant for {mention} was applied, but I couldn't find the voting message in this channel. Was it removed? {link_to_original_message} cc {RESPONSIBLE_MENTION}"
ERROR_MESSAGE_GRANTLESS_PROPOSAL_VOTING_LINK_REMOVED = "The proposal by {author} is applied! However, I couldn't find the voting message in this channel. Was it removed? {link_to_original_message} cc {RESPONSIBLE_MENTION}"

# When functionality is paused
PROPOSALS_PAUSED_RESPONSE = "Our proposal box is overflowing with awesome ideas! We're taking a little pause to catch up. But don't worry, we'll be back in action soon. Thanks for your patience!"
PROPOSALS_PAUSED_RECOVERY_RESPONSE = "Bonjour! Our bot is taking a petit peu de repos to start the day off on the right foot. Don't worry, it's a short break - try again in just a minute!"
VOTING_PAUSED_RECOVERY_RESPONSE = "Hey there! We're in the middle of a database recovery, which means we can't count your vote just yet. Give it a minute, and then come back and cast your ballot again!"

# Help messages
HELP_MESSAGE_NON_AUTHORIZED_USER = f"""
Unfortunately, you don't have a Layer 3 role which is needed to use Consensus bot on Eco server.

If you're interested in learning more about the project, check out {GITHUB_PROJECT_URL}

The bot is an open-source project under MIT license. Contributions are welcome! See "Contributing" section on GitHub if you're interested.

Also looking for teammates! If you possess expertise in Python and are excited about the project, please don't hesitate to reach out {RESPONSIBLE_MENTION}. Also looking for a QA automation engineer onboard.
"""
HELP_MESSAGE_AUTHORIZED_USER = f"""
Hey there, are you ready to shake things up? Look no further, because the !propose command is here to save the day! 🎆

Here's how it works:

- Need a grant? Type anywhere: `!propose @username amount reason`. For example:
> !propose @JohnSnow 100 for saving the kingdom

- Have an idea but don't need a grant? Type whatever you want after "!propose":
> !propose to run a community meeting tonight at 20 UTC

- Your proposal will be sent straight to the `#l3-voting` channel for all to see. And don't worry, you don't have to lift a finger after that - just make sure you explained your proposal clearly and let the magic happen! 🦥

- After {int(PROPOSAL_DURATION_SECONDS / 60 / 60)} hours, if there's less than {LAZY_CONSENSUS_THRESHOLD} dissenters, BAM! You've got the green light. If you requested a grant, it will be automatically applied. 🚀 I will keep you all updated.

- If you disagree to any proposal, add the {CANCEL_EMOJI_UNICODE} reaction to it in `#l3-voting`. Don't worry, you can change your mind later (unless it's too late). Bonus points if you tell us why you're against it! ⏱️

- Also, if you change your mind regarding your own proposal, just add {CANCEL_EMOJI_UNICODE} to it in `#l3-voting` and poof! It's gone. Magic! 🎩

Before submitting a proposal, make sure to explain the background and details of it. Use the lazy consensus responsibly. *Clearly state what actions will be taken if the proposal is approved.* Avoid vague descriptions, and submit proposals in the appropriate channel (e.g. the channel of your activity or #l3-season-1-activities). The bot will create a post in #l3-voting once you send a proposal.

So, don't be shy and get those creative juices flowing! Let's make Eco the best it can be with some fresh ideas! 🌟

For power users:
- Some shortcuts of `!propose` are: {", ".join(PROPOSAL_COMMAND_ALIASES)}.
- Run `!export` to receive analytics.

For questions, ideas or partnership, reach out to {RESPONSIBLE_MENTION}. The project is looking for contributors and teammates: {GITHUB_PROJECT_URL}
"""
HELP_MESSAGE_VOTED_INCORRECTLY = "Oops, looks like you're trying to vote, but on a wrong message! 😕 To make your vote count, please head to the voting message in #l3-voting: {voting_link}."

# ======================
# General proposal texts
# ======================

PROPOSAL_CANCELLED_VOTING_CHANNEL = {
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "Proposal cancelled due to opposition from {threshold} members - {voters_list}: {link_to_original_message}",
    ProposalResult.CANCELLED_BY_PROPOSER: ":leaves: Proposal cancelled by author ({author}): {link_to_original_message}",
}

# =====================
# Proposals with grants
# =====================


def NEW_PROPOSAL_WITH_GRANT_AMOUNT_REACTION(amount):
    if amount < 1500:
        return ":moneybag:"
    if amount < 5000:
        return ":moneybag::moneybag:"
    if amount < 20000:
        return ":moneybag::moneybag::moneybag:"
    return ":moneybag::moneybag::moneybag::moneybag::moneybag:"


# Active voting
NEW_GRANT_PROPOSAL_RESPONSE = """
Alright, let's make this happen! The proposal to grant {mention} {amount} points has been submitted. Layer 3 members who object can vote here: {voting_link}
"""
NEW_GRANT_PROPOSAL_VOTING_CHANNEL_MESSAGE = """
:rocket:{amount_reaction} **Active grant proposal** by {author}
{countdown} will grant {amount} points to {mention}: {description}
"""

# Finished voting
GRANT_PROPOSAL_ACCEPTED_VOTING_CHANNEL_EDIT = """
:tada: Granted {amount} points to {mention}: {description}
*Proposed by {author}: {link_to_original_message}*
"""
GRANT_PROPOSAL_RESULT_PROPOSER_RESPONSE = {
    ProposalResult.ACCEPTED: "Hooray! :tada: The grant has been given and {mention} is now richer by {amount} points!",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "Sorry, {author}, but it looks like {threshold} members weren't on board with your proposal: {voting_link}. No hard feelings, though! Take some time to reflect, make some tweaks, and try again with renewed vigor. :dove:",
    ProposalResult.CANCELLED_BY_PROPOSER: "{author} has cancelled the proposal.",
}

# =====================
# Grantless proposals
# =====================

# Active voting
NEW_GRANTLESS_PROPOSAL_RESPONSE = "Nice one, but let's see what the community thinks! Layer 3 members who object can vote here: {voting_link}"
NEW_GRANTLESS_PROPOSAL_VOTING_CHANNEL_MESSAGE = """
:rocket: **Active proposal** (no grant) by {author}
{countdown}: {description}
"""

# Finished voting
GRANTLESS_PROPOSAL_ACCEPTED_VOTING_CHANNEL_EDIT = """
:tada: Accepted proposal of {author}: {description}
*Proposed here: {link_to_original_message}*
"""
GRANTLESS_PROPOSAL_RESULT_PROPOSER_RESPONSE = {
    ProposalResult.ACCEPTED: "Hooray! :tada: The proposal has been accepted!",
    ProposalResult.CANCELLED_BY_REACHING_THRESHOLD: "Sorry, {author}, but it looks like {threshold} members weren't on board with your proposal: {voting_link}. No hard feelings, though! Take some time to reflect, make some tweaks, and try again with renewed vigor. :dove:",
    ProposalResult.CANCELLED_BY_PROPOSER: "{author} has cancelled the proposal.",
}
