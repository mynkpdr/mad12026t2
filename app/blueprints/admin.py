from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..extensions import db
from ..models import EXAM_TYPES, Booking, Course, Exam, Rubric, Score, Slot, User
from ..services import RuleError, notify, search, stats
from ..services import booking as booking_service
from ..services import slots as slot_service
from ..utils import form_int, parse_date, restrict_to

bp = Blueprint("admin", __name__, url_prefix="/admin")
restrict_to(bp, "admin")


PER_PAGE = 15


def page_of(query):
    """One page of results; ?page=N in the URL picks the page."""
    return query.paginate(page=request.args.get("page", 1, type=int), per_page=PER_PAGE, error_out=False)


def back(default="admin.dashboard"):
    return redirect(request.referrer or url_for(default))


@bp.route("/")
def dashboard():
    return render_template("admin/dashboard.html", totals=stats.totals(), charts=stats.charts(),
                           pending=User.query.filter_by(role="examiner", approved=False).all(),
                           recent=Booking.query.order_by(Booking.id.desc()).limit(6).all())


@bp.route("/search")
def global_search():
    q = request.args.get("q", "").strip()
    found = {"students": search.users("student", q), "examiners": search.users("examiner", q),
             "exams": search.exams(q), "bookings": search.bookings(q)}
    return render_template("admin/search.html", q=q, **{k: v.limit(10).all() for k, v in found.items()})


# ---------- courses ----------
@bp.route("/courses")
def courses():
    return render_template("admin/courses.html", courses=Course.query.order_by(Course.code).all())


@bp.route("/courses/new", methods=["GET", "POST"])
@bp.route("/courses/<int:id>/edit", methods=["GET", "POST"])
def course_form(id=None):
    course = db.get_or_404(Course, id) if id else None
    if request.method == "POST":
        form = request.form
        code = form["code"].strip().upper()
        other = Course.query.filter_by(code=code).first()
        if other and other is not course:
            raise RuleError("A course with this code already exists.")
        course = course or Course()
        course.code, course.name = code, form["name"].strip()
        course.description, course.active = form["description"].strip(), "active" in form
        db.session.add(course)
        db.session.commit()
        flash("Course saved.", "success")
        return redirect(url_for("admin.courses"))
    return render_template("admin/course_form.html", course=course)


@bp.route("/courses/<int:id>/delete", methods=["POST"])
def course_delete(id):
    course = db.get_or_404(Course, id)
    if course.exams:
        raise RuleError("This course has examinations. Mark it inactive instead of deleting it.")
    db.session.delete(course)
    db.session.commit()
    flash("Course deleted.", "success")
    return back("admin.courses")


# ---------- exams ----------
@bp.route("/exams")
def exams():
    q = request.args.get("q", "").strip()
    return render_template("admin/exams.html", exams=page_of(search.exams(q)), q=q)


@bp.route("/exams/new", methods=["GET", "POST"])
@bp.route("/exams/<int:id>/edit", methods=["GET", "POST"])
def exam_form(id=None):
    exam = db.get_or_404(Exam, id) if id else None
    if request.method == "POST":
        form = request.form
        exam = exam or Exam()
        exam.course_id = form_int(form, "course_id")
        exam.name, exam.description = form["name"].strip(), form["description"].strip()
        if form["exam_type"] not in EXAM_TYPES:
            raise RuleError("Choose a valid examination type.")
        exam.exam_type = form["exam_type"]
        exam.duration_minutes, exam.max_marks = form_int(form, "duration_minutes"), form_int(form, "max_marks")
        exam.slot_start, exam.slot_end = parse_date(form["slot_start"]), parse_date(form["slot_end"])
        exam.booking_start, exam.booking_end = parse_date(form["booking_start"]), parse_date(form["booking_end"])
        if exam.slot_end < exam.slot_start or exam.booking_end < exam.booking_start:
            raise RuleError("An end date cannot be before its start date.")
        db.session.add(exam)
        db.session.commit()
        flash("Examination saved.", "success")
        return redirect(url_for("admin.exam_detail", id=exam.id))
    return render_template("admin/exam_form.html", exam=exam, courses=Course.query.filter_by(active=True).all(), types=EXAM_TYPES)


@bp.route("/exams/<int:id>")
def exam_detail(id):
    exam = db.get_or_404(Exam, id)
    examiners = User.query.filter_by(role="examiner", approved=True, active=True).all()
    return render_template("admin/exam_detail.html", exam=exam, examiners=examiners)


@bp.route("/exams/<int:id>/delete", methods=["POST"])
def exam_delete(id):
    exam = db.get_or_404(Exam, id)
    if exam.slots:
        raise RuleError("This examination already has slots, so it cannot be deleted. Mark it completed instead.")
    db.session.delete(exam)
    db.session.commit()
    flash("Examination deleted.", "success")
    return redirect(url_for("admin.exams"))


# What each button on the exam page does: (field to set, value to set).
EXAM_ACTIONS = {
    "slots_open": ("slots_override", "open"), "slots_close": ("slots_override", "closed"), "slots_auto": ("slots_override", None),
    "booking_open": ("booking_override", "open"), "booking_close": ("booking_override", "closed"),
    "booking_auto": ("booking_override", None), "complete": ("completed", True), "reopen": ("completed", False),
}


@bp.route("/exams/<int:id>/control", methods=["POST"])
def exam_control(id):
    exam = db.get_or_404(Exam, id)
    action = request.form["action"]
    if action in ("publish", "unpublish"):
        if action == "publish":
            waiting = Booking.query.filter_by(exam_id=exam.id, status="booked").count()
            if waiting:
                raise RuleError(f"{waiting} booked student(s) are not evaluated yet.")
        exam.results_published = action == "publish"
        db.session.commit()
        if exam.results_published:
            notify.results_published(exam)
    else:
        field, value = EXAM_ACTIONS[action]
        setattr(exam, field, value)
        db.session.commit()
    flash("Updated.", "success")
    return back()


@bp.route("/exams/<int:id>/examiners", methods=["POST"])
def exam_examiners(id):
    exam = db.get_or_404(Exam, id)
    ids = [int(i) for i in request.form.getlist("examiner_ids")]
    exam.examiners = User.query.filter(User.id.in_(ids), User.role == "examiner").all()
    db.session.commit()
    flash("Assigned examiners updated.", "success")
    return back()


# ---------- rubrics ----------
def _fill_rubric(rubric, form):
    rubric.name, rubric.description = form["name"].strip(), form["description"].strip()
    rubric.max_marks, rubric.weightage = form_int(form, "max_marks"), form_int(form, "weightage")


@bp.route("/exams/<int:id>/rubrics", methods=["POST"])
def rubric_add(id):
    rubric = Rubric(exam_id=db.get_or_404(Exam, id).id)
    _fill_rubric(rubric, request.form)
    db.session.add(rubric)
    db.session.commit()
    return back()


def _unscored_rubric(id):
    rubric = db.get_or_404(Rubric, id)
    if Score.query.filter_by(rubric_id=id).first():
        raise RuleError("Marks were already given using this criterion, so it can no longer change.")
    return rubric


@bp.route("/rubrics/<int:id>", methods=["POST"])
def rubric_edit(id):
    _fill_rubric(_unscored_rubric(id), request.form)
    db.session.commit()
    return back()


@bp.route("/rubrics/<int:id>/delete", methods=["POST"])
def rubric_delete(id):
    db.session.delete(_unscored_rubric(id))
    db.session.commit()
    return back()


# ---------- examiners and students ----------
@bp.route("/examiners")
def examiners():
    q = request.args.get("q", "").strip()
    return render_template("admin/examiners.html", users=page_of(search.users("examiner", q)), q=q)


@bp.route("/examiners/new", methods=["POST"])
def examiner_add():
    form = request.form
    if User.query.filter_by(email=form["email"].strip().lower()).first():
        raise RuleError("This email is already registered.")
    if len(form["password"]) < 8:
        raise RuleError("Password must have at least 8 characters.")
    user = User(name=form["name"].strip(), email=form["email"].strip().lower(), role="examiner",
                department=form["department"].strip(), phone=form["phone"].strip())
    user.set_password(form["password"])
    db.session.add(user)
    db.session.commit()
    flash("Examiner added and approved.", "success")
    return back()


@bp.route("/users/<int:id>/approve", methods=["POST"])
def approve(id):
    db.get_or_404(User, id).approved = True
    db.session.commit()
    flash("Examiner approved.", "success")
    return back()


@bp.route("/users/<int:id>/toggle", methods=["POST"])
def toggle_active(id):
    user = db.get_or_404(User, id)
    if user.role == "admin":
        raise RuleError("The admin cannot be deactivated.")
    user.active = not user.active
    db.session.commit()
    flash(f"{user.name} is now {'active' if user.active else 'deactivated'}.", "success")
    return back()


@bp.route("/students")
def students():
    q = request.args.get("q", "").strip()
    return render_template("admin/students.html", users=page_of(search.users("student", q)), q=q)


# ---------- slots and bookings ----------
@bp.route("/slots")
def slots():
    slots = page_of(Slot.query.order_by(Slot.date.desc(), Slot.start_time))
    examiners = User.query.filter_by(role="examiner", approved=True, active=True).all()
    return render_template("admin/slots.html", slots=slots, examiners=examiners)


@bp.route("/slots/<int:id>/examiner", methods=["POST"])
def slot_examiner(id):
    slot_service.change_examiner(db.get_or_404(Slot, id), db.get_or_404(User, form_int(request.form, "examiner_id")))
    flash("Examiner changed.", "success")
    return back()


@bp.route("/bookings")
def bookings():
    q = request.args.get("q", "").strip()
    return render_template("admin/bookings.html", bookings=page_of(search.bookings(q)), q=q)


@bp.route("/bookings/<int:id>/reschedule", methods=["POST"])
def reschedule(id):
    booking_service.reschedule(db.get_or_404(Booking, id), db.get_or_404(Slot, form_int(request.form, "slot_id")))
    flash("Booking rescheduled.", "success")
    return back()
