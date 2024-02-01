# Discord Consensus Bot

This Discord bot helps communities make faster and more efficient decisions using the Lazy Consensus process. Users can submit proposals and have them automatically approved if there are no objections. This approach, used by leading open-source [projects](https://community.apache.org/committers/lazyConsensus.html), saves time by eliminating the need for explicit voting:

> The key thing about lazy consensus is that it’s easier for people to agree by doing nothing, than it is to object, which requires them to propose an alternative. This has two effects: first, people are less likely to object for the sake of objecting and, second, it cuts down on the amount of unnecessary discussion.

To improve sustainability, the bot uses PM2. If the script or system crashes, PM2 will restore the execution and any pending proposals will be recovered from the database, preserving the timer.

## Getting Started
These instructions will get you a copy of the project up and running on your machine.

1. Clone the project and cd into it:
```
git clone https://github.com/nisnevich/discord-lazy-consensus-bot

cd discord-lazy-consensus-bot
```

2. Create token file with your bot's [token](https://discord.com/developers/applications) integrated with your server:

```
echo <TOKEN> > token

chmod 600 token # You should make it only readable by you
```

3. Run startup.sh to install dependencies and start the project.
```
./startup.sh # Made with Debian-based systems in mind
```

4. Use bot from Discord:
- `!propose mention amount reason`: Submit a proposal to give a grant. The grant will be automatically applied after 3 days (72 hours), unless a certain amount of members with "Layer 3" role react with :x: emoji, which would cancel the proposal. Example:
```
!propose @ChangpengZhao 50 for leading the successful launch of Binance Coin (BNB) 
```

- `!propose description`: Submit a proposal that doesn't require a grant. The approval and cancelling rules are the same. Example:
```
!propose to schedule a community meetup next Friday at 18:00 UTC
```

5. To stop the bot, use shutdown.sh.
```
./shutdown.sh
```

### Dependencies:
- [Python 3.6](https://www.python.org/downloads/release/python-360/) or higher
- [Discord API 2.1](https://discord.com/developers/docs/intro) 
- [SQLAlchemy 1.4.46](https://www.sqlalchemy.org/)
- [NLTK](https://www.nltk.org/)
- [PM2](https://pm2.io) (requires [npm](https://www.npmjs.com) and [Node.js](https://nodejs.org))
- [Google Cloud SDK](https://cloud.google.com/sdk)

## User Guide

List of commands available (all constants mentioned below in **UPPERCASE** are defined in const.py):

- `!propose` to submit a proposal to lazy consensus (it can be financial or not, depending on the syntax: `!propose @user 100 reason` for a financial, and `!propose description` for a simple one).
- `!tips` to send allocation from a personal pool (each members pool is limited by **FREE_FUNDING_LIMIT_PERSON_PER_SEASON**).
- `!export` to receive analytics (bot will send a spreadsheet with multiple pages, such as financial statistics, user activity, proposals history).
- `!help` to receive a message with usage instructions.

Here's a general description how the bot can be used:
- Each proposal submitted with `!propose` will be posted in the voting channel (defined by **VOTING_CHANNEL_ID**). The voting time period is defined by **PROPOSAL_DURATION_SECONDS**.
- In order to support or object a proposal, members should react with emojis to the message in the voting channel (emojis defined with **EMOJI_VOTING_YES** or **EMOJI_VOTING_NO**). Only members with certain roles defined in **ROLE_IDS_ALLOWED** list are allowed to vote.
- In lazy consensus, for a proposal to be cancelled, it has to reach a number of downvotes equal to **LAZY_CONSENSUS_THRESHOLD_NEGATIVE**. Otherwise it will be accepted (unless **FULL_CONSENSUS_ENABLED** is True). Read more about lazy consensus [here](https://community.apache.org/committers/decisionMaking.html).
- Additionally, if **FULL_CONSENSUS_ENABLED** is True, then in order to pass, each proposal has to reach a minimum of **FULL_CONSENSUS_THRESHOLD_POSITIVE** supportive votes. Otherwise it will be cancelled after a period of **PROPOSAL_DURATION_SECONDS**. Read more about full consensus [here](https://docs.fedoraproject.org/en-US/dei/policy/decision-process/#_full_consensus).

Other important constants not mentioned above:
- **GRANT_APPLY_CHANNEL_ID** - a channel where the finance will be sent by the bot (uses `!grant` command which can be enabled via [accountant](https://github.com/eco/discord-accountant) or another bot).
- **BOT_ID** - a Discord ID of the bot added to the server.
- **RESPONSIBLE_ID** - a Discord ID of a member responsible for maintaining the bot (used in error messages to instantly ping).
And few more. Make sure to check "Critical application constants" in const.py and verify all values before running a bot. Adoption to each new server should involve editing text messages under the "Messages texts" section, for better user experience.

## Contributing

Looking to contribute? Check out [good first issues](https://github.com/nisnevich/eco-discord-lazy-consensus-bot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22), or just [issues](https://github.com/nisnevich/eco-discord-lazy-consensus-bot/issues). Also you can [buy me a coffee](https://www.buymeacoffee.com/a.nisnevich). :)

The bot has been developed targetting [Eco](https://eco.org/) Discord community.

There are three primary branches (the main difference between them is some constants):
- `main` is used for development
- `beta` is for beta testing on Eco Discord Test Server
- `prod` is for the main Eco server


