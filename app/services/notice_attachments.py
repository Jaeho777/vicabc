"""Validate, store and clean up notice files without exposing a public directory."""

import os
import re
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

import olefile
from flask import current_app

from app.extensions import db
from app.models.notice_attachment import NoticeAttachment


PRESENTATION_TYPE = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
)
CONTENT_TYPES_NAMESPACE = "http://schemas.openxmlformats.org/package/2006/content-types"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
PPT_MIME = "application/vnd.ms-powerpoint"
STORAGE_NAME = re.compile(r"[a-f0-9]{32}\.(?:ppt|pptx)\Z")


class AttachmentValidationError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def attachment_directory():
    configured = current_app.config.get("NOTICE_UPLOAD_DIR")
    return Path(configured or Path(current_app.instance_path) / "notice-attachments")


def attachment_path(storage_name):
    if not STORAGE_NAME.fullmatch(storage_name):
        raise ValueError("Invalid stored attachment name")
    return attachment_directory() / storage_name


def attachment_mimetype(attachment):
    return PPTX_MIME if attachment.storage_name.endswith(".pptx") else PPT_MIME


def _validate_pptx(stream):
    """Inspect the package without extracting or executing any embedded content."""
    try:
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > 10000:
                raise AttachmentValidationError("슬라이드 파일의 내부 항목이 너무 많습니다.")
            names = [entry.filename for entry in entries]
            if len(names) != len(set(names)):
                raise AttachmentValidationError("중복된 내부 항목이 있는 파일입니다.")
            for entry in entries:
                name = entry.filename
                if (
                    "\\" in name
                    or name.startswith("/")
                    or ".." in PurePosixPath(name).parts
                    or entry.flag_bits & 1
                    or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                ):
                    raise AttachmentValidationError("지원하지 않는 슬라이드 파일 구조입니다.")
            if sum(entry.file_size for entry in entries) > 200 * 1024 * 1024:
                raise AttachmentValidationError("압축 해제 크기가 너무 큰 파일입니다.")
            for name in ["[Content_Types].xml", "ppt/presentation.xml"]:
                if name not in names or archive.getinfo(name).file_size > 2 * 1024 * 1024:
                    raise AttachmentValidationError("정상적인 PPTX 파일을 선택해주세요.")
            types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
            main_type = next(
                (
                    item.get("ContentType")
                    for item in types.findall(f"{{{CONTENT_TYPES_NAMESPACE}}}Override")
                    if item.get("PartName") == "/ppt/presentation.xml"
                ),
                None,
            )
            if main_type != PRESENTATION_TYPE:
                raise AttachmentValidationError("일반 PowerPoint PPTX 파일만 첨부할 수 있습니다.")
            presentation = ElementTree.fromstring(archive.read("ppt/presentation.xml"))
            if presentation.tag != (
                "{http://schemas.openxmlformats.org/presentationml/2006/main}presentation"
            ):
                raise AttachmentValidationError("정상적인 PPTX 파일을 선택해주세요.")
            if archive.testzip() is not None:
                raise AttachmentValidationError("손상된 슬라이드 항목이 있는 파일입니다.")
    except AttachmentValidationError:
        raise
    except (zipfile.BadZipFile, KeyError, RuntimeError, ValueError, OSError, NotImplementedError, ElementTree.ParseError) as error:
        raise AttachmentValidationError("손상되었거나 PPTX 형식이 아닌 파일입니다.") from error


def _validate_ppt(stream):
    try:
        with olefile.OleFileIO(stream) as document:
            if not document.exists("PowerPoint Document"):
                raise AttachmentValidationError("정상적인 PPT 파일을 선택해주세요.")
    except AttachmentValidationError:
        raise
    except (OSError, ValueError, TypeError) as error:
        raise AttachmentValidationError("손상되었거나 PPT 형식이 아닌 파일입니다.") from error


def _stage_attachment(upload):
    name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name or len(name) > 200 or any(ord(character) < 32 for character in name):
        raise AttachmentValidationError("첨부파일 이름을 확인해주세요. 최대 200자입니다.")
    extension = Path(name).suffix.lower()
    if extension not in {".ppt", ".pptx"}:
        raise AttachmentValidationError("PPT 또는 PPTX 파일만 첨부할 수 있습니다.")

    limit = current_app.config["NOTICE_MAX_ATTACHMENT_BYTES"]
    # Werkzeug gives us a seekable temporary stream. Check size before parsing it.
    upload.stream.seek(0, os.SEEK_END)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size == 0:
        raise AttachmentValidationError("비어 있는 파일은 첨부할 수 없습니다.")
    if size > limit:
        raise AttachmentValidationError("첨부파일은 20MB 이하로 올려주세요.", 413)
    if extension == ".pptx":
        _validate_pptx(upload.stream)
    else:
        _validate_ppt(upload.stream)
    upload.stream.seek(0)

    directory = attachment_directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    storage_name = uuid.uuid4().hex + extension
    destination = attachment_path(storage_name)
    try:
        with destination.open("xb") as output:
            os.chmod(destination, 0o600)
            while chunk := upload.stream.read(1024 * 1024):
                output.write(chunk)
    except Exception:
        _remove_file(storage_name)
        raise
    return NoticeAttachment(original_name=name, storage_name=storage_name, size_bytes=size)


def _remove_file(storage_name):
    try:
        attachment_path(storage_name).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Could not clean up notice attachment")


def save_notice(notice, upload=None, remove_attachment=False):
    """Keep the old file on any validation/DB failure; remove it after commit."""
    previous = notice.attachment
    replacement = None
    try:
        if upload is not None and upload.filename:
            replacement = _stage_attachment(upload)
        if replacement is not None or remove_attachment:
            # Delete/flush before replacing the one-to-one unique FK.
            if previous is not None:
                notice.attachment = None
                db.session.delete(previous)
                db.session.flush()
            notice.attachment = replacement
        db.session.add(notice)
        db.session.commit()
    except Exception:
        db.session.rollback()
        if replacement is not None:
            _remove_file(replacement.storage_name)
        raise
    if previous is not None and (replacement is not None or remove_attachment):
        _remove_file(previous.storage_name)


def delete_notice(notice):
    previous_name = notice.attachment.storage_name if notice.attachment else None
    try:
        db.session.delete(notice)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    if previous_name:
        _remove_file(previous_name)
