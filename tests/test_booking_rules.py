from datetime import date, time, timedelta

import pytest

from app.extensions import db
from app.services import RuleError, booking, evaluation, slots
from tests.conftest import add_user


def test_slot_closes_when_full_and_blocks_overbooking(world):
    s1, s2 = world["students"]
    booking.book(s1, world["slot"])
    assert world["slot"].status == "Full"
    with pytest.raises(RuleError, match="full"):
        booking.book(s2, world["slot"])


def test_duplicate_booking_for_same_exam_is_blocked(world):
    s1 = world["students"][0]
    other = slots.create_slot(world["exam"], world["examiner"], date.today() + timedelta(days=2), time(10), time(11), 5)
    booking.book(s1, world["slot"])
    with pytest.raises(RuleError, match="already"):
        booking.book(s1, other)


def test_cancel_frees_seat_and_allows_rebooking(world):
    s1 = world["students"][0]
    b = booking.book(s1, world["slot"])
    booking.cancel(b)
    assert world["slot"].available_seats == 1
    booking.book(s1, world["slot"])
    assert world["slot"].booked == 1


def test_booking_outside_window_is_blocked(world):
    world["exam"].booking_override = "closed"
    db.session.commit()
    with pytest.raises(RuleError, match="not open"):
        booking.book(world["students"][0], world["slot"])


def test_slots_only_during_creation_period_and_no_overlap(world):
    exam, examiner = world["exam"], world["examiner"]
    with pytest.raises(RuleError, match="overlaps"):
        slots.create_slot(exam, examiner, world["slot"].date, time(10, 15), time(11, 15), 1)
    exam.slots_override = "closed"
    with pytest.raises(RuleError, match="not open"):
        slots.create_slot(exam, examiner, world["slot"].date, time(14), time(15), 1)


def test_slot_cannot_be_edited_once_booking_started(world):
    booking.book(world["students"][0], world["slot"])
    with pytest.raises(RuleError, match="before booking"):
        slots.update_slot(world["slot"], date.today(), time(10), time(11), 2)


def test_only_slot_owner_can_evaluate_and_marks_are_weighted(world):
    b = booking.book(world["students"][0], world["slot"])
    stranger = add_user("other", "examiner")
    rubrics = world["exam"].rubrics
    scores = {rubrics[0].id: 10, rubrics[1].id: 5}
    with pytest.raises(RuleError, match="own slots"):
        evaluation.evaluate(b, stranger, scores, "")
    evaluation.evaluate(b, world["examiner"], scores, "ok")
    assert b.marks == 80  # (10/10*60 + 5/10*40) / 100 * 100
    assert b.status == "completed"


def test_reschedule_moves_seat(world):
    b = booking.book(world["students"][0], world["slot"])
    other = slots.create_slot(world["exam"], world["examiner"], date.today() + timedelta(days=2), time(10), time(11), 2)
    booking.reschedule(b, other)
    assert world["slot"].available_seats == 1 and other.available_seats == 1


def test_slot_is_locked_once_exam_is_completed(world):
    world["exam"].booking_override = "closed"
    world["exam"].completed = True
    db.session.commit()
    assert not world["slot"].editable
    assert world["slot"].status == "Completed"


def test_dashboard_counts_are_real_numbers(world):
    from app.services import stats

    for student in world["students"]:
        other = slots.create_slot(world["exam"], world["examiner"], date.today() + timedelta(days=3 + student.id), time(10), time(11), 1)
        booking.book(student, other)
    completion = stats.charts()["completion"]
    assert completion["pending"] == [2] and completion["evaluated"] == [0]
    assert stats.totals()["Bookings"] == 2


def test_no_slots_or_bookings_in_the_past(world):
    with pytest.raises(RuleError, match="past"):
        slots.create_slot(world["exam"], world["examiner"], date.today() - timedelta(days=1), time(14), time(15), 1)
    world["slot"].date = date.today() - timedelta(days=1)
    db.session.commit()
    with pytest.raises(RuleError, match="already taken place"):
        booking.book(world["students"][0], world["slot"])
