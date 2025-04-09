# create_admin.py
from app import create_app
from app.extensions import db
from app.models.user import User
import getpass
import sys

def create_admin():
    """创建管理员用户"""
    app = create_app()
    
    with app.app_context():
        # 获取用户输入
        print("=== 创建管理员账号 ===")
        username = input("请输入管理员用户名: ").strip()
        email = input("请输入管理员邮箱: ").strip()
        
        # 检查用户名和邮箱是否已存在
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            print(f"错误: 用户名或邮箱已存在。")
            return False
        
        # 获取并确认密码
        password = getpass.getpass("请输入管理员密码: ")
        confirm_password = getpass.getpass("请再次输入密码确认: ")
        
        if password != confirm_password:
            print("错误: 两次输入的密码不匹配。")
            return False
            
        if len(password) < 6:
            print("错误: 密码长度必须至少为6个字符。")
            return False
        
        # 创建管理员用户
        admin = User(
            username=username,
            email=email,
            role='admin'
        )
        admin.set_password(password)
        
        # 保存到数据库
        try:
            db.session.add(admin)
            db.session.commit()
            print(f"成功: 管理员用户 '{username}' 创建成功!")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"错误: 创建用户失败 - {str(e)}")
            return False

if __name__ == "__main__":
    success = create_admin()
    sys.exit(0 if success else 1)