from sqlalchemy import func
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.level import Level
from app.models.vocabulary import Vocabulary
from app.routes.admin import admin_required, admin_level_required
from flask import session
from datetime import datetime

from app.models.user_progress import UserProgress


voca_bp = Blueprint('voca', __name__, url_prefix='/voca')

@voca_bp.route('/')
@login_required
def index():
    # 초등, 중등, 고등 카테고리의 레벨들을 가져옴
    elementary_levels = Level.query.filter_by(category='초등').all()
    middle_levels = Level.query.filter_by(category='중등').all()
    high_levels = Level.query.filter_by(category='고등').all()
    
    # 레벨 이름에서 그룹 번호 추출하여 정렬
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
    
    # 그룹 번호 순으로 정렬
    elementary_levels.sort(key=sort_by_group)
    middle_levels.sort(key=sort_by_group)
    high_levels.sort(key=sort_by_group)
    
    # 사용자의 모든 레벨 진도 정보 가져오기
    from app.models.user_progress import UserProgress
    from sqlalchemy import func
    
    # 각 레벨별 진도 정보를 저장할 딕셔너리
    level_progress = {}
    
    # 현재 사용자의 모든 레벨에 대한 진도 정보 계산
    for level in elementary_levels + middle_levels + high_levels:
        # 레벨의 총 단어 수
        total_words = Vocabulary.query.filter_by(level_id=level.id).count()
        
        if total_words > 0:
            # 완료한 단어 수 (status = 2는 학습 완료)
            completed_words = (UserProgress.query
                              .join(Vocabulary)
                              .filter(UserProgress.user_id == current_user.id,
                                     Vocabulary.level_id == level.id,
                                     UserProgress.status == 2)
                              .count())
            
            # 진행 중인 단어 수 (status = 1은 학습 중)
            in_progress_words = (UserProgress.query
                                .join(Vocabulary)
                                .filter(UserProgress.user_id == current_user.id,
                                       Vocabulary.level_id == level.id,
                                       UserProgress.status == 1)
                                .count())
            
            # 진도율 계산
            progress_percent = (completed_words / total_words) * 100 if total_words > 0 else 0
            
            # 결과 저장
            level_progress[level.id] = {
                'total_words': total_words,
                'completed_words': completed_words,
                'in_progress_words': in_progress_words,
                'progress_percent': round(progress_percent, 1)
            }
        else:
            # 단어가 없는 레벨의 경우
            level_progress[level.id] = {
                'total_words': 0,
                'completed_words': 0,
                'in_progress_words': 0,
                'progress_percent': 0
            }
    
    return render_template('voca/index.html', 
                           elementary_levels=elementary_levels,
                           middle_levels=middle_levels,
                           high_levels=high_levels,
                           level_progress=level_progress)


@voca_bp.route('/level/<int:level_id>')
@login_required
def voca_level_words(level_id):
    level = Level.query.get_or_404(level_id)
    vocabularies = Vocabulary.query.filter_by(level_id=level_id).all()
    
    # 사용자의 단어 학습 상태 가져오기
    from app.models.user_progress import UserProgress
    
    # 단어별 학습 상태를 저장할 딕셔너리
    vocabulary_progress = {}
    
    # 현재 사용자의 이 레벨에 대한 모든 진도 정보 가져오기
    progress_entries = UserProgress.query.filter(
        UserProgress.user_id == current_user.id,
        UserProgress.vocabulary_id.in_([v.id for v in vocabularies])
    ).all()
    
    # 단어별 학습 상태 매핑
    for entry in progress_entries:
        vocabulary_progress[entry.vocabulary_id] = {
            'status': entry.status,
            'total_score': entry.total_score
        }
    
    # 완료된 단어 수 계산
    completed_words = sum(1 for entry in progress_entries if entry.status == 2)
    total_words = len(vocabularies)
    
    return render_template('voca/voca_level_words.html', 
                           level=level,
                           vocabularies=vocabularies,
                           vocabulary_progress=vocabulary_progress,
                           total_words=total_words,
                           completed_words=completed_words)




@voca_bp.route('/level/<int:level_id>/practice')
@voca_bp.route('/level/<int:level_id>/practice/<int:word_index>')
@login_required
def level_practice(level_id, word_index=None):
    # 레벨 정보 가져오기
    level = Level.query.get_or_404(level_id)
    
    # 해당 레벨의 단어들 가져오기
    vocabularies = Vocabulary.query.filter_by(level_id=level_id).all()
    
    if not vocabularies:
        flash('이 레벨에 등록된 단어가 없습니다.', 'info')
        return redirect(url_for('voca.voca_level_words', level_id=level_id))
    
    # 세션에 단어 목록이 없으면 초기화
    session_key = f'level_{level_id}_words'
    
    if session_key not in session:
        # 단어 ID 목록을 랜덤하게 섞어서 세션에 저장
        import random
        vocabulary_ids = [v.id for v in vocabularies]
        random.shuffle(vocabulary_ids)
        session[session_key] = vocabulary_ids
    
    # 총 단어 수
    total_words = len(vocabularies)
    
    # word_index가 지정되지 않았으면 랜덤 인덱스 생성
    if word_index is None:
        import random
        random_vocabulary = random.choice(vocabularies)
        vocabulary = random_vocabulary
        word_number = 1
    else:
        # 인덱스 조정 (세션 인덱스는 0부터 시작)
        array_index = word_index - 1
        if array_index < 0 or array_index >= len(session[session_key]):
            array_index = 0
        vocabulary_id = session[session_key][array_index]
        vocabulary = Vocabulary.query.get(vocabulary_id)
        word_number = word_index
    
    # 다음 단어 인덱스 계산
    next_index = word_number + 1 if word_number < total_words else 1
    
    return render_template('voca/practice_word.html', 
                          level=level,
                          vocabulary=vocabulary,
                          word_number=word_number,
                          total_words=total_words,
                          next_index=next_index)




import os
import tempfile
from flask import request, jsonify

@voca_bp.route('/process_audio', methods=['POST'])
@login_required
def process_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    word_to_compare = request.form.get('word', '')
    
    # 임시 파일로 오디오 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
        audio_file.save(temp_audio.name)
        temp_filename = temp_audio.name
    
    try:
        from app.services.speech_service import transcribe_audio, calculate_pronunciation_accuracy
        
        # 오디오 파일 텍스트 변환
        result = transcribe_audio(temp_filename)
        transcribed_text = result["text"]
        
        # 정확도 계산
        accuracy, details = calculate_pronunciation_accuracy(transcribed_text, word_to_compare)
        
        # 파일 삭제
        os.unlink(temp_filename)
        
        return jsonify({
            'success': True,
            'transcribed_text': transcribed_text,
            'original_word': word_to_compare,
            'accuracy': accuracy,
            'details': details,
            'processing_time': result.get("processing_time", 0)
        })
        
    except Exception as e:
        # 임시 파일 삭제
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        return jsonify({'error': str(e)}), 500
    

@voca_bp.route('/save_progress', methods=['POST'])
@login_required
def save_progress():
    data = request.json
    vocabulary_id = data.get('vocabulary_id')
    speaking_score = data.get('speaking_score', 0)
    english_writing_score = data.get('english_writing_score', 0)
    korean_writing_score = data.get('korean_writing_score', 0)
    
    # 총점 계산 - 듣기 점수 제외하고 말하기, 영어 쓰기, 한글 쓰기 평균
    total_score = (speaking_score + english_writing_score + korean_writing_score) // 3
    
    # 기존 진도 확인
    progress = UserProgress.query.filter_by(
        user_id=current_user.id,
        vocabulary_id=vocabulary_id
    ).first()
    
    if progress:
        # 기존 진도 업데이트
        progress.speaking_score = speaking_score
        progress.english_writing_score = english_writing_score
        progress.korean_writing_score = korean_writing_score
        progress.total_score = total_score
        progress.last_studied_at = datetime.utcnow()
        progress.study_count += 1
        
        # 모든 점수가 80점 이상이면 학습 완료로 표시
        if speaking_score >= 80 and english_writing_score >= 80 and korean_writing_score >= 80:
            progress.status = 2  # 학습 완료
        else:
            progress.status = 1  # 학습 중
    else:
        # 새 진도 생성
        progress = UserProgress(
            user_id=current_user.id,
            vocabulary_id=vocabulary_id,
            speaking_score=speaking_score,
            english_writing_score=english_writing_score,
            korean_writing_score=korean_writing_score,
            total_score=total_score,
            status=2 if (speaking_score >= 80 and english_writing_score >= 80 and korean_writing_score >= 80) else 1
        )
        db.session.add(progress)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'status': progress.status,
        'total_score': total_score
    })