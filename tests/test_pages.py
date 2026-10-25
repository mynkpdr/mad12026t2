"""Every page opens without an error for the role it belongs to."""
from app.services import booking, evaluation


def test_all_pages_render(app, world):
    b = booking.book(world["students"][0], world["slot"])
    rubrics = world["exam"].rubrics
    evaluation.evaluate(b, world["examiner"], {rubrics[0].id: 9, rubrics[1].id: 6.5}, "Well done")
    world["exam"].results_published = True
    exam, slot = world["exam"].id, world["slot"].id
    pages = {
        ("admin@emp.local", "admin123"): ["/admin/", "/admin/courses", "/admin/courses/new", "/admin/exams", "/admin/exams?page=9",
                                         "/admin/exams/new", f"/admin/exams/{exam}", f"/admin/exams/{exam}/edit", "/admin/examiners",
                                         "/admin/students?q=s", "/admin/slots", "/admin/bookings", "/admin/search?q=test", "/profile"],
        ("examiner@t.com", "password123"): ["/examiner/", "/examiner/exams", "/examiner/slots", f"/examiner/slots/{slot}",
                                            f"/examiner/bookings/{b.id}/evaluate", f"/examiner/exams/{exam}/slots/new"],
        ("s1@t.com", "password123"): ["/student/", "/student/exams", "/student/exams?open=1&type=Viva", "/student/exams?q=&type=&course=&open=1", "/student/exams?course=1", f"/student/exams/{exam}",
                                      "/student/bookings", "/student/results", f"/student/results/{b.id}/scorecard.pdf", "/api/bookings"],
    }
    for (email, password), urls in pages.items():
        client = app.test_client()
        client.post("/login", data={"email": email, "password": password})
        for url in urls:
            assert client.get(url).status_code == 200, url


def test_login_page_renders(app):
    assert app.test_client().get("/login").status_code == 200
    assert app.test_client().get("/register").status_code == 200

