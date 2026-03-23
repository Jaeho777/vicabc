import json
import os
import tempfile
from datetime import datetime

import pytz
from flask import Blueprint, jsonify, render_template, request, session
from flask_login import current_user, login_required

from app.extensions import db
from app.models.village_certification import VillageCertification
from app.services.speech_service import transcribe_audio
from app.services.village_service import (
    INTRO_PROMPT,
    MAX_TURNS,
    evaluate_response,
    get_next_prompt,
    summarize_level,
)


village_bp = Blueprint("village", __name__, url_prefix="/village")


def ensure_village_certification_table():
    VillageCertification.__table__.create(bind=db.engine, checkfirst=True)


def get_latest_village_result(user_id):
    try:
        ensure_village_certification_table()
        return (
            VillageCertification.query.filter_by(user_id=user_id)
            .order_by(VillageCertification.exam_date.desc())
            .first()
        )
    except Exception as exc:
        print(f"Village 결과 조회 오류: {exc}")
        return None


@village_bp.route("/")
@login_required
def index():
    latest_result = get_latest_village_result(current_user.id)
    return render_template("village/index.html", latest_result=latest_result)


@village_bp.route("/exam")
@login_required
def exam():
    session["village_exam"] = {
        "turn_index": 0,
        "current_prompt": INTRO_PROMPT,
        "question_key": "greeting",
        "history": [],
    }
    session.modified = True

    latest_result = get_latest_village_result(current_user.id)
    return render_template(
        "village/exam.html",
        initial_prompt=INTRO_PROMPT,
        max_turns=MAX_TURNS,
        latest_result=latest_result,
    )


@village_bp.route("/process_audio", methods=["POST"])
@login_required
def process_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    exam_state = session.get("village_exam")
    if not exam_state:
        return jsonify({"error": "시험 세션이 없습니다. 다시 시작해주세요."}), 400

    audio_file = request.files["audio"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as temp_audio:
        audio_file.save(temp_audio.name)
        temp_filename = temp_audio.name

    try:
        result = transcribe_audio(temp_filename)
        transcribed_text = result["text"]
    except Exception as exc:
        if os.path.exists(temp_filename):
            os.unlink(temp_filename)
        print(f"Village 음성 처리 오류: {exc}")
        return jsonify({"error": str(exc)}), 500

    if os.path.exists(temp_filename):
        os.unlink(temp_filename)

    turn_index = exam_state.get("turn_index", 0)
    question_key = exam_state.get("question_key", "greeting")
    prompt_text = exam_state.get("current_prompt", INTRO_PROMPT)

    evaluation = evaluate_response(question_key, transcribed_text)

    history = exam_state.get("history", [])
    history.append(
        {
            "prompt": prompt_text,
            "response": transcribed_text,
            "score": evaluation["score"],
            "feedback": evaluation["feedback"],
        }
    )

    is_complete = turn_index + 1 >= MAX_TURNS
    if is_complete:
        overall_score = round(sum(item["score"] for item in history) / len(history)) if history else 0
        level_label, level_feedback = summarize_level(overall_score)
        passed = overall_score >= 75

        saved = False
        try:
            ensure_village_certification_table()
            korea_tz = pytz.timezone("Asia/Seoul")
            certification = VillageCertification(
                user_id=current_user.id,
                topic="daily conversation",
                level_label=level_label,
                passed=passed,
                score=overall_score,
                turn_count=len(history),
                transcript=json.dumps(history, ensure_ascii=False),
                feedback=level_feedback,
                exam_date=datetime.now(korea_tz),
            )
            db.session.add(certification)
            db.session.commit()
            saved = True
        except Exception as exc:
            db.session.rollback()
            print(f"Village 결과 저장 오류: {exc}")

        session.pop("village_exam", None)
        session.modified = True

        return jsonify(
            {
                "success": True,
                "completed": True,
                "transcribed_text": transcribed_text,
                "turn_score": evaluation["score"],
                "turn_feedback": evaluation["feedback"],
                "overall_score": overall_score,
                "level_label": level_label,
                "level_feedback": level_feedback,
                "passed": passed,
                "saved": saved,
                "history": history,
            }
        )

    next_prompt, next_key = get_next_prompt(turn_index, transcribed_text)
    exam_state["turn_index"] = turn_index + 1
    exam_state["current_prompt"] = next_prompt
    exam_state["question_key"] = next_key
    exam_state["history"] = history
    session["village_exam"] = exam_state
    session.modified = True

    return jsonify(
        {
            "success": True,
            "completed": False,
            "transcribed_text": transcribed_text,
            "turn_score": evaluation["score"],
            "turn_feedback": evaluation["feedback"],
            "next_prompt": next_prompt,
            "current_turn": turn_index + 1,
            "max_turns": MAX_TURNS,
            "history": history,
        }
    )
