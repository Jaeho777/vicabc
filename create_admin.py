# create_admin.py
import os
import getpass
import sys

from app import create_app, db
from app.models import User
from werkzeug.security import generate_password_hash

def create_admin_account(username, email, password, full_name, admin_type):
    """관리자 계정을 생성합니다."""
    try:
        app = create_app()
        with app.app_context():
            # 이미 존재하는 사용자인지 확인
            exists = User.query.filter(
                (User.username == username) | (User.email == email)
            ).first()
            
            if exists:
                print(f"오류: 사용자명 '{username}' 또는 이메일 '{email}'이 이미 존재합니다.")
                return False
            
            # 관리자 계정 생성
            admin = User(
                username=username,
                email=email,
                full_name=full_name,
                gender='남성',  # 기본값 설정
                age=30,  # 기본값 설정
                church='시스템',  # 기본값 설정
                school='관리자',  # 기본값 설정
                grade=0,  # 기본값 설정
                phone='010-0000-0000',  # 기본값 설정
                parent_phone='010-0000-0000',  # 기본값 설정
                security_question='관리자 계정입니다',  # 기본값 설정
                security_answer='관리자',  # 기본값 설정
                is_admin=True,
                admin_type=admin_type
            )
            admin.password_hash = generate_password_hash(password)
            
            db.session.add(admin)
            db.session.commit()
            print(f"관리자 계정 '{username}'이 성공적으로 생성되었습니다.")
            return True
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        return False

def interactive_create_admin():
    """대화형 관리자 계정 생성"""
    print("VOCA 애플리케이션 관리자 계정 생성")
    print("=" * 40)
    
    username = input("사용자명: ")
    email = input("이메일: ")
    full_name = input("이름: ")
    
    while True:
        admin_type = input("관리자 유형 (A: 최종관리자, B: 교회관리자, C: 학생관리자): ").upper()
        if admin_type in ['A', 'B', 'C']:
            break
        print("잘못된 관리자 유형입니다. A, B, C 중 하나를 입력하세요.")
    
    password = getpass.getpass("비밀번호: ")
    confirm_password = getpass.getpass("비밀번호 확인: ")
    
    if password != confirm_password:
        print("비밀번호가 일치하지 않습니다.")
        return
    
    if len(password) < 6:
        print("비밀번호는 최소 6자 이상이어야 합니다.")
        return
    
    create_admin_account(username, email, password, full_name, admin_type)

def create_default_admin():
    """기본 관리자 계정 생성"""
    password = os.environ.get("DEFAULT_ADMIN_PASSWORD")
    if not password:
        print("오류: DEFAULT_ADMIN_PASSWORD 환경 변수를 설정한 뒤 다시 실행하세요.")
        return False

    create_admin_account(
        username='admin',
        email='admin@example.com',
        password=password,
        full_name='관리자',
        admin_type='A'
    )

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--default':
        # 기본 관리자 계정 생성
        create_default_admin()
    else:
        # 대화형 관리자 계정 생성
        interactive_create_admin()
