# app/routes/exam.py
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.level import Level
from app.models.vocabulary import Vocabulary
from app.models.certification import Certification
from datetime import datetime
import random
import pytz

exam_bp = Blueprint('exam', __name__, url_prefix='/exam')

@exam_bp.route('/voca')
@login_required
def voca_index():
    """VOCA 인증시험 메인 페이지"""
    # 초등, 중등, 고등 카테고리의 레벨들을 가져옴
    elementary_levels = Level.query.filter_by(category='초등').all()
    middle_levels = Level.query.filter_by(category='중등').all()
    high_levels = Level.query.filter_by(category='고등').all()
    
    # 정렬 함수 (레벨 이름 기준) - 수정된 부분
    def sort_by_group(level):
        # 새로운 형식: "초등1-G3-학교" 또는 기존 형식: "초등1-G3"
        try:
            # 레벨 이름에서 "G" 뒤의 숫자 부분 추출
            import re
            # G 다음의 숫자를 찾기 (G1, G2, G3 등)
            match = re.search(r'-G(\d+)', level.name)
            if match:
                return int(match.group(1))
            return 0  # G가 없으면 0으로 정렬
        except:
            return 0  # 변환 오류 시 0으로 정렬
    
    # 정렬
    elementary_levels.sort(key=sort_by_group)
    middle_levels.sort(key=sort_by_group)
    high_levels.sort(key=sort_by_group)
    
    # 사용자의 이전 인증 시험 결과 가져오기
    previous_results = {}
    for level in elementary_levels + middle_levels + high_levels:
        # 해당 레벨의 최근 시험 결과
        latest_cert = (Certification.query
                       .filter_by(user_id=current_user.id, level_id=level.id)
                       .order_by(Certification.exam_date.desc())
                       .first())
        
        if latest_cert:
            previous_results[level.id] = {
                'passed': latest_cert.passed,
                'score': latest_cert.score,
                'exam_date': latest_cert.exam_date
            }
    
    return render_template('voca_exam/index.html',
                          elementary_levels=elementary_levels,
                          middle_levels=middle_levels,
                          high_levels=high_levels,
                          previous_results=previous_results)

@exam_bp.route('/voca/level/<int:level_id>/start')
@login_required
def voca_start_exam(level_id):
    """VOCA 인증시험 시작"""
    # 레벨 정보 가져오기
    level = Level.query.get_or_404(level_id)
    
    # 해당 레벨의 단어들 가져오기
    vocabularies = Vocabulary.query.filter_by(level_id=level_id).all()
    
    if not vocabularies:
        flash('이 레벨에 등록된 단어가 없습니다.', 'info')
        return redirect(url_for('exam.voca_index'))
    
    # 세션에 시험 정보 저장
    session_key = f'exam_voca_level_{level_id}'
    
    # 단어 ID 목록을 랜덤하게 섞어서 세션에 저장
    vocabulary_ids = [v.id for v in vocabularies]
    random.shuffle(vocabulary_ids)
    session[session_key] = vocabulary_ids
    
    # 첫 번째 단어로 리다이렉트
    return redirect(url_for('exam.voca_take_exam', level_id=level_id, word_index=1))

@exam_bp.route('/voca/level/<int:level_id>/exam/<int:word_index>')
@login_required
def voca_take_exam(level_id, word_index):
    """VOCA 인증시험 단어별 시험 페이지"""
    # 레벨 정보 가져오기
    level = Level.query.get_or_404(level_id)
    
    # 세션에서 단어 ID 목록 가져오기
    session_key = f'exam_voca_level_{level_id}'
    if session_key not in session:
        return redirect(url_for('exam.voca_start_exam', level_id=level_id))
    
    vocabulary_ids = session[session_key]
    total_words = len(vocabulary_ids)
    
    # 인덱스 조정 (세션 인덱스는 0부터 시작)
    array_index = word_index - 1
    if array_index < 0 or array_index >= total_words:
        array_index = 0
    
    vocabulary_id = vocabulary_ids[array_index]
    vocabulary = Vocabulary.query.get(vocabulary_id)
    
    # 다음 단어 인덱스 계산
    next_index = word_index + 1 if word_index < total_words else 0
    
    # 결과 저장 키 생성
    results_key = f'exam_voca_results_{level_id}'
    if results_key not in session:
        session[results_key] = {}
    
    return render_template('voca_exam/exam_word.html',
                          level=level,
                          vocabulary=vocabulary,
                          word_number=word_index,
                          total_words=total_words,
                          next_index=next_index,
                          is_last_word=(next_index == 0))

@exam_bp.route('/save_voca_result', methods=['POST'])
@login_required
def save_voca_result():
    """VOCA 시험 결과 저장 (AJAX)"""
    data = request.json
    level_id = data.get('level_id')
    vocabulary_id = data.get('vocabulary_id')
    speaking_score = data.get('speaking_score', 0)
    english_writing_score = data.get('english_writing_score', 0)
    
    # 총점 계산 (말하기 50%, 영어 쓰기 50%)
    total_score = (speaking_score + english_writing_score) // 2
    
    # 결과를 세션에 저장
    results_key = f'exam_voca_results_{level_id}'
    if results_key not in session:
        session[results_key] = {}
    
    session[results_key][str(vocabulary_id)] = {
        'speaking_score': speaking_score,
        'english_writing_score': english_writing_score,
        'total_score': total_score,
        'passed': total_score >= 80  # 80점 이상이면 합격으로 간주
    }
    
    # session 변경사항을 저장
    session.modified = True
    
    return jsonify({'success': True})

@exam_bp.route('/voca/level/<int:level_id>/result')
@login_required
def voca_exam_result(level_id):
    """VOCA 시험 결과 페이지"""
    # 레벨 정보 가져오기
    level = Level.query.get_or_404(level_id)
    
    # 세션에서 결과 가져오기
    results_key = f'exam_voca_results_{level_id}'
    if results_key not in session:
        flash('시험 결과를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('exam.voca_index'))
    
    results = session[results_key]
    
    # 총점 및 합격 여부 계산
    total_words = len(results)
    if total_words == 0:
        flash('시험 결과를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('exam.voca_index'))
    
    passed_words = sum(1 for r in results.values() if r.get('passed', False))
    overall_score = sum(r.get('total_score', 0) for r in results.values()) // total_words
    
    # 100% 정답이면 합격, 그렇지 않으면 불합격
    is_passed = passed_words == total_words

    korea_tz = pytz.timezone('Asia/Seoul')
    korea_time = datetime.now(korea_tz)
    
    # 데이터베이스에 결과 저장
    certification = Certification(
        user_id=current_user.id,
        level_id=level_id,
        passed=is_passed,
        score=overall_score,
        exam_date=korea_time,
    )
    
    db.session.add(certification)
    db.session.commit()
    
    # 세션에서 시험 데이터 삭제
    if results_key in session:
        del session[results_key]
    
    session_key = f'exam_voca_level_{level_id}'
    if session_key in session:
        del session[session_key]
    
    return render_template('voca_exam/exam_result.html',
                          level=level,
                          overall_score=overall_score,
                          total_words=total_words,
                          passed_words=passed_words,
                          is_passed=is_passed)