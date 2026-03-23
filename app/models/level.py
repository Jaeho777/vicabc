# app/models/level.py
from datetime import datetime
from app.extensions import db

class Level(db.Model):
    __tablename__ = 'levels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)  # A1, A2, B1 등
    description = db.Column(db.String(200))
    category = db.Column(db.String(20), default='초등')  # 초등, 중등, 고등
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정 (Level에 속한 단어들)
    vocabularies = db.relationship('Vocabulary', backref='level', lazy=True)
    
    def __repr__(self):
        return f'<Level {self.name}>'