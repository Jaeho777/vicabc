# app/routes/main.py
from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from app.routes import main_bp

@main_bp.route('/')
@login_required
def index():
    return render_template('index.html')