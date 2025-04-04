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

# 添加新的版本模型
class LegalRegulationVersion(db.Model):
    """法规版本信息表"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    version_number = db.Column(db.String(50))  # 如 "1.0", "2.0" 或具体年份如 "2010版"
    revision_date = db.Column(db.DateTime)     # 修订日期
    effective_date = db.Column(db.DateTime)    # 该版本生效日期
    publish_date = db.Column(db.DateTime)      # 该版本公布日期
    status = db.Column(db.String(20), default='current')  # 状态如 "current", "superseded", "archived"
    changes_summary = db.Column(db.Text)       # 主要变更摘要
    
    # 反向关联到法规
    regulation = relationship('LegalRegulation', back_populates='versions')
    structures = relationship('LegalStructure', back_populates='version')
    causes = relationship('LegalCause', back_populates='version')
    
    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

# 修改主法规模型
class LegalRegulation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)  # 法规名称
    issuing_authority = db.Column(db.String(100))  # 制定机关
    effective_date = db.Column(db.DateTime)      # 施行日期
    publish_date = db.Column(db.DateTime)        # 公布日期
    hierarchy_level = db.Column(db.String(50))   # 法律效力位阶
    validity_status = db.Column(db.String(50))   # 时效性
    province = db.Column(db.String(50))          # 省份
    city = db.Column(db.String(50))              # 城市
    
    # 版本管理字段
    original_enactment_date = db.Column(db.DateTime)  # 最初制定日期
    latest_revision_date = db.Column(db.DateTime)     # 最新修订日期
    current_version_id = db.Column(db.Integer)        # 当前版本ID
    
    # 关联
    structures = relationship('LegalStructure', back_populates='regulation', cascade='all, delete-orphan')
    causes = relationship('LegalCause', back_populates='regulation', cascade='all, delete-orphan')
    versions = relationship('LegalRegulationVersion', back_populates='regulation', cascade='all, delete-orphan')

class LegalStructure(db.Model):
    """法律条文结构"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    version_id = db.Column(db.Integer, db.ForeignKey('legal_regulation_version.id', name='fk_structure_version_id'))
    
    article = db.Column(db.Integer)  # 条
    paragraph = db.Column(db.Integer)  # 款
    item = db.Column(db.Integer)  # 项
    section = db.Column(db.Integer)  # 目
    
    content = db.Column(db.Text, nullable=False)
    original_text = db.Column(db.Text)  # 原始文本
    
     # 关联
    regulation = relationship('LegalRegulation', back_populates='structures')
    version = relationship('LegalRegulationVersion', back_populates='structures')

class LegalCause(db.Model):
    """法律事由"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    version_id = db.Column(db.Integer, db.ForeignKey('legal_regulation_version.id', name='fk_cause_version_id'))
    
    code = db.Column(db.String(100), nullable=False)  # 唯一编号
    description = db.Column(db.Text, nullable=False)  # 事由描述
    
    # 匹配Excel中的列
    violation_type = db.Column(db.String(200))  # 违则
    violation_clause = db.Column(db.String(200))  # 违则条款
    behavior = db.Column(db.Text)  # 行为
    illegal_behavior = db.Column(db.Text)  # 违法行为
    penalty_type = db.Column(db.String(200))  # 罚则
    penalty_clause = db.Column(db.String(200))  # 罚则条款
    
    severity = db.Column(db.String(20))  # 严重程度
    
    # 关联的处罚
    punishments = relationship('LegalPunishment', back_populates='cause', cascade='all, delete-orphan')
    
    # 反向关联
    regulation = relationship('LegalRegulation', back_populates='causes')
    version = relationship('LegalRegulationVersion', back_populates='causes')

class LegalPunishment(db.Model):
    """具体处罚措施"""
    id = db.Column(db.Integer, primary_key=True)
    cause_id = db.Column(db.Integer, db.ForeignKey('legal_cause.id'), nullable=False)
    version_id = db.Column(db.Integer, db.ForeignKey('legal_regulation_version.id', name='fk_punishment_version_id'))  # 添加这行
    
    circumstance = db.Column(db.String(200))  # 情形
    punishment_type = db.Column(db.String(100))  # 处罚类型
    progressive_punishment = db.Column(db.String(200))  # 递进处罚
    industry = db.Column(db.String(200))  # 行业
    subject_level = db.Column(db.String(100))  # 主体级别
    punishment_target = db.Column(db.String(100))  # 处罚对象
    punishment_details = db.Column(db.Text)  # 处罚明细
    additional_notes = db.Column(db.Text)  # 行政行为
    
    # 反向关联
    cause = relationship('LegalCause', back_populates='punishments')
    version = relationship('LegalRegulationVersion')  # 可选：添加此项以便于查询

