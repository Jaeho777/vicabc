# app/models/__init__.py
from app.extensions import db
from app.models.user import User
from app.models.level import Level
from app.models.vocabulary import Vocabulary
from app.models.user_progress import UserProgress  # 추가
from app.models.chapter import Chapter
from app.models.story import Story
from app.models.story_progress import StoryProgress
from app.models.story_certification import StoryCertification
from app.models.village_certification import VillageCertification
