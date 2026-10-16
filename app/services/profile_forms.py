"""CSRF protection scoped to the profile form."""

import hmac
import secrets

from flask import abort, request, session


def profile_csrf_token():
    """Keep the profile token separate from notice and other form tokens."""
    token = session.get("profile_csrf_token")
    if not isinstance(token, str) or not token:
        token = secrets.token_urlsafe(32)
        session["profile_csrf_token"] = token
    return token


def validate_profile_csrf_token():
    expected = session.get("profile_csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    if (
        not isinstance(expected, str)
        or not expected
        or not submitted
        or not hmac.compare_digest(expected.encode(), submitted.encode())
    ):
        abort(400, "요청을 확인할 수 없습니다. 화면을 새로고침한 뒤 다시 시도해주세요.")
