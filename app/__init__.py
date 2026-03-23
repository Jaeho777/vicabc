# app/__init__.py
from flask import Flask
from app.config import Config
from app.extensions import db, migrate, login_manager

def create_app():
    app = Flask(__name__)
    
    app.config.from_object(Config)
    
    # 확장 모듈 초기화
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    
    # 블루프린트 등록
    from app.routes.auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # 메인 블루프린트 등록
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    from app.routes.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    from app.routes.content import content_bp
    app.register_blueprint(content_bp)

    from app.routes.voca import voca_bp
    app.register_blueprint(voca_bp)

    from app.routes.exam import exam_bp
    app.register_blueprint(exam_bp)

    from app.routes.story import story_bp
    app.register_blueprint(story_bp)

    return app