from sqlalchemy import func
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.chapter import Chapter
from app.models.story import Story
from flask import session
from datetime import datetime
import random
import os
import tempfile
from flask import request, jsonify
import pytz
from difflib import SequenceMatcher

from app.models.story_progress import StoryProgress
from app.models.story_certification import StoryCertification

story_bp = Blueprint('story', __name__, url_prefix='/story')


def _normalize_score(value):
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(score, 100))


def _normalize_text_for_similarity(text):
    return " ".join((text or "").strip().lower().split())


def _calculate_text_similarity_score(submitted_text, reference_text):
    submitted = _normalize_text_for_similarity(submitted_text)
    reference = _normalize_text_for_similarity(reference_text)

    if not submitted or not reference:
        return 0

    return _normalize_score(SequenceMatcher(None, submitted, reference).ratio() * 100)


def _story_exam_session_key(chapter_id):
    return f'story_exam_chapter_{chapter_id}'


def _story_exam_results_key(chapter_id):
    return f'story_exam_results_{chapter_id}'


def _story_exam_speaking_key(chapter_id):
    return f'story_exam_speaking_scores_{chapter_id}'


def _get_story_exam_story_ids(chapter_id):
    return session.get(_story_exam_session_key(chapter_id), [])


def _get_story_exam_story(chapter_id, story_id):
    if not chapter_id or not story_id:
        return None

    story_ids = _get_story_exam_story_ids(chapter_id)
    if story_id not in story_ids:
        return None

    return Story.query.filter_by(id=story_id, chapter_id=chapter_id).first()


def _store_story_exam_speaking_score(chapter_id, story_id, score):
    scores = session.get(_story_exam_speaking_key(chapter_id), {})
    current_score = _normalize_score(scores.get(str(story_id), 0))
    scores[str(story_id)] = max(current_score, _normalize_score(score))
    session[_story_exam_speaking_key(chapter_id)] = scores
    session.modified = True

@story_bp.route('/')
@login_required
def index():
    # 초등, 중등, 고등별로 학년 데이터 구성
    grades_data = {
        '초등': list(range(1, 7)),  # 1-6학년
        '중등': list(range(1, 4)),  # 1-3학년 
        '고등': list(range(1, 4))   # 1-3학년
    }
    
    return render_template('story/index.html', grades_data=grades_data)

@story_bp.route('/grade/<int:grade>/semester/<int:semester>')
@login_required
def semester_chapters(grade, semester):
    """특정 학년의 특정 학기 챕터들 표시"""
    # 해당 학년, 학기의 모든 챕터들 가져오기
    chapters = Chapter.query.filter_by(
        grade=grade, 
        semester=semester,
        category='초등'  # 일단 초등만
    ).order_by(Chapter.order).all()
    
    # 각 챕터별 진도 정보 계산
    chapter_progress = {}
    for chapter in chapters:
        # 챕터의 총 스토리 수
        total_stories = len(chapter.stories)
        
        if total_stories > 0:
            # 완료한 스토리 수
            completed_stories = 0
            in_progress_stories = 0
            
            for story in chapter.stories:
                progress = StoryProgress.query.filter_by(
                    user_id=current_user.id,
                    story_id=story.id
                ).first()
                
                if progress:
                    if progress.status == 2:  # 완료
                        completed_stories += 1
                    elif progress.status == 1:  # 진행중
                        in_progress_stories += 1
            
            # 진도율 계산
            progress_percent = (completed_stories / total_stories) * 100
            
            chapter_progress[chapter.id] = {
                'total_stories': total_stories,
                'completed_stories': completed_stories,
                'in_progress_stories': in_progress_stories,
                'progress_percent': round(progress_percent, 1)
            }
        else:
            chapter_progress[chapter.id] = {
                'total_stories': 0,
                'completed_stories': 0,
                'in_progress_stories': 0,
                'progress_percent': 0
            }
    
    return render_template('story/semester_chapters.html',
                          grade=grade,
                          semester=semester,
                          chapters=chapters,
                          chapter_progress=chapter_progress)

@story_bp.route('/chapter/<int:chapter_id>')
@login_required
def chapter_stories(chapter_id):
    """특정 챕터의 스토리 목록"""
    chapter = Chapter.query.get_or_404(chapter_id)
    stories = Story.query.filter_by(chapter_id=chapter_id).order_by(Story.order).all()
    
    # 사용자의 스토리 학습 상태 가져오기
    story_progress = {}
    
    for story in stories:
        progress = StoryProgress.query.filter_by(
            user_id=current_user.id,
            story_id=story.id
        ).first()
        
        if progress:
            story_progress[story.id] = {
                'status': progress.status,
                'total_score': progress.total_score
            }
    
    # 완료된 스토리 수 계산
    completed_stories = sum(1 for progress in story_progress.values() if progress['status'] == 2)
    total_stories = len(stories)
    
    return render_template('story/chapter_stories.html',
                          chapter=chapter,
                          stories=stories,
                          story_progress=story_progress,
                          total_stories=total_stories,
                          completed_stories=completed_stories)

@story_bp.route('/chapter/<int:chapter_id>/practice')
@story_bp.route('/chapter/<int:chapter_id>/practice/<int:story_index>')
@login_required
def chapter_practice(chapter_id, story_index=None):
    """챕터 내 스토리 순서대로 연습"""
    chapter = Chapter.query.get_or_404(chapter_id)
    stories = Story.query.filter_by(chapter_id=chapter_id).order_by(Story.order).all()
    
    if not stories:
        flash('이 챕터에 등록된 스토리가 없습니다.', 'info')
        return redirect(url_for('story.chapter_stories', chapter_id=chapter_id))
    
    # 총 스토리 수
    total_stories = len(stories)
    
    # story_index가 지정되지 않았으면 첫 번째 스토리
    if story_index is None:
        story_index = 1
    
    # 인덱스 조정 (1부터 시작)
    array_index = story_index - 1
    if array_index < 0 or array_index >= total_stories:
        array_index = 0
        story_index = 1
    
    story = stories[array_index]
    existing_progress = StoryProgress.query.filter_by(
        user_id=current_user.id,
        story_id=story.id
    ).first()
    
    # 다음 스토리 인덱스 계산
    next_index = story_index + 1 if story_index < total_stories else 1
    
    return render_template('story/practice_story.html',
                          chapter=chapter,
                          story=story,
                          story_number=story_index,
                          total_stories=total_stories,
                          next_index=next_index,
                          existing_progress=existing_progress)

@story_bp.route('/process_audio', methods=['POST'])
@login_required
def process_audio():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file provided'}), 400
    
    audio_file = request.files['audio']
    exam_mode = request.form.get('exam_mode') == '1'
    chapter_id = request.form.get('chapter_id', type=int)
    story_id = request.form.get('story_id', type=int)
    story = _get_story_exam_story(chapter_id, story_id) if exam_mode else None
    text_to_compare = story.english_text if story else request.form.get('word', '')

    if exam_mode and not story:
        return jsonify({'error': 'Invalid exam context'}), 400
    
    # 임시 파일로 오디오 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
        audio_file.save(temp_audio.name)
        temp_filename = temp_audio.name
    
    try:
        from app.services.speech_service import (
            build_pronunciation_feedback,
            calculate_pronunciation_accuracy,
            transcribe_audio,
        )
        
        # 오디오 파일 텍스트 변환
        result = transcribe_audio(temp_filename)
        transcribed_text = result["text"]
        
        # 정확도 계산 (긴 텍스트용)
        accuracy, details = calculate_pronunciation_accuracy(transcribed_text, text_to_compare)
        feedback = build_pronunciation_feedback(transcribed_text, text_to_compare)

        if exam_mode:
            _store_story_exam_speaking_score(chapter_id, story_id, accuracy)
            feedback = {
                'summary': feedback.get('summary', '말하기 결과를 확인했습니다.')
            }
            details = f"텍스트 유사도 기반 말하기 점수: {accuracy:.1f}점"
        
        # 파일 삭제
        os.unlink(temp_filename)
        
        return jsonify({
            'success': True,
            'transcribed_text': transcribed_text,
            'original_text': None if exam_mode else text_to_compare,
            'accuracy': accuracy,
            'details': details,
            'feedback': feedback,
            'processing_time': result.get("processing_time", 0)
        })
        
    except Exception as e:
        # 임시 파일 삭제
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        print(f"Story 음성 처리 에러: {str(e)}")
        return jsonify({'error': str(e)}), 500


@story_bp.route('/exam/evaluate_writing', methods=['POST'])
@login_required
def evaluate_exam_writing():
    data = request.get_json(silent=True) or {}
    chapter_id = data.get('chapter_id')
    story_id = data.get('story_id')
    english_input = data.get('english_input', '')
    korean_input = data.get('korean_input', '')

    chapter_id = int(chapter_id) if chapter_id is not None else None
    story_id = int(story_id) if story_id is not None else None
    story = _get_story_exam_story(chapter_id, story_id)
    if not story:
        return jsonify({'success': False, 'error': 'Invalid exam context'}), 400

    english_score = _calculate_text_similarity_score(english_input, story.english_text)
    korean_score = _calculate_text_similarity_score(korean_input, story.korean_text)

    return jsonify({
        'success': True,
        'english_writing_score': english_score,
        'korean_writing_score': korean_score,
    })

@story_bp.route('/save_progress', methods=['POST'])
@login_required
def save_progress():
    data = request.json
    story_id = data.get('story_id')
    speaking_score = data.get('speaking_score', 0)
    english_writing_score = data.get('english_writing_score', 0)
    korean_writing_score = data.get('korean_writing_score', 0)
    
    # 총점 계산 - 말하기, 영어 쓰기, 한글 쓰기 평균
    total_score = (speaking_score + english_writing_score + korean_writing_score) // 3
    
    # 기존 진도 확인
    progress = StoryProgress.query.filter_by(
        user_id=current_user.id,
        story_id=story_id
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
        progress = StoryProgress(
            user_id=current_user.id,
            story_id=story_id,
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

# === 인증시험 관련 라우트들 ===

@story_bp.route('/exam')
@login_required
def story_exam_index():
    """Story 인증시험 메인 페이지"""
    # 초등, 중등, 고등별로 학년 데이터 구성
    grades_data = {
        '초등': list(range(1, 7)),  # 1-6학년
        '중등': list(range(1, 4)),  # 1-3학년 
        '고등': list(range(1, 4))   # 1-3학년
    }
    
    return render_template('story_exam/index.html', grades_data=grades_data)

@story_bp.route('/exam/grade/<int:grade>/semester/<int:semester>')
@login_required
def exam_semester_chapters(grade, semester):
    """인증시험용 학기별 챕터 목록"""
    chapters = Chapter.query.filter_by(
        grade=grade, 
        semester=semester,
        category='초등'
    ).order_by(Chapter.order).all()
    
    # 사용자의 이전 인증 시험 결과 가져오기
    previous_results = {}
    for chapter in chapters:
        latest_cert = (
            StoryCertification.query
            .filter(
                StoryCertification.user_id == current_user.id,
                StoryCertification.chapter_id == chapter.id,
            )
            .order_by(StoryCertification.exam_date.desc())
            .first()
        )
        
        if latest_cert:
            previous_results[chapter.id] = {
                'passed': latest_cert.passed,
                'score': latest_cert.score,
                'exam_date': latest_cert.exam_date
            }
    
    return render_template('story_exam/semester_chapters.html',
                          grade=grade,
                          semester=semester,
                          chapters=chapters,
                          previous_results=previous_results)

@story_bp.route('/exam/chapter/<int:chapter_id>/start')
@login_required
def story_start_exam(chapter_id):
    """Story 인증시험 시작"""
    chapter = Chapter.query.get_or_404(chapter_id)
    stories = Story.query.filter_by(chapter_id=chapter_id).order_by(Story.order).all()
    
    if not stories:
        flash('이 챕터에 등록된 스토리가 없습니다.', 'info')
        return redirect(url_for('story.story_exam_index'))
    
    # 세션에 시험 정보 저장
    session_key = _story_exam_session_key(chapter_id)
    results_key = _story_exam_results_key(chapter_id)
    speaking_key = _story_exam_speaking_key(chapter_id)
    
    # 스토리 ID 목록을 순서대로 세션에 저장 (랜덤 없음)
    story_ids = [s.id for s in stories]
    session[session_key] = story_ids
    session[results_key] = {}
    session[speaking_key] = {}
    
    # 첫 번째 스토리로 리다이렉트
    return redirect(url_for('story.story_take_exam', chapter_id=chapter_id, story_index=1))

@story_bp.route('/exam/chapter/<int:chapter_id>/exam/<int:story_index>')
@login_required
def story_take_exam(chapter_id, story_index):
    """Story 인증시험 스토리별 시험 페이지"""
    chapter = Chapter.query.get_or_404(chapter_id)
    
    # 세션에서 스토리 ID 목록 가져오기
    session_key = _story_exam_session_key(chapter_id)
    if session_key not in session:
        return redirect(url_for('story.story_start_exam', chapter_id=chapter_id))
    
    story_ids = session[session_key]
    total_stories = len(story_ids)
    
    # 인덱스 조정 (세션 인덱스는 0부터 시작)
    array_index = story_index - 1
    if array_index < 0 or array_index >= total_stories:
        array_index = 0
    
    story_id = story_ids[array_index]
    story = Story.query.get(story_id)
    if not story or story.chapter_id != chapter_id:
        flash('시험 스토리를 불러오지 못했습니다.', 'danger')
        return redirect(url_for('story.story_start_exam', chapter_id=chapter_id))
    
    # 다음 스토리 인덱스 계산
    next_index = story_index + 1 if story_index < total_stories else 0
    
    # 결과 저장 키 생성
    results_key = _story_exam_results_key(chapter_id)
    if results_key not in session:
        session[results_key] = {}
    
    return render_template('story_exam/exam_story.html',
                          chapter=chapter,
                          story=story,
                          story_number=story_index,
                          total_stories=total_stories,
                          next_index=next_index,
                          is_last_story=(next_index == 0))

@story_bp.route('/save_story_exam_result', methods=['POST'])
@login_required
def save_story_exam_result():
    """Story 시험 결과 저장 (AJAX)"""
    data = request.get_json(silent=True) or {}
    chapter_id = data.get('chapter_id')
    story_id = data.get('story_id')
    english_input = data.get('english_input', '')
    korean_input = data.get('korean_input', '')

    chapter_id = int(chapter_id) if chapter_id is not None else None
    story_id = int(story_id) if story_id is not None else None
    
    if not chapter_id or not story_id:
        return jsonify({'success': False, 'error': '시험 정보가 올바르지 않습니다.'}), 400

    story = _get_story_exam_story(chapter_id, story_id)
    if not story:
        return jsonify({'success': False, 'error': '유효하지 않은 시험 요청입니다.'}), 400

    speaking_scores = session.get(_story_exam_speaking_key(chapter_id), {})
    speaking_score = _normalize_score(speaking_scores.get(str(story_id), 0))
    english_writing_score = _calculate_text_similarity_score(english_input, story.english_text)
    korean_writing_score = _calculate_text_similarity_score(korean_input, story.korean_text)

    # 총점 계산 (말하기 40%, 영어 쓰기 30%, 한글 쓰기 30%)
    total_score = round(speaking_score * 0.4 + english_writing_score * 0.3 + korean_writing_score * 0.3)
    
    # 결과를 세션에 저장
    results_key = _story_exam_results_key(chapter_id)
    if results_key not in session:
        session[results_key] = {}
    
    session[results_key][str(story_id)] = {
        'speaking_score': speaking_score,
        'english_writing_score': english_writing_score,
        'korean_writing_score': korean_writing_score,
        'total_score': total_score,
        'passed': total_score >= 80  # 80점 이상이면 합격으로 간주
    }
    
    # session 변경사항을 저장
    session.modified = True
    
    return jsonify({
        'success': True,
        'speaking_score': speaking_score,
        'english_writing_score': english_writing_score,
        'korean_writing_score': korean_writing_score,
        'total_score': total_score,
    })

@story_bp.route('/exam/chapter/<int:chapter_id>/result')
@login_required
def story_exam_result(chapter_id):
    """Story 시험 결과 페이지"""
    chapter = Chapter.query.get_or_404(chapter_id)
    
    # 세션에서 결과 가져오기
    session_key = _story_exam_session_key(chapter_id)
    results_key = _story_exam_results_key(chapter_id)
    if results_key not in session or session_key not in session:
        flash('시험 결과를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('story.story_exam_index'))
    
    results = session[results_key]
    story_ids = session[session_key]
    
    # 총점 및 합격 여부 계산
    total_stories = len(story_ids)
    if total_stories == 0:
        flash('시험 결과를 찾을 수 없습니다.', 'danger')
        return redirect(url_for('story.story_exam_index'))

    missing_story_ids = [story_id for story_id in story_ids if str(story_id) not in results]
    if missing_story_ids:
        first_missing_story_id = missing_story_ids[0]
        first_missing_index = story_ids.index(first_missing_story_id) + 1
        flash('모든 스토리를 제출한 뒤 결과를 볼 수 있습니다.', 'warning')
        return redirect(url_for('story.story_take_exam', chapter_id=chapter_id, story_index=first_missing_index))
    
    passed_stories = sum(1 for r in results.values() if r.get('passed', False))
    overall_score = sum(r.get('total_score', 0) for r in results.values()) // total_stories
    
    # 100% 정답이면 합격, 그렇지 않으면 불합격
    is_passed = passed_stories == total_stories

    korea_tz = pytz.timezone('Asia/Seoul')
    korea_time = datetime.now(korea_tz)
    
    stories = Story.query.filter(Story.id.in_(story_ids)).order_by(Story.order).all()
    stories_by_id = {story.id: story for story in stories}

    story_result_rows = []
    for story_id in story_ids:
        story = stories_by_id.get(story_id)
        if not story:
            continue

        result = results.get(str(story_id), {})
        story_result_rows.append({
            'order': story.order,
            'english_text': story.english_text,
            'korean_text': story.korean_text,
            'speaking_score': result.get('speaking_score', 0),
            'english_writing_score': result.get('english_writing_score', 0),
            'korean_writing_score': result.get('korean_writing_score', 0),
            'total_score': result.get('total_score', 0),
            'passed': result.get('passed', False),
        })
    story_result_rows.sort(key=lambda row: row['order'])

    certification = StoryCertification(
        user_id=current_user.id,
        level_id=None,
        chapter_id=chapter.id,
        passed=is_passed,
        score=overall_score,
        exam_date=korea_time,
    )
    db.session.add(certification)
    
    db.session.commit()
    
    # 세션에서 시험 데이터 삭제
    if results_key in session:
        del session[results_key]
    
    if session_key in session:
        del session[session_key]
    speaking_key = _story_exam_speaking_key(chapter_id)
    if speaking_key in session:
        del session[speaking_key]
    
    return render_template('story_exam/exam_result.html',
                          chapter=chapter,
                          overall_score=overall_score,
                          total_stories=total_stories,
                          passed_stories=passed_stories,
                          is_passed=is_passed,
                          story_result_rows=story_result_rows)

@story_bp.route('/api/chapters/<int:grade>/<int:semester>')
@login_required
def api_chapters(grade, semester):
    """챕터 데이터를 JSON으로 반환하는 API"""
    chapters = Chapter.query.filter_by(
        grade=grade, 
        semester=semester,
        category='초등'
    ).order_by(Chapter.order).all()
    
    # 각 챕터별 진도 정보 계산
    chapters_data = []
    for chapter in chapters:
        total_stories = len(chapter.stories)
        
        if total_stories > 0:
            completed_stories = 0
            in_progress_stories = 0
            
            for story in chapter.stories:
                progress = StoryProgress.query.filter_by(
                    user_id=current_user.id,
                    story_id=story.id
                ).first()
                
                if progress:
                    if progress.status == 2:
                        completed_stories += 1
                    elif progress.status == 1:
                        in_progress_stories += 1
            
            progress_percent = (completed_stories / total_stories) * 100
        else:
            completed_stories = 0
            in_progress_stories = 0
            progress_percent = 0
        
        chapters_data.append({
            'id': chapter.id,
            'title': chapter.title,
            'order': chapter.order,
            'progress': {
                'total_stories': total_stories,
                'completed_stories': completed_stories,
                'in_progress_stories': in_progress_stories,
                'progress_percent': round(progress_percent, 1)
            }
        })
    
    return jsonify({
        'success': True,
        'chapters': chapters_data
    })
