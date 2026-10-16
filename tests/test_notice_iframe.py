"""Notice list routing and same-origin iframe regression tests.

The real notice templates run against an isolated in-memory database. These
tests never contact the production server or invoke a document converter.
"""

import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from flask import g

import test_notice_attachments as fixtures
from app.extensions import db
from app.models.notice import Notice


class _DocumentElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def matching(self, tag):
        return [attributes for name, attributes in self.elements if name == tag]


class NoticeIframeTests(unittest.TestCase):
    tearDown = fixtures.NoticeAttachmentTests.tearDown
    make_user = staticmethod(fixtures.NoticeAttachmentTests.make_user)
    sign_in = fixtures.NoticeAttachmentTests.sign_in
    post_notice = fixtures.NoticeAttachmentTests.post_notice
    create_notice = fixtures.NoticeAttachmentTests.create_notice

    def setUp(self):
        fixtures.NoticeAttachmentTests.setUp(self)
        # Isolate the dashboard from unrelated learning blueprints while still
        # rendering its real notice links, including the formerly broken URL.
        for endpoint in (
            "exam.voca_index", "voca.index", "story.story_exam_index",
            "story.index", "village.exam", "village.index",
        ):
            self.app.add_url_rule(
                "/__test/" + endpoint.replace(".", "/"),
                endpoint=endpoint,
                view_func=lambda: "unused test endpoint",
            )
        self.notice = self.create_notice()

    def sign_out(self):
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()

    def viewer_url(self, notice_id=None):
        return f"/notices/{self.notice.id if notice_id is None else notice_id}/preview/viewer"

    def test_both_notice_list_paths_work_for_admin_and_student_without_redirect(self):
        for user in (self.admin, self.student):
            self.sign_in(user)
            for url in ("/notices", "/notices/"):
                with self.subTest(user=user.username, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn("Location", response.headers)
                    self.assertIn(
                        f'href="/notices/{self.notice.id}"',
                        response.get_data(as_text=True),
                    )

    def test_both_notice_list_paths_require_login(self):
        self.sign_out()
        for url in ("/notices", "/notices/"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth/login", response.headers["Location"])

    def test_dashboard_notice_link_resolves_to_working_list(self):
        self.sign_in(self.student)
        with patch("app.routes.main.get_weekly_rankings", return_value=[]):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        links = _DocumentElements(response.get_data(as_text=True)).matching("a")
        notice_links = [link["href"] for link in links if link.get("href") == "/notices"]
        self.assertEqual(notice_links, ["/notices"])
        self.assertEqual(self.client.get(notice_links[0]).status_code, 200)

    def test_detail_embeds_viewer_and_offers_a_new_tab_fallback(self):
        self.sign_in(self.student)
        response = self.client.get(f"/notices/{self.notice.id}")
        self.assertEqual(response.status_code, 200)
        document = _DocumentElements(response.get_data(as_text=True))
        frames = document.matching("iframe")
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0].get("src"), self.viewer_url())
        self.assertTrue(frames[0].get("title"))
        self.assertIn("allowfullscreen", frames[0])
        fallback = [
            link for link in document.matching("a")
            if link.get("href") == self.viewer_url() and link.get("target") == "_blank"
        ]
        self.assertEqual(len(fallback), 1)
        self.assertIn("noopener", fallback[0].get("rel", "").split())
        self.assertFalse(any("data-notice-preview" in attrs for _, attrs in document.elements))

    def test_viewer_is_available_to_admin_and_student_without_starting_conversion(self):
        for user in (self.admin, self.student):
            self.sign_in(user)
            with self.subTest(user=user.username):
                with (
                    patch("app.routes.main.preview_status") as status,
                    patch("app.routes.main.prepare_preview") as prepare,
                ):
                    response = self.client.get(self.viewer_url())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.mimetype, "text/html")
                status.assert_not_called()
                prepare.assert_not_called()

    def test_viewer_requires_login_and_does_not_leak_private_document(self):
        self.sign_out()
        response = self.client.get(self.viewer_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])
        self.assertNotIn(self.notice.attachment.original_name, response.get_data(as_text=True))
        self.assertNotIn("notice-test-csrf", response.get_data(as_text=True))

    def test_viewer_uses_private_no_store_and_same_origin_embedding_headers(self):
        self.sign_in(self.student)
        response = self.client.get(self.viewer_url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cache_control.private)
        self.assertTrue(response.cache_control.no_store)
        self.assertIn("Cookie", response.vary)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        directives = {}
        for directive in response.headers.get("Content-Security-Policy", "").split(";"):
            parts = directive.split()
            if parts:
                directives[parts[0]] = parts[1:]
        self.assertEqual(directives, {
            "default-src": ["'none'"],
            "script-src": ["'self'"],
            "style-src": ["'self'"],
            "img-src": ["'self'", "blob:"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'self'"],
            "base-uri": ["'none'"],
            "form-action": ["'none'"],
            "object-src": ["'none'"],
        })

    def test_viewer_exposes_authenticated_same_origin_api_urls_and_session_csrf(self):
        self.sign_in(self.student)
        response = self.client.get(self.viewer_url())
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        document = _DocumentElements(html)
        viewers = [attrs for _, attrs in document.elements if "data-notice-preview" in attrs]
        self.assertEqual(len(viewers), 1)
        viewer = viewers[0]
        prefix = f"/notices/{self.notice.id}/preview"
        self.assertEqual(viewer.get("data-status-url"), prefix)
        self.assertEqual(viewer.get("data-prepare-url"), prefix + "/prepare")
        self.assertEqual(viewer.get("data-page-url"), prefix + "/pages/0")
        self.assertEqual(viewer.get("data-csrf-token"), "notice-test-csrf")
        for selector in ("data-preview-prev", "data-preview-next", "data-preview-expand"):
            self.assertTrue(any(selector in attributes for _, attributes in document.elements))
        scripts = document.matching("script")
        self.assertEqual(len(scripts), 1)
        self.assertTrue(scripts[0].get("src", "").startswith("/static/js/notice-preview.js"))
        for tag, attributes in document.elements:
            self.assertFalse(any(name.lower().startswith("on") for name in attributes))
            if tag in ("script", "link"):
                source = attributes.get("src", attributes.get("href", ""))
                self.assertTrue(source.startswith("/static/"), (tag, source))
        self.assertNotIn("view.officeapps.live.com", html)
        self.assertNotIn("docs.google.com/gview", html)

    def test_viewer_escapes_filename_and_never_executes_notice_markup(self):
        self.notice.title = '<script>alert("notice-title")</script>'
        self.notice.body = '<script>alert("notice-body")</script>'
        self.notice.attachment.original_name = '<svg onload=alert("file")>.pptx'
        db.session.commit()
        response = self.client.get(self.viewer_url())
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn(self.notice.title, html)
        self.assertNotIn(self.notice.body, html)
        self.assertNotIn(self.notice.attachment.original_name, html)
        self.assertIn("&lt;svg", html)
        self.assertFalse(_DocumentElements(html).matching("svg"))

    def test_viewer_without_attachment_is_not_found(self):
        notice = Notice(title="첨부 없는 공지", body="본문")
        db.session.add(notice)
        db.session.commit()
        response = self.client.get(self.viewer_url(notice.id))
        self.assertEqual(response.status_code, 404)

    def test_viewer_for_unknown_notice_is_not_found(self):
        self.assertEqual(self.client.get(self.viewer_url(999999)).status_code, 404)

    def test_viewer_with_missing_original_file_is_not_found(self):
        original = Path(self.upload_directory.name) / self.notice.attachment.storage_name
        original.unlink()
        self.assertEqual(self.client.get(self.viewer_url()).status_code, 404)

    def test_viewer_is_get_only_and_does_not_create_or_replace_files(self):
        before = list(Path(self.upload_directory.name).iterdir())
        response = self.client.post(self.viewer_url(), data={"csrf_token": "notice-test-csrf"})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(list(Path(self.upload_directory.name).iterdir()), before)


if __name__ == "__main__":
    unittest.main()
