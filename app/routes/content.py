# app/routes/content.py
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.level import Level
from app.models.vocabulary import Vocabulary
from app.routes.admin import admin_required, admin_level_required
import pandas as pd
import os
from werkzeug.utils import secure_filename

content_bp = Blueprint('content', __name__, url_prefix='/content')

@content_bp.route('/vocabulary/import', methods=['GET', 'POST'])
@login_required
@admin_required
@admin_level_required('A')  # 최종 관리자만 접근 가능
def import_vocabulary():
    if request.method == 'POST':
        # 업로드된 파일이 있는지 확인
        if 'vocabulary_file' not in request.files:
            flash('파일이 없습니다.', 'danger')
            return redirect(request.url)
        
        file = request.files['vocabulary_file']
        
        # 파일 이름이 비어있는지 확인
        if file.filename == '':
            flash('선택된 파일이 없습니다.', 'danger')
            return redirect(request.url)
        
        # 파일 확장자 확인
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('엑셀 파일(.xlsx, .xls)만 허용됩니다.', 'danger')
            return redirect(request.url)
        
        try:
            # 데이터프레임으로 읽기
            df = pd.read_excel(file)
            
            # 필수 열 확인 - 새로운 열 이름으로 변경
            required_columns = ['순번', '학년', '그룹이름', '영어단어', '한국어뜻']
            for col in required_columns:
                if col not in df.columns:
                    flash(f'필수 열 "{col}"이 엑셀 파일에 없습니다.', 'danger')
                    return redirect(request.url)
            
            # 병합된 셀 처리 - forward fill로 빈 셀을 이전 값으로 채움
            df['학년'] = df['학년'].fillna(method='ffill')
            df['그룹이름'] = df['그룹이름'].fillna(method='ffill')
            
            # 빈 행 제거 (영어단어나 한국어뜻이 없는 행)
            df = df.dropna(subset=['영어단어', '한국어뜻'])
            
            # 데이터 가져오기
            imported_count = 0
            for _, row in df.iterrows():
                grade = row['학년']
                group_name_full = row['그룹이름']  # "G1-학교 (school)" 형태
                word = row['영어단어']
                meaning_full = row['한국어뜻']  # "(명)수업, 반" 형태
                
                # 한국어뜻에서 품사와 의미 분리
                import re
                part_of_speech = None
                meaning_clean = meaning_full
                
                # (명), (동), (형) 등의 품사 패턴 찾기
                pos_match = re.match(r'\(([^)]+)\)', meaning_full)
                if pos_match:
                    part_of_speech = pos_match.group(1)
                    # 품사 부분 제거하고 깨끗한 의미만 추출
                    meaning_clean = re.sub(r'^\([^)]+\)', '', meaning_full).strip()
                
                # 그룹이름에서 그룹번호 추출 (G1-학교 (school) -> G1)
                group_match = re.match(r'(G\d+)', group_name_full)
                if not group_match:
                    flash(f'그룹이름 형식이 잘못되었습니다: {group_name_full}', 'danger')
                    continue
                
                group_number = group_match.group(1)[1:]  # G1 -> 1
                
                # 그룹 주제명 추출 (G1-학교 (school) -> 학교)
                theme_match = re.search(r'G\d+-([^(]+)', group_name_full)
                theme_name = theme_match.group(1).strip() if theme_match else ""
                
                # 레벨 이름 생성 (예: '초등1-G1-학교')
                if 1 <= grade <= 6:
                    category = '초등'
                    level_name = f'초등{grade}-G{group_number}-{theme_name}'
                elif 7 <= grade <= 9:
                    category = '중등'
                    level_name = f'중등{grade-6}-G{group_number}-{theme_name}'
                else:
                    category = '고등'
                    level_name = f'고등{grade-9}-G{group_number}-{theme_name}'
                
                # 레벨 확인/생성
                level = Level.query.filter_by(name=level_name).first()
                if not level:
                    level = Level(name=level_name, category=category)
                    db.session.add(level)
                    db.session.flush()  # ID 할당을 위해 flush
                
                # 단어 중복 확인
                existing_vocab = Vocabulary.query.filter_by(word=word, level_id=level.id).first()
                if existing_vocab:
                    # 기존 단어 업데이트 (단어와 의미만 업데이트, 기존 점수는 유지)
                    existing_vocab.meaning = meaning_clean
                    if part_of_speech:
                        existing_vocab.part_of_speech = part_of_speech
                else:
                    # 새 단어 추가
                    new_vocab = Vocabulary(
                        word=word,
                        meaning=meaning_clean,
                        part_of_speech=part_of_speech,
                        level_id=level.id
                    )
                    db.session.add(new_vocab)
                    imported_count += 1
            
            db.session.commit()
            flash(f'{imported_count}개의 새 단어가 성공적으로 추가되었습니다.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'파일 처리 중 오류가 발생했습니다: {str(e)}', 'danger')
            
    return render_template('admin/import_vocabulary.html')

@content_bp.route('/story/import', methods=['GET', 'POST'])
@login_required
@admin_required
@admin_level_required('A')  # 최종 관리자만 접근 가능
def import_story():
    if request.method == 'POST':
        # 엑셀 파일 확인
        if 'story_file' not in request.files:
            flash('엑셀 파일이 없습니다.', 'danger')
            return redirect(request.url)
        
        excel_file = request.files['story_file']
        
        if excel_file.filename == '':
            flash('선택된 파일이 없습니다.', 'danger')
            return redirect(request.url)
        
        if not excel_file.filename.endswith(('.xlsx', '.xls')):
            flash('엑셀 파일(.xlsx, .xls)만 허용됩니다.', 'danger')
            return redirect(request.url)
        
        # 오디오 ZIP 파일 확인 (선택사항)
        audio_zip = request.files.get('audio_zip')
        
        try:
            import pandas as pd
            from app.models.chapter import Chapter
            from app.models.story import Story
            
            # 엑셀 파일 읽기
            df = pd.read_excel(excel_file)
            
            # 필수 열 확인
            required_columns = ['학년', '학기', '챕터순서', '챕터제목', '스토리순서', '한국어텍스트', '영어텍스트', '오디오파일명']
            for col in required_columns:
                if col not in df.columns:
                    flash(f'필수 열 "{col}"이 엑셀 파일에 없습니다.', 'danger')
                    return redirect(request.url)
            
            # 병합된 셀 처리
            df['학년'] = df['학년'].fillna(method='ffill')
            df['학기'] = df['학기'].fillna(method='ffill')
            df['챕터순서'] = df['챕터순서'].fillna(method='ffill')
            df['챕터제목'] = df['챕터제목'].fillna(method='ffill')
            
            # 빈 행 제거
            df = df.dropna(subset=['영어텍스트', '한국어텍스트'])
            
            imported_count = 0
            chapter_cache = {}
            
            for _, row in df.iterrows():
                grade = int(row['학년'])
                semester = int(row['학기'])
                chapter_order = int(row['챕터순서'])
                chapter_title = row['챕터제목']
                story_order = int(row['스토리순서'])
                korean_text = row['한국어텍스트']
                english_text = row['영어텍스트']
                audio_filename = row['오디오파일명']
                
                # 카테고리 결정
                if 1 <= grade <= 6:
                    category = '초등'
                elif 7 <= grade <= 9:
                    category = '중등'
                else:
                    category = '고등'
                
                # 챕터 확인/생성
                chapter_key = f"{grade}-{semester}-{chapter_order}"
                if chapter_key not in chapter_cache:
                    chapter = Chapter.query.filter_by(
                        grade=grade,
                        semester=semester,
                        order=chapter_order,
                        category=category
                    ).first()
                    
                    if not chapter:
                        chapter = Chapter(
                            grade=grade,
                            semester=semester,
                            order=chapter_order,
                            title=chapter_title,
                            category=category
                        )
                        db.session.add(chapter)
                        db.session.flush()
                    
                    chapter_cache[chapter_key] = chapter
                
                chapter = chapter_cache[chapter_key]
                
                # 스토리 중복 확인
                existing_story = Story.query.filter_by(
                    chapter_id=chapter.id,
                    order=story_order
                ).first()
                
                if existing_story:
                    # 기존 스토리 업데이트
                    existing_story.korean_text = korean_text
                    existing_story.english_text = english_text
                    existing_story.audio_filename = audio_filename
                else:
                    # 새 스토리 추가 (title 제거)
                    new_story = Story(
                        chapter_id=chapter.id,
                        order=story_order,
                        korean_text=korean_text,
                        english_text=english_text,
                        audio_filename=audio_filename
                    )
                    db.session.add(new_story)
                    imported_count += 1
                
                # 오디오 파일 복사 (ZIP에서 추출된 파일이 있는 경우)
                if temp_audio_dir and audio_filename and audio_filename in audio_files:
                    audio_source = audio_files[audio_filename]
                    audio_dest = os.path.join(audio_save_dir, audio_filename)
                    try:
                        shutil.copy2(audio_source, audio_dest)
                        print(f"오디오 파일 복사 완료: {audio_filename}")
                    except Exception as e:
                        print(f"오디오 파일 복사 실패 {audio_filename}: {str(e)}")
            
            db.session.commit()
            
            # 임시 디렉토리 정리
            if temp_audio_dir and os.path.exists(temp_audio_dir):
                shutil.rmtree(temp_audio_dir)
            
            flash(f'{imported_count}개의 새 스토리가 성공적으로 추가되었습니다.', 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'파일 처리 중 오류가 발생했습니다: {str(e)}', 'danger')
    
    return render_template('admin/import_story.html')
    