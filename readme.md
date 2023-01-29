# Eco Discord Lazy Consensus Bot

This Discord bot helps communities make faster and more efficient decisions using the Lazy Consensus process. Users can submit proposals and have them automatically approved if there are no objections. This approach, used by leading open-source [projects](https://community.apache.org/committers/lazyConsensus.html), saves time by eliminating the need for explicit voting:

> The key thing about lazy consensus is that it’s easier for people to agree by doing nothing, than it is to object, which requires them to propose an alternative. This has two effects: first, people are less likely to object for the sake of objecting and, second, it cuts down on the amount of unnecessary discussion.

The bot is developed specifically for [Eco](https://eco.org/) Discord community. You can [join](http://discord.eco.org/) to see it in action.

To improve sustainability, the bot uses PM2. If the script or system crashes, PM2 will restore the execution and any pending proposals will be recovered from the database, preserving the timer.

## Getting Started
These instructions will get you a copy of the project up and running on your machine.

1. Clone the project and cd into it:
```
git clone https://github.com/nisnevich/eco-discord-lazy-consensus-bot

cd eco-discord-lazy-consensus-bot
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
- [Node.js](https://nodejs.org)
- [npm](https://www.npmjs.com)
- [PM2](https://pm2.io)
- [Python 3.6](https://www.python.org/downloads/release/python-360/) or higher
- [SQLAlchemy](https://www.sqlalchemy.org/)

## Contributing

Looking to contribute? Check out [good first issues](https://github.com/nisnevich/eco-discord-lazy-consensus-bot/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22), or just [issues](https://github.com/nisnevich/eco-discord-lazy-consensus-bot/issues). Also you can [buy me a coffee](https://www.buymeacoffee.com/a.nisnevich). :)

There are three primary branches (the main difference between them is some constants):
- `main` is used for development
- `beta` is for beta testing on Eco Discord Test Server
- `prod` is for the main Eco server


