from datetime import date, datetime

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Booking, Slot
from . import RuleError


def _take_seat(slot):
    """Add one student to the slot in a single atomic UPDATE, so two students can never overbook."""
    if slot.date < date.today():
        raise RuleError("This slot has already taken place.")
    taken = db.session.execute(
        db.update(Slot)
        .where(Slot.id == slot.id, Slot.booked < Slot.capacity, Slot.cancelled.is_(False))
        .values(booked=Slot.booked + 1)
    ).rowcount
    if not taken:
        raise RuleError("This slot is full or cancelled.")


def _release_seat(slot):
    db.session.execute(db.update(Slot).where(Slot.id == slot.id).values(booked=Slot.booked - 1))


def book(student, slot):
    if not slot.exam.booking_open:
        raise RuleError("Booking is not open for this exam.")
    _take_seat(slot)
    booking = Booking(student=student, slot=slot, exam=slot.exam)
    db.session.add(booking)
    try:
        db.session.commit()
    except IntegrityError:  # the unique index caught a duplicate booking
        db.session.rollback()
        raise RuleError("You already have a booking for this exam.") from None
    return booking


def cancel(booking):
    if booking.status != "booked":
        raise RuleError("Only an active booking can be cancelled.")
    if not booking.exam.booking_open:
        raise RuleError("The booking deadline has passed, so this booking can no longer be cancelled.")
    booking.status = "cancelled"
    booking.cancelled_at = datetime.now()
    _release_seat(booking.slot)
    db.session.commit()


def reschedule(booking, new_slot):
    """Admin: move a booking to another slot of the same exam."""
    if booking.status != "booked":
        raise RuleError("Only an active booking can be rescheduled.")
    if new_slot.exam_id != booking.exam_id:
        raise RuleError("Choose a slot of the same exam.")
    if new_slot.id == booking.slot_id:
        raise RuleError("The booking is already in this slot.")
    _take_seat(new_slot)
    _release_seat(booking.slot)
    booking.note += f"Moved from slot #{booking.slot_id} to #{new_slot.id} by admin on {datetime.now():%d %b %Y}. "
    booking.slot = new_slot
    db.session.commit()
