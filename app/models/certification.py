# app/models/certification.py
from datetime import datetime
from app.extensions import db

class Certification(db.Model):
    __tablename__ = 'certifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    level_id = db.Column(db.Integer, db.ForeignKey('levels.id'), nullable=False)
    
    # 시험 결과 (0: 불합격, 1: 합격)
    passed = db.Column(db.Boolean, default=False)
    
    # 시험 점수
    score = db.Column(db.Integer, default=0)
    
    # 시험 일자
    exam_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # 관계 설정
    user = db.relationship('User', backref=db.backref('certifications', lazy='dynamic'))
    level = db.relationship('Level', backref=db.backref('certifications', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Certification user_id={self.user_id} level_id={self.level_id} passed={self.passed}>'