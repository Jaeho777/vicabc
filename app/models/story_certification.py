# app/models/story_certification.py
from datetime import datetime
from app.extensions import db

class StoryCertification(db.Model):
    __tablename__ = 'story_certifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    
    # 시험 결과 (0: 불합격, 1: 합격)
    passed = db.Column(db.Boolean, default=False)
    
    # 시험 점수
    score = db.Column(db.Integer, default=0)
    
    # 시험 일자
    exam_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정
    user = db.relationship('User', backref=db.backref('story_certifications', lazy='dynamic'))
    level = db.relationship('Level', backref=db.backref('story_certifications', lazy='dynamic'))
    chapter = db.relationship('Chapter', backref=db.backref('story_certifications', lazy='dynamic'))
    
    def __repr__(self):
        return (
            f'<StoryCertification user_id={self.user_id} '
            f'level_id={self.level_id} chapter_id={self.chapter_id} passed={self.passed}>'
        )
