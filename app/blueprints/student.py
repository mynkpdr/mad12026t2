from datetime import date

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from ..extensions import db
from ..models import EXAM_TYPES, Booking, Course, Exam, Slot
from ..services import booking as booking_service
from ..services import notify, scorecard, search
from ..utils import restrict_to

bp = Blueprint("student", __name__, url_prefix="/student")
restrict_to(bp, "student")


def my_bookings():
    return Booking.query.filter_by(student_id=current_user.id).order_by(Booking.id.desc()).all()


def my_booking(id):
    booking = db.get_or_404(Booking, id)
    if booking.student_id != current_user.id:
        abort(403)
    return booking


@bp.route("/")
def dashboard():
    bookings = my_bookings()
    booked_exam_ids = {b.exam_id for b in bookings if b.status != "cancelled"}
    open_exams = [e for e in Exam.query.all() if e.booking_open and e.id not in booked_exam_ids]
    upcoming = sorted((b for b in bookings if b.status == "booked"), key=lambda b: (b.slot.date, b.slot.start_time))
    return render_template(
        "student/dashboard.html", open_exams=open_exams, upcoming=upcoming,
        open_slots=sum(s.available_seats for e in open_exams for s in e.slots if not s.cancelled),
        results=[b for b in bookings if b.result_visible], booked_count=len(upcoming),
    )


@bp.route("/exams")
def exams():
    q, exam_type = request.args.get("q", "").strip(), request.args.get("type", "")
    course_id = request.args.get("course", type=int)
    found = [e for e in search.exams(q, exam_type, course_id).all() if e.status != "Draft"]
    if request.args.get("open"):
        found = [e for e in found if e.booking_open]
    return render_template("student/exams.html", exams=found, q=q, course_id=course_id, types=EXAM_TYPES, courses=Course.query.all())


@bp.route("/exams/<int:id>")
def exam_detail(id):
    exam = db.get_or_404(Exam, id)
    mine = next((b for b in my_bookings() if b.exam_id == id and b.status != "cancelled"), None)
    slots = [s for s in sorted(exam.slots, key=lambda s: (s.date, s.start_time)) if not s.cancelled]
    return render_template("student/exam_detail.html", exam=exam, slots=slots, mine=mine)


@bp.route("/slots/<int:id>/book", methods=["POST"])
def book(id):
    notify.booking_confirmed(booking_service.book(current_user, db.get_or_404(Slot, id)))
    flash("Slot booked!", "success")
    return redirect(url_for("student.bookings"))


@bp.route("/bookings")
def bookings():
    return render_template("student/bookings.html", bookings=my_bookings(), today=date.today())


@bp.route("/bookings/<int:id>/cancel", methods=["POST"])
def cancel(id):
    booking_service.cancel(my_booking(id))
    flash("Booking cancelled.", "success")
    return redirect(url_for("student.bookings"))


@bp.route("/results")
def results():
    return render_template("student/results.html", bookings=[b for b in my_bookings() if b.result_visible])


@bp.route("/results/<int:id>/scorecard.pdf")
def scorecard_pdf(id):
    booking = my_booking(id)
    if not booking.result_visible:
        abort(403)
    return Response(scorecard.make_pdf(booking), mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=scorecard_{booking.exam.course.code}_{booking.id}.pdf"})
