# app/models/user_progress.py
from datetime import datetime
from app.extensions import db

class UserProgress(db.Model):
    __tablename__ = 'user_progress'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    vocabulary_id = db.Column(db.Integer, db.ForeignKey('vocabularies.id'), nullable=False)
    
    # 학습 상태 (0: 미학습, 1: 학습 중, 2: 학습 완료)
    status = db.Column(db.Integer, default=0)
    
    # 점수 기록 - 듣기 점수는 제거하고 영어와 한글 쓰기 점수 분리
    speaking_score = db.Column(db.Integer, default=0)
    english_writing_score = db.Column(db.Integer, default=0)
    korean_writing_score = db.Column(db.Integer, default=0)
    
    # 평균 점수
    total_score = db.Column(db.Integer, default=0)
    
    # 학습 일자
    last_studied_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 학습 횟수
    study_count = db.Column(db.Integer, default=0)
    
    # 고유 제약 조건 (한 사용자가 같은 단어를 중복해서 등록하지 않도록)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'vocabulary_id', name='uix_user_vocabulary'),
    )
    
    def __repr__(self):
        return f'<UserProgress user_id={self.user_id} vocabulary_id={self.vocabulary_id} status={self.status}>'