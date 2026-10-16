# app/routes/auth.py (처음 부분만 수정)
from flask import Blueprint, current_app, make_response, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.user import User
from app.services.profile import ProfileValidationError, save_profile_name
from app.services.profile_forms import profile_csrf_token, validate_profile_csrf_token
# 나머지 코드는 동일
import random
import string
import secrets
from flask import session


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email', '')
        if email.strip() == '':
            email = None  
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        gender = request.form.get('gender')
        age = request.form.get('age')
        church = request.form.get('church')
        school = request.form.get('school')
        grade = request.form.get('grade')
        phone = request.form.get('phone')
        parent_phone = request.form.get('parent_phone')
        security_question = request.form.get('security_question')
        security_answer = request.form.get('security_answer')
        
        # 비밀번호 확인
        # 비밀번호 확인
        if password != confirm_password:
            flash('비밀번호가 일치하지 않습니다.', 'danger')
            return render_template('auth/register.html')

        # 사용자 이름 중복 확인
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('이미 사용 중인 아이디입니다.', 'danger')
            return render_template('auth/register.html')

        # 이메일 중복 확인 (이메일이 제공된 경우)
        if email:
            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash('이미 사용 중인 이메일입니다.', 'danger')
                return render_template('auth/register.html')
        
        new_user = User(
            username=username,
            email=email,
            full_name=full_name,
            gender=gender,
            age=int(age),
            church=church,
            school=school,
            grade=int(grade),
            phone=phone,
            parent_phone=parent_phone,
            security_question=security_question,
            security_answer=security_answer
        )
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('회원가입이 완료되었습니다. 로그인해주세요.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        step = request.form.get('step', 'find_user')
        
        if step == 'find_user':
            # 1단계: 사용자 이름으로 계정 찾기
            username = request.form.get('username')
            user = User.query.filter_by(username=username).first()
            
            if not user:
                flash('존재하지 않는 사용자입니다.', 'danger')
                return render_template('auth/forgot_password.html', step='find_user')
                
            # 사용자를 찾았으면 보안 질문 단계로 이동
            return render_template('auth/forgot_password.html', 
                                  step='answer_question',
                                  username=username,
                                  security_question=user.security_question)
        
        elif step == 'answer_question':
            # 2단계: 보안 질문 확인
            username = request.form.get('username')
            security_answer = request.form.get('security_answer')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.security_answer == security_answer:
                # 답변이 맞으면 비밀번호 재설정 단계로 이동
                return render_template('auth/forgot_password.html', 
                                      step='reset_password',
                                      username=username)
            else:
                flash('보안 질문 답변이 일치하지 않습니다.', 'danger')
                return render_template('auth/forgot_password.html', 
                                      step='answer_question',
                                      username=username,
                                      security_question=user.security_question)
        
        elif step == 'reset_password':
            # 3단계: 새 비밀번호 설정
            username = request.form.get('username')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if new_password != confirm_password:
                flash('비밀번호가 일치하지 않습니다.', 'danger')
                return render_template('auth/forgot_password.html', 
                                      step='reset_password',
                                      username=username)
            
            user = User.query.filter_by(username=username).first()
            if user:
                user.set_password(new_password)
                db.session.commit()
                
                flash('비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인하세요.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('사용자를 찾을 수 없습니다.', 'danger')
                return redirect(url_for('auth.forgot_password'))
    
    return render_template('auth/forgot_password.html', step='find_user')


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Let a signed-in user edit their own display name, and nothing else."""
    user = current_user._get_current_object()
    profile_name = user.full_name
    profile_error = None
    status = 200

    if request.method == 'POST':
        request.max_content_length = 8192
        validate_profile_csrf_token()
        profile_name = request.form.get('full_name', '')
        try:
            save_profile_name(user, profile_name)
        except ProfileValidationError as error:
            profile_error = str(error)
            status = 400
        except SQLAlchemyError:
            current_app.logger.error('Could not save the profile display name.')
            profile_error = '이름을 저장하지 못했습니다. 잠시 후 다시 시도해주세요.'
            status = 503
        else:
            flash('이름을 변경했습니다.', 'success')
            return redirect(url_for('auth.profile'), code=303)

    response = make_response(render_template(
        'auth/profile.html',
        csrf_token=profile_csrf_token(),
        profile_name=profile_name,
        profile_error=profile_error,
    ), status)
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.vary.add('Cookie')
    return response
