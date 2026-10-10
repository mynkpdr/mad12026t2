from ..extensions import db
from ..models import Booking, Course, Exam, User

# Every function returns a query, so callers can paginate it (pages), limit it or take .all().


def _match(query, id_column, text_columns, q):
    """Keep rows whose text columns contain q, or whose id equals q when q is a number."""
    if not q:
        return query
    conditions = [c.ilike(f"%{q}%") for c in text_columns]
    if q.isdigit():
        conditions.append(id_column == int(q))
    return query.filter(db.or_(*conditions))


def users(role, q=""):
    query = User.query.filter_by(role=role)
    return _match(query, User.id, [User.name, User.email], q).order_by(User.id.desc())


def exams(q="", exam_type="", course_id=None):
    query = Exam.query.join(Course)
    if exam_type:
        query = query.filter(Exam.exam_type == exam_type)
    if course_id:
        query = query.filter(Exam.course_id == course_id)
    return _match(query, Exam.id, [Exam.name, Course.code, Course.name], q).order_by(Exam.id.desc())


def bookings(q=""):
    query = Booking.query.join(User, Booking.student_id == User.id).join(Exam)
    return _match(query, Booking.id, [User.name, Exam.name], q).order_by(Booking.id.desc())
