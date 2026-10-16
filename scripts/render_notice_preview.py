#!/usr/bin/env python3
"""Render a copied presentation inside an unprivileged, offline systemd unit.

This script deliberately does not import the Flask app, database or secrets.
The caller must apply the resource and filesystem sandbox before executing it.
"""

import argparse
import json
import os
import re
import stat
import struct
import subprocess
import sys
import tarfile
from pathlib import Path


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MACRO_SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry">
 <item oor:path="/org.openoffice.Office.Common/Security/Scripting">
  <prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>
 </item>
</oor:items>
"""


def regular_file(path, max_bytes):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= max_bytes:
        raise ValueError("Invalid generated file")
    return metadata.st_size


def validate_png(path):
    size = regular_file(path, 8 * 1024 * 1024)
    with path.open("rb") as source:
        header = source.read(24)
    if header[:8] != PNG_SIGNATURE or header[8:16] != b"\x00\x00\x00\rIHDR":
        raise ValueError("Invalid generated slide")
    width, height = struct.unpack(">II", header[16:24])
    if not (0 < width <= 1600 and 0 < height <= 1600):
        raise ValueError("Invalid slide dimensions")
    return size


def render(job, max_pages, max_bytes):
    if os.geteuid() == 0:
        raise RuntimeError("The document worker must not run as root")
    if not job.is_absolute() or job.is_symlink() or not job.is_dir():
        raise ValueError("Invalid worker directory")
    inputs = [path for path in (job / "input.ppt", job / "input.pptx") if path.is_file()]
    if len(inputs) != 1:
        raise ValueError("Expected exactly one presentation")
    source = inputs[0]
    regular_file(source, 20 * 1024 * 1024)
    # The caller mounts this as a memory- and size-capped writable filesystem.
    # The host job directory itself is root-owned and read-only in the unit.
    scratch = job / "scratch"
    output = scratch / "output"
    output.mkdir(mode=0o700)
    profile = scratch / "profile"
    (profile / "user").mkdir(mode=0o700, parents=True)
    (profile / "user" / "registrymodifications.xcu").write_text(MACRO_SETTINGS, encoding="utf-8")
    temporary = scratch / "tmp"
    temporary.mkdir(mode=0o700)
    environment = {
        "PATH": "/usr/bin:/bin", "HOME": str(profile), "TMPDIR": str(temporary),
        "XDG_CACHE_HOME": str(scratch / "cache"), "XDG_CONFIG_HOME": str(scratch / "config"),
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "SAL_USE_VCLPLUGIN": "svp",
    }
    export_parameters = {
        "ExportHiddenSlides": {"type": "boolean", "value": "false"},
        "ExportNotesPages": {"type": "boolean", "value": "false"},
    }
    conversion_options = "pdf:impress_pdf_Export:" + json.dumps(export_parameters)
    subprocess.run(
        [
            "/usr/bin/libreoffice", f"-env:UserInstallation={profile.as_uri()}",
            "--headless", "--nologo", "--nodefault", "--nolockcheck", "--norestore",
            "--convert-to", conversion_options, "--outdir", str(output), str(source),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=55, env=environment, cwd=job,
    )
    pdf = output / "input.pdf"
    total_size = regular_file(pdf, min(max_bytes, 64 * 1024 * 1024))
    with pdf.open("rb") as document:
        if document.read(5) != b"%PDF-":
            raise ValueError("Converter did not produce a PDF")
    info = subprocess.run(
        ["/usr/bin/pdfinfo", str(pdf)], check=True, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, timeout=5, env=environment, cwd=job,
    )
    match = re.search(rb"^Pages:\s+(\d+)\s*$", info.stdout, re.MULTILINE)
    pages = int(match.group(1)) if match else 0
    if not 1 <= pages <= max_pages:
        raise ValueError("Presentation exceeds the slide limit")
    for page in range(1, pages + 1):
        prefix = output / f"page-{page:04d}"
        subprocess.run(
            [
                "/usr/bin/pdftoppm", "-f", str(page), "-l", str(page), "-singlefile",
                "-png", "-r", "96", "-scale-to", "1600", str(pdf), str(prefix),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=10, env=environment, cwd=job,
        )
        total_size += validate_png(prefix.with_suffix(".png"))
        if total_size > max_bytes:
            raise ValueError("Preview exceeds the storage limit")
    pdf.unlink()
    (output / "preview.json").write_text(json.dumps({"pages": pages}), encoding="ascii")
    # An inherited descriptor is the only persistent host output the worker can
    # write. The unit's file-size limit bounds it; the parent validates each entry.
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", format=tarfile.USTAR_FORMAT) as bundle:
        bundle.add(output / "preview.json", arcname="preview.json", recursive=False)
        for page in range(1, pages + 1):
            name = f"page-{page:04d}.png"
            bundle.add(output / name, arcname=name, recursive=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", required=True, type=Path)
    parser.add_argument("--max-pages", required=True, type=int)
    parser.add_argument("--max-bytes", required=True, type=int)
    arguments = parser.parse_args()
    if not 1 <= arguments.max_pages <= 100 or not 1024 * 1024 <= arguments.max_bytes <= 200 * 1024 * 1024:
        parser.error("Resource limits are outside the allowed range")
    try:
        render(arguments.job_dir, arguments.max_pages, arguments.max_bytes)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        # Never echo document text, original file names or subprocess output.
        print("Slide preview conversion failed", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
