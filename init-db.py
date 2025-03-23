"""
初始化数据库脚本
"""
from app import app, db

with app.app_context():
    # 创建所有表
    db.create_all()
    print("数据库表已成功创建!")
