"""Small JSON API. It uses the same login session and the same services as the website."""
from flask import Blueprint, abort, jsonify, request
from flask_login import current_user

from ..extensions import db
from ..models import Booking, Exam, Slot
from ..services import booking as booking_service
from ..services import search

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.before_request
def need_login():
    if not current_user.is_authenticated:
        return jsonify(error="Login required"), 401


def admin_only():
    if current_user.role != "admin":
        abort(403)


def exam_json(e):
    return {"id": e.id, "name": e.name, "course": e.course.code, "type": e.exam_type, "status": e.status,
            "duration_minutes": e.duration_minutes, "max_marks": e.max_marks}


def slot_json(s):
    return {"id": s.id, "exam_id": s.exam_id, "examiner": s.examiner.name, "date": s.date.isoformat(),
            "start": s.start_time.strftime("%H:%M"), "end": s.end_time.strftime("%H:%M"),
            "available_seats": s.available_seats, "status": s.status}


def booking_json(b):
    return {"id": b.id, "student": b.student.name, "exam": b.exam.name, "slot_id": b.slot_id, "status": b.status,
            "marks": b.marks if b.result_visible or current_user.role != "student" else None}


def user_json(u):
    return {"id": u.id, "name": u.name, "email": u.email, "department": u.department, "active": u.active, "approved": u.approved}


@bp.route("/exams")
def exams():
    return jsonify([exam_json(e) for e in search.exams(request.args.get("q", "")).all()])


@bp.route("/exams/<int:id>")
def exam(id):
    return jsonify(exam_json(db.get_or_404(Exam, id)))


@bp.route("/exams/<int:id>/slots")
def exam_slots(id):
    return jsonify([slot_json(s) for s in db.get_or_404(Exam, id).slots if not s.cancelled])


@bp.route("/examiners")
def examiners():
    admin_only()
    return jsonify([user_json(u) for u in search.users("examiner", request.args.get("q", "")).all()])


@bp.route("/students")
def students():
    admin_only()
    return jsonify([user_json(u) for u in search.users("student", request.args.get("q", "")).all()])


@bp.route("/bookings")
def bookings():
    if current_user.role == "admin":
        found = Booking.query.all()
    elif current_user.role == "student":
        found = Booking.query.filter_by(student_id=current_user.id).all()
    else:
        found = Booking.query.join(Slot).filter(Slot.examiner_id == current_user.id).all()
    return jsonify([booking_json(b) for b in found])


@bp.route("/bookings", methods=["POST"])
def create_booking():
    if current_user.role != "student":
        abort(403)
    slot = db.get_or_404(Slot, request.get_json()["slot_id"])
    return jsonify(booking_json(booking_service.book(current_user, slot))), 201


@bp.route("/bookings/<int:id>", methods=["DELETE"])
def cancel_booking(id):
    booking = db.get_or_404(Booking, id)
    if booking.student_id != current_user.id:
        abort(403)
    booking_service.cancel(booking)
    return jsonify(booking_json(booking))
