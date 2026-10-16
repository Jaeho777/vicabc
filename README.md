# vicabc

공지사항에 PPT/PPTX를 첨부하면 로그인한 학생이 웹에서 슬라이드를 넘겨볼 수 있습니다. 원본 다운로드도 유지하며 공지당 1개·최대 20MB입니다. 미리보기 서버에는 LibreOffice·Poppler가 필요합니다. [사용·배포·백업 안내](docs/NOTICE_ATTACHMENTS.md)를 확인하세요.

로그인 후 상단 **마이페이지**에서 본인 이름을 바꿀 수 있습니다. 관리자에게는 **공지 작성 · PPT 업로드** 진입 버튼을 표시합니다. [마이페이지·권한·유지보수 안내](docs/PROFILE_AND_NAVIGATION.md)를 확인하세요.

Flask based English learning platform for vocabulary, story, exam, and admin flows.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set `SECRET_KEY` and `DATABASE_URL`.
4. Initialize the database with `python init_db.py`.
5. Run the app with `python run.py`.

## Production

- App entrypoint: `wsgi:app`
- Reverse proxy: Nginx
- App server: Gunicorn
