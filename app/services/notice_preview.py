"""Create private, cached slide images with a restricted conversion worker.

Documents never go to an external viewer.  The web process only copies input,
starts a non-privileged systemd unit and accepts bounded PNG output from it.
"""

import fcntl
import json
import os
import pwd
import re
import shutil
import stat
import struct
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from flask import current_app

from app.services.notice_attachments import STORAGE_NAME, attachment_path


MANIFEST_VERSION = 1
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_IMAGE_EDGE = 1600
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_RENDERER = "/opt/vicabc-preview/render_notice_preview.py"
DEFAULT_WORK_ROOT = "/var/lib/vicabc-preview/work"


def _preview_directory():
    configured = current_app.config.get("NOTICE_PREVIEW_DIR")
    return Path(configured or Path(current_app.instance_path) / "notice-previews")


def _cache_directory(storage_name):
    if not isinstance(storage_name, str) or not STORAGE_NAME.fullmatch(storage_name):
        raise ValueError("Invalid stored attachment name")
    return _preview_directory() / storage_name


def _result(state, pages=0, **extra):
    messages = {
        "ready": "슬라이드를 바로 볼 수 있습니다.",
        "pending": "슬라이드 미리보기를 준비할 수 있습니다.",
        "busy": "다른 슬라이드를 준비하고 있습니다. 잠시 후 다시 시도합니다.",
        "error": "미리보기를 만들지 못했습니다. 원본 파일을 내려받아 확인해주세요.",
        "unavailable": "현재 미리보기를 사용할 수 없습니다. 원본 파일을 내려받아주세요.",
    }
    return {"state": state, "pages": pages, "message": messages[state], **extra}


def _max_pages():
    return min(100, max(1, int(current_app.config.get("NOTICE_PREVIEW_MAX_PAGES", 100))))


def _max_bytes():
    return min(
        200 * 1024 * 1024,
        max(1024 * 1024, int(current_app.config.get("NOTICE_PREVIEW_MAX_BYTES", 200 * 1024 * 1024))),
    )


def _timeout():
    return min(90, max(15, int(current_app.config.get("NOTICE_PREVIEW_TIMEOUT_SECONDS", 75))))


def _read_manifest(directory, storage_name):
    path = directory / "preview.json"
    if directory.is_symlink() or path.is_symlink() or path.stat().st_size > 4096:
        raise ValueError("Invalid preview manifest")
    with path.open(encoding="utf-8") as source:
        manifest = json.load(source)
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != MANIFEST_VERSION
        or manifest.get("storage_name") != storage_name
    ):
        raise ValueError("Invalid preview manifest")
    return manifest


def _valid_png(path):
    """Reject links, oversized output and implausible image dimensions."""
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or not 24 <= metadata.st_size <= MAX_IMAGE_BYTES:
        return False
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as image:
        header = image.read(24)
    if header[:8] != PNG_SIGNATURE or header[8:16] != b"\x00\x00\x00\rIHDR":
        return False
    width, height = struct.unpack(">II", header[16:24])
    return 0 < width <= MAX_IMAGE_EDGE and 0 < height <= MAX_IMAGE_EDGE


def _renderer_available():
    """Fail closed if the isolated worker was not installed by an operator."""
    if not current_app.config.get("NOTICE_PREVIEW_ENABLED", True) or os.geteuid() != 0:
        return False
    renderer = Path(current_app.config.get("NOTICE_PREVIEW_RENDERER", DEFAULT_RENDERER))
    work_root = Path(current_app.config.get("NOTICE_PREVIEW_WORK_ROOT", DEFAULT_WORK_ROOT))
    try:
        user = pwd.getpwnam(current_app.config.get("NOTICE_PREVIEW_USER", "vicpreview"))
        metadata = renderer.lstat()
        work_metadata = work_root.lstat()
        return (
            user.pw_uid != 0
            and stat.S_ISREG(metadata.st_mode)
            and metadata.st_uid == 0
            and metadata.st_mode & 0o022 == 0
            and stat.S_ISDIR(work_metadata.st_mode)
            and work_metadata.st_uid == 0
            and work_metadata.st_mode & 0o022 == 0
            and Path("/run/systemd/system").is_dir()
            and all(
                shutil.which(command)
                for command in ("systemd-run", "systemctl", "libreoffice", "pdfinfo", "pdftoppm")
            )
        )
    except (OSError, KeyError):
        return False


def _ready_page_count(manifest):
    pages = manifest.get("pages")
    if manifest.get("state") != "ready" or type(pages) is not int or not 1 <= pages <= _max_pages():
        raise ValueError("Invalid preview page count")
    return pages


def preview_status(attachment):
    """Return safe display state without running a converter or touching the DB."""
    if attachment is None:
        return _result("unavailable")
    storage_name = attachment.storage_name
    directory = _cache_directory(storage_name)
    if not attachment_path(storage_name).is_file():
        return _result("unavailable")
    try:
        manifest = _read_manifest(directory, storage_name)
        if manifest.get("state") == "ready":
            pages = _ready_page_count(manifest)
            if all(_valid_png(directory / f"page-{page:04d}.png") for page in range(1, pages + 1)):
                return _result("ready", pages)
        elif manifest.get("state") == "error":
            failed_at = manifest.get("failed_at")
            cooldown = max(1, int(current_app.config.get("NOTICE_PREVIEW_RETRY_SECONDS", 60)))
            if isinstance(failed_at, (int, float)):
                retry_after = max(0, int(cooldown - (time.time() - failed_at)))
                if retry_after:
                    return _result("error", retry_after=retry_after)
    except (OSError, ValueError, TypeError, OverflowError):
        pass
    return _result("pending" if _renderer_available() else "unavailable")


def preview_page_path(attachment, page):
    if type(page) is not int or page < 1:
        raise ValueError("Invalid preview page")
    if attachment is None or not attachment_path(attachment.storage_name).is_file():
        raise FileNotFoundError("Preview page unavailable")
    directory = _cache_directory(attachment.storage_name)
    try:
        pages = _ready_page_count(_read_manifest(directory, attachment.storage_name))
        path = directory / f"page-{page:04d}.png"
        # Serving one page must not read every image of a large presentation.
        if page > pages or not _valid_png(path):
            raise FileNotFoundError("Preview page unavailable")
        return path
    except OSError as error:
        raise FileNotFoundError("Preview page unavailable") from error


def _write_manifest(directory, manifest):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = directory / f".manifest-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as output:
            os.chmod(temporary, 0o600)
            json.dump(manifest, output, ensure_ascii=True)
        os.replace(temporary, directory / "preview.json")
    finally:
        temporary.unlink(missing_ok=True)


def _run_renderer(job):
    """systemd owns the entire process group, including office subprocesses."""
    unit = f"vicabc-preview-{job.name}"
    timeout = _timeout()
    renderer = str(Path(current_app.config.get("NOTICE_PREVIEW_RENDERER", DEFAULT_RENDERER)).resolve())
    user = current_app.config.get("NOTICE_PREVIEW_USER", "vicpreview")
    identity = pwd.getpwnam(user)
    scratch = job / "scratch"
    scratch.mkdir(mode=0o700)
    properties = [
        f"User={user}", f"Group={identity.pw_gid}",
        "NoNewPrivileges=yes", "PrivateNetwork=yes", "PrivateTmp=yes", "PrivateDevices=yes",
        "ProtectSystem=strict", "ProtectHome=yes", "ProtectProc=invisible",
        "ProtectKernelTunables=yes", "ProtectKernelModules=yes", "ProtectControlGroups=yes",
        "RestrictSUIDSGID=yes", "LockPersonality=yes", "CapabilityBoundingSet=",
        "RestrictAddressFamilies=AF_UNIX", "UMask=0077", "MemoryMax=1G", "MemorySwapMax=0",
        "TasksMax=64", "CPUQuota=100%", "LimitFSIZE=256M", "LimitNOFILE=256",
        "TimeoutStopSec=5s", "RestrictRealtime=yes", "SystemCallArchitectures=native",
        f"RuntimeMaxSec={timeout}s",
        "TemporaryFileSystem="
        f"{scratch}:rw,size=384M,mode=0700,uid={identity.pw_uid},gid={identity.pw_gid} "
        "/tmp:rw,size=16M,mode=1777 /var/tmp:rw,size=16M,mode=1777",
        "InaccessiblePaths=/var/www /run -/opt/vicabc-backups", "KillMode=control-group",
    ]
    command = ["systemd-run", "--quiet", "--wait", "--pipe", "--collect", f"--unit={unit}"]
    command += [f"--property={value}" for value in properties]
    command += [
        "/usr/bin/python3", "-I", renderer, "--job-dir", str(job),
        "--max-pages", str(_max_pages()), "--max-bytes", str(_max_bytes()),
    ]
    environment = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
    archive = job / "rendered.tar"
    try:
        with archive.open("xb") as output:
            os.chmod(archive, 0o600)
            subprocess.run(
                command, check=True, stdout=output, stderr=subprocess.DEVNULL,
                timeout=timeout + 5, env=environment,
            )
        _unpack_output(archive, job / "output")
    except subprocess.TimeoutExpired:
        # Do not leave a detached converter running after the request times out.
        subprocess.run(
            ["systemctl", "stop", unit], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, env=environment,
        )
        raise
    finally:
        archive.unlink(missing_ok=True)


def _unpack_output(archive, output):
    """Accept a small, flat image archive, never archive-controlled paths."""
    if archive.stat().st_size > _max_bytes() + 1024 * 1024:
        raise ValueError("Worker output archive exceeds storage limit")
    output.mkdir(mode=0o700)
    names = set()
    total_size = 0
    with tarfile.open(archive, mode="r:") as bundle:
        for member in bundle:
            name = member.name
            if (
                not member.isfile()
                or name in names
                or len(names) >= _max_pages() + 1
                or (name != "preview.json" and not re.fullmatch(r"page-[0-9]{4}\.png", name))
                or not 0 < member.size <= (4096 if name == "preview.json" else MAX_IMAGE_BYTES)
            ):
                raise ValueError("Invalid worker output archive")
            names.add(name)
            total_size += member.size
            if total_size > _max_bytes() + 4096:
                raise ValueError("Worker output exceeds storage limit")
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError("Missing worker output")
            with source, (output / name).open("xb") as destination:
                os.chmod(output / name, 0o600)
                shutil.copyfileobj(source, destination, length=1024 * 1024)
    if "preview.json" not in names:
        raise ValueError("Missing worker output manifest")


def _copy_rendered_pages(job, staging, storage_name):
    output = job / "output"
    if output.is_symlink() or not output.is_dir() or output.resolve().parent != job.resolve():
        raise ValueError("Invalid worker output")
    manifest_path = output / "preview.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 4096:
        raise ValueError("Invalid worker output manifest")
    with manifest_path.open(encoding="utf-8") as source:
        manifest = json.load(source)
    pages = manifest.get("pages") if isinstance(manifest, dict) else None
    if type(pages) is not int or not 1 <= pages <= _max_pages():
        raise ValueError("Invalid worker page count")
    total_size = 0
    staging.mkdir(mode=0o700)
    for page in range(1, pages + 1):
        source = output / f"page-{page:04d}.png"
        if not _valid_png(source):
            raise ValueError("Invalid worker slide image")
        total_size += source.stat().st_size
        if total_size > _max_bytes():
            raise ValueError("Preview output exceeds storage limit")
        destination = staging / source.name
        descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as input_file, destination.open("xb") as output_file:
            os.chmod(destination, 0o600)
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
    _write_manifest(staging, {
        "version": MANIFEST_VERSION, "storage_name": storage_name,
        "state": "ready", "pages": pages,
    })
    return pages


def prepare_preview(attachment):
    """Prepare once; a non-blocking global lock bounds concurrent office work."""
    status = preview_status(attachment)
    if status["state"] != "pending":
        return status
    directory = _preview_directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(directory / ".conversion.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _result("busy", retry_after=2)
        status = preview_status(attachment)
        if status["state"] != "pending":
            return status
        storage_name = attachment.storage_name
        destination = _cache_directory(storage_name)
        staging = directory / f".staging-{uuid.uuid4().hex}"
        work_root = Path(current_app.config.get("NOTICE_PREVIEW_WORK_ROOT", DEFAULT_WORK_ROOT))
        job = work_root / uuid.uuid4().hex
        try:
            user = pwd.getpwnam(current_app.config.get("NOTICE_PREVIEW_USER", "vicpreview"))
            # The converter cannot create host files: its only writable directory
            # is a size-capped temporary filesystem mounted inside this job.
            job.mkdir(mode=0o711)
            source = attachment_path(storage_name)
            input_path = job / ("input" + source.suffix)
            with source.open("rb") as input_file, input_path.open("xb") as output_file:
                os.chmod(input_path, 0o400)
                shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            os.chown(input_path, user.pw_uid, user.pw_gid)
            _run_renderer(job)
            pages = _copy_rendered_pages(job, staging, storage_name)
            if not source.is_file():
                return _result("unavailable")
            if destination.exists():
                shutil.rmtree(destination)
            os.replace(staging, destination)
            return _result("ready", pages)
        except (OSError, ValueError, KeyError, subprocess.SubprocessError, tarfile.TarError):
            current_app.logger.exception("Could not prepare notice slide preview")
            if attachment_path(storage_name).is_file():
                try:
                    _write_manifest(destination, {
                        "version": MANIFEST_VERSION, "storage_name": storage_name,
                        "state": "error", "failed_at": time.time(),
                    })
                except OSError:
                    current_app.logger.exception("Could not cache notice preview failure")
            retry_after = max(1, int(current_app.config.get("NOTICE_PREVIEW_RETRY_SECONDS", 60)))
            return _result("error", retry_after=retry_after)
        finally:
            shutil.rmtree(job, ignore_errors=True)
            shutil.rmtree(staging, ignore_errors=True)
            if not attachment_path(storage_name).is_file():
                shutil.rmtree(destination, ignore_errors=True)


def remove_preview(storage_name):
    """Removing or replacing an original also removes its private image cache."""
    try:
        directory = _cache_directory(storage_name)
        if directory.is_symlink():
            directory.unlink()
        elif directory.exists():
            shutil.rmtree(directory)
    except (OSError, ValueError):
        current_app.logger.exception("Could not clean up notice slide preview")
