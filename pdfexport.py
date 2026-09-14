import sqlite3
import sys
import calendar as cal_module
from datetime import datetime
from collections import defaultdict

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.pdfbase.pdfmetrics import stringWidth

import blackout

DB_PATH = "tpct.db"


# ------------------------------------------------------------
# DATA LOADING
# ------------------------------------------------------------

def get_request_details(conn, request_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.request_id, c.name, r.start_date, r.end_date,
               r.daily_start_time, r.daily_end_time, r.allowed_days_of_week, r.created_at
        FROM training_plan_requests r
        JOIN competencies c ON r.competency_id = c.competency_id
        WHERE r.request_id = ?
        """,
        (request_id,)
    )
    return cur.fetchone()


def get_segments(conn, request_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ps.segment_date, ps.start_time, ps.end_time,
               t.name, ps.hours_this_segment, i.name
        FROM plan_segments ps
        JOIN tasks t ON ps.task_id = t.task_id
        JOIN instructors i ON ps.assigned_instructor_id = i.instructor_id
        WHERE ps.request_id = ?
        ORDER BY ps.segment_date, ps.start_time
        """,
        (request_id,)
    )
    return cur.fetchall()


def get_infeasibility_reasons(conn, request_id):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT reason_type, detail
        FROM infeasibility_reasons
        WHERE request_id = ?
        ORDER BY reason_id
        """,
        (request_id,)
    )
    return cur.fetchall()


def get_batch_segments(conn, batch_id):
    """
    Every segment across every competency component in a concurrent
    batch, tagged with which competency each one belongs to. Returns
    list of (segment_date, start_time, end_time, task_name, hours,
    instructor_name, competency_name, request_id).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ps.segment_date, ps.start_time, ps.end_time, t.name, ps.hours_this_segment,
               i.name, c.name, ps.request_id
        FROM plan_segments ps
        JOIN tasks t ON ps.task_id = t.task_id
        JOIN instructors i ON ps.assigned_instructor_id = i.instructor_id
        JOIN training_plan_requests r ON ps.request_id = r.request_id
        JOIN competencies c ON r.competency_id = c.competency_id
        WHERE r.batch_id = ?
        ORDER BY ps.segment_date, ps.start_time
        """,
        (batch_id,)
    )
    return cur.fetchall()


def get_batch_components(conn, batch_id):
    """
    Every component (request) in a batch, feasible or not. Returns
    list of (request_id, competency_name, start_date, end_date, feasible).
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT r.request_id, c.name, r.start_date, r.end_date
        FROM training_plan_requests r
        JOIN competencies c ON r.competency_id = c.competency_id
        WHERE r.batch_id = ?
        ORDER BY r.request_id
        """,
        (batch_id,)
    )
    components = []
    for request_id, competency_name, start_date, end_date in cur.fetchall():
        cur.execute("SELECT 1 FROM plan_segments WHERE request_id = ? LIMIT 1", (request_id,))
        feasible = cur.fetchone() is not None
        components.append((request_id, competency_name, start_date, end_date, feasible))
    return components


BATCH_COMPETENCY_PALETTE = ["#1a3a5c", "#8c1c1c", "#2e7d32", "#6a1b9a", "#e65100", "#00838f"]


def _assign_competency_colors(competency_names):
    """Consistent color per competency name, cycling through a fixed palette."""
    color_map = {}
    for name in competency_names:
        if name not in color_map:
            color_map[name] = BATCH_COMPETENCY_PALETTE[len(color_map) % len(BATCH_COMPETENCY_PALETTE)]
    return color_map


DAY_NAMES = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


def format_date_display(iso_date_str):
    d = datetime.strptime(iso_date_str, "%Y-%m-%d").date()
    return f"{DAY_NAMES[d.weekday()]}, {d.strftime('%d %b %Y')}"


def format_days_of_week(days_str):
    day_ints = [int(x) for x in days_str.split(",")]
    return ", ".join(DAY_NAMES[d] for d in sorted(day_ints))


# ------------------------------------------------------------
# STYLES
# ------------------------------------------------------------

def get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TPCTTitle", parent=styles["Title"], fontSize=18, spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        name="TPCTSubtitle", parent=styles["Normal"], fontSize=10,
        textColor=colors.grey, spaceAfter=14
    ))
    styles.add(ParagraphStyle(
        name="TPCTDateHeader", parent=styles["Heading2"], fontSize=12,
        spaceBefore=14, spaceAfter=4, textColor=colors.HexColor("#1a3a5c")
    ))
    styles.add(ParagraphStyle(
        name="TPCTTableCell", parent=styles["Normal"], fontSize=9, leading=11
    ))
    return styles


def _cell(text, styles):
    """
    Wraps table cell text in a Paragraph so ReportLab actually wraps
    it within the column width — a plain string in a Table cell does
    NOT wrap and will silently overflow into the next column instead.
    """
    return Paragraph(str(text), styles["TPCTTableCell"])


# ------------------------------------------------------------
# FEASIBLE PLAN -> CALENDAR PDF
# ------------------------------------------------------------

def build_plan_pdf(conn, request_id, output_path):
    details = get_request_details(conn, request_id)
    if not details:
        raise ValueError(f"No request found with request_id={request_id}")

    (req_id, competency_name, start_date, end_date,
     daily_start_time, daily_end_time, allowed_days_str, created_at) = details

    segments = get_segments(conn, request_id)
    if not segments:
        raise ValueError(
            f"request_id={request_id} has no segments — it may be infeasible. "
            f"Use build_infeasibility_pdf() instead."
        )

    styles = get_styles()
    story = []

    # --- Header ---
    story.append(Paragraph(competency_name, styles["TPCTTitle"]))
    story.append(Paragraph(
        f"Training Plan &nbsp;|&nbsp; {start_date} to {end_date} &nbsp;|&nbsp; "
        f"Daily hours: {daily_start_time}-{daily_end_time} &nbsp;|&nbsp; "
        f"Training days: {format_days_of_week(allowed_days_str)}",
        styles["TPCTSubtitle"]
    ))

    total_hours = sum(seg[4] for seg in segments)
    story.append(Paragraph(
        f"Total instructional hours: {total_hours:g}",
        styles["TPCTSubtitle"]
    ))

    # --- Group segments by date ---
    segments_by_date = {}
    for segment_date, start_time, end_time, task_name, hours, instructor_name in segments:
        segments_by_date.setdefault(segment_date, []).append(
            (start_time, end_time, task_name, hours, instructor_name)
        )

    for segment_date in sorted(segments_by_date.keys()):
        story.append(Paragraph(format_date_display(segment_date), styles["TPCTDateHeader"]))

        table_data = [["Time", "Task", "Instructor", "Hours"]]
        for start_time, end_time, task_name, hours, instructor_name in segments_by_date[segment_date]:
            table_data.append([
                f"{start_time}-{end_time}",
                _cell(task_name, styles),
                _cell(instructor_name, styles),
                f"{hours:g}"
            ])

        table = Table(table_data, colWidths=[1.1 * inch, 3.3 * inch, 1.6 * inch, 0.6 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch
    )
    doc.build(story)


# ------------------------------------------------------------
# FEASIBLE PLAN -> MONTH-GRID (WALL CALENDAR) PDF
# ------------------------------------------------------------

WEEKDAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _month_grid_cell_style():
    styles = getSampleStyleSheet()
    return ParagraphStyle(
        name="MonthCell", parent=styles["Normal"], fontSize=6.5, leading=8,
    )


def _truncate(text, max_len):
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


MONTH_CELL_FONT = "Helvetica"
MONTH_CELL_FONT_SIZE = 6.5


def _build_session_line(start_time, task_name, instructor_name, available_width_pt):
    """
    Builds one "HH:MM Task Name (Instructor)" line, truncating ONLY the
    task name (with an ellipsis) as much as needed so the full line
    fits within available_width_pt on a single rendered line — rather
    than letting reportlab wrap it onto a second line.

    Uses actual font-metric width calculations (not a character-count
    guess), so it adapts correctly to different font sizes/columns.
    """
    prefix = f"{start_time} "
    suffix = f" ({instructor_name})"

    def line_width(task_text):
        return stringWidth(prefix + task_text + suffix, MONTH_CELL_FONT, MONTH_CELL_FONT_SIZE)

    if line_width(task_name) <= available_width_pt:
        return prefix + task_name + suffix

    # Trim the task name one character at a time (from the end) until
    # "task…" fits, replacing the trimmed tail with an ellipsis.
    trimmed = task_name
    while trimmed and line_width(trimmed + "…") > available_width_pt:
        trimmed = trimmed[:-1]

    if not trimmed:
        # Even the ellipsis alone doesn't fit — extremely narrow column.
        # Fall back to just the ellipsis rather than crashing.
        return prefix + "…" + suffix

    return prefix + trimmed + "…" + suffix


def build_month_grid_pdf(conn, request_id, output_path):
    """
    Generates a traditional month-view wall calendar (one page per
    calendar month the plan touches), with each day's sessions listed
    compactly inside its grid box. Complements the agenda-style PDF
    from build_plan_pdf() — this one is for a printable/at-a-glance
    view, the agenda one is for a detailed read-through.
    """
    details = get_request_details(conn, request_id)
    if not details:
        raise ValueError(f"No request found with request_id={request_id}")

    (req_id, competency_name, start_date, end_date,
     daily_start_time, daily_end_time, allowed_days_str, created_at) = details

    segments = get_segments(conn, request_id)
    if not segments:
        raise ValueError(
            f"request_id={request_id} has no segments — it may be infeasible. "
            f"A month-grid view only applies to a feasible, scheduled plan."
        )

    # Blackout dates within the plan's window, so empty grid cells caused
    # by a holiday are labeled instead of showing up as a blank, unexplained day.
    blackout_labels_by_date = {
        d: label for d, label, source in blackout.list_blackout_dates(conn, start_date, end_date)
    }

    # Group segments by date
    segments_by_date = defaultdict(list)
    for segment_date, start_time, end_time, task_name, hours, instructor_name in segments:
        segments_by_date[segment_date].append((start_time, task_name, instructor_name))

    for date_key in segments_by_date:
        segments_by_date[date_key].sort(key=lambda s: s[0])

    # Figure out which (year, month) pairs this plan touches
    all_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in segments_by_date.keys()]
    months_touched = sorted(set((d.year, d.month) for d in all_dates))

    cell_style = _month_grid_cell_style()
    styles = get_styles()
    story = []

    for i, (year, month) in enumerate(months_touched):
        if i > 0:
            story.append(PageBreak())

        month_name = cal_module.month_name[month]
        story.append(Paragraph(f"{competency_name}", styles["TPCTTitle"]))
        story.append(Paragraph(f"{month_name} {year}", styles["TPCTSubtitle"]))

        cal = cal_module.Calendar(firstweekday=0)  # Monday start
        weeks = cal.monthdayscalendar(year, month)  # list of weeks, each a list of 7 ints (0 = not in month)

        col_width = 10.0 * inch / 7
        cell_padding = 4 + 4  # LEFTPADDING + RIGHTPADDING, set below in the table style
        available_text_width = col_width - cell_padding

        table_data = [WEEKDAY_HEADERS]
        blackout_cell_positions = []  # (week_idx, day_idx) needing grey shading

        for week_idx, week in enumerate(weeks, start=1):  # +1 because row 0 is the header
            row = []
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    row.append("")
                    continue

                date_key = f"{year:04d}-{month:02d}-{day_num:02d}"
                day_segments = segments_by_date.get(date_key, [])
                holiday_label = blackout_labels_by_date.get(date_key)

                lines = [f"<b>{day_num}</b>"]
                if holiday_label:
                    lines.append(f"<i>{holiday_label}</i>")
                    blackout_cell_positions.append((day_idx, week_idx))
                for start_time, task_name, instructor_name in day_segments:
                    line = _build_session_line(
                        start_time, task_name, instructor_name, available_text_width
                    )
                    lines.append(line)

                cell_html = "<br/>".join(lines)
                row.append(Paragraph(cell_html, cell_style))
            table_data.append(row)

        table = Table(table_data, colWidths=[col_width] * 7)

        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]

        # Shade any blank (out-of-month) cells grey
        for week_idx, week in enumerate(weeks, start=1):  # +1 because row 0 is the header
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    style_commands.append(
                        ("BACKGROUND", (day_idx, week_idx), (day_idx, week_idx), colors.HexColor("#f5f5f5"))
                    )

        # Shade blackout dates (federal holidays, etc.) a distinct light
        # red so they read as "excluded for a reason," not just empty
        for day_idx, week_idx in blackout_cell_positions:
            style_commands.append(
                ("BACKGROUND", (day_idx, week_idx), (day_idx, week_idx), colors.HexColor("#fbe4e4"))
            )

        table.setStyle(TableStyle(style_commands))
        story.append(table)

    doc = SimpleDocTemplate(
        output_path, pagesize=landscape(letter),
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch
    )
    doc.build(story)




def build_batch_plan_pdf(conn, batch_id, output_path):
    """
    Combined agenda-style PDF across every competency in a concurrent
    batch — day-by-day, but each session tagged with which competency
    it belongs to (since instructor/task alone won't tell you that
    once multiple competencies are running together). Any component
    that came back infeasible is still listed, with its reasons, so
    a partial batch is never silently incomplete.
    """
    components = get_batch_components(conn, batch_id)
    if not components:
        raise ValueError(f"No components found for batch_id={batch_id}")

    segments = get_batch_segments(conn, batch_id)
    styles = get_styles()
    story = []

    feasible_names = sorted(set(c[1] for c in components if c[4]))
    story.append(Paragraph("Concurrent Training Plan", styles["TPCTTitle"]))
    story.append(Paragraph(
        " &nbsp;|&nbsp; ".join(feasible_names) if feasible_names else "No feasible components",
        styles["TPCTSubtitle"]
    ))

    if segments:
        total_hours = sum(seg[4] for seg in segments)
        story.append(Paragraph(f"Total instructional hours (all competencies): {total_hours:g}", styles["TPCTSubtitle"]))

        segments_by_date = defaultdict(list)
        for segment_date, start_time, end_time, task_name, hours, instructor_name, competency_name, request_id in segments:
            segments_by_date[segment_date].append(
                (start_time, end_time, task_name, hours, instructor_name, competency_name)
            )

        for segment_date in sorted(segments_by_date.keys()):
            story.append(Paragraph(format_date_display(segment_date), styles["TPCTDateHeader"]))

            table_data = [["Time", "Competency", "Task", "Instructor", "Hours"]]
            for start_time, end_time, task_name, hours, instructor_name, competency_name in segments_by_date[segment_date]:
                table_data.append([
                    f"{start_time}-{end_time}",
                    _cell(competency_name, styles),
                    _cell(task_name, styles),
                    _cell(instructor_name, styles),
                    f"{hours:g}"
                ])

            table = Table(table_data, colWidths=[1.0 * inch, 1.7 * inch, 2.3 * inch, 1.3 * inch, 0.5 * inch])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(table)

    infeasible_components = [c for c in components if not c[4]]
    if infeasible_components:
        story.append(Spacer(1, 14))
        story.append(Paragraph("Components That Could Not Be Scheduled", styles["TPCTDateHeader"]))
        for request_id, competency_name, start_date, end_date, feasible in infeasible_components:
            story.append(Paragraph(f"<b>{competency_name}</b> ({start_date} to {end_date})", styles["Normal"]))
            for reason_type, detail in get_infeasibility_reasons(conn, request_id):
                story.append(Paragraph(f"&nbsp;&nbsp;— [{reason_type.replace('_', ' ').title()}] {detail}", styles["Normal"]))
            story.append(Spacer(1, 6))

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch
    )
    doc.build(story)


def build_batch_month_grid_pdf(conn, batch_id, output_path):
    """
    Combined month-view wall calendar across every competency in a
    concurrent batch. Each competency gets its own color (shown in a
    legend), and every session's text is tinted with its competency's
    color so a day with multiple competencies running is still
    readable at a glance — same one-line-per-session guarantee as the
    single-plan version, just with color layered on top.
    """
    components = get_batch_components(conn, batch_id)
    if not components:
        raise ValueError(f"No components found for batch_id={batch_id}")

    segments = get_batch_segments(conn, batch_id)
    if not segments:
        raise ValueError(
            f"batch_id={batch_id} has no scheduled segments — every component may be infeasible. "
            f"Use build_batch_plan_pdf() to see the infeasibility reasons."
        )

    feasible_components = [c for c in components if c[4]]
    overall_start = min(c[2] for c in feasible_components)
    overall_end = max(c[3] for c in feasible_components)
    blackout_labels_by_date = {
        d: label for d, label, source in blackout.list_blackout_dates(conn, overall_start, overall_end)
    }

    competency_names = [c[1] for c in feasible_components]
    color_map = _assign_competency_colors(competency_names)

    segments_by_date = defaultdict(list)
    for segment_date, start_time, end_time, task_name, hours, instructor_name, competency_name, request_id in segments:
        segments_by_date[segment_date].append((start_time, task_name, instructor_name, competency_name))
    for date_key in segments_by_date:
        segments_by_date[date_key].sort(key=lambda s: s[0])

    all_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in segments_by_date.keys()]
    months_touched = sorted(set((d.year, d.month) for d in all_dates))

    cell_style = _month_grid_cell_style()
    styles = get_styles()
    story = []

    story.append(Paragraph("Concurrent Training Plan", styles["TPCTTitle"]))
    legend_data = [[Paragraph(f'<font color="{color_map[name]}">\u25A0</font> {name}', styles["Normal"])]
                   for name in competency_names]
    legend_table = Table(legend_data, colWidths=[6.0 * inch])
    legend_table.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(legend_table)
    story.append(Spacer(1, 10))

    for i, (year, month) in enumerate(months_touched):
        if i > 0:
            story.append(PageBreak())

        month_name = cal_module.month_name[month]
        story.append(Paragraph(f"{month_name} {year}", styles["TPCTSubtitle"]))

        cal = cal_module.Calendar(firstweekday=0)
        weeks = cal.monthdayscalendar(year, month)

        col_width = 10.0 * inch / 7
        available_text_width = col_width - 8

        table_data = [WEEKDAY_HEADERS]
        blackout_cell_positions = []

        for week_idx, week in enumerate(weeks, start=1):
            row = []
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    row.append("")
                    continue

                date_key = f"{year:04d}-{month:02d}-{day_num:02d}"
                day_segments = segments_by_date.get(date_key, [])
                holiday_label = blackout_labels_by_date.get(date_key)

                lines = [f"<b>{day_num}</b>"]
                if holiday_label:
                    lines.append(f"<i>{holiday_label}</i>")
                    blackout_cell_positions.append((day_idx, week_idx))
                for start_time, task_name, instructor_name, competency_name in day_segments:
                    line = _build_session_line(start_time, task_name, instructor_name, available_text_width)
                    color = color_map.get(competency_name, "#000000")
                    lines.append(f'<font color="{color}">{line}</font>')

                cell_html = "<br/>".join(lines)
                row.append(Paragraph(cell_html, cell_style))
            table_data.append(row)

        table = Table(table_data, colWidths=[col_width] * 7)
        style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3a5c")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]

        for week_idx, week in enumerate(weeks, start=1):
            for day_idx, day_num in enumerate(week):
                if day_num == 0:
                    style_commands.append(
                        ("BACKGROUND", (day_idx, week_idx), (day_idx, week_idx), colors.HexColor("#f5f5f5"))
                    )
        for day_idx, week_idx in blackout_cell_positions:
            style_commands.append(
                ("BACKGROUND", (day_idx, week_idx), (day_idx, week_idx), colors.HexColor("#fbe4e4"))
            )

        table.setStyle(TableStyle(style_commands))
        story.append(table)

    infeasible_components = [c for c in components if not c[4]]
    if infeasible_components:
        story.append(PageBreak())
        story.append(Paragraph("Components That Could Not Be Scheduled", styles["TPCTDateHeader"]))
        for request_id, competency_name, start_date, end_date, feasible in infeasible_components:
            story.append(Paragraph(f"<b>{competency_name}</b> ({start_date} to {end_date})", styles["Normal"]))
            for reason_type, detail in get_infeasibility_reasons(conn, request_id):
                story.append(Paragraph(f"&nbsp;&nbsp;— [{reason_type.replace('_', ' ').title()}] {detail}", styles["Normal"]))
            story.append(Spacer(1, 6))

    doc = SimpleDocTemplate(
        output_path, pagesize=landscape(letter),
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch
    )
    doc.build(story)


def build_infeasibility_pdf(conn, request_id, output_path):
    details = get_request_details(conn, request_id)
    if not details:
        raise ValueError(f"No request found with request_id={request_id}")

    (req_id, competency_name, start_date, end_date,
     daily_start_time, daily_end_time, allowed_days_str, created_at) = details

    reasons = get_infeasibility_reasons(conn, request_id)
    if not reasons:
        raise ValueError(
            f"request_id={request_id} has no infeasibility reasons — it may be feasible. "
            f"Use build_plan_pdf() instead."
        )

    styles = get_styles()
    story = []

    story.append(Paragraph(f"{competency_name} — Plan Not Viable", styles["TPCTTitle"]))
    story.append(Paragraph(
        f"Requested window: {start_date} to {end_date} &nbsp;|&nbsp; "
        f"Daily hours: {daily_start_time}-{daily_end_time} &nbsp;|&nbsp; "
        f"Training days: {format_days_of_week(allowed_days_str)}",
        styles["TPCTSubtitle"]
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "The requested constraints cannot be satisfied for the following reason(s):",
        styles["Normal"]
    ))
    story.append(Spacer(1, 10))

    table_data = [["Type", "Detail"]]
    for reason_type, detail in reasons:
        table_data.append([reason_type.replace("_", " ").title(), _cell(detail, styles)])

    table = Table(table_data, colWidths=[1.3 * inch, 5.3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8c1c1c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch
    )
    doc.build(story)


# ------------------------------------------------------------
# UNIFIED ENTRY POINT
# ------------------------------------------------------------

def export_plan_to_pdf(conn, request_id, output_path):
    """
    Figures out whether the request was feasible or not, and builds
    the appropriate PDF (calendar vs. infeasibility report).
    """
    segments = get_segments(conn, request_id)
    if segments:
        build_plan_pdf(conn, request_id, output_path)
        return "plan"
    else:
        build_infeasibility_pdf(conn, request_id, output_path)
        return "infeasibility_report"


# ------------------------------------------------------------
# DEMO
# ------------------------------------------------------------

if __name__ == "__main__":
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    if len(sys.argv) > 1:
        request_id = int(sys.argv[1])
    else:
        import scheduler
        cur = conn.cursor()
        cur.execute("SELECT competency_id FROM competencies WHERE name = ?",
                    ("Security Team Watchstander - Initial",))
        row = cur.fetchone()
        if not row:
            print("No 'Security Team Watchstander - Initial' competency found. Run seed.py first.")
            exit(1)
        competency_id = row[0]

        cur.execute("SELECT instructor_id FROM instructors")
        all_instructor_ids = [r[0] for r in cur.fetchall()]

        result = scheduler.create_training_plan(
            conn,
            competency_id=competency_id,
            start_date="2026-09-01",
            end_date="2026-09-21",
            daily_start_time="08:00",
            daily_end_time="16:00",
            allowed_days_of_week=[0, 1, 2, 3, 4],
            available_instructor_ids=all_instructor_ids,
        )
        request_id = result["request_id"]
        print(f"Generated demo plan (request_id={request_id}, feasible={result['feasible']})")

    output_path = f"training_plan_{request_id}.pdf"
    kind = export_plan_to_pdf(conn, request_id, output_path)
    print(f"PDF generated: {output_path} (type: {kind})")

    conn.close()
