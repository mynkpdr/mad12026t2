from app.services import booking
from tests.conftest import add_user, login


def test_roles_cannot_open_other_dashboards(app, world):
    client = app.test_client()
    assert client.get("/admin/").status_code == 302  # not logged in -> login page
    login(client, "s1")
    assert client.get("/student/").status_code == 200
    assert client.get("/admin/").status_code == 403
    assert client.get("/examiner/").status_code == 403


def test_unapproved_examiner_is_sent_to_pending_page(app):
    add_user("newbie", "examiner", approved=False)
    client = app.test_client()
    login(client, "newbie")
    response = client.get("/examiner/")
    assert response.status_code == 302 and response.location.endswith("/pending")


def test_results_hidden_until_published_and_other_student_blocked(app, world):
    b = booking.book(world["students"][0], world["slot"])
    client = app.test_client()
    login(client, "s2")
    assert client.get(f"/student/results/{b.id}/scorecard.pdf").status_code == 403


def test_examiner_cannot_open_another_examiners_slot(app, world):
    add_user("other", "examiner")
    client = app.test_client()
    login(client, "other")
    assert client.get(f"/examiner/slots/{world['slot'].id}").status_code == 403


def test_api_requires_login(app):
    assert app.test_client().get("/api/exams").status_code == 401
