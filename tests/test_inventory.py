"""Unit tests for the inventory stock and movement logic."""
import os
import unittest

os.environ.setdefault("STATS_LINK_SECRET", "test-secret-demo-only-key")

from stem_telebot.core import stats_web  # noqa: E402
from stem_telebot.core.database import (  # noqa: E402
    INVENTORY_HEADERS,
    INVENTORY_LOG_HEADERS,
    Database,
)


class FakeCell:
    def __init__(self, row, col=1):
        self.row = row
        self.col = col


class FakeWS:
    def __init__(self, rows):
        self.rows = [list(row) for row in rows]

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def get_all_records(self):
        if not self.rows:
            return []
        headers = [str(cell).strip() for cell in self.rows[0]]
        records = []
        for row in self.rows[1:]:
            record = {}
            for index, header in enumerate(headers):
                if not header:
                    continue
                record[header] = row[index] if index < len(row) else ""
            records.append(record)
        return records

    def find(self, value, in_column=1):
        target = str(value).strip().upper()
        for idx, row in enumerate(self.rows, start=1):
            if len(row) >= in_column and str(row[in_column - 1]).strip().upper() == target:
                return FakeCell(idx)
        return None

    def row_values(self, row):
        return list(self.rows[row - 1])

    def update_cell(self, row, col, value):
        while len(self.rows[row - 1]) < col:
            self.rows[row - 1].append("")
        self.rows[row - 1][col - 1] = value

    def append_row(self, row):
        self.rows.append(list(row))


class FakeDB(Database):
    def __init__(self, sheets):
        self.sheets = sheets

    def get_sheet(self, sheet_name="Registrations"):
        return self.sheets.get(sheet_name)


def make_db():
    return FakeDB(
        {
            "Inventory": FakeWS([INVENTORY_HEADERS]),
            "InventoryLog": FakeWS([INVENTORY_LOG_HEADERS]),
        }
    )


class InventoryTests(unittest.TestCase):
    def test_add_item_assigns_sequential_id_and_logs_opening_stock(self):
        db = make_db()

        first = db.add_inventory_item("A4 Paper", "Consumable", 10, "ream", "Store", 5, "Ali")
        second = db.add_inventory_item("Glue", "Consumable", 2, "bottle", "Store", 1, "Ali")

        self.assertTrue(first["ok"])
        self.assertEqual(first["id"], "INV-001")
        self.assertEqual(second["id"], "INV-002")

        log = db.get_inventory_log()
        self.assertEqual(len(log), 2)
        self.assertEqual(log[-1]["item_id"], "INV-001")
        self.assertEqual(log[-1]["delta"], 10)
        self.assertEqual(log[-1]["balance"], 10)

    def test_adjust_inventory_applies_delta_and_records_movement(self):
        db = make_db()
        db.add_inventory_item("A4 Paper", "Consumable", 10, "ream", "Store", 5, "Ali")

        result = db.adjust_inventory("inv-001", -3, "Used for event", "Siti")

        self.assertTrue(result["ok"])
        self.assertEqual(result["current"], 10)
        self.assertEqual(result["new_qty"], 7)
        self.assertEqual(db.get_inventory_items()[0]["qty"], 7)

        log = db.get_inventory_log()
        self.assertEqual(log[0]["delta"], -3)
        self.assertEqual(log[0]["balance"], 7)
        self.assertEqual(log[0]["reason"], "Used for event")

    def test_adjust_inventory_rejects_below_zero_without_writing(self):
        db = make_db()
        db.add_inventory_item("A4 Paper", "Consumable", 10, "ream", "Store", 5, "Ali")

        result = db.adjust_inventory("INV-001", -100, "Too many", "Ali")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "insufficient")
        self.assertEqual(db.get_inventory_items()[0]["qty"], 10)
        self.assertEqual(len(db.get_inventory_log()), 1)

    def test_adjust_inventory_unknown_id(self):
        db = make_db()
        result = db.adjust_inventory("INV-999", 1, "Restock", "Ali")
        self.assertEqual(result["error"], "not_found")

    def test_add_item_rejects_negative_quantity(self):
        db = make_db()
        result = db.add_inventory_item("Broken", "Misc", -5, "unit", "Store", 0, "Ali")
        self.assertEqual(result["error"], "negative_qty")
        self.assertEqual(db.get_inventory_items(), [])


class RoleConfigTests(unittest.TestCase):
    def _db(self, records):
        db = FakeDB({"system_admins": FakeWS(records)})
        db.superadmin_ids = set()
        db.admin_ids = set()
        db.cached_sheet_admins = []
        db.cached_sheet_logistics = []
        db.maintenance_mode = False
        db.last_config_refresh = 0
        return db

    def test_roles_split_admin_and_logistics(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By", "Role"],
                ["111", "@alice", "SA:9", "Admin"],
                ["222", "@bob", "SA:9", "Logistics"],
                ["333", "@carol", "SA:9", ""],
            ]
        )
        db.refresh_system_config(force=True)

        self.assertIn(111, db.cached_sheet_admins)
        self.assertIn(333, db.cached_sheet_admins)  # blank role = legacy admin
        self.assertNotIn(222, db.cached_sheet_admins)
        self.assertIn(222, db.cached_sheet_logistics)

        self.assertTrue(db.is_logistics(222))
        self.assertFalse(db.is_admin(222))
        self.assertTrue(db.is_inventory_user(222))
        self.assertFalse(db.is_inventory_user(111))
        self.assertTrue(db.is_admin(111))

    def test_list_sheet_accounts_includes_role_and_name(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By", "Role"],
                ["111", "@alice", "SA:9", "Admin"],
                ["222", "@bob", "SA:9", "Logistics"],
            ]
        )
        accounts = db.list_sheet_accounts()
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0]["name"], "@alice")
        self.assertEqual(accounts[1]["role"], "Logistics")

    def test_superadmin_is_not_inventory_user_even_with_logistics_row(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By", "Role"],
                ["999", "@sa", "SA:1", "Logistics"],
            ]
        )
        db.superadmin_ids = {999}
        db.refresh_system_config(force=True)
        self.assertTrue(db.is_logistics(999))
        self.assertFalse(db.is_inventory_user(999))

    def test_env_admin_is_not_inventory_user_even_with_logistics_row(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By", "Role"],
                ["888", "@env", "SA:1", "Logistics"],
            ]
        )
        db.admin_ids = {888}
        db.refresh_system_config(force=True)
        self.assertTrue(db.is_logistics(888))
        self.assertFalse(db.is_inventory_user(888))

    def test_has_sheet_account_detects_existing_ids_only(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By", "Role"],
                ["111", "@alice", "SA:9", "Admin"],
                ["222", "@bob", "SA:9", "Logistics"],
            ]
        )
        self.assertTrue(db.has_sheet_account(111))
        self.assertTrue(db.has_sheet_account("222"))
        self.assertFalse(db.has_sheet_account(999))
        self.assertFalse(db.has_sheet_account("not-an-id"))

    def test_legacy_three_column_sheet_still_loads_as_admin(self):
        db = self._db(
            [
                ["User ID", "Name", "Added By"],
                ["444", "Old Admin", "SA:9"],
            ]
        )
        db.refresh_system_config(force=True)
        self.assertIn(444, db.cached_sheet_admins)

    def test_add_admin_writes_role_and_splits_cache(self):
        db = self._db([["User ID", "Name", "Added By", "Role"]])
        self.assertTrue(db.add_admin(555, "@dave", "SA:9", "Logistics"))

        rows = db.sheets["system_admins"].get_all_values()
        self.assertEqual(rows[-1], ["555", "@dave", "SA:9", "Logistics"])
        self.assertIn(555, db.cached_sheet_logistics)
        self.assertNotIn(555, db.cached_sheet_admins)


class SuggestionTests(unittest.TestCase):
    def test_suggestions_dedupe_and_order_by_frequency(self):
        from stem_telebot.handlers.superadmin import _suggestions

        self.assertEqual(
            _suggestions(["A", "B", "A", "", " C ", "C"], limit=2),
            ["A", "C"],
        )

    def test_suggestions_exclude_reserved_and_long_values(self):
        from stem_telebot.handlers.superadmin import _suggestions

        values = ["Cancel", "A" * 30, "Store Room"]
        self.assertEqual(_suggestions(values), ["Store Room"])


class InventoryTokenTests(unittest.TestCase):
    def test_token_roundtrip_and_tamper(self):
        token = stats_web.create_inventory_token()
        self.assertTrue(stats_web.verify_inventory_token(token))
        self.assertFalse(stats_web.verify_inventory_token(token[:-4] + "0000"))
        self.assertFalse(stats_web.verify_inventory_token("0.deadbeef"))
        self.assertFalse(stats_web.verify_inventory_token("garbage"))

    def test_expired_token_rejected(self):
        expired = f"1.{stats_web._sign('inventory.1')}"
        self.assertFalse(stats_web.verify_inventory_token(expired))


if __name__ == "__main__":
    unittest.main()
