from datetime import datetime

from flask import abort, current_app, flash, jsonify, make_response, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required
from werkzeug.exceptions import RequestEntityTooLarge

from app.extensions import db
from app.models.notice import Notice
from app.routes import main_bp
from app.services.dashboard import get_weekly_rankings
from app.services.notice_attachments import (
    AttachmentValidationError,
    attachment_mimetype,
    attachment_path,
    delete_notice,
    save_notice,
)
from app.services.notice_forms import notice_csrf_token, validate_notice_csrf_token
from app.services.notice_preview import prepare_preview, preview_page_path, preview_status


@main_bp.route("/")
@login_required
def index():
    notices = Notice.query.order_by(Notice.published_at.desc(), Notice.id.desc()).limit(5).all()
    rankings = get_weekly_rankings(limit=5)
    return render_template("index.html", notices=notices, rankings=rankings)


@main_bp.route("/notices", strict_slashes=False)
@login_required
def notices():
    notice_list = Notice.query.order_by(Notice.published_at.desc(), Notice.id.desc()).all()
    return render_template("notices/index.html", notices=notice_list)


@main_bp.route("/notices/<int:notice_id>")
@login_required
def notice_detail(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    return render_template("notices/detail.html", notice=notice, csrf_token=notice_csrf_token())


@main_bp.route("/notices/<int:notice_id>/attachment")
@login_required
def notice_attachment(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    if not notice.attachment:
        abort(404)
    path = attachment_path(notice.attachment.storage_name)
    if not path.is_file():
        abort(404)
    response = send_file(
        path,
        as_attachment=True,
        download_name=notice.attachment.original_name,
        mimetype=attachment_mimetype(notice.attachment),
        conditional=False,
        etag=False,
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.vary.add("Cookie")
    return response


def _notice_with_attachment(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    if not notice.attachment or not attachment_path(notice.attachment.storage_name).is_file():
        abort(404)
    return notice


def _private_preview_response(response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.vary.add("Cookie")
    return response


@main_bp.route("/notices/<int:notice_id>/preview/viewer")
@login_required
def notice_preview_viewer(notice_id):
    notice = _notice_with_attachment(notice_id)
    response = make_response(render_template(
        "notices/preview.html", notice=notice, csrf_token=notice_csrf_token(),
    ))
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' blob:; connect-src 'self'; frame-ancestors 'self'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'"
    )
    response.headers["Referrer-Policy"] = "same-origin"
    return _private_preview_response(response)


@main_bp.route("/notices/<int:notice_id>/preview")
@login_required
def notice_preview_status(notice_id):
    notice = _notice_with_attachment(notice_id)
    return _private_preview_response(jsonify(preview_status(notice.attachment)))


@main_bp.route("/notices/<int:notice_id>/preview/prepare", methods=["POST"])
@login_required
def notice_preview_prepare(notice_id):
    request.max_content_length = 4096
    validate_notice_csrf_token()
    notice = _notice_with_attachment(notice_id)
    result = prepare_preview(notice.attachment)
    response = jsonify(result)
    response.status_code = {
        "ready": 200, "pending": 202, "busy": 202, "unavailable": 503, "error": 422,
    }.get(result["state"], 500)
    if result.get("retry_after"):
        response.headers["Retry-After"] = str(result["retry_after"])
    return _private_preview_response(response)


@main_bp.route("/notices/<int:notice_id>/preview/pages/<int:page>")
@login_required
def notice_preview_page(notice_id, page):
    notice = _notice_with_attachment(notice_id)
    try:
        path = preview_page_path(notice.attachment, page)
    except (ValueError, FileNotFoundError):
        abort(404)
    response = send_file(path, mimetype="image/png", conditional=False, etag=False, max_age=0)
    return _private_preview_response(response)


@main_bp.route("/notices/new", methods=["GET", "POST"])
@login_required
def notice_create():
    _require_notice_admin()
    if request.method == "POST":
        return _handle_notice_save()
    return _render_notice_form()


@main_bp.route("/notices/<int:notice_id>/edit", methods=["GET", "POST"])
@login_required
def notice_edit(notice_id):
    _require_notice_admin()
    notice = Notice.query.get_or_404(notice_id)
    if request.method == "POST":
        return _handle_notice_save(notice)
    return _render_notice_form(notice)


@main_bp.route("/notices/<int:notice_id>/delete", methods=["POST"])
@login_required
def notice_delete(notice_id):
    _require_notice_admin()
    validate_notice_csrf_token()
    notice = Notice.query.get_or_404(notice_id)
    delete_notice(notice)
    flash("공지를 삭제했습니다.", "success")
    return redirect(url_for("main.notices"))


@main_bp.route("/ranking")
@login_required
def ranking():
    return render_template("ranking/index.html", rankings=get_weekly_rankings())


def _require_notice_admin():
    if not current_user.is_admin:
        abort(403)


def _render_notice_form(notice=None, error=None, status=200):
    return render_template(
        "notices/form.html",
        notice=notice,
        csrf_token=notice_csrf_token(),
        form_error=error,
        form_values=request.form if request.method == "POST" else None,
    ), status


def _handle_notice_save(notice=None):
    try:
        request.max_content_length = current_app.config["NOTICE_MAX_ATTACHMENT_BYTES"] + 1024 * 1024
        validate_notice_csrf_token()
        updated = _notice_from_form()
        is_new = notice is None
        if is_new:
            notice = updated
        else:
            notice.title = updated.title
            notice.body = updated.body
            notice.published_at = updated.published_at
        uploads = [file for file in request.files.getlist("attachment") if file.filename]
        if len(uploads) > 1:
            raise AttachmentValidationError("공지마다 첨부파일은 하나만 올릴 수 있습니다.")
        save_notice(
            notice,
            upload=uploads[0] if uploads else None,
            remove_attachment=request.form.get("remove_attachment") == "1",
        )
    except AttachmentValidationError as error:
        db.session.rollback()
        return _render_notice_form(None if is_new else notice, str(error), error.status_code)
    except RequestEntityTooLarge:
        # The oversized request body must not be parsed again by the error template.
        return "첨부파일은 20MB 이하로 올려주세요. 뒤로 가서 다시 선택해주세요.", 413
    flash("공지를 등록했습니다." if is_new else "공지를 수정했습니다.", "success")
    return redirect(url_for("main.notice_detail", notice_id=notice.id))


def _notice_from_form():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    published_at_value = request.form.get("published_at", "").strip()
    if not title:
        abort(400, "공지 제목을 입력해주세요.")
    if len(title) > 200:
        abort(400, "공지 제목은 200자 이하로 입력해주세요.")
    if len(body) > 50000:
        abort(400, "공지 내용은 50,000자 이하로 입력해주세요.")

    try:
        published_at = (
            datetime.strptime(published_at_value, "%Y-%m-%dT%H:%M")
            if published_at_value
            else datetime.utcnow()
        )
    except ValueError:
        abort(400, "공지 일시 형식이 올바르지 않습니다.")
    return Notice(title=title, body=body, published_at=published_at)
