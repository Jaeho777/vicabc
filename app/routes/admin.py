from flask import Blueprint, render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from functools import wraps
from app.extensions import db
from app.models.user import User
import random #나중에 제거
from app.models.level import Level
from app.models.vocabulary import Vocabulary
from app.models.user_progress import UserProgress
from app.models.certification import Certification


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('관리자 권한이 필요합니다.', 'danger')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def admin_level_required(level):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 'A'가 최고 관리자, 'B'가 교회 전체 관리자, 'C'가 교회 과목 담당자
            admin_levels = {'A': 3, 'B': 2, 'C': 1}
            user_level = admin_levels.get(current_user.admin_type, 0)
            required_level = admin_levels.get(level, 0)
            
            if user_level < required_level:
                flash(f'{level} 레벨 이상의 관리자 권한이 필요합니다.', 'danger')
                return redirect(url_for('admin.admin'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# 관리자 메인 페이지
@admin_bp.route('/')
@login_required
@admin_required
def admin():
    return render_template('admin/admin.html')

# 사용자 관리 페이지
@admin_bp.route('/users')
@login_required
@admin_required
def user_management():
    # A 레벨은 모든 사용자, B 레벨은 자신의 교회와 다른 교회 요약, C 레벨은 자신의 교회만
    users = []
    if current_user.admin_type == 'A':  # 시스템 전체 관리자
        users = User.query.all()
    elif current_user.admin_type == 'B':  # 교회 전체 관리자
        # 다른 교회 정보도 보이지만 자세한 정보는 제한
        users = User.query.filter_by(church=current_user.church).all()
    elif current_user.admin_type == 'C':  # 교회 과목 담당자
        # 자신의 교회 사용자만 표시
        users = User.query.filter_by(church=current_user.church).all()
    
    return render_template('admin/user_management.html', users=users)



# 관리자 권한 변경 (A 레벨만 가능)
@admin_bp.route('/change_admin/<int:user_id>/<admin_type>')
@login_required
@admin_required
@admin_level_required('A')
def change_admin(user_id, admin_type):
    user = User.query.get_or_404(user_id)
    if admin_type in ['A', 'B', 'C', 'none']:
        if admin_type == 'none':
            user.is_admin = False
            user.admin_type = None
        else:
            user.is_admin = True
            user.admin_type = admin_type
        db.session.commit()
        flash(f'{user.username}의 관리자 권한이 {admin_type}로 변경되었습니다.', 'success')
    return redirect(url_for('admin.user_management'))



# 학생 관리 페이지
@admin_bp.route('/student_management')
@login_required
@admin_required
def student_management():
    churches = []
    selected_church = None
    
    # A 레벨은 모든, B/C 레벨은 자신의 교회만
    if current_user.admin_type == 'A':
        # 시스템 전체 관리자: 모든 교회 목록을 가져옴
        churches = db.session.query(User.church).distinct().all()
        churches = [church[0] for church in churches if church[0]]
        
        # 교회 선택 (GET 파라미터로 전달 or 첫 번째 교회)
        selected_church = request.args.get('church', churches[0] if churches else None)
    else:
        # B, C 레벨: 자신의 교회만
        selected_church = current_user.church
    
    # 선택된 교회에 속한 비관리자 사용자만 조회
    students = []
    if selected_church:
        students = User.query.filter_by(church=selected_church, is_admin=False).all()
    
    # 선택된 탭 (기본값: voca)
    tab = request.args.get('tab', 'voca')
    
    return render_template(
        'admin/student_management.html',
        churches=churches,
        selected_church=selected_church,
        students=students,
        tab=tab
    )


# admin.py에 추가할 코드

# 교회 관리 페이지 수정
@admin_bp.route('/church_management')
@login_required
@admin_required
@admin_level_required('B')  # A, B 레벨만 접근 가능
def church_management():
    all_churches = []
    selected_church = None
    
    # 모든 교회 목록을 가져옴 (A, B 모두 모든 교회 확인 가능)
    all_churches = db.session.query(User.church).distinct().all()
    all_churches = [church[0] for church in all_churches if church[0]]
    
    # 교회 선택 (GET 파라미터로 전달 or 첫 번째 교회)
    selected_church = request.args.get('church', all_churches[0] if all_churches else None)
    
    # 학년 그룹 정의 (임시 데이터)
    grade_groups = [
        {"name": "초등1", "voca_avg": round(1 + 2 * random.random(), 1), 
         "story_avg": round(1 + 2 * random.random(), 1), "conv_avg": round(1 + 2 * random.random(), 1)},
        {"name": "초등2", "voca_avg": round(1 + 2 * random.random(), 1), 
         "story_avg": round(1 + 2 * random.random(), 1), "conv_avg": round(1 + 2 * random.random(), 1)},
        {"name": "초등3", "voca_avg": round(1 + 2 * random.random(), 1), 
         "story_avg": round(1 + 2 * random.random(), 1), "conv_avg": round(1 + 2 * random.random(), 1)},
        {"name": "초등4", "voca_avg": round(1 + 2 * random.random(), 1), 
         "story_avg": round(1 + 2 * random.random(), 1), "conv_avg": round(1 + 2 * random.random(), 1)}
    ]
    
    return render_template(
        'admin/church_management.html', 
        all_churches=all_churches,
        selected_church=selected_church,
        grade_groups=grade_groups
    )



# admin.py에 추가
@admin_bp.route('/content')
@login_required
@admin_required
@admin_level_required('A')  # 최종 관리자만 접근 가능
def content_management():
    return render_template('admin/content_management.html')



@admin_bp.route('/delete_level/<int:level_id>', methods=['POST'])
@login_required
@admin_required
@admin_level_required('A')  # 최종관리자만 접근 가능
def delete_level(level_id):
    """레벨과 관련된 모든 데이터 삭제"""
    try:
        # 레벨 정보 가져오기
        level = Level.query.get_or_404(level_id)
        level_name = level.name
        
        # 해당 레벨의 모든 단어 가져오기
        vocabularies = Vocabulary.query.filter_by(level_id=level_id).all()
        vocabulary_ids = [vocab.id for vocab in vocabularies]
        
        # 1. 해당 단어들의 모든 학습 진도 기록 삭제
        if vocabulary_ids:
            UserProgress.query.filter(UserProgress.vocabulary_id.in_(vocabulary_ids)).delete(synchronize_session=False)
        
        # 2. 해당 레벨의 모든 인증 기록 삭제
        Certification.query.filter_by(level_id=level_id).delete()
        
        # 3. 해당 레벨의 모든 단어 삭제
        Vocabulary.query.filter_by(level_id=level_id).delete()
        
        # 4. 레벨 자체 삭제
        db.session.delete(level)
        
        # 변경사항 커밋
        db.session.commit()
        
        flash(f'"{level_name}" 레벨과 관련된 모든 데이터가 성공적으로 삭제되었습니다.', 'success')
        
    except Exception as e:
        # 오류 발생 시 롤백
        db.session.rollback()
        flash(f'레벨 삭제 중 오류가 발생했습니다: {str(e)}', 'danger')
    
    # 단어 학습 페이지로 리다이렉트
    return redirect(url_for('voca.index'))