"""`flask seed`: realistic demo data (courses modelled on the IIT Madras BS degree).

All demo accounts use the password "password123".
"""
import random
from datetime import date, datetime, time, timedelta

import click
from flask.cli import with_appcontext

from .extensions import db
from .models import Course, Exam, Rubric, User
from .services import booking as booking_service, evaluation, slots as slot_service

PASSWORD = "password123"
FUTURE = 400  # days; see add_slots

# Codes, names and credits follow the IIT Madras BS degree academics page (study.iitm.ac.in/ds/academics.html).
COURSES = [
    ("BSMA1001", "Mathematics for Data Science I", "Foundation · 4 credits. Sets, functions, graphs and calculus foundations."),
    ("BSMA1002", "Statistics for Data Science I", "Foundation · 4 credits. Descriptive statistics, probability and distributions."),
    ("BSCS1002", "Programming in Python", "Foundation · 4 credits. Control flow, functions, data structures and files."),
    ("BSCS2001", "Database Management Systems", "Diploma in Programming · 4 credits. Relational model, SQL, normalisation, transactions."),
    ("BSCS2002", "Programming, Data Structures and Algorithms using Python", "Diploma in Programming · 4 credits. Searching, sorting, graphs and complexity."),
    ("BSCS2003", "Modern Application Development I", "Diploma in Programming · 4 credits. Web apps with Flask, Jinja2, SQLite and REST APIs."),
    ("BSCS2003P", "Modern Application Development I - Project", "Diploma in Programming · 2 credits. Build and defend a full Flask application."),
    ("BSCS2005", "Programming Concepts using Java", "Diploma in Programming · 4 credits. Object-oriented design, collections and concurrency."),
    ("BSCS2004", "Machine Learning Foundations", "Diploma in Data Science · 4 credits. Linear algebra, probability and optimisation for ML."),
    ("BSSE2002", "Tools in Data Science", "Diploma in Data Science · 3 credits. Sourcing, preparing, analysing and deploying data."),
]

EXAMINERS = [
    ("Dr. Anjali Raghavan", "Computer Science"), ("Prof. Karthik Subramanian", "Computer Science"),
    ("Dr. Meenakshi Iyer", "Mathematics"), ("Dr. Arvind Krishnan", "Data Science"), ("Ms. Shreya Banerjee", "Data Science"),
]
PENDING_EXAMINERS = [("Dr. Rohit Venkatesh", "Electrical Engineering"), ("Prof. Lakshmi Narayanan", "Management Studies")]

STUDENTS = [
    "Aarav Mehta", "Diya Kapoor", "Kabir Singh", "Ananya Iyer", "Rohan Das", "Meera Nair", "Ishaan Gupta", "Saanvi Reddy",
    "Vihaan Joshi", "Aditi Menon", "Arjun Pillai", "Kavya Sharma", "Reyansh Bose", "Myra Choudhury", "Advait Kulkarni",
    "Tara Fernandes", "Krishna Rao", "Nisha Agarwal", "Siddharth Verma", "Pooja Hegde", "Yash Malhotra", "Riya Saxena",
    "Aryan Chatterjee", "Sneha Patil", "Dev Bhattacharya", "Zara Khan", "Om Prakash", "Lavanya Murthy", "Neil D'Souza",
    "Gauri Deshpande", "Harsh Vardhan", "Fatima Sheikh", "Varun Sethi", "Ira Mukherjee", "Kunal Bajaj", "Anika Jain",
]

RUBRICS = {
    "Viva": [("Conceptual understanding", 10, 40), ("Code walkthrough", 10, 30), ("Live modification", 10, 20), ("Communication", 10, 10)],
    "Practical": [("Correctness", 20, 50), ("Efficiency", 10, 30), ("Explanation", 10, 20)],
    "Project Demo": [("Feature completeness", 10, 40), ("Design and usability", 10, 20), ("Code quality", 10, 20), ("Q&A", 10, 20)],
    "Assessment": [("Accuracy", 10, 60), ("Method and working", 10, 40)],
}

REMARKS = [
    "Clear grasp of the request-response cycle. Explain database relationships more confidently.",
    "Strong live modification. Structure answers before diving into code.",
    "Good communication and clean code. Revise how sessions and cookies work.",
    "Solid effort. Be more precise with terminology during explanations.",
    "Excellent understanding of the data model; edge cases were handled well.",
    "Answers were correct but slow. Practise tracing code without running it.",
    "Very good project. Add validation on the server side, not only in the browser.",
    "Good debugging approach. Work on time management in the practical.",
    "Explained trade-offs thoughtfully. Strong overall performance.",
    "Needs more practice writing SQL joins by hand.",
]


def make_user(name, email, role, **extra):
    user = User(name=name, email=email, role=role, **extra)
    user.set_password(PASSWORD)
    db.session.add(user)
    return user


def email_for(name):
    words = [w for w in name.lower().replace("'", "").split() if not w.endswith(".")]
    return f"{words[0]}.{words[-1]}@faculty.emp.local"


@click.command("seed")
@with_appcontext
def seed_command():
    """Fill the database with realistic demo data."""
    if Course.query.first():
        raise click.ClickException("Demo data already exists. Delete instance/emp.db to start fresh.")
    rng = random.Random(2026)  # same data every time
    today = date.today()
    day = lambda offset: today + timedelta(days=offset)  # noqa: E731

    courses = {code: Course(code=code, name=name, description=text) for code, name, text in COURSES}
    db.session.add_all(courses.values())
    examiners = [make_user(n, email_for(n), "examiner", department=d, phone=f"+91 98{rng.randint(10000000, 99999999)}") for n, d in EXAMINERS]
    for n, d in PENDING_EXAMINERS:
        make_user(n, email_for(n), "examiner", department=d, approved=False)
    students = [make_user(n, f"24f{1000001 + i * 37}@ds.emp.local", "student", phone=f"+91 9{rng.randint(100000000, 999999999)}")
                for i, n in enumerate(STUDENTS)]
    students[-1].active = False  # one deactivated account, to show the feature
    db.session.commit()
    ability = {s.id: rng.uniform(.45, .95) for s in students}  # each student is consistently strong or weak

    def exam(code, name, kind, minutes, slots_from, booking_from, team, **extra):
        e = Exam(course=courses[code], name=name, exam_type=kind, duration_minutes=minutes, max_marks=100,
                 description=f"{kind} for {courses[code].name}.", slot_start=day(slots_from), slot_end=day(slots_from + 6),
                 booking_start=day(booking_from), booking_end=day(booking_from + 9), examiners=team, **extra)
        e.rubrics = [Rubric(name=n, max_marks=m, weightage=w) for n, m, w in RUBRICS[kind]]
        db.session.add(e)
        db.session.commit()
        return e

    def add_slots(e, first_day, days, hours, capacity):
        """Past slots are created far in the future, booked, then moved back (the app refuses past dates)."""
        e.slots_override = "open"  # open the window just while seeding
        for d in range(days):
            for k, examiner in enumerate(e.examiners):
                for h in hours:
                    start = time(h + k % 2)  # examiners on the same day start at different hours
                    end = (datetime.combine(today, start) + timedelta(minutes=max(e.duration_minutes, 30) * capacity)).time()
                    slot_service.create_slot(e, examiner, day(first_day + d + (FUTURE if first_day < 1 else 0)), start, end, capacity)
        e.slots_override = None
        db.session.commit()

    def add_bookings(e, share, evaluate_share=0.0):
        e.booking_override = "open"
        free = [s for s in e.slots if not s.cancelled]
        for student in rng.sample(students[:-1], int(len(students[:-1]) * share)):
            open_slots = [s for s in free if s.available_seats > 0]
            if not open_slots:
                break
            b = booking_service.book(student, rng.choice(open_slots))
            opened = datetime.combine(e.booking_start, time(9))
            latest = min(datetime.now(), opened + timedelta(days=8))  # bookings never lie in the future
            b.created_at = opened + (latest - opened) * rng.random()
            if rng.random() < evaluate_share:
                scores = {r.id: round(min(r.max_marks, max(0, r.max_marks * (ability[student.id] + rng.uniform(-.15, .12)))) * 2) / 2
                          for r in e.rubrics}
                evaluation.evaluate(b, b.slot.examiner, scores, rng.choice(REMARKS))
        e.booking_override = None
        if e.slots[0].date > day(FUTURE // 2):  # move seeded past slots back to their real dates
            for slot in e.slots:
                slot.date -= timedelta(days=FUTURE)
        db.session.commit()

    a, k, m, v, s = examiners
    # Finished and published.
    java = exam("BSCS2005", "Java Practical: Term 2", "Practical", 45, -62, -54, [k, v])
    add_slots(java, -44, 3, [9, 14], 2)
    add_bookings(java, .55, 1)
    mad = exam("BSCS2003P", "MAD I Project Viva: September", "Viva", 15, -40, -32, [a, k, s])
    add_slots(mad, -20, 3, [10, 15], 2)
    add_bookings(mad, .85, 1)
    # Exam over, evaluation still in progress (gives examiners a to-do list).
    maths = exam("BSMA1001", "Maths I Oral Assessment", "Assessment", 30, -22, -15, [m])
    add_slots(maths, -4, 3, [9, 11, 14], 3)
    add_bookings(maths, .6, .7)
    # Booking is open right now.
    dbms = exam("BSCS2001", "DBMS SQL Practical", "Practical", 45, -10, -2, [a, v])
    add_slots(dbms, 3, 3, [9, 11], 2)
    add_bookings(dbms, .4)
    tds = exam("BSSE2002", "TDS Project Demo", "Project Demo", 20, -5, 0, [s, v])
    add_slots(tds, 6, 2, [14, 16], 2)
    add_bookings(tds, .2)
    # Examiners are adding slots; booking opens later.
    python = exam("BSCS1002", "Python OPPE: Supervised Retake", "Assessment", 60, -1, 6, [k, m])
    add_slots(python, 10, 1, [10], 4)
    # Planned for later (draft).
    exam("BSCS2004", "MLF End-term Viva", "Viva", 20, 8, 16, [m, s])

    for e in (java, mad):
        e.completed = e.results_published = True
    db.session.commit()
    click.echo(f"Demo data created: {len(courses)} courses, {len(examiners)} examiners, {len(students)} students. "
               f"Password for every demo account: {PASSWORD}")
