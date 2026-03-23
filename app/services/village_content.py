VILLAGE_TOTAL_COUNT = 16


def _audio_path(village_number, filename):
    return f"audio/village/{village_number}/{filename}"


def _lesson(village_number, lesson_number, prompt, response, practice_keywords):
    lesson_prefix = f"{village_number}.{lesson_number}"
    return {
        "number": lesson_number,
        "title": f"Lesson {lesson_number}",
        "dialogue_lines": [
            {"label": "Sentence A", "text": prompt},
            {"label": "Sentence B", "text": response},
        ],
        "base_reference_text": f"{prompt} {response}",
        "base_audio_path": _audio_path(village_number, f"{lesson_prefix}a.m4a"),
        "practice_audio_path": _audio_path(village_number, f"{lesson_prefix}b.m4a"),
        "practice_reference_text": None,
        "practice_keywords": practice_keywords,
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
}


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
