# app/routes/__init__.py
from flask import Blueprint

# 메인 페이지 블루프린트
main_bp = Blueprint('main', __name__)

# 블루프린트 import
from app.routes import main