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
- `!propose <mention> <amount> [description]`: Submit a grant proposal. The proposal will be approved after 3 days (72 hours) unless any Layer 3 member reacts with :x: emoji, in that case the proposal will be cancelled.

5. To stop the bot, use shutdown.sh.
```
./shutdown.sh
```

### Dependencies:
- [Node.js](https://nodejs.org)
- [npm](https://www.npmjs.com)
- [PM2](https://pm2.io)
- [Python 3.6](https://www.python.org/downloads/release/python-360/) or higher
- [sqlite3](https://www.sqlite.org)

## Contributing
Contributions are welcome! Feel free to create pull requests or reach out. Also you can [buy me a coffee](https://www.buymeacoffee.com/a.nisnevich).
