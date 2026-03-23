# app/models/story.py (완전 교체)
from datetime import datetime
from app.extensions import db

class Story(db.Model):
    __tablename__ = 'stories'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Chapter와의 관계
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    
    # 챕터 내에서의 순서
    order = db.Column(db.Integer, nullable=False)
    
    # title 필드 제거 - 더 이상 필요없음
    
    # 텍스트
    korean_text = db.Column(db.Text, nullable=False)   # 한국어 텍스트
    english_text = db.Column(db.Text, nullable=False)  # 영어 텍스트
    
    # 음성 파일명
    audio_filename = db.Column(db.String(255))
    
    # 생성일
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 인덱스 추가 (챕터와 순서로 정렬하기 위해)
    __table_args__ = (
        db.Index('ix_story_chapter_order', 'chapter_id', 'order'),
    )
    
    def __repr__(self):
        return f'<Story {self.chapter_id}-{self.order}>'
    
    @property
    def display_title(self):
        """표시용 제목 생성 (챕터 제목 + 순서)"""
        return f"{self.chapter_obj.title} - {self.order}"