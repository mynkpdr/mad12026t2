from datetime import date, datetime

from ..extensions import db
from ..models import Slot
from . import RuleError


def _minutes(start, end):
    return (datetime.combine(date.min, end) - datetime.combine(date.min, start)).seconds // 60


def _check_overlap(examiner_id, day, start, end, ignore_id=None):
    clash = Slot.query.filter(
        Slot.examiner_id == examiner_id, Slot.date == day, Slot.cancelled.is_(False),
        Slot.start_time < end, Slot.end_time > start, Slot.id != ignore_id,
    ).first()
    if clash:
        raise RuleError("This examiner already has a slot that overlaps this time.")


def _check_slot(exam, examiner_id, day, start, end, capacity, booked=0, ignore_id=None):
    if day < date.today():
        raise RuleError("A slot cannot be in the past.")
    if end <= start:
        raise RuleError("End time must be after start time.")
    if _minutes(start, end) < exam.duration_minutes:
        raise RuleError(f"A slot must be at least {exam.duration_minutes} minutes (the exam duration).")
    if capacity < max(1, booked):
        raise RuleError("Capacity must be at least 1 and not below the seats already booked.")
    _check_overlap(examiner_id, day, start, end, ignore_id)


def create_slot(exam, examiner, day, start, end, capacity):
    if not exam.slots_open:
        raise RuleError("Slot creation is not open for this exam.")
    if examiner not in exam.examiners:
        raise RuleError("You are not assigned to this exam.")
    _check_slot(exam, examiner.id, day, start, end, capacity)
    slot = Slot(exam=exam, examiner=examiner, date=day, start_time=start, end_time=end, capacity=capacity)
    db.session.add(slot)
    db.session.commit()
    return slot


def _require_editable(slot):
    if not slot.editable:
        raise RuleError("A slot can only be changed before booking starts.")


def update_slot(slot, day, start, end, capacity):
    _require_editable(slot)
    _check_slot(slot.exam, slot.examiner_id, day, start, end, capacity, slot.booked, slot.id)
    slot.date, slot.start_time, slot.end_time, slot.capacity = day, start, end, capacity
    db.session.commit()


def remove_slot(slot):
    _require_editable(slot)
    slot.cancelled = True  # kept in the database so history is not lost
    db.session.commit()


def change_examiner(slot, examiner):
    """Admin: hand a slot to another approved examiner."""
    if slot.cancelled:
        raise RuleError("This slot is cancelled.")
    if examiner.id == slot.examiner_id:
        raise RuleError("This examiner already runs the slot.")
    if examiner.role != "examiner" or not (examiner.approved and examiner.active):
        raise RuleError("Choose an approved, active examiner.")
    _check_overlap(examiner.id, slot.date, slot.start_time, slot.end_time, slot.id)
    if examiner not in slot.exam.examiners:
        slot.exam.examiners.append(examiner)
    slot.examiner = examiner
    db.session.commit()
