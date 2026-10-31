# Examination Management Portal

Flask + Jinja2 + Bootstrap + SQLite, with an "academic editorial" design (Fraunces and Schibsted Grotesk fonts from
Google Fonts, light and dark themes, collapsible sidebar, edge-aware tooltips, SVG logo and favicon). Three roles: **Admin** (sets up courses, exams, rubrics, approves examiners),
**Examiner** (creates slots, evaluates students), **Student** (books slots, sees results).

**Author:** Mayank Kumar Poddar · Roll no. 23f3004197 · 23f3004197@ds.study.iitm.ac.in

## Run it (local, pip only)

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
flask --app run seed        # optional: demo data (courses, exams, users, bookings)
python run.py               # http://127.0.0.1:5000
```

The database (`instance/emp.db`) and the admin account are created automatically on first start.

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@emp.local` | `admin123` (set `ADMIN_EMAIL` / `ADMIN_PASSWORD` to change) |
| Examiner | `anjali.raghavan@faculty.emp.local`, `meenakshi.iyer@faculty.emp.local` (has evaluations waiting) | `password123` |
| Student | `24f1000001@ds.emp.local` ... (36 students, see the admin's Students page) | `password123` |
| Waiting for approval | `farhan.qureshi@faculty.emp.local` | `password123` |

The demo data follows the IIT Madras BS degree: real course codes and names (for example BSCS2003 Modern Application
Development I), with exams in every state. Two are completed with published results, one is waiting for evaluation,
two are open for booking, one is in slot creation and one is a draft.

Run the tests: `python -m pytest`

## How the code is organised

```
app/
  models.py        all tables (User, Course, Exam, Rubric, Slot, Booking, Score)
  services/        the business rules (one small file per topic)
    slots.py         create / edit / remove slots, change examiner
    booking.py       book, cancel, reschedule (overbooking + duplicate protection)
    evaluation.py    marks calculation and "only my own students" rule
    search.py        search by name or ID
    stats.py         dashboard numbers and chart data
    notify.py        emails       scorecard.py   PDF scorecard
  blueprints/      thin web routes: auth, admin, examiner, student, api (JSON)
  templates/       Jinja2 pages; _macros.html holds the reusable pieces (status pill, ticket, pager...)
  static/          css/app.css (the whole design, colours as variables), Bootstrap + Chart.js saved locally,
                  js/ui.js (theme, sidebar, tooltip placement; nothing depends on it), img/ (logo, favicons)
  cli.py           `flask seed` demo data
config.py  run.py  tests/  Dockerfile  docker-compose.yml
```

Rule of thumb: **routes read the form and show a page; services decide what is allowed.**
A service that refuses something raises `RuleError`; one error handler turns it into a red message.

## Key rules and where they live

| Rule | Where |
| --- | --- |
| Slots only during the slot-creation period; edit/remove only before booking starts | `services/slots.py`, `Exam.slots_open`, `Slot.editable` |
| Booking only during the booking period | `services/booking.py` |
| No overbooking; slot becomes *Full* automatically | `_take_seat`: one atomic `UPDATE ... WHERE booked < capacity` |
| No duplicate booking for the same exam | unique database index `one_live_booking` in `models.py` |
| Examiner evaluates only students in their own slots | `services/evaluation.py` and `examiner.my_slot` |
| Results hidden until admin publishes | `Booking.result_visible` |
| Role access | `restrict_to(blueprint, role)` in `utils.py` |
| No slots or bookings in the past | `services/slots.py`, `services/booking.py` |
| Long lists are paged (15 per page) | `page_of()` in `blueprints/admin.py`, `pager` macro |

Exam status (Draft / Slot Creation / Booking Open / Closed / Completed) is **calculated** from the dates and the admin's
open/close switches, so it can never disagree with them.

Marks: `total = sum(score / max * weightage) / sum(weightage) * exam max marks`.

## JSON API (login session required; POST/DELETE need the `X-CSRFToken` header)

`GET /api/exams`, `/api/exams/<id>`, `/api/exams/<id>/slots`, `/api/examiners` (admin), `/api/students` (admin),
`/api/bookings` (own bookings; all for admin), `POST /api/bookings {"slot_id": 1}`, `DELETE /api/bookings/<id>`.

## Email

Emails (booking confirmed, result published) are logged to the terminal. To really send, set `MAIL_SERVER`, `MAIL_PORT`.
For local testing: `pip install aiosmtpd && python -m aiosmtpd -n -l localhost:8025`, then `MAIL_SERVER=localhost python run.py`.

## Deploy (optional)

```bash
SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") ADMIN_PASSWORD=choose-one docker compose up --build
```

`APP_ENV=production` makes the app refuse to start without `SECRET_KEY` and `ADMIN_PASSWORD`.
SQLite is the required database, so run **one** gunicorn worker. Moving to a bigger database later only means changing
`DATABASE_URL`, because all queries go through SQLAlchemy.
