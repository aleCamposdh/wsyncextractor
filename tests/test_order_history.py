import unittest
from unittest import mock

import pandas as pd

import order_history


def _df():
    return pd.DataFrame({
        "Job title Final": [
            "Clean / LOT 1 / WESTVIEW / 100",
            "Final Clean / LOT 1 / WESTVIEW / 100",  # mismo PO, otra actividad
            "Clean / LOT 2 / WESTVIEW / 101",
        ],
        "total": ["1.00", "2.00", "3.00"],
    })


class SplitExportedTests(unittest.TestCase):
    def test_same_po_other_activity_is_not_duplicate(self):
        known = {"mungo:clean / lot 1 / westview / 100": "2026-11-01T10:00:00+00:00"}
        with mock.patch.object(order_history, "_fetch_known", return_value=known):
            new, dups, keys = order_history.split_exported(_df())
        self.assertEqual(new["total"].tolist(), ["2.00", "3.00"])
        self.assertEqual(dups["total"].tolist(), ["1.00"])
        self.assertEqual(dups["Exported At"].tolist(), ["11/01/2026 10:00"])
        self.assertEqual(len(keys), 2)

    def test_missing_key_column_raises(self):
        with self.assertRaises(ValueError):
            order_history.order_keys(pd.DataFrame({"total": ["1"]}))


if __name__ == "__main__":
    unittest.main()
