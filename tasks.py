"""Persistencia y reportes del modulo de tareas de WorkSync."""
from __future__ import annotations

import html
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Iterable

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from database import get_supabase


TASKS_TABLE = "worksync_tasks"
ASSIGNEES = ("Danna", "Karen", "Nia", "Tatiana")
ASSIGNEE_COLORS = {
    "Danna": "#CA8A04",
    "Karen": "#EA580C",
    "Nia": "#7C3AED",
    "Tatiana": "#2563EB",
}
PRIORITIES = ("Alta", "Media", "Baja")
PRIORITY_RANK = {"Alta": 1, "Media": 2, "Baja": 3}
REMINDER_SENTINEL = "__WORKSYNC_REMINDER__"


def init_db() -> None:
    """Validate that the shared Supabase task table is available."""
    get_supabase().table(TASKS_TABLE).select("id").limit(1).execute()


def create_task(title: str, description: str, assignee: str, priority: str, due_date: date) -> None:
    if assignee not in ASSIGNEES or priority not in PRIORITIES:
        raise ValueError("Asignado o prioridad no validos")
    get_supabase().table(TASKS_TABLE).insert({
        "title": title.strip(),
        "description": description.strip(),
        "assignee": assignee,
        "priority": priority,
        "due_date": due_date.isoformat(),
    }).execute()


def list_tasks(assignees: Iterable[str] | None = None, priorities: Iterable[str] | None = None,
               statuses: Iterable[str] | None = None) -> list[dict]:
    query = get_supabase().table(TASKS_TABLE).select("*").neq("title", REMINDER_SENTINEL)
    for field, values in (("assignee", assignees), ("priority", priorities)):
        chosen = list(values or [])
        if chosen:
            query = query.in_(field, chosen)
    chosen_statuses = list(statuses or [])
    if len(chosen_statuses) == 1:
        query = query.eq("completed", chosen_statuses[0] == "Completada")
    rows = query.execute().data or []
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
    completed_at = datetime.now(timezone.utc).isoformat() if completed else None
    get_supabase().table(TASKS_TABLE).update({
        "completed": completed,
        "completed_at": completed_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def set_priority(task_id: str, priority: str) -> None:
    if priority not in PRIORITIES:
        raise ValueError("Prioridad no valida")
    get_supabase().table(TASKS_TABLE).update({
        "priority": priority,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", task_id).execute()


def delete_task(task_id: str) -> None:
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
    chosen_assignees = list(assignees or [])
    if chosen_assignees:
        query = query.in_("assignee", chosen_assignees)
    rows = query.execute().data or []
    return sorted(
        rows,
        key=lambda task: (PRIORITY_RANK.get(task["priority"], 99), task["due_date"]),
    )


def build_pdf(tasks: list[dict], start: date, end: date, status: str,
              assignees: Iterable[str] | None = None) -> bytes:
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
        data = [["Tarea", "Asignada a", "Prioridad", "Fecha", "Estado", "Descripcion"]]
        for task in tasks:
            data.append([
                Paragraph(html.escape(task["title"]), cell_style),
                Paragraph(html.escape(task["assignee"]), center_style),
                Paragraph(task["priority"], center_style),
                Paragraph(datetime.fromisoformat(task["due_date"]).strftime("%d/%m/%Y"), center_style),
                Paragraph("Completada" if task["completed"] else "Pendiente", center_style),
                Paragraph(html.escape(task["description"] or "—"), cell_style),
            ])
        table = Table(data, repeatRows=1, colWidths=[1.7*inch, 0.85*inch, 0.72*inch, 0.75*inch, 0.82*inch, 3.15*inch])
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

