"""Validation and persistence for the user's editable display name."""

import unicodedata

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db


class ProfileValidationError(ValueError):
    """A submitted display name cannot be stored."""


def validate_profile_name(value):
    """Return a trimmed, printable name matching users.full_name's limit."""
    if not isinstance(value, str):
        raise ProfileValidationError("이름을 입력해주세요.")
    if any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in value
    ):
        raise ProfileValidationError("이름에는 줄바꿈이나 보이지 않는 제어 문자를 사용할 수 없습니다.")

    name = value.strip()
    if not name:
        raise ProfileValidationError("이름을 입력해주세요.")
    if len(name) > 100:
        raise ProfileValidationError("이름은 100자 이하로 입력해주세요.")
    return name


def save_profile_name(user, value):
    """Change only this authenticated user's name, with atomic persistence."""
    name = validate_profile_name(value)
    try:
        user.full_name = name
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return name
