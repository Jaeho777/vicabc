"""Notice attachment regression tests using an isolated, temporary application.

Run with ``python -m unittest discover -s tests -v``. These tests never connect
to the production database or use the normal application startup hooks.
"""

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from flask import Flask, g
from jinja2 import ChoiceLoader, DictLoader

from app.extensions import db, login_manager
from app.models.notice import Notice
from app.models.notice_attachment import NoticeAttachment
from app.models.user import User
from app.routes import main_bp
from app.routes.auth import auth_bp
from app.services.notice_attachments import _validate_pptx


def presentation_bytes(extra_members=None):
    """Build a small, internally consistent PPTX package without dependencies."""
    members = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/ppt/presentation.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
            '<Override PartName="/ppt/slides/slide1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="ppt/presentation.xml"/></Relationships>'
        ),
        "ppt/presentation.xml": (
            '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>'
            '<p:sldSz cx="9144000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/>'
            "</p:presentation>"
        ),
        "ppt/_rels/presentation.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
            'Target="slides/slide1.xml"/></Relationships>'
        ),
        "ppt/slides/slide1.xml": (
            '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:cSld><p:spTree/></p:cSld></p:sld>'
        ),
    }
    members.update(extra_members or {})
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


class NoticeAttachmentTests(unittest.TestCase):
    def test_python310_spooled_stream_without_seekable_is_supported(self):
        class LegacyStream:
            def __init__(self, data):
                self.buffer = io.BytesIO(data)

            def read(self, size=-1):
                return self.buffer.read(size)

            def seek(self, offset, whence=0):
                return self.buffer.seek(offset, whence)

            def tell(self):
                return self.buffer.tell()

        stream = LegacyStream(presentation_bytes())
        self.assertFalse(hasattr(stream, "seekable"))
        _validate_pptx(stream)

    def setUp(self):
        self.upload_directory = tempfile.TemporaryDirectory(prefix="vic-notice-test-")
        self.app = Flask("app")
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="notice-tests-only-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            NOTICE_UPLOAD_DIR=self.upload_directory.name,
            NOTICE_MAX_ATTACHMENT_BYTES=20 * 1024 * 1024,
        )
        # Keep the actual notice templates while isolating unrelated navigation.
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            self.app.jinja_loader,
        ])
        db.init_app(self.app)
        login_manager.init_app(self.app)
        self.app.register_blueprint(auth_bp)
        self.app.register_blueprint(main_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.admin = self.make_user("notice-admin", is_admin=True)
        self.student = self.make_user("notice-student", is_admin=False)
        db.session.add_all([self.admin, self.student])
        db.session.commit()
        self.client = self.app.test_client()
        self.sign_in(self.admin)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()
        self.upload_directory.cleanup()

    @staticmethod
    def make_user(username, is_admin):
        return User(
            username=username,
            password_hash="unused-test-password-hash",
            full_name="공지 테스트",
            gender="기타",
            age=15,
            church="테스트",
            grade=1,
            parent_phone="01000000000",
            security_question="테스트",
            security_answer="테스트",
            is_admin=is_admin,
        )

    def sign_in(self, user):
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()
            session["_user_id"] = str(user.id)
            session["_fresh"] = True
            session["notice_csrf_token"] = "notice-test-csrf"

    def post_notice(self, url="/notices/new", filename=None, content=None, **fields):
        data = {
            "title": "수학 학습 안내",
            "body": "이번 주 수업 자료입니다.",
            "csrf_token": "notice-test-csrf",
        }
        data.update(fields)
        if filename is not None:
            data["attachment"] = (
                io.BytesIO(presentation_bytes() if content is None else content),
                filename,
            )
        return self.client.post(url, data=data, content_type="multipart/form-data")

    def create_notice(self, filename="수학 수업자료.pptx"):
        response = self.post_notice(filename=filename)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notice.query.count(), 1)
        return Notice.query.one()

    def stored_files(self):
        return [path for path in Path(self.upload_directory.name).rglob("*") if path.is_file()]

    def test_admin_creates_and_student_downloads_unicode_attachment(self):
        payload = presentation_bytes()
        response = self.post_notice(filename="수학 수업자료.pptx", content=payload)
        self.assertEqual(response.status_code, 302)
        notice = Notice.query.one()
        attachment = notice.attachment
        self.assertEqual(attachment.original_name, "수학 수업자료.pptx")
        self.assertEqual(attachment.size_bytes, len(payload))
        self.assertEqual(len(self.stored_files()), 1)
        self.assertEqual(self.stored_files()[0].read_bytes(), payload)
        self.assertNotEqual(attachment.storage_name, attachment.original_name)
        self.sign_in(self.student)
        response = self.client.get(f"/notices/{notice.id}/attachment")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, payload)
            disposition = response.headers["Content-Disposition"]
            self.assertTrue(disposition.startswith("attachment;"))
            self.assertIn("filename*=UTF-8''" + quote(attachment.original_name), disposition)
        finally:
            response.close()

    def test_anonymous_download_requires_login(self):
        notice = self.create_notice()
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()
        response = self.client.get(f"/notices/{notice.id}/attachment")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.headers["Location"])

    def test_student_cannot_manage_notices(self):
        notice = self.create_notice()
        self.sign_in(self.student)
        for url in ("/notices/new", f"/notices/{notice.id}/edit"):
            with self.subTest(method="GET", url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        for url in ("/notices/new", f"/notices/{notice.id}/edit", f"/notices/{notice.id}/delete"):
            with self.subTest(method="POST", url=url):
                self.assertEqual(self.post_notice(url).status_code, 403)
        self.assertEqual(Notice.query.count(), 1)
        self.assertEqual(NoticeAttachment.query.count(), 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_every_notice_mutation_requires_csrf(self):
        notice = self.create_notice()
        for url in ("/notices/new", f"/notices/{notice.id}/edit", f"/notices/{notice.id}/delete"):
            with self.subTest(url=url):
                response = self.client.post(url, data={"title": "변경 시도"})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Notice.query.one().title, "수학 학습 안내")
        self.assertEqual(len(self.stored_files()), 1)

    def test_create_form_exposes_csrf_and_upload_field(self):
        response = self.client.get("/notices/new")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('name="csrf_token"', html)
        self.assertIn('name="attachment"', html)
        self.assertIn('enctype="multipart/form-data"', html)

    def test_invalid_files_leave_no_database_record_or_file(self):
        malformed_crc = bytearray(presentation_bytes())
        marker = b"<p:cSld><p:spTree/></p:cSld>"
        marker_offset = malformed_crc.index(marker)
        malformed_crc[marker_offset] ^= 1
        cases = [
            ("program.exe", presentation_bytes()),
            ("pretend.pptx", b"not a zip archive"),
            ("pretend.ppt", b"not an OLE document"),
            ("unsafe.pptx", presentation_bytes({"../escaped.txt": "unsafe"})),
            ("corrupt.pptx", bytes(malformed_crc)),
        ]
        for filename, content in cases:
            with self.subTest(filename=filename):
                response = self.post_notice(filename=filename, content=content)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(Notice.query.count(), 0)
                self.assertEqual(NoticeAttachment.query.count(), 0)
                self.assertEqual(self.stored_files(), [])

    def test_oversize_file_is_rejected_without_persisting(self):
        self.app.config["NOTICE_MAX_ATTACHMENT_BYTES"] = 128
        response = self.post_notice(filename="large.pptx", content=presentation_bytes())
        self.assertEqual(response.status_code, 413)
        self.assertEqual(Notice.query.count(), 0)
        self.assertEqual(NoticeAttachment.query.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_empty_title_does_not_store_attachment(self):
        response = self.post_notice(filename="unused.pptx", title="   ")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Notice.query.count(), 0)
        self.assertEqual(self.stored_files(), [])

    def test_replacement_removes_only_previous_attachment(self):
        notice = self.create_notice()
        old_path = self.stored_files()[0]
        unrelated = Path(self.upload_directory.name) / "unrelated.keep"
        unrelated.write_bytes(b"keep")
        response = self.post_notice(f"/notices/{notice.id}/edit", filename="독서 안내.pptx")
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual(Notice.query.one().attachment.original_name, "독서 안내.pptx")
        self.assertEqual(NoticeAttachment.query.count(), 1)
        self.assertFalse(old_path.exists())
        self.assertEqual(unrelated.read_bytes(), b"keep")
        self.assertEqual(len(self.stored_files()), 2)

    def test_invalid_replacement_preserves_existing_notice_and_file(self):
        notice = self.create_notice()
        old_storage_name = notice.attachment.storage_name
        old_path = self.stored_files()[0]
        old_payload = old_path.read_bytes()
        response = self.post_notice(
            f"/notices/{notice.id}/edit",
            filename="bad.pptx",
            content=b"invalid",
            title="저장되면 안 되는 제목",
        )
        self.assertEqual(response.status_code, 400)
        db.session.expire_all()
        notice = Notice.query.one()
        self.assertEqual(notice.title, "수학 학습 안내")
        self.assertEqual(notice.attachment.storage_name, old_storage_name)
        self.assertEqual(old_path.read_bytes(), old_payload)
        self.assertEqual(NoticeAttachment.query.count(), 1)
        self.assertEqual(len(self.stored_files()), 1)

    def test_edit_without_new_attachment_preserves_it(self):
        notice = self.create_notice()
        old_storage_name = notice.attachment.storage_name
        response = self.post_notice(f"/notices/{notice.id}/edit", title="수정된 안내")
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertEqual(Notice.query.one().attachment.storage_name, old_storage_name)
        self.assertEqual(len(self.stored_files()), 1)

    def test_failed_database_commit_preserves_previous_attachment_and_cleans_new_file(self):
        notice = self.create_notice()
        old_storage_name = notice.attachment.storage_name
        old_path = self.stored_files()[0]
        original_payload = old_path.read_bytes()
        with patch.object(db.session, "commit", side_effect=RuntimeError("simulated commit failure")):
            with self.assertRaisesRegex(RuntimeError, "simulated commit failure"):
                self.post_notice(
                    f"/notices/{notice.id}/edit",
                    filename="교체하면 안 되는 자료.pptx",
                    title="저장되면 안 되는 제목",
                )
        db.session.expire_all()
        preserved = Notice.query.one()
        self.assertEqual(preserved.title, "수학 학습 안내")
        self.assertEqual(preserved.attachment.storage_name, old_storage_name)
        self.assertEqual(NoticeAttachment.query.count(), 1)
        self.assertEqual(old_path.read_bytes(), original_payload)
        self.assertEqual(self.stored_files(), [old_path])

    def test_removing_attachment_preserves_notice_and_unrelated_file(self):
        notice = self.create_notice()
        original_path = self.stored_files()[0]
        unrelated = Path(self.upload_directory.name) / "unrelated.keep"
        unrelated.write_bytes(b"keep")
        response = self.post_notice(f"/notices/{notice.id}/edit", remove_attachment="1")
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        self.assertIsNone(Notice.query.one().attachment)
        self.assertEqual(NoticeAttachment.query.count(), 0)
        self.assertFalse(original_path.exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(self.client.get(f"/notices/{notice.id}/attachment").status_code, 404)

    def test_deleting_notice_removes_attachment_and_keeps_other_files(self):
        notice = self.create_notice()
        original_path = self.stored_files()[0]
        unrelated = Path(self.upload_directory.name) / "unrelated.keep"
        unrelated.write_bytes(b"keep")
        response = self.post_notice(f"/notices/{notice.id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Notice.query.count(), 0)
        self.assertEqual(NoticeAttachment.query.count(), 0)
        self.assertFalse(original_path.exists())
        self.assertTrue(unrelated.exists())

    def test_filename_and_body_are_escaped_in_notice_detail(self):
        filename = '<img src=x onerror=alert(1)>.pptx'
        response = self.post_notice(filename=filename, body="<script>alert(1)</script>")
        self.assertEqual(response.status_code, 302)
        response = self.client.get(response.headers["Location"])
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;img", html)


if __name__ == "__main__":
    unittest.main()
