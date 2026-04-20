#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO_ROOT = REPO_ROOT / "app" / "static" / "audio" / "stories"

GRADE_RE = re.compile(r"^Grade\s+(\d+)$")
TITLE_RE = re.compile(r"^\d+\.\s+(.+)$")
SENTENCE_RE = re.compile(r"^(\d+)-(\d+)-(\d+)\.\s+(.+)$")


def default_markdown_path() -> Path:
    repo_candidate = REPO_ROOT / "bible_story_extracted_sentences.md"
    if repo_candidate.exists():
        return repo_candidate

    return REPO_ROOT.parent / "bible_story_extracted_sentences.md"


@dataclass
class ChapterContent:
    title: str
    stories: list[tuple[int, str]] = field(default_factory=list)


def parse_markdown(markdown_path: Path) -> dict[int, dict[int, ChapterContent]]:
    parsed: dict[int, dict[int, ChapterContent]] = {}
    current_grade: int | None = None
    pending_title: str | None = None

    for raw_line in markdown_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        grade_match = GRADE_RE.match(line)
        if grade_match:
            current_grade = int(grade_match.group(1))
            parsed.setdefault(current_grade, {})
            pending_title = None
            continue

        title_match = TITLE_RE.match(line)
        if title_match:
            pending_title = title_match.group(1).strip()
            continue

        sentence_match = SENTENCE_RE.match(line)
        if not sentence_match:
            continue

        grade = int(sentence_match.group(1))
        chapter_order = int(sentence_match.group(2))
        story_order = int(sentence_match.group(3))
        english_text = sentence_match.group(4).strip()

        if current_grade is not None and current_grade != grade:
            current_grade = grade
            parsed.setdefault(current_grade, {})

        grade_content = parsed.setdefault(grade, {})
        if chapter_order not in grade_content:
            grade_content[chapter_order] = ChapterContent(
                title=pending_title or f"Chapter {chapter_order}"
            )
            pending_title = None

        grade_content[chapter_order].stories.append((story_order, english_text))

    for grade_content in parsed.values():
        for chapter in grade_content.values():
            chapter.stories.sort(key=lambda item: item[0])

    return parsed


def relative_audio_filename(audio_root: Path, grade: int, chapter_order: int, story_order: int) -> str | None:
    relative_path = Path(str(grade)) / f"{grade}-{chapter_order}" / f"{grade}-{chapter_order}-{story_order}.mp3"
    return relative_path.as_posix() if (audio_root / relative_path).exists() else None


def print_summary(parsed: dict[int, dict[int, ChapterContent]], audio_root: Path) -> list[str]:
    warnings: list[str] = []

    for grade in sorted(parsed):
        print(f"Grade {grade}")
        for chapter_order in sorted(parsed[grade]):
            chapter = parsed[grade][chapter_order]
            audio_dir = audio_root / str(grade) / f"{grade}-{chapter_order}"
            audio_count = len(list(audio_dir.glob("*.mp3"))) if audio_dir.exists() else 0
            story_count = len(chapter.stories)
            status = "OK" if audio_count == story_count else f"MISMATCH audio={audio_count}"
            print(f"  {grade}-{chapter_order}: text={story_count} {status} | {chapter.title}")
            if audio_count != story_count:
                warnings.append(
                    f"{grade}-{chapter_order}: text={story_count}, audio={audio_count}, title={chapter.title}"
                )

    return warnings


def import_content(markdown_path: Path, audio_root: Path) -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from app import create_app
    from app.extensions import db
    from app.models.chapter import Chapter
    from app.models.story import Story

    parsed = parse_markdown(markdown_path)

    app = create_app()
    with app.app_context():
        created_chapters = 0
        created_stories = 0
        updated_stories = 0
        missing_audio = []

        for grade in sorted(parsed):
            for chapter_order in sorted(parsed[grade]):
                chapter_content = parsed[grade][chapter_order]
                chapter = (
                    Chapter.query
                    .filter_by(grade=grade, order=chapter_order, category='초등')
                    .order_by(Chapter.semester.asc(), Chapter.id.asc())
                    .first()
                )

                if chapter is None:
                    chapter = Chapter(
                        grade=grade,
                        semester=1,
                        order=chapter_order,
                        title=chapter_content.title,
                        category='초등',
                    )
                    db.session.add(chapter)
                    db.session.flush()
                    created_chapters += 1
                else:
                    chapter.semester = 1
                    chapter.title = chapter_content.title
                    chapter.category = '초등'

                for story_order, english_text in chapter_content.stories:
                    story = Story.query.filter_by(chapter_id=chapter.id, order=story_order).first()
                    audio_filename = relative_audio_filename(audio_root, grade, chapter_order, story_order)

                    if story is None:
                        story = Story(
                            chapter_id=chapter.id,
                            order=story_order,
                            korean_text='',
                            english_text=english_text,
                            audio_filename=audio_filename,
                        )
                        db.session.add(story)
                        created_stories += 1
                    else:
                        story.english_text = english_text
                        if not story.korean_text:
                            story.korean_text = ''
                        story.audio_filename = audio_filename
                        updated_stories += 1

                    if audio_filename is None:
                        missing_audio.append(f"{grade}-{chapter_order}-{story_order}")

        db.session.commit()

    print(f"Imported chapters: {created_chapters}")
    print(f"Created stories: {created_stories}")
    print(f"Updated stories: {updated_stories}")
    if missing_audio:
        print("Stories without matching audio:")
        for item in missing_audio:
            print(f"  - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import Bible Story chapters from markdown and grade-based audio folders.")
    parser.add_argument("--markdown", type=Path, default=default_markdown_path())
    parser.add_argument("--audio-root", type=Path, default=DEFAULT_AUDIO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.markdown.exists():
        raise SystemExit(f"Markdown file not found: {args.markdown}")
    if not args.audio_root.exists():
        raise SystemExit(f"Audio root not found: {args.audio_root}")

    parsed = parse_markdown(args.markdown)
    warnings = print_summary(parsed, args.audio_root)

    if args.dry_run:
        print("Dry run only. No database changes were made.")
        return 0

    import_content(args.markdown, args.audio_root)

    if warnings:
        print("Chapters with text/audio count mismatches:")
        for warning in warnings:
            print(f"  - {warning}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
