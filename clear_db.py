# clear_data.py
# 创建Flask应用上下文
from app import create_app
from app.extensions import db
from app.models.regulation import LegalRegulation, LegalStructure, LegalCause, LegalPunishment, LegalRegulationVersion

def clear_database():
    """清空业务数据但保留数据库结构和用户账户"""
    try:
        # 创建应用上下文
        app = create_app()
        with app.app_context():
            # 先删除具有外键依赖的表中的数据
            print("正在删除处罚数据...")
            db.session.query(LegalPunishment).delete()
            
            print("正在删除事由数据...")
            db.session.query(LegalCause).delete()
            
            print("正在删除条文数据...")
            db.session.query(LegalStructure).delete()
            
            print("正在删除版本数据...")
            db.session.query(LegalRegulationVersion).delete()
            
            print("正在删除法规数据...")
            db.session.query(LegalRegulation).delete()
            
            # 提交事务
            db.session.commit()
            print("所有业务数据已清空")
            
    except Exception as e:
        db.session.rollback()
        print(f"清空数据时发生错误: {str(e)}")

if __name__ == "__main__":
    clear_database()