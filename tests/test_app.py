import unittest
from pathlib import Path
from uuid import uuid4

from server import ExpenseStore, IdempotencyConflict, ValidationError


class ExpenseStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        workspace_temp_root = Path(__file__).resolve().parents[1] / ".tmp-tests"
        workspace_temp_root.mkdir(exist_ok=True)
        self.db_path = workspace_temp_root / f"test-{uuid4()}.db"
        self.store = ExpenseStore(self.db_path)

    def tearDown(self) -> None:
        try:
            if self.db_path.exists():
                self.db_path.unlink()
        except PermissionError:
            pass

    def test_create_expense_replays_same_idempotency_key(self) -> None:
        payload = {
            "amount": "125.50",
            "category": "Food",
            "description": "Lunch",
            "date": "2026-04-30",
        }

        first = self.store.create_expense(payload, "same-key")
        second = self.store.create_expense(payload, "same-key")

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.expense["id"], second.expense["id"])

    def test_create_expense_rejects_reused_key_for_different_payload(self) -> None:
        self.store.create_expense(
            {
                "amount": "500.00",
                "category": "Travel",
                "description": "Cab",
                "date": "2026-04-28",
            },
            "shared-key",
        )

        with self.assertRaises(IdempotencyConflict):
            self.store.create_expense(
                {
                    "amount": "800.00",
                    "category": "Travel",
                    "description": "Flight",
                    "date": "2026-04-28",
                },
                "shared-key",
            )

    def test_list_expenses_filters_and_sorts_by_date_desc(self) -> None:
        self.store.create_expense(
            {
                "amount": "120.00",
                "category": "Food",
                "description": "Dinner",
                "date": "2026-04-20",
            },
            "food-1",
        )
        self.store.create_expense(
            {
                "amount": "300.00",
                "category": "Travel",
                "description": "Train",
                "date": "2026-04-18",
            },
            "travel-1",
        )
        self.store.create_expense(
            {
                "amount": "90.00",
                "category": "Food",
                "description": "Breakfast",
                "date": "2026-04-21",
            },
            "food-2",
        )

        filtered = self.store.list_expenses(category="food", sort="date_desc")

        self.assertEqual([expense["description"] for expense in filtered], ["Breakfast", "Dinner"])

    def test_validation_rejects_negative_amount(self) -> None:
        with self.assertRaises(ValidationError):
            self.store.create_expense(
                {
                    "amount": "-10.00",
                    "category": "Misc",
                    "description": "Refund mishap",
                    "date": "2026-04-21",
                },
                "bad-amount",
            )

    def test_description_is_optional(self) -> None:
        created = self.store.create_expense(
            {
                "amount": "45.00",
                "category": "Bills",
                "description": "",
                "date": "2026-04-25",
            },
            "optional-description",
        )

        self.assertEqual(created.expense["description"], "")

    def test_validation_rejects_missing_date(self) -> None:
        with self.assertRaises(ValidationError):
            self.store.create_expense(
                {
                    "amount": "45.00",
                    "category": "Bills",
                    "description": "",
                    "date": "",
                },
                "missing-date",
            )

    def test_default_listing_uses_created_at_order(self) -> None:
        first = self.store.create_expense(
            {
                "amount": "50.00",
                "category": "Food",
                "description": "First",
                "date": "2026-04-01",
            },
            "created-order-1",
        )
        second = self.store.create_expense(
            {
                "amount": "60.00",
                "category": "Food",
                "description": "Second",
                "date": "2026-03-01",
            },
            "created-order-2",
        )

        listed = self.store.list_expenses()

        self.assertEqual(listed[0]["id"], second.expense["id"])
        self.assertEqual(listed[1]["id"], first.expense["id"])

    def test_delete_expense_removes_entry(self) -> None:
        created = self.store.create_expense(
            {
                "amount": "80.00",
                "category": "Travel",
                "description": "Cab",
                "date": "2026-04-10",
            },
            "delete-entry",
        )

        deleted = self.store.delete_expense(created.expense["id"])

        self.assertTrue(deleted)
        self.assertEqual(self.store.list_expenses(), [])

    def test_delete_expense_returns_false_for_missing_id(self) -> None:
        self.assertFalse(self.store.delete_expense("missing-id"))


if __name__ == "__main__":
    unittest.main()
