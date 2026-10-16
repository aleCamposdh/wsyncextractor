import unittest
from datetime import date
from unittest.mock import patch

import tasks


class TaskModuleTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        self.client = FakeSupabase(self.rows)
        self.supabase_patch = patch("tasks.get_supabase", return_value=self.client)
        self.supabase_patch.start()
        tasks.init_db()

    def tearDown(self):
        self.supabase_patch.stop()

    def test_tasks_are_sorted_by_priority(self):
        tasks.create_task("Baja", "", "Nia", "Baja", date(2026, 10, 14))
        tasks.create_task("Alta", "", "Danna", "Alta", date(2026, 10, 14))
        tasks.create_task("Media", "", "Karen", "Media", date(2026, 10, 14))

        self.assertEqual(
            [task["priority"] for task in tasks.list_tasks()],
            ["Alta", "Media", "Baja"],
        )

    def test_filter_completion_and_pdf(self):
        tasks.create_task("Revisar orden", "Detalle", "Tatiana", "Alta", date(2026, 10, 14))
        task = tasks.list_tasks()[0]
        tasks.set_completed(task["id"], True)

        completed = tasks.list_tasks(assignees=["Tatiana"], statuses=["Completada"])
        self.assertEqual(len(completed), 1)
        report_rows = tasks.report_tasks(date(2026, 10, 14), date(2026, 10, 14), "Completadas")
        pdf = tasks.build_pdf(
            report_rows, date(2026, 10, 14), date(2026, 10, 14), "Completadas"
        )
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_priority_update_and_report_by_assignee(self):
        tasks.create_task("Tarea Danna", "", "Danna", "Media", date(2026, 10, 14))
        tasks.create_task("Tarea Karen", "", "Karen", "Alta", date(2026, 10, 14))
        danna_task = tasks.list_tasks(assignees=["Danna"])[0]

        tasks.set_priority(danna_task["id"], "Alta")

        self.assertEqual(tasks.list_tasks(assignees=["Danna"])[0]["priority"], "Alta")
        report_rows = tasks.report_tasks(
            date(2026, 10, 14), date(2026, 10, 14), "Todas", ["Karen"]
        )
        self.assertEqual([row["assignee"] for row in report_rows], ["Karen"])
        pdf = tasks.build_pdf(
            report_rows, date(2026, 10, 14), date(2026, 10, 14), "Todas", ["Karen"]
        )
        self.assertTrue(pdf.startswith(b"%PDF"))
class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
        self.operation = "select"
        self.payload = None

    def select(self, _columns):
        self.operation = "select"
        return self

    def limit(self, _limit):
        return self

    def insert(self, payload):
        self.operation, self.payload = "insert", payload
        return self

    def update(self, payload):
        self.operation, self.payload = "update", payload
        return self

    def delete(self):
        self.operation = "delete"
        return self

    def eq(self, field, value):
        self.filters.append(("eq", field, value))
        return self

    def in_(self, field, values):
        self.filters.append(("in", field, values))
        return self

    def gte(self, field, value):
        self.filters.append(("gte", field, value))
        return self

    def lte(self, field, value):
        self.filters.append(("lte", field, value))
        return self

    def _matches(self, row):
        for operation, field, value in self.filters:
            if operation == "eq" and row[field] != value:
                return False
            if operation == "in" and row[field] not in value:
                return False
            if operation == "gte" and row[field] < value:
                return False
            if operation == "lte" and row[field] > value:
                return False
        return True

    def execute(self):
        matching = [row for row in self.rows if self._matches(row)]
        if self.operation == "insert":
            row = {
                "id": str(len(self.rows) + 1),
                "completed": False,
                "completed_at": None,
                "created_at": f"2026-10-14T00:00:0{len(self.rows)}+00:00",
                "updated_at": f"2026-10-14T00:00:0{len(self.rows)}+00:00",
                **self.payload,
            }
            self.rows.append(row)
            return FakeResponse([row])
        if self.operation == "update":
            for row in matching:
                row.update(self.payload)
            return FakeResponse(matching)
        if self.operation == "delete":
            self.rows[:] = [row for row in self.rows if not self._matches(row)]
            return FakeResponse(matching)
        return FakeResponse(matching)


class FakeSupabase:
    def __init__(self, rows):
        self.rows = rows

    def table(self, _name):
        return FakeQuery(self.rows)


if __name__ == "__main__":
    unittest.main()
