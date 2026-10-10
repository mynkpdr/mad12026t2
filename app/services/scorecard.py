from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def make_pdf(booking):
    """Return the PDF bytes of one student's scorecard."""
    exam, styles = booking.exam, getSampleStyleSheet()
    scores = {s.rubric_id: s.score for s in booking.scores}
    rows = [["Criterion", "Marks", "Out of", "Weightage"]]
    rows += [[r.name, scores[r.id], r.max_marks, r.weightage] for r in exam.rubrics]
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]))
    story = [
        Paragraph("Examination Scorecard", styles["Title"]),
        Paragraph(f"Student: {booking.student.name} ({booking.student.email})", styles["Normal"]),
        Paragraph(f"Exam: {exam.name} ({exam.course.code}, {exam.exam_type})", styles["Normal"]),
        Paragraph(f"Date: {booking.slot.date:%d %b %Y}", styles["Normal"]),
        Spacer(1, 16), table, Spacer(1, 16),
        Paragraph(f"<b>Total: {booking.marks} / {exam.max_marks}</b>", styles["Heading3"]),
        Paragraph(f"Examiner remarks: {booking.remarks or '-'}", styles["Normal"]),
    ]
    buffer = BytesIO()
    SimpleDocTemplate(buffer, pagesize=A4).build(story)
    return buffer.getvalue()
