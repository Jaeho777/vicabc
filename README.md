# vicabc

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
