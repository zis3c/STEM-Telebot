"""Notification tests for adding admin/logistics accounts."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from stem_telebot.handlers import superadmin


class AccountPromotionMessageTests(unittest.IsolatedAsyncioTestCase):
    async def _confirm(self, role):
        update = MagicMock()
        update.effective_user.id = 1
        update.effective_user.first_name = "SA"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {
            "lang": "EN",
            "manage_section": "logistics" if role == "Logistics" else "admin",
            "add_account_pending": {"id": 222, "label": "@bob"},
        }
        context.bot.send_message = AsyncMock()

        with patch.object(superadmin.db, "is_superadmin", return_value=True), \
             patch.object(superadmin.db, "has_sheet_account", return_value=False), \
             patch.object(superadmin.db, "add_admin", return_value=True), \
             patch.object(superadmin.db, "log_action", return_value=None):
            await superadmin.add_account_confirm(update, context)

        return context.bot.send_message.await_args.kwargs["text"]

    async def test_logistics_role_gets_logistics_message(self):
        text = await self._confirm("Logistics")
        self.assertIn("promoted to Logistics", text)
        self.assertNotIn("promoted to Admin", text)

    async def test_admin_role_gets_admin_message(self):
        text = await self._confirm("Admin")
        self.assertIn("promoted to Admin", text)
        self.assertNotIn("Logistics access", text)


if __name__ == "__main__":
    unittest.main()
