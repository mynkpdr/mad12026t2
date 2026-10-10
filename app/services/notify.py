from flask import current_app
from flask_mail import Message

from ..extensions import mail
from ..models import Booking


def send(to, subject, body):
    """Email is a side effect after the data is saved, so a mail failure is logged, not fatal."""
    current_app.logger.info("Email to %s: %s", to, subject)
    try:
        mail.send(Message(subject, recipients=[to], body=body))
    except OSError:
        current_app.logger.exception("Could not send email to %s", to)


def booking_confirmed(booking):
    slot = booking.slot
    send(
        booking.student.email,
        f"Booking confirmed: {booking.exam.name}",
        f"Hi {booking.student.name},\n\nYour slot for {booking.exam.name} is booked on "
        f"{slot.date:%d %b %Y}, {slot.start_time:%H:%M}-{slot.end_time:%H:%M}.\n",
    )


def results_published(exam):
    for booking in Booking.query.filter_by(exam_id=exam.id, status="completed"):
        send(
            booking.student.email,
            f"Result published: {exam.name}",
            f"Hi {booking.student.name},\n\nYour result for {exam.name} is out: "
            f"{booking.marks}/{exam.max_marks}. Log in to see the feedback.\n",
        )
