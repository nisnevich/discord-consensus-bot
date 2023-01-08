# Eco Discord Lazy Consensus Bot

The Eco Discord Lazy Consensus Bot is a Discord bot that helps communities make decisions by implementing the Lazy Consensus decision-making process. It allows users to submit grant proposals and have them approved if there are no objections after a certain period of time. It was developed for [Eco](https://eco.org/) Discord community.

## Getting Started
These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

1. Clone the project:
```
git clone https://github.com/nisnevich/eco-discord-lazy-consensus-bot
```

2. Create token.txt file with your bot's token:

```
echo <TOKEN> > token.txt

chmod 600 token.txt # You should make it only readable by you
```

3. Run startup.sh to install dependencies and start the project.
`./startup.sh`

4. Use bot from Discord:
- `!grant_proposal <mention> <amount> [description]`: Submit a grant proposal. The proposal will be approved after GRANT_PROPOSAL_TIMER_SECONDS unless a L3 member reacts with a :x: emoji to the original message or the confirmation message.

5. To stop the bot, use shutdown.sh.
`./shutdown.sh`

### Dependencies:
- [Node.js](https://nodejs.org)
- [npm](https://www.npmjs.com)
- [PM2](https://pm2.io)
- [Python 3.6](https://www.python.org/downloads/release/python-360/) or higher
- [sqlite3](https://www.sqlite.org)

## Contributing
Contributions are welcome! Feel free to create pull requests or reach out. Also you can [buy me a coffee](https://www.buymeacoffee.com/a.nisnevich).
