# run.py
from app import create_app
from flask import redirect, url_for
from flask_login import current_user

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)