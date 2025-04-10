# app/__init__.py
from flask import Flask, render_template
from app.extensions import db, login_manager, admin, migrate
from app.models import User

def create_app(config_object='config.Config'):
    """应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_object)
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # 注册蓝图
    from app.views.auth import auth_bp
    from app.views.regulation import regulation_bp
    from app.views.export import export_bp
    from app.views.admin import setup_admin
    from app.views.process import process_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(regulation_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(process_bp)
    
    
    # 设置Admin
    setup_admin(app)
    
    # 辅助函数
    register_context_processors(app)
    register_template_filters(app)
    
    return app

def register_context_processors(app):
    """注册上下文处理器"""
    # 获取处罚计数辅助函数
    @app.context_processor
    def utility_processor():
        from app.models import LegalCause, LegalPunishment
        
        def get_punishment_count(regulation_id):
            """获取特定法规的处罚总数"""
            return db.session.query(LegalPunishment).\
                join(LegalCause).\
                filter(LegalCause.regulation_id == regulation_id).\
                count()
                
        return {
            'get_punishment_count': get_punishment_count
        }

def register_template_filters(app):
    """注册模板过滤器"""
    @app.template_filter('nl2br')
    def nl2br_filter(text):
        """将换行符转换为 HTML <br> 标签"""
        if not text:
            return ""
        return text.replace('\n', '<br>')