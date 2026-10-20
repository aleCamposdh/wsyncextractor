"""Persistencia y reportes del modulo de tareas de WorkSync."""
from __future__ import annotations

import html
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable
from uuid import uuid4
from zoneinfo import ZoneInfo

from database import get_supabase


TASKS_TABLE = "worksync_tasks"
TASK_ATTACHMENTS_BUCKET = "worksync-task-attachments"
ASSIGNEES = ("Danna", "Karen", "Nia", "Tatiana")
ASSIGNEE_COLORS = {
    "Danna": "#DB2777",
    "Karen": "#EA580C",
    "Nia": "#7C3AED",
    "Tatiana": "#2563EB",
}
PRIORITIES = ("Alta", "Media", "Baja")
PRIORITY_RANK = {"Alta": 1, "Media": 2, "Baja": 3}
RECURRENCE_PATTERNS = ("Diaria", "Semanal", "Mensual")
REMINDER_SENTINEL = "__WORKSYNC_REMINDER__"
LOCAL_TIMEZONE = ZoneInfo("America/Costa_Rica")


def init_db() -> None:
    """Validate that the shared Supabase task table is available."""
    get_supabase().table(TASKS_TABLE).select("id").limit(1).execute()


def task_assignees(task: dict) -> list[str]:
    stored = task.get("assigned_to") or ""
    chosen = [name.strip() for name in stored.split(",") if name.strip() in ASSIGNEES]
    primary = task.get("assignee")
    if primary in ASSIGNEES and primary not in chosen:
        chosen.insert(0, primary)
    return chosen or ([primary] if primary else [])


def task_completion_map(task: dict) -> dict[str, str]:
    """Return per-assignee completion timestamps, including legacy completed tasks."""
    stored = task.get("assignee_completions")
    completions = dict(stored) if isinstance(stored, dict) else {}
    if task.get("completed") and not completions:
        completed_at = task.get("completed_at") or task.get("updated_at") or task.get("created_at")
        if completed_at:
            completions = {name: completed_at for name in task_assignees(task)}
    return completions


def task_assignee_completed(task: dict, assignee: str) -> bool:
    return assignee in task_completion_map(task)


def format_task_datetime(value: str | None) -> str:
    if not value:
        return "—"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LOCAL_TIMEZONE).strftime("%d/%m/%Y %I:%M %p")


def create_task(title: str, description: str, assignee: str | Iterable[str],
                priority: str, due_date: date, is_recurring: bool = False,
                recurrence_pattern: str | None = None) -> str:
    chosen_assignees = ([assignee] if isinstance(assignee, str) else list(assignee))
    if not chosen_assignees or any(name not in ASSIGNEES for name in chosen_assignees) or priority not in PRIORITIES:
        raise ValueError("Asignado o prioridad no validos")
    if is_recurring and recurrence_pattern not in RECURRENCE_PATTERNS:
        raise ValueError("Frecuencia de recurrencia no valida")
    response = get_supabase().table(TASKS_TABLE).insert({
        "title": title.strip(),
        "description": description.strip(),
        "assignee": chosen_assignees[0],
        "assigned_to": ", ".join(dict.fromkeys(chosen_assignees)),
        "priority": priority,
        "due_date": due_date.isoformat(),
        "is_recurring": bool(is_recurring),
        "recurrence_pattern": recurrence_pattern if is_recurring else None,
    }).execute()
    return response.data[0]["id"]


def update_task(task_id: str, title: str, description: str,
                assignee: str | Iterable[str], priority: str, due_date: date,
                is_recurring: bool = False,
                recurrence_pattern: str | None = None) -> None:
    chosen_assignees = ([assignee] if isinstance(assignee, str) else list(assignee))
    if not title.strip() or not chosen_assignees:
        raise ValueError("Escribe el nombre y selecciona al menos una persona")
    if any(name not in ASSIGNEES for name in chosen_assignees) or priority not in PRIORITIES:
        raise ValueError("Asignado o prioridad no validos")
    if is_recurring and recurrence_pattern not in RECURRENCE_PATTERNS:
        raise ValueError("Frecuencia de recurrencia no valida")
    response = get_supabase().table(TASKS_TABLE).select("*").eq("id", task_id).execute()
    if not response.data:
        raise ValueError("La tarea ya no existe")
    current_task = response.data[0]
    completions = {
        name: completed_at
        for name, completed_at in task_completion_map(current_task).items()
        if name in chosen_assignees
    }
    all_completed = all(name in completions for name in chosen_assignees)
    was_completed = bool(current_task.get("completed"))
    completed_at = current_task.get("completed_at") if was_completed and all_completed else None
    if all_completed and not completed_at:
        completed_at = datetime.now(timezone.utc).isoformat()
    get_supabase().table(TASKS_TABLE).update({
        "title": title.strip(),
        "description": description.strip(),
        "assignee": chosen_assignees[0],
        "assigned_to": ", ".join(dict.fromkeys(chosen_assignees)),
        "priority": priority,
        "due_date": due_date.isoformat(),
        "is_recurring": bool(is_recurring),
        "recurrence_pattern": recurrence_pattern if is_recurring else None,
        "assignee_completions": completions,
        "completed": all_completed,
        "completed_at": completed_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def ensure_task_attachments_bucket() -> None:
    storage = get_supabase().storage
    try:
        storage.get_bucket(TASK_ATTACHMENTS_BUCKET)
    except Exception as error:
        if "not found" not in str(error).lower() and "404" not in str(error):
            raise
        storage.create_bucket(
            TASK_ATTACHMENTS_BUCKET,
            options={
                "public": False,
                "file_size_limit": 8 * 1024 * 1024,
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
            },
        )


def upload_task_attachment(task_id: str, filename: str, content_type: str,
                           content: bytes, previous_path: str | None = None) -> None:
    allowed_types = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    if content_type not in allowed_types:
        raise ValueError("La foto debe ser JPG, PNG o WebP")
    if len(content) > 8 * 1024 * 1024:
        raise ValueError("La foto no puede superar 8 MB")
    extension = Path(filename).suffix.lower() or allowed_types[content_type]
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = allowed_types[content_type]
    path = f"{task_id}/{uuid4().hex}{extension}"
    ensure_task_attachments_bucket()
    storage = get_supabase().storage.from_(TASK_ATTACHMENTS_BUCKET)
    storage.upload(path, content, {"content-type": content_type, "upsert": "false"})
    try:
        get_supabase().table(TASKS_TABLE).update({
            "attachment_path": path,
            "attachment_name": filename,
            "attachment_type": content_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", task_id).execute()
    except Exception:
        storage.remove([path])
        raise
    if previous_path and previous_path != path:
        storage.remove([previous_path])


def remove_task_attachment(task_id: str, attachment_path: str | None) -> None:
    if attachment_path:
        get_supabase().storage.from_(TASK_ATTACHMENTS_BUCKET).remove([attachment_path])
    get_supabase().table(TASKS_TABLE).update({
        "attachment_path": None,
        "attachment_name": None,
        "attachment_type": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def task_attachment_url(task: dict, expires_in: int = 3600) -> str | None:
    path = task.get("attachment_path")
    if not path:
        return None
    response = (
        get_supabase().storage.from_(TASK_ATTACHMENTS_BUCKET)
        .create_signed_url(path, expires_in)
    )
    if isinstance(response, dict):
        return response.get("signedURL") or response.get("signedUrl")
    return getattr(response, "signedURL", None) or getattr(response, "signedUrl", None)


def list_tasks(assignees: Iterable[str] | None = None, priorities: Iterable[str] | None = None,
               statuses: Iterable[str] | None = None,
               is_recurring: bool | None = None) -> list[dict]:
    query = get_supabase().table(TASKS_TABLE).select("*").neq("title", REMINDER_SENTINEL)
    if is_recurring is not None:
        query = query.eq("is_recurring", is_recurring)
    for field, values in (("priority", priorities),):
        chosen = list(values or [])
        if chosen:
            query = query.in_(field, chosen)
    chosen_statuses = list(statuses or [])
    if len(chosen_statuses) == 1:
        query = query.eq("completed", chosen_statuses[0] == "Completada")
    rows = query.execute().data or []
    chosen_assignees = set(assignees or [])
    if chosen_assignees:
        rows = [task for task in rows if chosen_assignees.intersection(task_assignees(task))]
    return sorted(
        rows,
        key=lambda task: (
            PRIORITY_RANK.get(task["priority"], 99),
            bool(task["completed"]),
            task["due_date"],
            task["created_at"],
        ),
    )


def set_completed(task_id: str, completed: bool) -> None:
    response = get_supabase().table(TASKS_TABLE).select("*").eq("id", task_id).execute()
    if not response.data:
        raise ValueError("La tarea ya no existe")
    task = response.data[0]
    completed_at = datetime.now(timezone.utc).isoformat() if completed else None
    completions = (
        {name: completed_at for name in task_assignees(task)} if completed else {}
    )
    get_supabase().table(TASKS_TABLE).update({
        "completed": completed,
        "completed_at": completed_at,
        "assignee_completions": completions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def set_assignee_completed(task_id: str, assignee: str, completed: bool) -> None:
    response = get_supabase().table(TASKS_TABLE).select("*").eq("id", task_id).execute()
    if not response.data:
        raise ValueError("La tarea ya no existe")
    task = response.data[0]
    assigned_people = task_assignees(task)
    if assignee not in assigned_people:
        raise ValueError("La persona no está asignada a esta tarea")
    completions = task_completion_map(task)
    now = datetime.now(timezone.utc).isoformat()
    if completed:
        completions[assignee] = now
    else:
        completions.pop(assignee, None)
    all_completed = all(name in completions for name in assigned_people)
    get_supabase().table(TASKS_TABLE).update({
        "assignee_completions": completions,
        "completed": all_completed,
        "completed_at": now if all_completed else None,
        "updated_at": now,
    }).eq("id", task_id).execute()


def set_priority(task_id: str, priority: str) -> None:
    if priority not in PRIORITIES:
        raise ValueError("Prioridad no valida")
    get_supabase().table(TASKS_TABLE).update({
        "priority": priority,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def delete_task(task_id: str) -> None:
    response = (
        get_supabase().table(TASKS_TABLE)
        .select("*").eq("id", task_id).execute()
    )
    if response.data and response.data[0].get("attachment_path"):
        get_supabase().storage.from_(TASK_ATTACHMENTS_BUCKET).remove(
            [response.data[0]["attachment_path"]]
        )
    get_supabase().table(TASKS_TABLE).delete().eq("id", task_id).execute()


def report_tasks(start: date, end: date, status: str,
                 assignees: Iterable[str] | None = None) -> list[dict]:
    query = (
        get_supabase()
        .table(TASKS_TABLE)
        .select("*")
        .neq("title", REMINDER_SENTINEL)
        .gte("due_date", start.isoformat())
        .lte("due_date", end.isoformat())
    )
    if status == "Completadas":
        query = query.eq("completed", True)
    elif status == "Pendientes":
        query = query.eq("completed", False)
    rows = query.execute().data or []
    chosen_assignees = set(assignees or [])
    if chosen_assignees:
        rows = [task for task in rows if chosen_assignees.intersection(task_assignees(task))]
    return sorted(
        rows,
        key=lambda task: (PRIORITY_RANK.get(task["priority"], 99), task["due_date"]),
    )


def build_pdf(tasks: list[dict], start: date, end: date, status: str,
              assignees: Iterable[str] | None = None) -> bytes:
    # PDF support is loaded only when a report is requested.  Keeping this
    # optional dependency out of the module import path prevents an issue in
    # ReportLab from taking down the tasks UI (and therefore the entire app).
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=32,
        leftMargin=32,
        topMargin=34,
        bottomMargin=30,
        title="Reporte de tareas WorkSync",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=26, textColor=colors.HexColor("#0C1628"), alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#64748B"), spaceAfter=12,
    )
    cell_style = ParagraphStyle("Cell", parent=styles["BodyText"], fontSize=7.5, leading=9)
    center_style = ParagraphStyle("Center", parent=cell_style, alignment=TA_CENTER)
    chosen_assignees = list(assignees or [])
    assignee_label = ", ".join(chosen_assignees) if chosen_assignees else "Todas"
    story = [
        Paragraph("WorkSync · Reporte de tareas", title_style),
        Paragraph(
            f"Periodo: {start.strftime('%d/%m/%Y')} – {end.strftime('%d/%m/%Y')}"
            f" &nbsp; | &nbsp; Estado: {status} &nbsp; | &nbsp; Persona: {html.escape(assignee_label)}",
            subtitle_style,
        ),
    ]

    total = len(tasks)
    completed = sum(int(task["completed"]) for task in tasks)
    pending = total - completed
    high = sum(task["priority"] == "Alta" for task in tasks)
    summary = Table(
        [["TOTAL", "COMPLETADAS", "PENDIENTES", "PRIORIDAD ALTA"],
         [str(total), str(completed), str(pending), str(high)]],
        colWidths=[1.55 * inch] * 4,
        rowHeights=[0.28 * inch, 0.48 * inch],
    )
    summary.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF7FC")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#036A8C")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#0F172A")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CDE8F2")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CDE8F2")),
    ]))
    story.extend([summary, Spacer(1, 14)])

    drawing = Drawing(470, 125)
    chart = VerticalBarChart()
    chart.x, chart.y, chart.width, chart.height = 45, 24, 385, 82
    chart.data = [[sum(task["priority"] == priority for task in tasks) for priority in PRIORITIES]]
    chart.categoryAxis.categoryNames = list(PRIORITIES)
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(1, max(chart.data[0], default=0))
    chart.valueAxis.valueStep = max(1, chart.valueAxis.valueMax // 4)
    chart.bars[0].fillColor = colors.HexColor("#00A8D8")
    chart.bars[0].strokeColor = None
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontSize = 7
    drawing.add(chart)
    story.extend([drawing, Spacer(1, 8)])

    if not tasks:
        story.append(Paragraph("No hay tareas para los filtros seleccionados.", styles["Normal"]))
    else:
        data = [[
            "Tarea", "Asignada a", "Prioridad", "Fecha límite", "Estado",
            "Creada / asignada", "Completada", "Progreso por persona", "Descripción",
        ]]
        for task in tasks:
            completions = task_completion_map(task)
            progress = "<br/>".join(
                f"{html.escape(person)}: "
                f"{html.escape(format_task_datetime(completions.get(person)) if person in completions else 'Pendiente')}"
                for person in task_assignees(task)
            )
            data.append([
                Paragraph(html.escape(task["title"]), cell_style),
                Paragraph(html.escape(", ".join(task_assignees(task))), center_style),
                Paragraph(task["priority"], center_style),
                Paragraph(datetime.fromisoformat(task["due_date"]).strftime("%d/%m/%Y"), center_style),
                Paragraph("Completada" if task["completed"] else "Pendiente", center_style),
                Paragraph(html.escape(format_task_datetime(task.get("created_at"))), center_style),
                Paragraph(html.escape(format_task_datetime(task.get("completed_at"))), center_style),
                Paragraph(progress, cell_style),
                Paragraph(html.escape(task["description"] or "—"), cell_style),
            ])
        table = Table(
            data,
            repeatRows=1,
            colWidths=[
                1.25*inch, .68*inch, .52*inch, .65*inch, .65*inch,
                .85*inch, .85*inch, 1.45*inch, 1.75*inch,
            ],
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0C1628")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4ED")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FC")]),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ]))
        story.append(table)

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#DCE4ED"))
        canvas.line(32, 22, landscape(letter)[0] - 32, 22)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.setFont("Helvetica", 7)
        canvas.drawString(32, 11, f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        canvas.drawRightString(landscape(letter)[0] - 32, 11, f"Pagina {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return buffer.getvalue()

