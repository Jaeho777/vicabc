# init_db.py
from app import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    from app.models.user import User
    from app.models.level import Level
    from app.models.vocabulary import Vocabulary
    from app.models.user_progress import UserProgress
    from app.models.certification import Certification
    from app.models.chapter import Chapter
    from app.models.story import Story
    from app.models.story_progress import StoryProgress
    from app.models.story_certification import StoryCertification
    from app.models.village_certification import VillageCertification
    db.create_all()
    print("데이터베이스 테이블이 성공적으로 생성되었습니다.")
