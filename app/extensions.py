# app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_admin import Admin
from flask_migrate import Migrate

# 创建扩展实例但不初始化
db = SQLAlchemy()
login_manager = LoginManager()
admin = Admin(name='法律法规管理平台', template_mode='bootstrap4')
migrate = Migrate()

# 设置LoginManager
login_manager.login_view = 'auth.login'