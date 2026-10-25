from datetime import date, time, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import Course, Exam, Rubric, User
from config import TestConfig


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


def add_user(name, role, approved=True):
    user = User(name=name, email=f"{name}@t.com", role=role, approved=approved)
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def world(app):
    """One open exam with an examiner, two students and a slot of capacity 1."""
    from app.services import slots

    examiner = add_user("examiner", "examiner")
    students = [add_user("s1", "student"), add_user("s2", "student")]
    course = Course(code="T1", name="Test course")
    today = date.today()
    exam = Exam(course=course, name="Test viva", exam_type="Viva", duration_minutes=30, max_marks=100,
                slot_start=today, slot_end=today, booking_start=today, booking_end=today, examiners=[examiner],
                rubrics=[Rubric(name="A", max_marks=10, weightage=60), Rubric(name="B", max_marks=10, weightage=40)])
    db.session.add(exam)
    db.session.commit()
    slot = slots.create_slot(exam, examiner, today + timedelta(days=1), time(10), time(11), 1)
    return {"examiner": examiner, "students": students, "exam": exam, "slot": slot}


def login(client, name):
    client.post("/login", data={"email": f"{name}@t.com", "password": "password123"})
