"""Authenticated notice preview regression tests with no production services.

Run with ``python -m unittest discover -s tests -v``. The shared fixture uses
an in-memory SQLite database; renderers are mocked and all files are temporary.
"""

import base64
import fcntl
import io
import json
import os
import struct
import subprocess
import tarfile
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, g

import test_notice_attachments as fixtures
from app.extensions import db
from app.models.notice import Notice
from app.services import notice_preview


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a4xkAAAAASUVORK5CYII="
)


class NoticePreviewRouteTests(unittest.TestCase):
    # Reuse only fixture helpers, not the attachment suite's test methods.
    tearDown = fixtures.NoticeAttachmentTests.tearDown
    make_user = staticmethod(fixtures.NoticeAttachmentTests.make_user)
    sign_in = fixtures.NoticeAttachmentTests.sign_in
    post_notice = fixtures.NoticeAttachmentTests.post_notice
    create_notice = fixtures.NoticeAttachmentTests.create_notice

    def setUp(self):
        fixtures.NoticeAttachmentTests.setUp(self)
        self.preview_directory = tempfile.TemporaryDirectory(prefix="vic-preview-test-")
        self.addCleanup(self.preview_directory.cleanup)
        self.app.config.update(
            NOTICE_PREVIEW_DIR=self.preview_directory.name,
            NOTICE_PREVIEW_ENABLED=False,
        )
        self.notice = self.create_notice()

    def sign_out(self):
        g.pop("_login_user", None)
        with self.client.session_transaction() as session:
            session.clear()

    def preview_url(self, suffix=""):
        return f"/notices/{self.notice.id}/preview{suffix}"

    def post_prepare(self, csrf_token="notice-test-csrf"):
        fields = {} if csrf_token is None else {"csrf_token": csrf_token}
        return self.client.post(self.preview_url("/prepare"), data=fields)

    def test_anonymous_cannot_check_prepare_or_read_slides(self):
        self.sign_out()
        with (
            patch("app.routes.main.preview_status") as status,
            patch("app.routes.main.prepare_preview") as prepare,
            patch("app.routes.main.preview_page_path") as page,
        ):
            responses = [
                self.client.get(self.preview_url()),
                self.post_prepare(),
                self.client.get(self.preview_url("/pages/1")),
            ]
        for response in responses:
            with self.subTest(url=response.request.path):
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth/login", response.headers["Location"])
        status.assert_not_called()
        prepare.assert_not_called()
        page.assert_not_called()

    def test_student_can_read_preview_status_without_csrf(self):
        self.sign_in(self.student)
        payload = {"state": "ready", "pages": 3, "message": "미리보기가 준비되었습니다."}
        with patch("app.routes.main.preview_status", return_value=payload) as status:
            response = self.client.get(self.preview_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)
        self.assertTrue(response.cache_control.private)
        self.assertTrue(response.cache_control.no_store)
        self.assertIn("Cookie", response.vary)
        status.assert_called_once_with(self.notice.attachment)

    def test_student_can_prepare_preview_with_valid_csrf(self):
        self.sign_in(self.student)
        payload = {"state": "ready", "pages": 2, "message": "미리보기가 준비되었습니다."}
        with patch("app.routes.main.prepare_preview", return_value=payload) as prepare:
            response = self.post_prepare()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), payload)
        prepare.assert_called_once_with(self.notice.attachment)

    def test_notice_detail_exposes_same_origin_iframe_instead_of_inline_viewer(self):
        self.sign_in(self.student)
        response = self.client.get(f"/notices/{self.notice.id}")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("<iframe", html)
        self.assertIn(f'src="{self.preview_url("/viewer")}"', html)
        self.assertNotIn("data-status-url=", html)
        self.assertNotIn("data-prepare-url=", html)
        self.assertNotIn("view.officeapps.live.com", html)
        self.assertNotIn("docs.google.com/gview", html)

    def test_preparation_requires_valid_session_csrf(self):
        for csrf_token in (None, "", "wrong-token", "한글토큰"):
            with self.subTest(csrf_token=csrf_token):
                with patch("app.routes.main.prepare_preview") as prepare:
                    response = self.post_prepare(csrf_token)
                self.assertEqual(response.status_code, 400)
                prepare.assert_not_called()

    def test_preparation_is_post_only(self):
        with patch("app.routes.main.prepare_preview") as prepare:
            response = self.client.get(self.preview_url("/prepare"))
        self.assertEqual(response.status_code, 405)
        prepare.assert_not_called()

    def test_preparation_rejects_oversized_requests_before_rendering(self):
        with patch("app.routes.main.prepare_preview") as prepare:
            response = self.client.post(
                self.preview_url("/prepare"),
                data={"csrf_token": "notice-test-csrf", "unused": "x" * 5000},
            )
        self.assertEqual(response.status_code, 413)
        prepare.assert_not_called()

    def test_preparation_state_maps_to_explicit_http_status(self):
        cases = [
            ("ready", 200),
            ("pending", 202),
            ("busy", 202),
            ("error", 422),
            ("unavailable", 503),
        ]
        for state, expected_status in cases:
            with self.subTest(state=state):
                payload = {"state": state, "pages": 2 if state == "ready" else 0, "message": "처리 상태"}
                with patch("app.routes.main.prepare_preview", return_value=payload):
                    response = self.post_prepare()
                self.assertEqual(response.status_code, expected_status)
                self.assertEqual(response.get_json(), payload)
                self.assertTrue(response.cache_control.private)
                self.assertTrue(response.cache_control.no_store)

    def test_busy_preview_reports_retry_after_to_clients(self):
        payload = {"state": "busy", "pages": 0, "message": "다른 자료를 준비 중입니다.", "retry_after": 2}
        with patch("app.routes.main.prepare_preview", return_value=payload):
            response = self.post_prepare()
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.headers["Retry-After"], "2")

    def test_status_does_not_start_the_converter(self):
        payload = {"state": "pending", "pages": 0, "message": "준비할 수 있습니다."}
        with (
            patch("app.routes.main.preview_status", return_value=payload),
            patch("app.routes.main.prepare_preview") as prepare,
        ):
            response = self.client.get(self.preview_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["state"], "pending")
        prepare.assert_not_called()

    def test_student_receives_png_with_private_no_store_headers(self):
        self.sign_in(self.student)
        png_payload = b"\x89PNG\r\n\x1a\nprivate-slide-test"
        path = Path(self.preview_directory.name) / "page-0001.png"
        path.write_bytes(png_payload)
        with patch("app.routes.main.preview_page_path", return_value=path) as page:
            response = self.client.get(self.preview_url("/pages/1"))
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, png_payload)
            self.assertEqual(response.mimetype, "image/png")
            self.assertIn("private", response.cache_control)
            self.assertTrue(response.cache_control.no_store)
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("Cookie", response.vary)
            self.assertNotIn("ETag", response.headers)
            disposition = response.headers.get("Content-Disposition", "")
            self.assertFalse(disposition.startswith("attachment;"))
        finally:
            response.close()
        page.assert_called_once_with(self.notice.attachment, 1)

    def test_missing_or_out_of_bounds_slide_is_not_served(self):
        for error in (FileNotFoundError("missing"), ValueError("out of range")):
            with self.subTest(error=type(error).__name__):
                with patch("app.routes.main.preview_page_path", side_effect=error):
                    response = self.client.get(self.preview_url("/pages/101"))
                self.assertEqual(response.status_code, 404)

    def test_non_integer_and_negative_page_paths_are_rejected(self):
        with patch("app.routes.main.preview_page_path") as page:
            for page_number in ("-1", "not-a-page", "..%2F..%2Fetc%2Fpasswd"):
                with self.subTest(page_number=page_number):
                    response = self.client.get(self.preview_url(f"/pages/{page_number}"))
                    self.assertEqual(response.status_code, 404)
        page.assert_not_called()

    def test_notice_without_attachment_has_no_preview_routes(self):
        no_attachment = Notice(title="첨부 없는 공지", body="일반 공지")
        db.session.add(no_attachment)
        db.session.commit()
        prefix = f"/notices/{no_attachment.id}/preview"
        with (
            patch("app.routes.main.preview_status") as status,
            patch("app.routes.main.prepare_preview") as prepare,
            patch("app.routes.main.preview_page_path") as page,
        ):
            responses = [
                self.client.get(prefix),
                self.client.post(prefix + "/prepare", data={"csrf_token": "notice-test-csrf"}),
                self.client.get(prefix + "/pages/1"),
            ]
        for response in responses:
            with self.subTest(url=response.request.path):
                self.assertEqual(response.status_code, 404)
        status.assert_not_called()
        prepare.assert_not_called()
        page.assert_not_called()

    def test_unknown_notice_returns_not_found_without_conversion(self):
        with (
            patch("app.routes.main.preview_status") as status,
            patch("app.routes.main.prepare_preview") as prepare,
            patch("app.routes.main.preview_page_path") as page,
        ):
            responses = [
                self.client.get("/notices/999999/preview"),
                self.client.post(
                    "/notices/999999/preview/prepare",
                    data={"csrf_token": "notice-test-csrf"},
                ),
                self.client.get("/notices/999999/preview/pages/1"),
            ]
        for response in responses:
            with self.subTest(url=response.request.path):
                self.assertEqual(response.status_code, 404)
        status.assert_not_called()
        prepare.assert_not_called()
        page.assert_not_called()

    def test_missing_original_file_never_starts_conversion_or_serves_cache(self):
        original = Path(self.upload_directory.name) / self.notice.attachment.storage_name
        original.unlink()
        with (
            patch("app.routes.main.preview_status") as status,
            patch("app.routes.main.prepare_preview") as prepare,
            patch("app.routes.main.preview_page_path") as page,
        ):
            responses = [
                self.client.get(self.preview_url()),
                self.post_prepare(),
                self.client.get(self.preview_url("/pages/1")),
            ]
        for response in responses:
            self.assertEqual(response.status_code, 404)
        status.assert_not_called()
        prepare.assert_not_called()
        page.assert_not_called()

    def test_current_attachment_is_resolved_each_time_after_replacement(self):
        previous_attachment = self.notice.attachment
        response = self.post_notice(
            f"/notices/{self.notice.id}/edit", filename="새 수업자료.pptx"
        )
        self.assertEqual(response.status_code, 302)
        db.session.expire_all()
        current_attachment = db.session.get(Notice, self.notice.id).attachment
        self.assertNotEqual(current_attachment.storage_name, previous_attachment.storage_name)
        payload = {"state": "pending", "pages": 0, "message": "새 자료입니다."}
        with patch("app.routes.main.preview_status", return_value=payload) as status:
            response = self.client.get(self.preview_url())
        self.assertEqual(response.status_code, 200)
        status.assert_called_once_with(current_attachment)

    def seed_private_cache(self):
        directory = Path(self.preview_directory.name) / self.notice.attachment.storage_name
        directory.mkdir()
        (directory / "page-0001.png").write_bytes(TINY_PNG)
        return directory

    def test_replacing_attachment_removes_its_previous_slide_cache(self):
        directory = self.seed_private_cache()
        response = self.post_notice(
            f"/notices/{self.notice.id}/edit", filename="교체된 수업자료.pptx"
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(directory.exists())

    def test_removing_attachment_removes_cached_slides_but_preserves_notice(self):
        directory = self.seed_private_cache()
        response = self.post_notice(f"/notices/{self.notice.id}/edit", remove_attachment="1")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(directory.exists())
        self.assertEqual(Notice.query.count(), 1)
        self.assertIsNone(Notice.query.one().attachment)

    def test_deleting_notice_removes_its_cached_slides(self):
        directory = self.seed_private_cache()
        response = self.post_notice(f"/notices/{self.notice.id}/delete")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(directory.exists())
        self.assertEqual(Notice.query.count(), 0)


class NoticePreviewServiceTests(unittest.TestCase):
    """Cache validation and bounded worker orchestration, without systemd/office."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="vic-preview-service-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.uploads = self.root / "uploads"
        self.uploads.mkdir()
        self.cache = self.root / "previews"
        self.work = self.root / "work"
        self.work.mkdir()
        self.storage_name = "a" * 32 + ".pptx"
        self.attachment = SimpleNamespace(storage_name=self.storage_name)
        self.source = self.uploads / self.storage_name
        self.source.write_bytes(b"private-original-presentation")
        self.app = Flask("notice-preview-service-test")
        self.app.config.update(
            NOTICE_UPLOAD_DIR=str(self.uploads),
            NOTICE_PREVIEW_DIR=str(self.cache),
            NOTICE_PREVIEW_WORK_ROOT=str(self.work),
            NOTICE_PREVIEW_ENABLED=True,
            NOTICE_PREVIEW_MAX_PAGES=100,
            NOTICE_PREVIEW_MAX_BYTES=200 * 1024 * 1024,
            NOTICE_PREVIEW_RETRY_SECONDS=60,
        )
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)

    def write_cache(self, pages=1, **updates):
        directory = self.cache / self.storage_name
        directory.mkdir(parents=True, exist_ok=True)
        manifest = {
            "version": 1,
            "storage_name": self.storage_name,
            "state": "ready",
            "pages": pages,
        }
        manifest.update(updates)
        (directory / "preview.json").write_text(json.dumps(manifest), encoding="utf-8")
        if type(pages) is int and 1 <= pages <= 100:
            for page in range(1, pages + 1):
                (directory / f"page-{page:04d}.png").write_bytes(TINY_PNG)
        return directory

    def fake_renderer(self, job):
        self.assertEqual((job / "input.pptx").read_bytes(), self.source.read_bytes())
        output = job / "output"
        output.mkdir()
        (output / "preview.json").write_text('{"pages": 2}', encoding="utf-8")
        for page in (1, 2):
            (output / f"page-{page:04d}.png").write_bytes(TINY_PNG)

    def prepare_with_fake_worker(self, renderer=None):
        user = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
        with (
            patch.object(notice_preview, "_renderer_available", return_value=True),
            patch.object(notice_preview.pwd, "getpwnam", return_value=user),
            patch.object(notice_preview.os, "chown"),
            patch.object(notice_preview, "_run_renderer", side_effect=renderer or self.fake_renderer),
        ):
            return notice_preview.prepare_preview(self.attachment)

    def test_missing_cache_is_pending_only_when_isolated_renderer_is_available(self):
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")
        with patch.object(notice_preview, "_renderer_available", return_value=False):
            self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "unavailable")

    def test_ready_cache_does_not_require_running_converter(self):
        directory = self.write_cache(pages=2)
        with patch.object(notice_preview, "_renderer_available", return_value=False):
            status = notice_preview.preview_status(self.attachment)
            path = notice_preview.preview_page_path(self.attachment, 2)
        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["pages"], 2)
        self.assertEqual(path, directory / "page-0002.png")

    def test_cached_preview_is_unavailable_when_original_disappears(self):
        self.write_cache()
        self.source.unlink()
        self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "unavailable")
        with self.assertRaises(FileNotFoundError):
            notice_preview.preview_page_path(self.attachment, 1)

    def test_invalid_storage_keys_never_escape_private_directory(self):
        for name in ("../outside", "/etc/passwd", "b" * 32 + ".pdf", "A" * 32 + ".pptx", None):
            with self.subTest(storage_name=name):
                with self.assertRaises(ValueError):
                    notice_preview.preview_status(SimpleNamespace(storage_name=name))

    def test_manifest_page_count_must_be_integer_and_within_limit(self):
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            for pages in (0, -1, True, "1", 101):
                with self.subTest(pages=pages):
                    self.write_cache(pages=pages)
                    self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")

    def test_manifest_version_and_storage_name_must_match_attachment(self):
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            for updates in ({"version": 2}, {"storage_name": "b" * 32 + ".pptx"}):
                with self.subTest(updates=updates):
                    self.write_cache(**updates)
                    self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")

    def test_truncated_png_and_oversized_image_dimensions_invalidate_cache(self):
        directory = self.write_cache()
        path = directory / "page-0001.png"
        header = TINY_PNG[:16]
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            for payload in (b"not an image", header + struct.pack(">II", 1601, 1), header + struct.pack(">II", 1, 0)):
                with self.subTest(payload=payload):
                    path.write_bytes(payload)
                    self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")

    def test_cache_does_not_follow_page_or_manifest_symbolic_links(self):
        directory = self.write_cache()
        outside = self.root / "outside.png"
        outside.write_bytes(TINY_PNG)
        page = directory / "page-0001.png"
        page.unlink()
        page.symlink_to(outside)
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")
        page.unlink()
        page.write_bytes(TINY_PNG)
        manifest = directory / "preview.json"
        outside_manifest = self.root / "outside.json"
        manifest.replace(outside_manifest)
        manifest.symlink_to(outside_manifest)
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")

    def test_page_number_rejects_zero_negative_boolean_and_non_integer(self):
        self.write_cache()
        for page in (0, -1, True, "1", None):
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    notice_preview.preview_page_path(self.attachment, page)
        with self.assertRaises(FileNotFoundError):
            notice_preview.preview_page_path(self.attachment, 2)

    def test_error_cooldown_prevents_repeated_conversion_attempts(self):
        self.write_cache(state="error", failed_at=time.time())
        with patch.object(notice_preview, "_run_renderer") as renderer:
            status = notice_preview.prepare_preview(self.attachment)
        self.assertEqual(status["state"], "error")
        self.assertGreater(status["retry_after"], 0)
        renderer.assert_not_called()
        self.write_cache(state="error", failed_at=time.time() - 61)
        with patch.object(notice_preview, "_renderer_available", return_value=True):
            self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "pending")

    def test_successful_worker_output_is_private_cached_and_job_is_removed(self):
        result = self.prepare_with_fake_worker()
        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["pages"], 2)
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "ready")
        page = notice_preview.preview_page_path(self.attachment, 1)
        self.assertEqual(page.read_bytes(), TINY_PNG)
        self.assertEqual(page.stat().st_mode & 0o777, 0o600)
        self.assertEqual(page.parent.stat().st_mode & 0o777, 0o700)
        with patch.object(notice_preview, "_run_renderer") as renderer:
            self.assertEqual(notice_preview.prepare_preview(self.attachment)["state"], "ready")
        renderer.assert_not_called()

    def test_conversion_timeout_leaves_retryable_error_and_no_job(self):
        def timeout(job):
            raise subprocess.TimeoutExpired("isolated-worker", 75)

        with patch.object(self.app.logger, "exception"):
            result = self.prepare_with_fake_worker(timeout)
        self.assertEqual(result["state"], "error")
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertFalse(any(self.cache.glob(".staging-*")))
        self.assertEqual(notice_preview.preview_status(self.attachment)["state"], "error")

    def test_global_lock_bounds_concurrent_converter_processes(self):
        self.cache.mkdir()
        with (self.cache / ".conversion.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with (
                patch.object(notice_preview, "_renderer_available", return_value=True),
                patch.object(notice_preview, "_run_renderer") as renderer,
            ):
                result = notice_preview.prepare_preview(self.attachment)
        self.assertEqual(result["state"], "busy")
        self.assertEqual(result["retry_after"], 2)
        renderer.assert_not_called()

    def test_disappearing_original_during_conversion_discards_generated_cache(self):
        def remove_original(job):
            self.fake_renderer(job)
            self.source.unlink()

        result = self.prepare_with_fake_worker(remove_original)
        self.assertEqual(result["state"], "unavailable")
        self.assertFalse((self.cache / self.storage_name).exists())
        self.assertEqual(list(self.work.iterdir()), [])
        self.assertFalse(any(self.cache.glob(".staging-*")))

    def test_untrusted_worker_cannot_publish_symlinked_slide(self):
        outside = self.root / "outside.png"
        outside.write_bytes(TINY_PNG)

        def symlink_output(job):
            output = job / "output"
            output.mkdir()
            (output / "preview.json").write_text('{"pages": 1}', encoding="utf-8")
            (output / "page-0001.png").symlink_to(outside)

        with patch.object(self.app.logger, "exception"):
            result = self.prepare_with_fake_worker(symlink_output)
        self.assertEqual(result["state"], "error")
        self.assertFalse((self.cache / self.storage_name / "page-0001.png").exists())
        self.assertEqual(outside.read_bytes(), TINY_PNG)

    def test_removal_cleans_only_matching_cache_and_preserves_other_files(self):
        directory = self.write_cache()
        unrelated = self.cache / "unrelated.keep"
        unrelated.write_bytes(b"preserve")
        notice_preview.remove_preview(self.storage_name)
        self.assertFalse(directory.exists())
        self.assertEqual(unrelated.read_bytes(), b"preserve")
        with patch.object(self.app.logger, "exception"):
            notice_preview.remove_preview("../outside")
        self.assertEqual(unrelated.read_bytes(), b"preserve")

    def test_removal_unlinks_cache_symlink_without_deleting_its_target(self):
        outside = self.root / "outside"
        outside.mkdir()
        marker = outside / "keep.txt"
        marker.write_bytes(b"preserve")
        self.cache.mkdir()
        (self.cache / self.storage_name).symlink_to(outside, target_is_directory=True)
        notice_preview.remove_preview(self.storage_name)
        self.assertFalse((self.cache / self.storage_name).exists())
        self.assertEqual(marker.read_bytes(), b"preserve")

    def write_worker_archive(self, entries):
        archive = self.work / "worker-output.tar"
        with tarfile.open(archive, mode="w:") as bundle:
            for name, payload, kind in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                if kind == tarfile.REGTYPE:
                    member.size = len(payload)
                    bundle.addfile(member, io.BytesIO(payload))
                else:
                    member.linkname = "../../outside"
                    bundle.addfile(member)
        return archive

    def test_worker_archive_extracts_only_expected_private_flat_files(self):
        archive = self.write_worker_archive([
            ("preview.json", b'{"pages":1}', tarfile.REGTYPE),
            ("page-0001.png", TINY_PNG, tarfile.REGTYPE),
        ])
        output = self.work / "unpacked"
        notice_preview._unpack_output(archive, output)
        self.assertEqual((output / "page-0001.png").read_bytes(), TINY_PNG)
        self.assertEqual((output / "page-0001.png").stat().st_mode & 0o777, 0o600)
        self.assertEqual(output.stat().st_mode & 0o777, 0o700)

    def test_worker_archive_rejects_paths_links_duplicates_and_missing_manifest(self):
        manifest = ("preview.json", b'{"pages":1}', tarfile.REGTYPE)
        cases = [
            [manifest, ("../outside", b"unsafe", tarfile.REGTYPE)],
            [manifest, ("/etc/passwd", b"unsafe", tarfile.REGTYPE)],
            [manifest, ("folder/page-0001.png", TINY_PNG, tarfile.REGTYPE)],
            [manifest, ("page-0001.png", b"", tarfile.SYMTYPE)],
            [manifest, ("page-0001.png", b"", tarfile.LNKTYPE)],
            [manifest, ("page-0001.png", b"", tarfile.DIRTYPE)],
            [manifest, manifest],
            [("page-0001.png", TINY_PNG, tarfile.REGTYPE)],
            [("preview.json", b"x" * 4097, tarfile.REGTYPE)],
        ]
        for index, entries in enumerate(cases):
            with self.subTest(entries=entries):
                archive = self.write_worker_archive(entries)
                with self.assertRaises(ValueError):
                    notice_preview._unpack_output(archive, self.work / f"rejected-{index}")
        self.assertFalse((self.root / "outside").exists())

    def test_worker_archive_cannot_exceed_page_count_limit(self):
        self.app.config["NOTICE_PREVIEW_MAX_PAGES"] = 1
        archive = self.write_worker_archive([
            ("preview.json", b'{"pages":2}', tarfile.REGTYPE),
            ("page-0001.png", TINY_PNG, tarfile.REGTYPE),
            ("page-0002.png", TINY_PNG, tarfile.REGTYPE),
        ])
        with self.assertRaises(ValueError):
            notice_preview._unpack_output(archive, self.work / "too-many-pages")

    def test_worker_archive_unpacked_size_is_bounded(self):
        self.app.config["NOTICE_PREVIEW_MAX_BYTES"] = 1024 * 1024
        archive = self.write_worker_archive([
            ("preview.json", b'{"pages":2}', tarfile.REGTYPE),
            ("page-0001.png", b"x" * 700000, tarfile.REGTYPE),
            ("page-0002.png", b"x" * 700000, tarfile.REGTYPE),
        ])
        with self.assertRaises(ValueError):
            notice_preview._unpack_output(archive, self.work / "oversized-output")


if __name__ == "__main__":
    unittest.main()
