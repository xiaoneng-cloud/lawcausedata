# app/models/regulation.py
from datetime import datetime
from app.extensions import db

class TimestampMixin:
    """添加创建和更新时间戳的Mixin类"""
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

class LegalRegulationVersion(db.Model, TimestampMixin):
    """法规版本信息表"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    version_number = db.Column(db.String(50))  # 如 "1.0", "2.0" 或年份如 "2010版"
    revision_date = db.Column(db.DateTime)     # 修订日期
    effective_date = db.Column(db.DateTime)    # 该版本生效日期
    publish_date = db.Column(db.DateTime)      # 该版本公布日期
    status = db.Column(db.String(20), default='current')  # "current", "superseded", "archived"
    changes_summary = db.Column(db.Text)       # 主要变更摘要
    step_id = db.Column(db.Integer, default=1)  # 默认值为1
    
    # 关联
    regulation = db.relationship('LegalRegulation', back_populates='versions')
    structures = db.relationship('LegalStructure', back_populates='version')
    causes = db.relationship('LegalCause', back_populates='version')
    
    def __str__(self):
        return f"{self.regulation.name} - {self.version_number}" if self.regulation else self.version_number

class LegalRegulation(db.Model, TimestampMixin):
    """法规模型"""
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
    structures = db.relationship('LegalStructure', back_populates='regulation', cascade='all, delete-orphan')
    causes = db.relationship('LegalCause', back_populates='regulation', cascade='all, delete-orphan')
    versions = db.relationship('LegalRegulationVersion', back_populates='regulation', cascade='all, delete-orphan')
    
    def __str__(self):
        return self.name
    
    def get_current_version(self):
        """获取当前版本"""
        if self.current_version_id:
            return LegalRegulationVersion.query.get(self.current_version_id)
        return None
    
    def get_structures(self, version_id=None):
        """获取指定版本的条文"""
        query = LegalStructure.query.filter_by(regulation_id=self.id)
        
        if version_id:
            query = query.filter(
                db.or_(
                    LegalStructure.version_id == version_id,
                    LegalStructure.version_id.is_(None)
                )
            )
        
        return query.order_by(LegalStructure.article, LegalStructure.paragraph, 
                             LegalStructure.item, LegalStructure.section).all()
    
    def get_causes(self, version_id=None):
        """获取指定版本的事由"""
        query = LegalCause.query.filter_by(regulation_id=self.id)
        
        if version_id:
            query = query.filter(
                db.or_(
                    LegalCause.version_id == version_id,
                    LegalCause.version_id.is_(None)
                )
            )
        
        return query.order_by(LegalCause.code).all()

class LegalStructure(db.Model, TimestampMixin):
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
    regulation = db.relationship('LegalRegulation', back_populates='structures')
    version = db.relationship('LegalRegulationVersion', back_populates='structures')
    
    def __str__(self):
        return f"第{self.article}条" if self.article else "未编号条文"

class LegalCause(db.Model, TimestampMixin):
    """法律事由"""
    id = db.Column(db.Integer, primary_key=True)
    regulation_id = db.Column(db.Integer, db.ForeignKey('legal_regulation.id'), nullable=False)
    version_id = db.Column(db.Integer, db.ForeignKey('legal_regulation_version.id', name='fk_cause_version_id'))
    
    code = db.Column(db.String(100), nullable=False)  # 唯一编号
    description = db.Column(db.Text, nullable=False)  # 事由描述
    
    # 各类特定信息
    violation_type = db.Column(db.String(200))  # 违则
    violation_clause = db.Column(db.String(200))  # 违则条款
    behavior = db.Column(db.Text)  # 行为
    illegal_behavior = db.Column(db.Text)  # 违法行为
    penalty_type = db.Column(db.String(200))  # 罚则
    penalty_clause = db.Column(db.String(200))  # 罚则条款
    
    severity = db.Column(db.String(20))  # 严重程度
    
    # 关联
    punishments = db.relationship('LegalPunishment', back_populates='cause', cascade='all, delete-orphan')
    regulation = db.relationship('LegalRegulation', back_populates='causes')
    version = db.relationship('LegalRegulationVersion', back_populates='causes')
    
    def __str__(self):
        return f"{self.code}: {self.description[:30]}..." if len(self.description) > 30 else self.description

class LegalPunishment(db.Model, TimestampMixin):
    """具体处罚措施"""
    id = db.Column(db.Integer, primary_key=True)
    cause_id = db.Column(db.Integer, db.ForeignKey('legal_cause.id'), nullable=False)
    version_id = db.Column(db.Integer, db.ForeignKey('legal_regulation_version.id', name='fk_punishment_version_id'))
    
    circumstance = db.Column(db.String(200))  # 情形
    punishment_type = db.Column(db.String(100))  # 处罚类型
    progressive_punishment = db.Column(db.String(200))  # 递进处罚
    industry = db.Column(db.String(200))  # 行业
    subject_level = db.Column(db.String(100))  # 主体级别
    punishment_target = db.Column(db.String(100))  # 处罚对象
    punishment_details = db.Column(db.Text)  # 处罚明细
    additional_notes = db.Column(db.Text)  # 行政行为
    
    # 关联
    cause = db.relationship('LegalCause', back_populates='punishments')
    version = db.relationship('LegalRegulationVersion')
    
    def __str__(self):
        return f"{self.punishment_type} - {self.cause.code}" if self.cause else self.punishment_type