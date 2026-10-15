from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from ..extensions import db
from ..models import Booking, Exam, Slot
from ..services import RuleError, evaluation
from ..services import slots as slot_service
from ..utils import form_int, parse_date, parse_time, restrict_to

bp = Blueprint("examiner", __name__, url_prefix="/examiner")
restrict_to(bp, "examiner")


def my_slot(id):
    slot = db.get_or_404(Slot, id)
    if slot.examiner_id != current_user.id:
        abort(403)
    return slot


def my_bookings(*statuses):
    return (Booking.query.join(Slot).filter(Slot.examiner_id == current_user.id, Booking.status.in_(statuses))
            .order_by(Slot.date, Slot.start_time).all())


@bp.route("/")
def dashboard():
    slots = Slot.query.filter_by(examiner_id=current_user.id, cancelled=False).all()
    return render_template("examiner/dashboard.html", exams=current_user.assigned_exams, slots=slots,
                           booked=sum(s.booked for s in slots), pending=my_bookings("booked"))


@bp.route("/exams")
def exams():
    return render_template("examiner/exams.html", exams=current_user.assigned_exams)


@bp.route("/slots")
def slots():
    mine = Slot.query.filter_by(examiner_id=current_user.id).order_by(Slot.date, Slot.start_time).all()
    return render_template("examiner/slots.html", slots=mine)


@bp.route("/exams/<int:exam_id>/slots/new", methods=["GET", "POST"])
@bp.route("/slots/<int:slot_id>/edit", methods=["GET", "POST"])
def slot_form(exam_id=None, slot_id=None):
    slot = my_slot(slot_id) if slot_id else None
    exam = slot.exam if slot else db.get_or_404(Exam, exam_id)
    if request.method == "POST":
        form = request.form
        values = (parse_date(form["date"]), parse_time(form["start_time"]), parse_time(form["end_time"]), form_int(form, "capacity"))
        if slot:
            slot_service.update_slot(slot, *values)
        else:
            slot_service.create_slot(exam, current_user, *values)
        flash("Slot saved.", "success")
        return redirect(url_for("examiner.slots"))
    return render_template("examiner/slot_form.html", exam=exam, slot=slot)


@bp.route("/slots/<int:id>/delete", methods=["POST"])
def slot_delete(id):
    slot_service.remove_slot(my_slot(id))
    flash("Slot removed.", "success")
    return redirect(url_for("examiner.slots"))


@bp.route("/slots/<int:id>")
def slot_students(id):
    return render_template("examiner/slot_students.html", slot=my_slot(id))


@bp.route("/bookings/<int:id>/evaluate", methods=["GET", "POST"])
def evaluate(id):
    booking = db.get_or_404(Booking, id)
    if booking.slot.examiner_id != current_user.id:
        abort(403)
    if request.method == "POST":
        try:
            scores = {r.id: float(request.form[f"score_{r.id}"]) for r in booking.exam.rubrics}
        except ValueError:
            raise RuleError("Marks must be numbers.") from None
        evaluation.evaluate(booking, current_user, scores, request.form["remarks"].strip())
        flash("Marks saved.", "success")
        return redirect(url_for("examiner.slot_students", id=booking.slot_id))
    return render_template("examiner/evaluate.html", booking=booking, scores={s.rubric_id: s.score for s in booking.scores})
