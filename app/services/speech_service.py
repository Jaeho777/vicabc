import os
import tempfile
import whisper
import numpy as np
import time
from difflib import SequenceMatcher


# 전역 변수로 모델 로드 (한 번만 로드하여 메모리 효율성 높이기)
whisper_model = None

def get_whisper_model(model_size="small"):
    """위스퍼 모델을 로드하는 함수 (지연 로딩)"""
    global whisper_model
    if whisper_model is None:
        # 처음 호출될 때만 모델 로드
        whisper_model = whisper.load_model(model_size)
    return whisper_model

def transcribe_audio(audio_file_path, language="en"):
    """오디오 파일을 텍스트로 변환하는 함수"""
    model = get_whisper_model()
    
    start_time = time.time()
    result = model.transcribe(audio_file_path, language=language)
    processing_time = time.time() - start_time
    
    return {
        "text": result["text"].strip().lower(),
        "processing_time": processing_time
    }

def calculate_pronunciation_accuracy(transcribed_text, original_text):
    """발음 정확도를 계산하는 함수"""
    return evaluate_pronunciation(transcribed_text, original_text)


def build_pronunciation_feedback(recognized_text, reference_text):
    """발음 비교 결과를 사람이 읽기 쉬운 피드백으로 정리"""

    def normalize_text(text):
        import re

        return re.sub(r"[^\w\s]", "", (text or "").lower()).strip()

    recognized_words = normalize_text(recognized_text).split()
    reference_words = normalize_text(reference_text).split()

    remaining_recognized = list(recognized_words)
    matched_words = []
    missing_words = []

    for word in reference_words:
        if word in remaining_recognized:
            matched_words.append(word)
            remaining_recognized.remove(word)
        else:
            missing_words.append(word)

    extra_words = remaining_recognized

    if not reference_words:
        summary = "비교할 기준 문장이 없습니다."
    elif not recognized_words:
        summary = "음성이 거의 인식되지 않았습니다. 조금 더 천천히 또렷하게 말해보세요."
    elif not missing_words and not extra_words:
        summary = "기준 문장과 거의 같게 말했습니다."
    elif len(missing_words) <= 2 and len(extra_words) <= 2:
        summary = "대체로 잘 따라 했습니다. 몇 단어만 더 정확히 말하면 됩니다."
    else:
        summary = "핵심 단어가 몇 개 빠지거나 다른 단어가 섞였습니다. 기준 문장을 다시 듣고 이어서 말해보세요."

    return {
        "summary": summary,
        "matched_words": matched_words,
        "missing_words": missing_words,
        "extra_words": extra_words,
    }

def evaluate_pronunciation(recognized_text, reference_text):
    """
    인식된 텍스트와 참조 텍스트를 비교하여 발음 점수 계산
    """
    # 텍스트 정규화
    def normalize_text(text):
        import re
        # 소문자화 및 특수 문자 제거
        return re.sub(r'[^\w\s]', '', text.lower()).strip()
    
    recognized = normalize_text(recognized_text)
    reference = normalize_text(reference_text)
    
    # 전체 텍스트 유사도 계산
    similarity = SequenceMatcher(None, recognized, reference).ratio()
    
    # 단어 기반 비교
    ref_words = reference.split()
    rec_words = recognized.split()
    
    # 매치된 단어 수
    matched_words = sum(1 for w in rec_words if w in ref_words)
    word_match_ratio = matched_words / len(ref_words) if ref_words else 0
    
    # 단어 순서 평가
    word_order_sim = 0
    if rec_words and ref_words:
        # 공통 단어 찾기
        common_words = set(rec_words).intersection(set(ref_words))
        
        # 각 단어의 위치 비교
        position_diffs = []
        for word in common_words:
            ref_positions = [i for i, w in enumerate(ref_words) if w == word]
            rec_positions = [i for i, w in enumerate(rec_words) if w == word]
            
            # 위치 차이의 최소값 계산 (가장 가까운 위치 쌍)
            min_diffs = [min(abs(r - p) for p in rec_positions) for r in ref_positions]
            position_diffs.extend(min_diffs)
        
        # 위치 유사도 계산
        if position_diffs:
            avg_pos_diff = sum(position_diffs) / len(position_diffs)
            max_pos_diff = max(len(ref_words), len(rec_words))
            word_order_sim = 1 - (avg_pos_diff / max_pos_diff if max_pos_diff > 0 else 0)
    
    # 가중치 적용한 최종 점수 계산
    final_score = (
        word_match_ratio * 0.5 +  # 단어 일치 50%
        similarity * 0.3 +        # 전체 텍스트 유사도 30%
        word_order_sim * 0.2      # 단어 순서 유사도 20%
    ) * 100
    
    # 세부 평가 정보 생성
    details = (
        f"단어 일치: {word_match_ratio * 100:.1f}% ({matched_words}/{len(ref_words)})\n"
        f"텍스트 유사도: {similarity * 100:.1f}%\n"
        f"단어 순서 정확도: {word_order_sim * 100:.1f}%"
    )
    
    return round(final_score, 1), details
    
