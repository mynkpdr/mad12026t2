from datetime import datetime

from ..extensions import db
from ..models import Score
from . import RuleError


def total_marks(exam, scores):
    """Each criterion: score/max, weighted by its weightage, scaled to the exam's maximum marks."""
    weight_sum = sum(r.weightage for r in exam.rubrics)
    got = sum(scores[r.id] / r.max_marks * r.weightage for r in exam.rubrics)
    return round(got / weight_sum * exam.max_marks, 2)


def evaluate(booking, examiner, scores, remarks):
    """scores: {rubric_id: number}. Only the examiner who owns the slot may evaluate."""
    exam = booking.exam
    if booking.slot.examiner_id != examiner.id:
        raise RuleError("You can only evaluate students booked in your own slots.")
    if booking.status == "cancelled":
        raise RuleError("This booking was cancelled.")
    if exam.results_published:
        raise RuleError("Results are already published, so marks can no longer change.")
    if not exam.rubrics:
        raise RuleError("The admin has not added rubric criteria for this exam yet.")
    for r in exam.rubrics:
        if not 0 <= scores[r.id] <= r.max_marks:
            raise RuleError(f"'{r.name}' must be between 0 and {r.max_marks}.")
    Score.query.filter_by(booking_id=booking.id).delete()
    for r in exam.rubrics:
        db.session.add(Score(booking=booking, rubric=r, score=scores[r.id]))
    booking.marks = total_marks(exam, scores)
    booking.remarks = remarks
    booking.status = "completed"
    booking.evaluated_at = datetime.now()
    db.session.commit()
