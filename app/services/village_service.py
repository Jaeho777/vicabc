import re


INTRO_PROMPT = "Hello, how are you?"
MAX_TURNS = 4

QUESTION_RULES = {
    "greeting": {
        "keywords": {
            "good",
            "great",
            "fine",
            "okay",
            "ok",
            "happy",
            "tired",
            "sad",
            "excited",
            "hungry",
            "sleepy",
            "awesome",
            "bad",
        },
    },
    "feeling_reason": {
        "keywords": {
            "because",
            "school",
            "study",
            "home",
            "friend",
            "family",
            "today",
            "busy",
            "fun",
            "happy",
            "tired",
        },
    },
    "after_school": {
        "keywords": {
            "play",
            "study",
            "soccer",
            "football",
            "piano",
            "taekwondo",
            "read",
            "homework",
            "game",
            "games",
            "music",
            "friends",
        },
    },
    "family": {
        "keywords": {
            "family",
            "mother",
            "father",
            "mom",
            "dad",
            "brother",
            "sister",
            "parents",
            "grandmother",
            "grandfather",
            "cousin",
        },
    },
}


def normalize_text(text):
    normalized = re.sub(r"[^a-z0-9\s']", " ", (text or "").lower())
    return " ".join(normalized.split())


def _word_count(text):
    if not text:
        return 0
    return len(text.split())


def _keyword_score(question_key, normalized_text):
    keywords = QUESTION_RULES.get(question_key, {}).get("keywords", set())
    if not keywords:
        return 0, 0

    hits = sum(1 for keyword in keywords if keyword in normalized_text)
    score = min(hits, 3) / 3 * 35
    return round(score), hits


def _expression_score(normalized_text):
    word_count = _word_count(normalized_text)
    score = min(word_count, 12) / 12 * 25

    if any(token in normalized_text.split() for token in {"i", "my", "we", "am", "like", "have"}):
        score += 8
    if "because" in normalized_text:
        score += 7

    return round(min(score, 40))


def _fluency_score(normalized_text):
    words = normalized_text.split()
    if not words:
        return 0

    unique_ratio = len(set(words)) / len(words)
    base_score = unique_ratio * 15

    if len(words) >= 4:
        base_score += 10
    elif len(words) >= 2:
        base_score += 5

    return round(min(base_score, 25))


def evaluate_response(question_key, response_text):
    normalized_text = normalize_text(response_text)
    if not normalized_text:
        return {
            "score": 0,
            "feedback": "답변이 거의 들리지 않았습니다. 조금 더 크고 또렷하게 말해보세요.",
            "normalized_text": normalized_text,
        }

    keyword_score, keyword_hits = _keyword_score(question_key, normalized_text)
    expression_score = _expression_score(normalized_text)
    fluency_score = _fluency_score(normalized_text)
    total_score = min(keyword_score + expression_score + fluency_score, 100)

    feedback_parts = []
    if keyword_hits == 0:
        feedback_parts.append("질문 핵심 단어를 더 직접적으로 넣어 답하면 좋아요.")
    if _word_count(normalized_text) < 5:
        feedback_parts.append("답변을 한 문장 이상으로 조금 더 길게 말해보세요.")
    if "because" not in normalized_text and question_key in {"greeting", "feeling_reason"}:
        feedback_parts.append("이유를 말할 때 because를 사용하면 더 자연스럽습니다.")
    if not feedback_parts:
        feedback_parts.append("좋아요. 질문에 맞는 답을 자연스럽게 이어갔습니다.")

    return {
        "score": round(total_score),
        "feedback": " ".join(feedback_parts),
        "normalized_text": normalized_text,
    }


def get_next_prompt(turn_index, response_text):
    normalized_text = normalize_text(response_text)

    if turn_index == 0:
        if any(word in normalized_text for word in {"good", "great", "fine", "happy", "awesome", "excited"}):
            return "That sounds great. Why do you feel that way today?", "feeling_reason"
        if any(word in normalized_text for word in {"bad", "sad", "tired", "sleepy", "angry"}):
            return "I see. Why do you feel that way today?", "feeling_reason"
        return "Thank you. Why do you feel that way today?", "feeling_reason"

    if turn_index == 1:
        return "What do you like to do after school?", "after_school"

    if turn_index == 2:
        return "Tell me about your family.", "family"

    return None, None


def summarize_level(score):
    if score >= 90:
        return "Village 4", "질문에 자연스럽게 반응하고 이유까지 덧붙일 수 있는 수준입니다."
    if score >= 75:
        return "Village 3", "기본 대화를 안정적으로 이어갈 수 있는 수준입니다."
    if score >= 60:
        return "Village 2", "짧은 대화는 가능하지만 조금 더 자세한 표현이 필요합니다."
    return "Village 1", "짧은 답은 가능하지만 문장 확장과 질문 대응 연습이 더 필요합니다."
