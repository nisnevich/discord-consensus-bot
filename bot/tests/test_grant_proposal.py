import asynctest
import unittest.mock as mock

from bot.propose import validate_grant_message
from bot.config.const import *


class TestValidateGrantMessage(asynctest.TestCase):
    @mock.patch("discord.User")
    async def test_valid_message(self, mock_user):
        original_message = asynctest.MagicMock()
        mock_user().receiver_ids = "@user"
        original_message.mentions = [mock_user()]
        mention = original_message.mentions[0].mention
        original_message.content = "!propose @user 100 test_description"
        original_message.reply = asynctest.CoroutineMock()
        amount = "100"
        description = "test_description"
        is_valid = await validate_grant_message(original_message, mention, amount, description)
        self.assertTrue(is_valid)
        original_message.reply.assert_not_called()

    async def test_message_with_no_mentions(self):
        original_message = asynctest.MagicMock()
        original_message.mentions = []
        mention = None
        original_message.content = "!propose 100 test_description"
        original_message.reply = asynctest.CoroutineMock()
        amount = "100"
        description = "test_description"
        is_valid = await validate_grant_message(original_message, mention, amount, description)
        self.assertFalse(is_valid)
        original_message.reply.assert_called_once_with(ERROR_MESSAGE_NO_MENTIONS)

    async def test_invalid_command_format(self):
        original_message = asynctest.MagicMock()
        original_message.mentions = [asynctest.MagicMock()]
        mention = original_message.mentions[0]
        original_message.content = "@user !propose 100 test_description"
        original_message.reply = asynctest.CoroutineMock()
        amount = "100"
        description = "test_description"
        is_valid = await validate_grant_message(original_message, mention, amount, description)
        self.assertFalse(is_valid)
        original_message.reply.assert_called_once_with(ERROR_MESSAGE_INVALID_COMMAND_FORMAT)

    @mock.patch("discord.User")
    async def test_invalid_user(self, mock_user):
        original_message = asynctest.MagicMock()
        original_message.content = "!propose not_a_valid_mention 100 test_description"
        original_message.mentions = [mock_user()]
        mention = original_message.mentions[0].mention
        original_message.reply = asynctest.CoroutineMock()
        mock_user.receiver_ids = "not_a_valid_mention"
        is_valid = await validate_grant_message(
            original_message, mention, "100", "test_description"
        )
        self.assertFalse(is_valid)
        original_message.reply.assert_called_once_with(ERROR_MESSAGE_INVALID_COMMAND_FORMAT)

    @mock.patch("discord.User")
    async def test_invalid_amount(self, mock_user):
        original_message = asynctest.MagicMock()
        original_message.mentions = [mock_user()]
        mention = original_message.mentions[0].mention
        original_message.content = (
            f"!propose {original_message.mentions[0].mention} not_a_digit test_description"
        )
        original_message.reply = asynctest.CoroutineMock()
        amount = "not_a_digit"
        description = "test_description"
        is_valid = await validate_grant_message(original_message, mention, amount, description)
        self.assertFalse(is_valid)
        original_message.reply.assert_called_once_with(ERROR_MESSAGE_INVALID_AMOUNT)

    @mock.patch("discord.User")
    async def test_invalid_description(self, mock_user):
        original_message = asynctest.MagicMock()
        original_message.mentions = [mock_user()]
        mention = original_message.mentions[0].mention
        original_message.content = f"!propose {original_message.mentions[0].mention} 100"
        original_message.reply = asynctest.CoroutineMock()
        amount = "100"
        description = ""
        is_valid = await validate_grant_message(original_message, mention, amount, description)
        self.assertFalse(is_valid)
        original_message.reply.assert_called_once_with(ERROR_MESSAGE_INVALID_DESCRIPTION)


if __name__ == '__main__':
    asynctest.main()
