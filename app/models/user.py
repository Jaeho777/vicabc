# app/models/user.py
from datetime import datetime
from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.models.certification import Certification
from app.models.level import Level

class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email = db.Column(db.String(120), unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    church = db.Column(db.String(100), nullable=False)
    school = db.Column(db.String(100))
    grade = db.Column(db.Integer, nullable=False)
    phone = db.Column(db.String(20))
    parent_phone = db.Column(db.String(20), nullable=False)
    security_question = db.Column(db.String(200), nullable=False)
    security_answer = db.Column(db.String(200), nullable=False)
    registered_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    admin_type = db.Column(db.String(1), nullable=True)  # 관리자 레벨 (A, B, C)
    education_level = db.Column(db.String(20))
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'
        
    def get_certification_level(self, category):
        """사용자의 특정 카테고리에서의 인증 레벨을 가져오는 메서드
        
        Args:
            category (str): '초등', '중등', '고등' 중 하나
            
        Returns:
            dict: {'level': 레벨 객체, 'date': 인증 날짜}
        """
        from app.models.certification import Certification
        from app.models.level import Level
        
        # 해당 카테고리에서 합격한 인증 시험 모두 찾기
        certifications = (Certification.query
                        .join(Level)
                        .filter(Certification.user_id == self.id,
                                Level.category == category,
                                Certification.passed == True)
                        .all())
        
        if not certifications:
            return {
                'level': None,
                'date': None
            }
        
        # 레벨 이름에서 학년과 그룹 번호 추출하여 정렬하는 함수
        def get_level_rank(level_name):
            try:
                # 카테고리 가중치 (고등=3, 중등=2, 초등=1)
                category_weight = {
                    '고등': 3000,
                    '중등': 2000,
                    '초등': 1000
                }
                
                # 카테고리와 학년 분리
                for cat in category_weight:
                    if cat in level_name:
                        category_part = cat
                        grade_part = level_name.replace(cat, '')
                        break
                else:
                    # 카테고리를 찾지 못한 경우
                    return 0
                
                # 학년 숫자 추출
                grade_digits = ''.join(filter(str.isdigit, grade_part.split('-')[0]))
                grade = int(grade_digits) if grade_digits else 0
                
                # 그룹 번호 추출
                group_part = level_name.split('-')[1] if '-' in level_name else 'G0'
                group_digits = ''.join(filter(str.isdigit, group_part))
                group = int(group_digits) if group_digits else 0
                
                # 카테고리 + 학년*100 + 그룹 형태로 숫자 반환
                # 예: 고등3-G2 = 3000 + 300 + 2 = 3302
                # 예: 초등6-G1 = 1000 + 600 + 1 = 1601
                return category_weight.get(category_part, 0) + (grade * 100) + group
                
            except Exception as e:
                print(f"레벨 파싱 오류: {level_name}, 오류: {e}")
                return 0
        
        # 가장 높은 레벨의 인증 찾기
        highest_cert = max(certifications, key=lambda cert: get_level_rank(cert.level.name))
        
        return {
            'level': highest_cert.level,
            'date': highest_cert.exam_date
        }