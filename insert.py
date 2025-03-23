# fix_database.py
from app import app, db
from sqlalchemy import text
import sqlite3

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE legal_regulation ADD COLUMN approved_by VARCHAR(100)'))
        print("已添加 approved_by 列")
    except (sqlite3.OperationalError, Exception) as e:
        if "duplicate column name" in str(e):
            print("approved_by 列已存在")
        else:
            print(f"添加 approved_by 列时出错: {e}")
    
    try:
        db.session.execute(text('ALTER TABLE legal_regulation ADD COLUMN revision_date DATETIME'))
        print("已添加 revision_date 列")
    except (sqlite3.OperationalError, Exception) as e:
        if "duplicate column name" in str(e):
            print("revision_date 列已存在")
        else:
            print(f"添加 revision_date 列时出错: {e}")
    
    try:
        db.session.execute(text('ALTER TABLE legal_regulation ADD COLUMN province VARCHAR(50)'))
        print("已添加 province 列")
    except (sqlite3.OperationalError, Exception) as e:
        if "duplicate column name" in str(e):
            print("province 列已存在")
        else:
            print(f"添加 province 列时出错: {e}")
    
    try:
        db.session.execute(text('ALTER TABLE legal_regulation ADD COLUMN city VARCHAR(50)'))
        print("已添加 city 列")
    except (sqlite3.OperationalError, Exception) as e:
        if "duplicate column name" in str(e):
            print("city 列已存在")
        else:
            print(f"添加 city 列时出错: {e}")
    
    db.session.commit()
    print("数据库修复过程完成！")