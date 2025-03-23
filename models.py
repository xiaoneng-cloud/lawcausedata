from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user')  # 'admin', 'manager', 'user'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __str__(self):
        return self.username

class LegalRegulation(db.Model):
    """法律法规主表"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    issued_by = db.Column(db.String(100))  # 发布部门（原source字段重命名）
    document_number = db.Column(db.String(100))  # 发布文号
    issued_date = db.Column(db.DateTime)  # 发布日期
    effective_date = db.Column(db.DateTime)  # 生效日期
    
    # 新增字段
    hierarchy_level = db.Column(db.String(50))  # 效力位阶
    industry_category = db.Column(db.String(100))  # 行业类别
    validity = db.Column(db.String(20), default='现行有效')  # 有效性：尚未生效、现行有效、已修改、已废止
    
    status = db.Column(db.String(20), default='active')  # 状态：active, archived
    
    # 关联条文
    structures = relationship('LegalStructure', back_populates='regulation', cascade='all, delete-orphan')
    # 关联事由
    causes = relationship('LegalCause', back_populates='regulation', cascade='all, delete-orphan')

class LegalStructure(db.Model):
    """法律条文结构"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    
    article = db.Column(db.Integer)  # 条
    paragraph = db.Column(db.Integer)  # 款
    item = db.Column(db.Integer)  # 项
    section = db.Column(db.Integer)  # 目
    
    content = db.Column(db.Text, nullable=False)
    original_text = db.Column(db.Text)  # 原始文本
    
    # 反向关联
    regulation = relationship('LegalRegulation', back_populates='structures')

class LegalCause(db.Model):
    """法律事由"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    
    code = db.Column(db.String(100), nullable=False)  # 唯一编号
    description = db.Column(db.Text, nullable=False)  # 事由描述
    
    # 新增字段，匹配Excel中的列
    violation_type = db.Column(db.String(200))  # 违则
    violation_clause = db.Column(db.String(200))  # 违则条款
    behavior = db.Column(db.Text)  # 行为
    illegal_behavior = db.Column(db.Text)  # 违法行为
    
    severity = db.Column(db.String(20))  # 严重程度
    
    # 关联的处罚
    punishments = relationship('LegalPunishment', back_populates='cause', cascade='all, delete-orphan')
    
    # 反向关联
    regulation = relationship('LegalRegulation', back_populates='causes')

class LegalPunishment(db.Model):
    """具体处罚措施"""
    id = db.Column(db.Integer, primary_key=True)
    cause_id = db.Column(db.Integer, db.ForeignKey('legal_cause.id'), nullable=False)
    
    circumstance = db.Column(db.String(200))  # 情形
    punishment_type = db.Column(db.String(100))  # 处罚类型
    progressive_punishment = db.Column(db.String(200))  # 递进处罚
    industry = db.Column(db.String(200))  # 行业
    subject_level = db.Column(db.String(100))  # 主体级别
    punishment_target = db.Column(db.String(100))  # 处罚对象
    punishment_details = db.Column(db.Text)  # 处罚明细
    additional_notes = db.Column(db.Text)  # 补充说明
    
    # 反向关联
    cause = relationship('LegalCause', back_populates='punishments')