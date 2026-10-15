"""CSRF validation scoped to notice forms without changing other application flows."""

import hmac
import secrets

from flask import abort, request, session


def notice_csrf_token():
    if "notice_csrf_token" not in session:
        session["notice_csrf_token"] = secrets.token_urlsafe(32)
    return session["notice_csrf_token"]


def validate_notice_csrf_token():
    expected = session.get("notice_csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    if not expected or not submitted or not hmac.compare_digest(expected.encode(), submitted.encode()):
        abort(400, "요청을 확인할 수 없습니다. 화면을 새로고침한 뒤 다시 시도해주세요.")
