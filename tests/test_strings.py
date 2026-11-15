"""Consistency tests for the inventory and account strings."""
import unittest
from string import Formatter

from stem_telebot.ui import strings

NEW_KEYS = (
    "INV_MENU",
    "INV_LIST_TITLE",
    "INV_LIST_LINE",
    "INV_LIST_MORE",
    "INV_EMPTY",
    "INV_EMPTY_ADJUST",
    "INV_ADD_STEP",
    "INV_UPDATE_HEADER",
    "INV_UPDATE_STEP",
    "INV_EDIT_HEADER",
    "INV_EDIT_STEP",
    "INV_Q_EDIT_FIELD",
    "INV_Q_EDIT_VALUE",
    "INV_EDIT_SUCCESS",
    "INV_EDIT_FAILED",
    "INV_ERR_FIELD",
    "INV_DELETE_HEADER",
    "INV_DELETE_CONFIRM",
    "INV_DELETE_SUCCESS",
    "INV_DELETE_FAILED",
    "INV_ERR_CONFIRM",
    "INV_LABEL_NAME",
    "INV_LABEL_CATEGORY",
    "INV_LABEL_QTY",
    "INV_LABEL_UNIT",
    "INV_LABEL_LOCATION",
    "INV_LABEL_MIN",
    "INV_LABEL_ITEM",
    "INV_LABEL_FIELD",
    "INV_LABEL_DIRECTION",
    "INV_LABEL_REASON",
    "INV_Q_NAME",
    "INV_Q_CATEGORY",
    "INV_Q_QTY",
    "INV_Q_UNIT",
    "INV_Q_LOCATION",
    "INV_Q_MIN",
    "INV_Q_ITEM",
    "INV_Q_DIRECTION",
    "INV_Q_ADJUST_QTY",
    "INV_Q_REASON",
    "INV_SUGGEST_HINT",
    "INV_ADD_SUCCESS",
    "INV_ADD_FAILED",
    "INV_UPDATE_SUCCESS",
    "INV_ERR_NUMBER",
    "INV_ERR_NEGATIVE",
    "INV_ERR_NAME",
    "INV_ERR_ITEM",
    "INV_ERR_DIRECTION",
    "INV_ERR_POSITIVE",
    "INV_ERR_NOT_FOUND",
    "INV_ERR_INSUFFICIENT",
    "INV_ERR_GENERIC",
    "INV_ERR_LOAD",
    "INV_EXIT",
    "INV_DASHBOARD_TITLE",
    "INV_DASHBOARD_UNAVAILABLE",
    "PROMPT_SA_ACCOUNT_STEP",
    "PROMPT_SA_ACCOUNT_CONFIRM",
    "ROLE_ADMIN",
    "ROLE_LOGISTICS",
    "ROLE_ADMIN_PLURAL",
    "ROLE_LOGISTICS_PLURAL",
    "MSG_SA_LIST_TITLE",
    "MSG_SA_LIST_EMPTY",
    "MSG_SA_LIST_LINE",
    "MSG_SA_ACCOUNT_PENDING_NONE",
    "MSG_SA_ACCOUNT_CONFIRM_HINT",
    "ERR_SA_ALREADY_ACCOUNT",
    "MSG_SA_ACCOUNT_DELETED",
    "ACC_DELETE_CONFIRM",
    "ACC_ERR_CONFIRM",
    "ERR_SA_ACCOUNT_NOT_FOUND",
    "ERR_SA_ACCOUNT_DB",
    "ERR_SA_NOT_ADMIN",
    "ERR_SA_NOT_LOGISTICS",
    "BTN_SA_LOGISTICS",
    "BTN_SA_LIST_LOGISTICS",
    "BTN_SA_DEL_LOGISTICS",
    "BTN_SA_INV_EDIT",
    "BTN_SA_INV_DELETE",
    "BTN_YES",
    "BTN_NO",
    "PROMPT_SA_DEL_LOGISTICS",
)


def _placeholders(value):
    return sorted(field for _, field, _, _ in Formatter().parse(value) if field)


class NewStringTranslationsTests(unittest.TestCase):
    def test_keys_exist_and_are_not_empty_in_both_languages(self):
        for key in NEW_KEYS:
            for lang in ("EN", "MS"):
                with self.subTest(key=key, lang=lang):
                    self.assertIn(key, strings.STRINGS[lang])
                    self.assertTrue(strings.STRINGS[lang][key].strip())

    def test_placeholders_match_between_languages(self):
        for key in NEW_KEYS:
            with self.subTest(key=key):
                en = _placeholders(strings.STRINGS["EN"][key])
                ms = _placeholders(strings.STRINGS["MS"][key])
                self.assertEqual(en, ms)


class EscapeMdTests(unittest.TestCase):
    def test_escapes_markdown_characters(self):
        escaped = strings.escape_md("A4_Paper *pack* [x](y) `code`")
        for char in ("_", "*", "[", "]", "(", "`"):
            self.assertIn("\\" + char, escaped)
        self.assertNotIn("A4_Paper", escaped)

    def test_handles_none_and_numbers(self):
        self.assertEqual(strings.escape_md(None), "")
        self.assertEqual(strings.escape_md(10), "10")


if __name__ == "__main__":
    unittest.main()
