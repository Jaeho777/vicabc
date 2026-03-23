# app/models/vocabulary.py
from datetime import datetime
from app.extensions import db

class Vocabulary(db.Model):
    __tablename__ = 'vocabularies'
    
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False)
    part_of_speech = db.Column(db.String(20))  # 품사 정보 (명사, 동사 등)
    meaning = db.Column(db.String(200), nullable=False)  # 한국어 의미
    
    # 레벨 관계 (외래키)
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    
    # 추가 정보
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Vocabulary {self.word}>'