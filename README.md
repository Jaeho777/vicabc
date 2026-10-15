# vicabc

공지사항에 PPT/PPTX 파일을 첨부할 수 있습니다. 관리자 작성 → 로그인한 학생 다운로드 흐름이며, 공지당 1개·최대 20MB입니다. [사용·배포·백업 안내](docs/NOTICE_ATTACHMENTS.md)를 확인하세요.

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
