from datetime import date, datetime

from flask_login import UserMixin
from sqlalchemy import Index, text
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

EXAM_TYPES = ["Viva", "Practical", "Project Demo", "Assessment"]

# Which examiners are assigned to which exam.
exam_examiners = db.Table(
    "exam_examiners",
    db.Column("exam_id", db.ForeignKey("exam.id"), primary_key=True),
    db.Column("examiner_id", db.ForeignKey("user.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    """Admin, examiner and student all live here; `role` tells them apart."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # admin / examiner / student
    department = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    approved = db.Column(db.Boolean, default=True, nullable=False)  # examiners start as False
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    @property
    def is_active(self):  # Flask-Login uses this to block deactivated users
        return self.active

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    active = db.Column(db.Boolean, default=True, nullable=False)


def _window_open(override, start, end):
    """Admin's open/close switch wins; otherwise the date window decides."""
    if override:
        return override == "open"
    return start <= date.today() <= end


class Exam(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.ForeignKey("course.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    exam_type = db.Column(db.String(20), nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default="")
    slot_start = db.Column(db.Date, nullable=False)  # examiners may create slots in this window
    slot_end = db.Column(db.Date, nullable=False)
    booking_start = db.Column(db.Date, nullable=False)  # students may book in this window
    booking_end = db.Column(db.Date, nullable=False)
    slots_override = db.Column(db.String(6))  # None (use dates) / "open" / "closed"
    booking_override = db.Column(db.String(6))
    completed = db.Column(db.Boolean, default=False, nullable=False)
    results_published = db.Column(db.Boolean, default=False, nullable=False)

    course = db.relationship("Course", backref="exams")
    examiners = db.relationship("User", secondary=exam_examiners, backref="assigned_exams")
    rubrics = db.relationship("Rubric", backref="exam", order_by="Rubric.id", cascade="all, delete-orphan")

    @property
    def slots_open(self):
        return not self.completed and _window_open(self.slots_override, self.slot_start, self.slot_end)

    @property
    def booking_open(self):
        return not self.completed and _window_open(self.booking_override, self.booking_start, self.booking_end)

    @property
    def status(self):
        if self.completed:
            return "Completed"
        if self.booking_open:
            return "Booking Open"
        if self.slots_open:
            return "Slot Creation"
        if date.today() < self.slot_start and not (self.slots_override or self.booking_override):
            return "Draft"
        return "Closed"


class Rubric(db.Model):
    """One marking criterion, e.g. 'Viva answers' out of 10 with weightage 40."""

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.ForeignKey("exam.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    max_marks = db.Column(db.Integer, nullable=False)
    weightage = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text, default="")


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.ForeignKey("exam.id"), nullable=False, index=True)
    examiner_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    booked = db.Column(db.Integer, default=0, nullable=False)  # seats taken
    cancelled = db.Column(db.Boolean, default=False, nullable=False)

    exam = db.relationship("Exam", backref="slots")
    examiner = db.relationship("User")

    @property
    def available_seats(self):
        return 0 if self.cancelled else self.capacity - self.booked

    @property
    def status(self):
        if self.cancelled:
            return "Cancelled"
        live = [b for b in self.bookings if b.status != "cancelled"]
        if self.exam.completed or (live and all(b.status == "completed" for b in live)):
            return "Completed"
        return "Full" if self.available_seats == 0 else "Available"

    @property
    def editable(self):
        """Examiner may change a slot only while slot creation is open and before booking starts."""
        return not self.cancelled and self.exam.slots_open and not self.exam.booking_open and self.booked == 0


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
    slot_id = db.Column(db.ForeignKey("slot.id"), nullable=False, index=True)
    exam_id = db.Column(db.ForeignKey("exam.id"), nullable=False, index=True)
    status = db.Column(db.String(10), default="booked", nullable=False)  # booked / cancelled / completed
    created_at = db.Column(db.DateTime, default=datetime.now)
    cancelled_at = db.Column(db.DateTime)
    note = db.Column(db.Text, default="")  # history, e.g. "Rescheduled by admin"
    marks = db.Column(db.Float)
    remarks = db.Column(db.Text)
    evaluated_at = db.Column(db.DateTime)

    student = db.relationship("User")
    slot = db.relationship("Slot", backref="bookings")
    exam = db.relationship("Exam")
    scores = db.relationship("Score", backref="booking", cascade="all, delete-orphan")

    # The database itself refuses a second live booking for the same student and exam.
    __table_args__ = (
        Index("one_live_booking", "student_id", "exam_id", unique=True, sqlite_where=text("status != 'cancelled'")),
    )

    @property
    def result_visible(self):
        return self.status == "completed" and self.exam.results_published


class Score(db.Model):
    """Marks given for one rubric criterion in one booking."""

    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.ForeignKey("booking.id"), nullable=False, index=True)
    rubric_id = db.Column(db.ForeignKey("rubric.id"), nullable=False, index=True)
    score = db.Column(db.Float, nullable=False)

    rubric = db.relationship("Rubric")
