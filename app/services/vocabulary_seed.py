import json
import tempfile
import unicodedata
from contextlib import contextmanager
from pathlib import Path

from app.extensions import db
from app.models.level import Level
from app.models.vocabulary import Vocabulary


CATALOG_PATH = Path(__file__).resolve().parents[1] / 'data' / 'vocabulary.json'
MANAGED_LEVEL_CATEGORY = 'VOCA'
SYNC_LOCK_PATH = Path(tempfile.gettempdir()) / 'vicabc-vocabulary-sync.lock'


def normalize_word(value):
    return unicodedata.normalize('NFKC', str(value or '')).strip().casefold()


def load_vocabulary_catalog():
    with CATALOG_PATH.open(encoding='utf-8') as catalog_file:
        catalog = json.load(catalog_file)

    levels = catalog.get('levels', [])
    words = [word for level in levels for word in level.get('words', [])]
    normalized_words = [normalize_word(word.get('word')) for word in words]

    if len(levels) != catalog.get('expected_level_count'):
        raise ValueError('VOCA 데이터의 Village 수가 원본과 일치하지 않습니다.')
    if len(words) != catalog.get('expected_word_count'):
        raise ValueError('VOCA 데이터의 단어 수가 원본과 일치하지 않습니다.')
    if not all(normalized_words) or len(set(normalized_words)) != len(normalized_words):
        raise ValueError('VOCA 데이터에 빈 단어 또는 중복 단어가 있습니다.')

    return catalog


@contextmanager
def vocabulary_sync_lock():
    with SYNC_LOCK_PATH.open('w') as lock_file:
        try:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except ImportError:
            pass
        yield


def sync_packaged_vocabulary():
    """Add or update the packaged Village VOCA catalog without touching legacy levels."""
    with vocabulary_sync_lock():
        catalog = load_vocabulary_catalog()
        levels_by_name = {
            level.name: level
            for level in Level.query.filter_by(category=MANAGED_LEVEL_CATEGORY).all()
        }

        added_levels = 0
        for level_data in catalog['levels']:
            level = levels_by_name.get(level_data['name'])
            description = f"{level_data['english_name']} · 최종 VOCA DB"
            if level is None:
                level = Level(
                    name=level_data['name'],
                    category=MANAGED_LEVEL_CATEGORY,
                    description=description,
                )
                db.session.add(level)
                db.session.flush()
                levels_by_name[level.name] = level
                added_levels += 1
            elif level.description != description:
                level.description = description

        managed_level_ids = [level.id for level in levels_by_name.values()]
        existing_words = (
            Vocabulary.query
            .filter(Vocabulary.level_id.in_(managed_level_ids))
            .order_by(Vocabulary.id.asc())
            .all()
        )
        words_by_key = {}
        for vocabulary in existing_words:
            words_by_key.setdefault(normalize_word(vocabulary.word), vocabulary)

        added_words = 0
        updated_words = 0
        unchanged_words = 0
        synced_word_ids = set()

        for level_data in catalog['levels']:
            level = levels_by_name[level_data['name']]
            for word_data in level_data['words']:
                key = normalize_word(word_data['word'])
                vocabulary = words_by_key.get(key)
                if vocabulary is None:
                    vocabulary = Vocabulary(
                        word=word_data['word'],
                        part_of_speech=word_data['part_of_speech'],
                        meaning=word_data['meaning'],
                        level_id=level.id,
                    )
                    db.session.add(vocabulary)
                    db.session.flush()
                    words_by_key[key] = vocabulary
                    added_words += 1
                else:
                    changed = False
                    desired_values = {
                        'word': word_data['word'],
                        'part_of_speech': word_data['part_of_speech'],
                        'meaning': word_data['meaning'],
                        'level_id': level.id,
                    }
                    for attribute, desired_value in desired_values.items():
                        if getattr(vocabulary, attribute) != desired_value:
                            setattr(vocabulary, attribute, desired_value)
                            changed = True
                    if changed:
                        updated_words += 1
                    else:
                        unchanged_words += 1
                synced_word_ids.add(vocabulary.id)

        if len(synced_word_ids) != catalog['expected_word_count']:
            db.session.rollback()
            raise ValueError('DB에 동기화된 VOCA 단어 수가 원본과 일치하지 않습니다.')

        db.session.commit()
        return {
            'version': catalog['version'],
            'levels': catalog['expected_level_count'],
            'words': catalog['expected_word_count'],
            'added_levels': added_levels,
            'added_words': added_words,
            'updated_words': updated_words,
            'unchanged_words': unchanged_words,
        }
