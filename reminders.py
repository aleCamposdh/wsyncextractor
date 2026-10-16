"""Persistencia de recordatorios compartidos de WorkSync."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

from database import get_supabase
from tasks import ASSIGNEES


REMINDERS_TABLE = "worksync_reminders"
TASKS_FALLBACK_TABLE = "worksync_tasks"
REMINDER_SENTINEL = "__WORKSYNC_REMINDER__"
_fallback_to_tasks = False


def init_reminders_db() -> None:
    """Valida que la tabla compartida de recordatorios esté disponible."""
    global _fallback_to_tasks
    try:
        get_supabase().table(REMINDERS_TABLE).select("id").limit(1).execute()
        _fallback_to_tasks = False
    except Exception:
        # Compatibilidad inmediata para instalaciones que aún no ejecutaron la migración.
        get_supabase().table(TASKS_FALLBACK_TABLE).select("id").limit(1).execute()
        _fallback_to_tasks = True


def create_reminder(description: str, reminder_date: date,
                    assignees: Iterable[str] | None = None) -> None:
    description = description.strip()
    chosen_assignees = list(dict.fromkeys(assignees or []))
    if not description:
        raise ValueError("La descripcion es obligatoria")
    if not chosen_assignees or any(name not in ASSIGNEES for name in chosen_assignees):
        raise ValueError("Selecciona al menos una persona valida")
    if _fallback_to_tasks:
        get_supabase().table(TASKS_FALLBACK_TABLE).insert({
            "title": REMINDER_SENTINEL,
            "description": description,
            "assignee": chosen_assignees[0],
            "assigned_to": ", ".join(chosen_assignees),
            "priority": "Baja",
            "due_date": reminder_date.isoformat(),
        }).execute()
    else:
        get_supabase().table(REMINDERS_TABLE).insert({
            "description": description,
            "reminder_date": reminder_date.isoformat(),
            "assignees": chosen_assignees,
        }).execute()


def list_reminders() -> list[dict]:
    if _fallback_to_tasks:
        rows = (
            get_supabase().table(TASKS_FALLBACK_TABLE).select("*")
            .eq("title", REMINDER_SENTINEL).execute().data or []
        )
        rows = [{
            **row,
            "reminder_date": row["due_date"],
            "acknowledged": bool(row["completed"]),
            "acknowledged_at": row.get("completed_at"),
            "assignees": [
                name.strip() for name in (row.get("assigned_to") or row["assignee"]).split(",")
                if name.strip() in ASSIGNEES
            ],
        } for row in rows]
    else:
        rows = (
            get_supabase().table(REMINDERS_TABLE).select("*").execute().data or []
        )
    return sorted(rows, key=lambda reminder: (
        reminder["reminder_date"], reminder["created_at"]
    ))


def pending_reminders_for(day: date) -> list[dict]:
    if _fallback_to_tasks:
        rows = (
            get_supabase().table(TASKS_FALLBACK_TABLE).select("*")
            .eq("title", REMINDER_SENTINEL)
            .eq("due_date", day.isoformat())
            .eq("completed", False).execute().data or []
        )
        rows = [{
            **row,
            "reminder_date": row["due_date"],
            "acknowledged": bool(row["completed"]),
            "assignees": [
                name.strip() for name in (row.get("assigned_to") or row["assignee"]).split(",")
                if name.strip() in ASSIGNEES
            ],
        } for row in rows]
    else:
        rows = (
            get_supabase().table(REMINDERS_TABLE)
            .select("*")
            .eq("reminder_date", day.isoformat())
            .eq("acknowledged", False)
            .execute().data or []
        )
    return sorted(rows, key=lambda reminder: reminder["created_at"])


def acknowledge_reminders(reminder_ids: Iterable[str]) -> None:
    chosen_ids = list(reminder_ids)
    if not chosen_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    if _fallback_to_tasks:
        payload = {"completed": True, "completed_at": now, "updated_at": now}
        table = TASKS_FALLBACK_TABLE
    else:
        payload = {"acknowledged": True, "acknowledged_at": now}
        table = REMINDERS_TABLE
    get_supabase().table(table).update(payload).in_("id", chosen_ids).execute()


def delete_reminder(reminder_id: str) -> None:
    table = TASKS_FALLBACK_TABLE if _fallback_to_tasks else REMINDERS_TABLE
    get_supabase().table(table).delete().eq("id", reminder_id).execute()
