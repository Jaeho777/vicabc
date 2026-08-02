from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models.notice import Notice
from app.routes import main_bp
from app.services.dashboard import get_weekly_rankings


@main_bp.route("/")
@login_required
def index():
    notices = Notice.query.order_by(Notice.published_at.desc(), Notice.id.desc()).limit(5).all()
    rankings = get_weekly_rankings(limit=5)
    return render_template("index.html", notices=notices, rankings=rankings)


@main_bp.route("/notices")
@login_required
def notices():
    notice_list = Notice.query.order_by(Notice.published_at.desc(), Notice.id.desc()).all()
    return render_template("notices/index.html", notices=notice_list)


@main_bp.route("/notices/<int:notice_id>")
@login_required
def notice_detail(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    return render_template("notices/detail.html", notice=notice)


@main_bp.route("/notices/new", methods=["GET", "POST"])
@login_required
def notice_create():
    _require_notice_admin()
    if request.method == "POST":
        notice = _notice_from_form()
        db.session.add(notice)
        db.session.commit()
        flash("공지를 등록했습니다.", "success")
        return redirect(url_for("main.notice_detail", notice_id=notice.id))
    return render_template("notices/form.html", notice=None)


@main_bp.route("/notices/<int:notice_id>/edit", methods=["GET", "POST"])
@login_required
def notice_edit(notice_id):
    _require_notice_admin()
    notice = Notice.query.get_or_404(notice_id)
    if request.method == "POST":
        updated_notice = _notice_from_form()
        notice.title = updated_notice.title
        notice.body = updated_notice.body
        notice.published_at = updated_notice.published_at
        db.session.commit()
        flash("공지를 수정했습니다.", "success")
        return redirect(url_for("main.notice_detail", notice_id=notice.id))
    return render_template("notices/form.html", notice=notice)


@main_bp.route("/notices/<int:notice_id>/delete", methods=["POST"])
@login_required
def notice_delete(notice_id):
    _require_notice_admin()
    notice = Notice.query.get_or_404(notice_id)
    db.session.delete(notice)
    db.session.commit()
    flash("공지를 삭제했습니다.", "success")
    return redirect(url_for("main.notices"))


@main_bp.route("/ranking")
@login_required
def ranking():
    return render_template("ranking/index.html", rankings=get_weekly_rankings())


def _require_notice_admin():
    if not current_user.is_admin:
        abort(403)


def _notice_from_form():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()
    published_at_value = request.form.get("published_at", "").strip()
    if not title:
        abort(400, "공지 제목을 입력해주세요.")

    try:
        published_at = (
            datetime.strptime(published_at_value, "%Y-%m-%dT%H:%M")
            if published_at_value
            else datetime.utcnow()
        )
    except ValueError:
        abort(400, "공지 일시 형식이 올바르지 않습니다.")
    return Notice(title=title, body=body, published_at=published_at)
