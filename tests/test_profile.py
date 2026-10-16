"""Profile editing and navigation tests with an isolated in-memory database.

These tests render the actual account/navigation templates. Unrelated learning
endpoints are URL-only stubs; production initialization, data, and servers are
never accessed.
"""

import unittest
from html.parser import HTMLParser
from unittest.mock import patch

from flask import g
from sqlalchemy.exc import SQLAlchemyError

import test_notice_attachments as fixtures
from app.extensions import db
from app.models.notice import Notice
from app.models.user import User


class _Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def matching(self, tag):
        return [attrs for name, attrs in self.elements if name == tag]


class ProfileTests(unittest.TestCase):
    tearDown = fixtures.NoticeAttachmentTests.tearDown
    make_user = staticmethod(fixtures.NoticeAttachmentTests.make_user)
    sign_in = fixtures.NoticeAttachmentTests.sign_in
    post_notice = fixtures.NoticeAttachmentTests.post_notice

    def setUp(self):
        fixtures.NoticeAttachmentTests.setUp(self)
        # Undo the notice fixture's minimal base: navigation is part of this
        # feature and must render correctly on the real site template.
        self.app.jinja_loader = self.app.jinja_loader.loaders[1]
        for endpoint in (
            "voca.index", "story.index", "story.story_exam_index",
            "village.index", "village.exam", "exam.voca_index",
            "exam.math_index", "admin.admin",
        ):
            self.app.add_url_rule(
                "/__test/" + endpoint.replace(".", "/"),
                endpoint=endpoint,
                view_func=lambda: "unused profile test endpoint",
            )
        self.admin.admin_type = "A"
        self.admin.full_name = "관리자 이름"
        self.student.full_name = "학생 이름"
        self.student.church = "학생 소속 교회"
        self.student.email = "student@example.test"
        db.session.commit()
        self.sign_in(self.student)

    def sign_out(self):
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()

    def token(self):
        response = self.client.get("/auth/profile")
        self.assertEqual(response.status_code, 200)
        fields = _Elements(response.get_data(as_text=True)).matching("input")
        csrf = [field for field in fields if field.get("name") == "csrf_token"]
        self.assertEqual(len(csrf), 1)
        self.assertEqual(csrf[0].get("type"), "hidden")
        self.assertTrue(csrf[0].get("value"))
        with self.client.session_transaction() as session:
            self.assertEqual(csrf[0]["value"], session["profile_csrf_token"])
        return csrf[0]["value"]

    def post_profile(self, full_name="변경한 이름", **fields):
        data = {"full_name": full_name, "csrf_token": self.token()}
        data.update(fields)
        return self.client.post("/auth/profile", data=data)

    def assert_name(self, user, expected):
        db.session.expire_all()
        self.assertEqual(db.session.get(User, user.id).full_name, expected)

    def assert_private(self, response):
        self.assertTrue(response.cache_control.private)
        self.assertTrue(response.cache_control.no_store)
        self.assertIn("Cookie", response.vary)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_get_and_post_require_login(self):
        self.sign_out()
        for method in (self.client.get, self.client.post):
            with self.subTest(method=method.__name__):
                response = method("/auth/profile", data={"full_name": "외부 변경"})
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth/login", response.headers["Location"])
                self.assertNotIn("학생 소속 교회", response.get_data(as_text=True))
        self.assert_name(self.student, "학생 이름")

    def test_profile_displays_current_name_and_readonly_account_information(self):
        response = self.client.get("/auth/profile")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("학생 소속 교회", html)
        self.assertIn("notice-student", html)
        self.assertIn("학생", html)
        fields = _Elements(html).matching("input")
        names = [field for field in fields if field.get("name") == "full_name"]
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0].get("value"), "학생 이름")
        self.assertEqual(names[0].get("maxlength"), "100")
        self.assertIn("required", names[0])
        for field in fields:
            if field.get("name") in ("username", "church", "is_admin", "admin_type"):
                self.assertTrue("readonly" in field or "disabled" in field)

    def test_profile_issues_session_bound_csrf_token(self):
        student_token = self.token()
        self.assertEqual(self.token(), student_token)
        self.sign_in(self.admin)
        self.assertNotEqual(self.token(), student_token)

    def test_student_updates_own_name_and_keeps_identity(self):
        student_id = self.student.id
        password_hash = self.student.password_hash
        response = self.post_profile("  김새이름  ")
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "/auth/profile")
        self.assert_name(self.student, "김새이름")
        self.assertEqual(self.student.id, student_id)
        self.assertEqual(self.student.username, "notice-student")
        self.assertEqual(self.student.password_hash, password_hash)
        self.assertEqual(User.query.count(), 2)
        self.assert_name(self.admin, "관리자 이름")
        html = self.client.get("/auth/profile").get_data(as_text=True)
        self.assertIn("김새이름", html)

    def test_admin_can_also_edit_own_name(self):
        self.sign_in(self.admin)
        response = self.post_profile("교사 이름")
        self.assertEqual(response.status_code, 303)
        self.assert_name(self.admin, "교사 이름")
        self.assertTrue(self.admin.is_admin)
        self.assertEqual(self.admin.admin_type, "A")
        self.assert_name(self.student, "학생 이름")

    def test_korean_spaces_and_one_hundred_characters_are_valid(self):
        for value in ("이 재호", "김민수", "가" * 100):
            with self.subTest(name=value):
                response = self.post_profile(value)
                self.assertEqual(response.status_code, 303)
                self.assert_name(self.student, value)

    def test_blank_missing_and_overlong_names_are_rejected_without_db_changes(self):
        for value in ("", "   ", "\u3000", "가" * 101):
            with self.subTest(name=repr(value)):
                response = self.post_profile(value)
                self.assertEqual(response.status_code, 400)
                self.assert_name(self.student, "학생 이름")
        response = self.client.post("/auth/profile", data={"csrf_token": self.token()})
        self.assertEqual(response.status_code, 400)
        self.assert_name(self.student, "학생 이름")

    def test_control_and_invisible_characters_are_rejected(self):
        for invalid in ("\x00", "\n", "\r", "\t", "\x7f", "\u200b", "\u202e", "\u2066", "\ufeff"):
            with self.subTest(codepoint=repr(invalid)):
                response = self.post_profile("김" + invalid + "민수")
                self.assertEqual(response.status_code, 400)
                self.assert_name(self.student, "학생 이름")

    def test_missing_wrong_and_other_session_csrf_tokens_are_rejected(self):
        self.sign_in(self.admin)
        other_token = self.token()
        self.sign_in(self.student)
        self.token()
        for token in (None, "wrong-token", "한글위조토큰", other_token):
            with self.subTest(token=repr(token)):
                data = {"full_name": "위조한 이름"}
                if token is not None:
                    data["csrf_token"] = token
                response = self.client.post("/auth/profile", data=data)
                self.assertEqual(response.status_code, 400)
                self.assert_name(self.student, "학생 이름")

    def test_mass_assignment_and_other_user_targeting_are_ignored(self):
        original_password_hash = self.student.password_hash
        response = self.post_profile(
            "정상 이름",
            id=str(self.admin.id), user_id=str(self.admin.id),
            username="hijacked-admin", is_admin="1", admin_type="A",
            email="attacker@example.test", church="변경 시도", password="new-password",
            password_hash="injected", security_answer="injected",
        )
        self.assertEqual(response.status_code, 303)
        self.assert_name(self.student, "정상 이름")
        self.assert_name(self.admin, "관리자 이름")
        self.assertEqual(self.student.username, "notice-student")
        self.assertFalse(self.student.is_admin)
        self.assertIsNone(self.student.admin_type)
        self.assertEqual(self.student.email, "student@example.test")
        self.assertEqual(self.student.church, "학생 소속 교회")
        self.assertEqual(self.student.password_hash, original_password_hash)
        self.assertEqual(self.student.security_answer, "테스트")

    def test_query_string_cannot_target_another_account(self):
        response = self.client.post(
            f"/auth/profile?user_id={self.admin.id}&username={self.admin.username}",
            data={"full_name": "내 새 이름", "csrf_token": self.token()},
        )
        self.assertEqual(response.status_code, 303)
        self.assert_name(self.student, "내 새 이름")
        self.assert_name(self.admin, "관리자 이름")

    def test_oversize_request_returns_413_without_changes(self):
        token = self.token()
        response = self.client.post("/auth/profile", data={
            "full_name": "가" * 65536,
            "csrf_token": token,
        })
        self.assertEqual(response.status_code, 413)
        self.assert_name(self.student, "학생 이름")

    def test_database_failure_rolls_back_and_exposes_no_internal_error(self):
        token = self.token()
        with patch.object(db.session, "commit", side_effect=SQLAlchemyError("private database details")):
            response = self.client.post("/auth/profile", data={
                "full_name": "저장 실패 이름", "csrf_token": token,
            })
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database details", response.get_data(as_text=True))
        self.assertNotIn("Traceback", response.get_data(as_text=True))
        self.assert_name(self.student, "학생 이름")
        self.assertEqual(self.post_profile("복구 뒤 이름").status_code, 303)
        self.assert_name(self.student, "복구 뒤 이름")

    def test_existing_untrusted_name_is_html_escaped_on_profile(self):
        self.student.full_name = '<script>alert("xss")</script>'
        db.session.commit()
        response = self.client.get("/auth/profile")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn(self.student.full_name, html)
        self.assertIn("&lt;script&gt;", html)
        self.assertFalse(any(
            name.lower().startswith("on")
            for _, attrs in _Elements(html).elements for name in attrs
        ))

    def test_profile_and_validation_responses_are_private(self):
        self.assert_private(self.client.get("/auth/profile"))
        self.assert_private(self.post_profile(""))

    def test_profile_has_notice_and_admin_upload_action_without_student_escalation(self):
        for user in (self.student, self.admin):
            self.sign_in(user)
            response = self.client.get("/auth/profile")
            self.assertEqual(response.status_code, 200)
            links = _Elements(response.get_data(as_text=True)).matching("a")
            self.assertTrue(any(link.get("href") == "/notices" for link in links))
            create_links = [link for link in links if link.get("href") == "/notices/new"]
            self.assertEqual(bool(create_links), bool(user.is_admin))
        self.sign_in(self.student)
        self.assertEqual(self.client.get("/notices/new").status_code, 403)
        self.assertEqual(self.post_notice(filename="학생 업로드.pptx").status_code, 403)
        self.assertEqual(Notice.query.count(), 0)

    def test_profile_and_notice_navigation_is_visible_on_dashboard_and_secondary_pages(self):
        for user in (self.student, self.admin):
            self.sign_in(user)
            for url in ("/", "/notices", "/auth/profile"):
                with self.subTest(user=user.username, path=url):
                    with patch("app.routes.main.get_weekly_rankings", return_value=[]):
                        response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    links = _Elements(response.get_data(as_text=True)).matching("a")
                    self.assertTrue(any(link.get("href") == "/auth/profile" for link in links))
                    self.assertTrue(any(link.get("href") == "/notices" for link in links))


if __name__ == "__main__":
    unittest.main()
