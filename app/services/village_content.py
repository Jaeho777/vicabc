from app.services.village_content_extra import EXTRA_VILLAGE_BLUEPRINTS


VILLAGE_TOTAL_COUNT = 16


def _audio_path(village_number, filename):
    return f"audio/village/{village_number}/{filename}"


def _lesson(village_number, lesson_number, prompt, response, practice_keywords, title=None):
    lesson_prefix = f"{village_number}.{lesson_number}"
    base_audio_filename = f"{lesson_prefix}a.m4a"
    practice_audio_filename = f"{lesson_prefix}b.m4a"
    return {
        "number": lesson_number,
        "title": title or f"Lesson {lesson_number}",
        "lesson_prefix": lesson_prefix,
        "dialogue_lines": [
            {"label": "Sentence A", "text": prompt},
            {"label": "Sentence B", "text": response},
        ],
        "base_reference_text": f"{prompt} {response}",
        "base_audio_filename": base_audio_filename,
        "practice_audio_filename": practice_audio_filename,
        "base_audio_path": _audio_path(village_number, base_audio_filename),
        "practice_audio_path": _audio_path(village_number, practice_audio_filename),
        "practice_reference_text": None,
        "practice_keywords": practice_keywords,
    }


def _build_village_from_blueprint(village_number, blueprint):
    return {
        "number": village_number,
        "theme_ko": blueprint["theme_ko"],
        "theme_en": blueprint["theme_en"],
        "summary": blueprint["summary"],
        "lessons": [
            _lesson(
                village_number,
                lesson_number,
                lesson["prompt"],
                lesson["response"],
                lesson["practice_keywords"],
                title=lesson["title"],
            )
            for lesson_number, lesson in enumerate(blueprint["lessons"], start=1)
        ],
    }


VILLAGE_CONTENT = {
    1: {
        "number": 1,
        "theme_ko": "학교",
        "theme_en": "School",
        "summary": "학교에서 자주 쓰는 인사, 교실 표현, 친구와의 짧은 대화를 연습합니다.",
        "lessons": [
            _lesson(1, 1, "Good morning.", "Good morning, Mr. Kim!", ["afternoon", "evening", "night"]),
            _lesson(1, 2, "Where are you going?", "To school.", ["hospital", "church", "work"]),
            _lesson(1, 3, "Are you a new student?", "Yes, I am.", ["member", "classmate", "friend"]),
            _lesson(1, 4, "What's your name?", "I'm Tom.", ["nickname", "age", "last name"]),
            _lesson(1, 5, "Do you have a class now?", "Yes, math class.", ["a test", "homework", "a club"]),
            _lesson(1, 6, "Is this your textbook?", "Yes, it is.", ["pencil", "notebook", "eraser"]),
            _lesson(1, 7, "Do you have a pencil?", "Yes, I do.", ["a ruler", "a pen", "an eraser"]),
            _lesson(1, 8, "Can I borrow your pencil?", "Sure. Here you are.", ["crayon", "color pencil", "marker"]),
            _lesson(1, 9, "Where is your notebook?", "On the desk.", ["sharpener", "book", "pencil case"]),
            _lesson(1, 10, "Is that your picture?", "Yes! I drew it.", ["poster", "homework", "photo"]),
            _lesson(1, 11, "What do you like to do?", "I like to read.", ["read", "play", "sing"]),
            _lesson(1, 12, "Let's study!", "Okay! Let's go!", ["play basketball", "watch baseball", "play tennis"]),
        ],
    },
    2: {
        "number": 2,
        "theme_ko": "문구점",
        "theme_en": "Stationery",
        "summary": "문구점에서 물건을 찾고 고르는 상황을 통해 요청과 선택 표현을 연습합니다.",
        "lessons": [
            _lesson(2, 1, "Do you need a pen?", "Yes, I need a pen.", ["an eraser", "a notebook", "a pencil"]),
            _lesson(2, 2, "Where is my pencil?", "It's on the desk.", ["eraser", "pen", "highlighter"]),
            _lesson(2, 3, "Can I use the scissors?", "Sure. Be careful!", ["glue", "ruler", "crayon"]),
            _lesson(2, 4, "Is this your tape?", "No, it's not mine.", ["pencil case", "folder", "compass"]),
            _lesson(2, 5, "What are you looking for?", "I'm looking for a glue stick.", ["shirt", "pants", "socks"]),
            _lesson(2, 6, "Which one do you want?", "The blue marker, please.", ["the red one", "small one", "that pencil"]),
            _lesson(2, 7, "Can I try this pen?", "Sure. Go ahead.", ["pencil", "crayon", "highlighter"]),
            _lesson(2, 8, "Can you help me find tape?", "Sure. Follow me.", ["paper clips", "stapler", "calculator"]),
            _lesson(2, 9, "Which color do you want?", "I want the red one.", ["size", "shape", "design"]),
            _lesson(2, 10, "How many notebooks do you need?", "Just two.", ["pens", "pencils", "crayons"]),
            _lesson(2, 11, "Which marker is better?", "This one is stronger.", ["pencil case", "colored pencil", "ruler"]),
            _lesson(2, 12, "Do you have more stickers?", "Yes, we have many.", ["glue sticks", "pencil sharpener", "paint brushes"]),
        ],
    },
    3: {
        "number": 3,
        "theme_ko": "병원",
        "theme_en": "Hospital",
        "summary": "병원에서 몸 상태를 말하고 도움을 요청하는 기본 표현을 연습합니다.",
        "lessons": [
            _lesson(3, 1, "Are you sick?", "Yes, I feel bad.", ["ill", "not feeling well", "feeling okay"]),
            _lesson(3, 2, "Let's go to the hospital.", "Okay, I need to see a doctor.", ["clinic", "doctor's office", "emergency room"]),
            _lesson(3, 3, "Where is the nurse?", "She is in the room.", ["doctor", "caregiver", "patient"]),
            _lesson(3, 4, "What's wrong?", "My leg hurts.", ["How do you feel?", "Where does it hurt?", "Does it hurt here?"]),
            _lesson(3, 5, "Can you open your mouth?", "Ahhh~", ["open your mouth wider", "Say 'ahhh' for me", "Let me see your mouth"]),
            _lesson(3, 6, "Do you have a fever?", "Yes, I do.", ["cold", "cough", "headache"]),
            _lesson(3, 7, "Do you need medicine?", "Yes, please.", ["water", "a bandage", "ice"]),
            _lesson(3, 8, "Your skin is red.", "I think I have a fever.", ["face", "eyes are", "nose"]),
            _lesson(3, 9, "Do you want to lie down?", "Yes, I do.", ["sit down", "rest", "drink water"]),
            _lesson(3, 10, "My tooth is wiggly.", "Does it hurt?", ["loose", "shaky", "moving"]),
            _lesson(3, 11, "Can you breathe in?", "Yes, I can.", ["Breathe out", "lift your arm", "move your leg"]),
            _lesson(3, 12, "My arm hurts.", "Does it hurt a lot?", ["head", "eyes", "neck"]),
        ],
    },
    4: {
        "number": 4,
        "theme_ko": "가족",
        "theme_en": "Family",
        "summary": "가족 소개, 감정 표현, 함께하는 상황에서 자주 쓰는 회화 패턴을 연습합니다.",
        "lessons": [
            _lesson(4, 1, "Who is she?", "She is my sister.", ["He", "The man", "The woman"]),
            _lesson(4, 2, "Where is your father?", "He is at work.", ["Mother", "Sister", "Brother"]),
            _lesson(4, 3, "Do you love your mom?", "Yes, I love her so much.", ["Dad", "Sister", "Uncle"]),
            _lesson(4, 4, "Is that your grandfather?", "Yes. He is kind.", ["Grandmother/She", "Aunt/She", "Cousin"]),
            _lesson(4, 5, "Are you happy today?", "Yes! We have a family party!", ["excited", "in a good mood", "feeling good"]),
            _lesson(4, 6, "Let's smile together!", "Okay! Say cheese!", ["Take a picture", "Laugh", "Say cheese"]),
            _lesson(4, 7, "What a nice family!", "Thank you. We are happy.", ["Sweet", "Lovely", "Wonderful"]),
            _lesson(4, 8, "Who is this girl?", "This is my daughter.", ["Boy", "Woman", "Man"]),
            _lesson(4, 9, "Are you sad?", "Yes. I miss my uncle.", ["upset", "worried", "lonely"]),
            _lesson(4, 10, "My brother is brave!", "Wow, that's cool!", ["Smart", "Friendly", "Kind"]),
            _lesson(4, 11, "Let's help mom.", "Sure. I'm ready!", ["Grandparent", "Sister", "Uncle"]),
            _lesson(4, 12, "Are we all here?", "Yes, we are all here.", ["Is everyone here?", "Is everybody here?", "Are we all together?"]),
        ],
    },
    5: {
        "number": 5,
        "theme_ko": "식당",
        "theme_en": "Restaurant",
        "summary": "식당에서 주문하고 맛을 표현하며 식사 상황에서 쓰는 기본 회화를 연습합니다.",
        "lessons": [
            _lesson(5, 1, "Are you hungry?", "Yes, I am.", ["thirsty", "full", "starving"]),
            _lesson(5, 2, "What do you want to eat?", "I want a burger.", ["pizza", "taco", "sandwich"]),
            _lesson(5, 3, "Can I have some water?", "Sure. Here you are.", ["juice", "milk", "soda"]),
            _lesson(5, 4, "How does it taste?", "It's delicious!", ["spicy", "sweet", "salty"]),
            _lesson(5, 5, "Is it hot?", "No, it's cold.", ["warm", "cool", "freezing"]),
            _lesson(5, 6, "Do you like spaghetti?", "Yes, I like it.", ["steak", "salad", "soup"]),
            _lesson(5, 7, "Where is the spoon?", "It's on the table.", ["fork", "knife", "napkin"]),
            _lesson(5, 8, "Can I have more bread?", "Of course.", ["butter", "jam", "honey"]),
            _lesson(5, 9, "Are you finished?", "Not yet.", ["ready", "done", "almost"]),
            _lesson(5, 10, "Do you want dessert?", "Yes, ice cream please.", ["cake", "cookie", "fruit"]),
            _lesson(5, 11, "How much is it?", "It's five dollars.", ["ten", "seven", "twelve"]),
            _lesson(5, 12, "Did you enjoy the meal?", "Yes, it was great.", ["wonderful", "nice", "good"]),
        ],
    },
}

for village_number, blueprint in EXTRA_VILLAGE_BLUEPRINTS.items():
    VILLAGE_CONTENT[village_number] = _build_village_from_blueprint(village_number, blueprint)


def get_village(village_number):
    village = VILLAGE_CONTENT.get(village_number)
    if not village:
        return None

    village_data = dict(village)
    village_data["lesson_count"] = len(village["lessons"])
    return village_data


def get_village_catalog():
    catalog = []
    for village_number in range(1, VILLAGE_TOTAL_COUNT + 1):
        village = get_village(village_number)
        if village:
            catalog.append(
                {
                    "number": village_number,
                    "available": True,
                    "theme_ko": village["theme_ko"],
                    "theme_en": village["theme_en"],
                    "summary": village["summary"],
                    "lesson_count": village["lesson_count"],
                }
            )
            continue

        catalog.append(
            {
                "number": village_number,
                "available": False,
                "theme_ko": "준비 중",
                "theme_en": "Coming Soon",
                "summary": "텍스트와 음원 정리가 끝나는 순서대로 이어서 추가됩니다.",
                "lesson_count": 0,
            }
        )

    return catalog
