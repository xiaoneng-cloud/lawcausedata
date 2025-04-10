# app/views/__init__.py
# 导入所有视图蓝图以便在应用工厂中注册
from app.views.auth import auth_bp
from app.views.regulation import regulation_bp
from app.views.export import export_bp
from app.views.admin import admin_bp
from app.views.process import process_bp