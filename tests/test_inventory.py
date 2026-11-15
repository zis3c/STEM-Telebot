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
