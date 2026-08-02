from collections import defaultdict
from datetime import datetime, timedelta

from app.extensions import db
from app.models.certification import Certification
from app.models.notice import Notice
from app.models.story_certification import StoryCertification
from app.models.story_progress import StoryProgress
from app.models.user import User
from app.models.user_progress import UserProgress
from app.models.village_certification import VillageCertification
from app.models.village_progress import VillageProgress


DEFAULT_NOTICES = (
    {
        "title": "7월 정기 점검 안내 (7/22 새벽 2시~4시)",
        "body": "안정적인 학습 환경을 위해 정기 점검을 진행합니다. 점검 시간에는 일부 기능을 이용할 수 없습니다.",
        "published_at": datetime(2026, 7, 19),
    },
    {
        "title": "여름방학 단어 챌린지 참여하고 포인트 받기",
        "body": "여름방학 동안 매일 단어 학습에 참여하고 학습 기록을 쌓아보세요.",
        "published_at": datetime(2026, 7, 17),
    },
    {
        "title": "Village 대화 연습 신규 레슨 5개 추가",
        "body": "Village에 새로운 실전 대화 레슨이 추가되었습니다. 학습 메뉴에서 바로 시작할 수 있습니다.",
        "published_at": datetime(2026, 7, 14),
    },
    {
        "title": "1학기 학습 리포트가 발송되었습니다",
        "body": "1학기 동안의 학습 현황을 확인할 수 있도록 학습 리포트를 준비했습니다.",
        "published_at": datetime(2026, 7, 10),
    },
    {
        "title": "Bible Story 4단원이 오픈되었습니다",
        "body": "Bible Story 4단원의 챕터와 스토리 학습을 이용할 수 있습니다.",
        "published_at": datetime(2026, 7, 5),
    },
)


def ensure_dashboard_notices():
    """Populate the initial dashboard notices only for a brand-new notice board."""
    if Notice.query.first() is not None:
        return

    db.session.add_all(Notice(**notice) for notice in DEFAULT_NOTICES)
    db.session.commit()


def current_week_start(now=None):
    now = now or datetime.utcnow()
    return (now - timedelta(days=now.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def get_weekly_rankings(limit=None, now=None):
    """Return rankings derived from actual learning records created this week.

    VOCA and Story contribute their recorded evaluation score. Village lessons do
    not have a score field, so each recorded study contributes 10 learning points.
    Certification results contribute their saved exam score.
    """
    week_start = current_week_start(now)
    scores = defaultdict(int)
    activities = defaultdict(int)

    for progress in UserProgress.query.filter(
        UserProgress.last_studied_at >= week_start,
        UserProgress.study_count > 0,
    ):
        scores[progress.user_id] += max(progress.total_score or 0, 0)
        activities[progress.user_id] += progress.study_count

    for progress in StoryProgress.query.filter(
        StoryProgress.last_studied_at >= week_start,
        StoryProgress.study_count > 0,
    ):
        scores[progress.user_id] += max(progress.total_score or 0, 0)
        activities[progress.user_id] += progress.study_count

    for progress in VillageProgress.query.filter(
        VillageProgress.last_studied_at >= week_start,
        VillageProgress.study_count > 0,
    ):
        scores[progress.user_id] += progress.study_count * 10
        activities[progress.user_id] += progress.study_count

    certification_models = (
        Certification,
        StoryCertification,
        VillageCertification,
    )
    for certification_model in certification_models:
        for result in certification_model.query.filter(
            certification_model.exam_date >= week_start,
        ):
            scores[result.user_id] += max(result.score or 0, 0)
            activities[result.user_id] += 1

    if not scores:
        return []

    users = {
        user.id: user
        for user in User.query.filter(
            User.id.in_(scores.keys()),
            User.is_admin.is_(False),
        )
    }
    palette = ("avatar-orange", "avatar-green", "avatar-red", "avatar-pink", "avatar-blue")
    rankings = []
    for user_id, score in scores.items():
        user = users.get(user_id)
        if user is None:
            continue
        rankings.append(
            {
                "user": user,
                "score": score,
                "activities": activities[user_id],
            }
        )

    rankings.sort(
        key=lambda entry: (
            -entry["score"],
            -entry["activities"],
            entry["user"].full_name or entry["user"].username,
        )
    )
    if limit is not None:
        rankings = rankings[:limit]

    for index, entry in enumerate(rankings):
        name = entry["user"].full_name or entry["user"].username
        entry["display_name"] = name
        entry["initial"] = name[:1]
        entry["avatar_class"] = palette[index % len(palette)]

    return rankings
