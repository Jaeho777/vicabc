import re


VILLAGE_SEMESTER_MAP = {
    (1, 1): (1,),
    (1, 2): (2,),
    (2, 1): (3,),
    (2, 2): (4,),
    (3, 1): (5,),
    (3, 2): (6,),
    (4, 1): (7, 8),
    (4, 2): (9, 10),
    (5, 1): (11, 12),
    (5, 2): (13, 14),
    (6, 1): (15,),
    (6, 2): (16,),
}


def get_village_number(level):
    match = re.match(r'^Village\s+(\d+)\b', level.name)
    return int(match.group(1)) if match else None


def build_village_curriculum(levels):
    """Group Village levels using the elementary grade/semester curriculum."""
    levels_by_number = {
        number: level
        for level in levels
        if (number := get_village_number(level)) is not None
    }

    curriculum = []
    for grade in range(1, 7):
        semesters = []
        for semester in (1, 2):
            village_numbers = VILLAGE_SEMESTER_MAP[(grade, semester)]
            semesters.append({
                'number': semester,
                'label': f'{grade}학년 {semester}학기',
                'village_numbers': village_numbers,
                'levels': [
                    levels_by_number[number]
                    for number in village_numbers
                    if number in levels_by_number
                ],
            })
        curriculum.append({
            'grade': grade,
            'label': f'{grade}학년',
            'semesters': semesters,
        })

    return curriculum
