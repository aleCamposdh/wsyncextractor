import unittest
from datetime import date

import pandas as pd

from mungo.transformer import (
    filtrar_por_start_date,
    limpiar_activity,
    normalizar_fecha,
    normalizar_total,
    transformar_ordenes_mungo,
)


class MungoTransformerTests(unittest.TestCase):
    def test_activity_removes_only_first_prefix(self):
        self.assertEqual(limpiar_activity("Interior Cleaning-Rough Clean"), "Rough Clean")
        self.assertEqual(limpiar_activity("Cleaning-Pre-Paint-Clean"), "Pre-Paint-Clean")
        self.assertEqual(limpiar_activity("Final Clean"), "Final Clean")

    def test_mungo_mapping(self):
        raw = pd.DataFrame([{
            "Activity": "Interior Cleaning-Rough Clean",
            "Lot#": 37,
            "Community": "RYDER PARK",
            "PO#": 49071413,
            "Address": "3622 Teslow Drive",
            "PO Amount": "190,61",
            "Start Date": "7/1/26",
        }])

        result = transformar_ordenes_mungo(raw)

        self.assertEqual(result.iloc[0].to_dict(), {
            "Client Name": "Mungo Homes",
            "Job title Final": "Rough Clean / LOT 37 / RYDER PARK / 49071413",
            "Full Property Address": "3622 Teslow Drive",
            "total": "190.61",
            "Start Date": "07/01/2026",
        })

    def test_amount_and_date_formats(self):
        self.assertEqual(normalizar_total("$1,234.56"), "1234.56")
        self.assertEqual(normalizar_total("1.234,56"), "1234.56")
        self.assertEqual(normalizar_fecha("7/1/2026"), "07/01/2026")

    def test_missing_columns_are_reported(self):
        with self.assertRaisesRegex(ValueError, "PO#"):
            transformar_ordenes_mungo(pd.DataFrame([{"Activity": "A-B"}]))

    def test_filters_by_exact_start_date(self):
        raw = pd.DataFrame({
            "PO#": [1, 2, 3],
            "Start Date": ["7/1/26", "07/02/2026", "invalid"],
        })

        result = filtrar_por_start_date(raw, date(2026, 7, 1), date(2026, 7, 1))

        self.assertEqual(result["PO#"].tolist(), [1])

    def test_filters_by_start_date_range(self):
        raw = pd.DataFrame({
            "PO#": [1, 2, 3],
            "Start Date": ["7/1/26", "07/02/2026", "07/10/2026"],
        })

        result = filtrar_por_start_date(raw, date(2026, 7, 1), date(2026, 7, 2))

        self.assertEqual(result["PO#"].tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
