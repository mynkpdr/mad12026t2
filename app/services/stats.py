from datetime import date

from sqlalchemy import case, func

from ..extensions import db
from ..models import Booking, Course, Exam, Slot, User


def totals():
    count = lambda model, *filters: model.query.filter(*filters).count()  # noqa: E731
    return {
        "Courses": count(Course),
        "Examinations": count(Exam),
        "Examiners": count(User, User.role == "examiner"),
        "Students": count(User, User.role == "student"),
        "Slots": count(Slot, Slot.cancelled.is_(False)),
        "Bookings": count(Booking, Booking.status != "cancelled"),
    }


def charts():
    """Plain lists for Chart.js: (labels, values) for each chart."""
    per_day = (
        db.session.query(func.date(Booking.created_at), func.count())
        .filter(Booking.status != "cancelled").group_by(func.date(Booking.created_at)).order_by(func.date(Booking.created_at)).all()
    )
    workload = (
        db.session.query(User.name, func.count(Booking.id))
        .join(Slot, Slot.examiner_id == User.id).join(Booking, Booking.slot_id == Slot.id)
        .filter(Booking.status != "cancelled").group_by(User.id).all()
    )
    completion = (
        db.session.query(
            Exam.name, Course.code,
            func.count(case((Booking.status == "completed", 1))),  # COUNT skips the NULLs that CASE gives otherwise
            func.count(case((Booking.status == "booked", 1))),
        )
        .join(Course).outerjoin(Booking, Booking.exam_id == Exam.id).group_by(Exam.id).order_by(Exam.booking_start).all()
    )
    return {
        "per_day": {"labels": [date.fromisoformat(d).strftime("%d %b") for d, _ in per_day], "values": [n for _, n in per_day]},
        "workload": {"labels": [n for n, _ in workload], "values": [c for _, c in workload]},
        "completion": {
            "labels": [c[1] for c in completion],
            "names": [c[0] for c in completion],
            "evaluated": [c[2] for c in completion],
            "pending": [c[3] for c in completion],
        },
    }
