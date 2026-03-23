# app/models/chapter.py
from datetime import datetime
from app.extensions import db

class Chapter(db.Model):
    __tablename__ = 'chapters'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # 학년 (1, 2, 3, 4, 5, 6)
    grade = db.Column(db.Integer, nullable=False)
    
    # 학기 (1: 1학기, 2: 2학기)
    semester = db.Column(db.Integer, nullable=False)
    
    # 챕터 순서 (해당 학기 내에서의 순서)
    order = db.Column(db.Integer, nullable=False)
    
    # 챕터 제목
    title = db.Column(db.String(200), nullable=False)
    
    # 카테고리 (초등, 중등, 고등)
    category = db.Column(db.String(20), nullable=False)
    
    # 생성일
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정: Chapter → Stories
    stories = db.relationship('Story', backref='chapter_obj', lazy=True, cascade='all, delete-orphan')
    
    # 인덱스 추가
    __table_args__ = (
        db.Index('ix_chapter_grade_semester_order', 'grade', 'semester', 'order'),
    )
    
    def __repr__(self):
        return f'<Chapter {self.grade}-{self.semester}: {self.title}>'