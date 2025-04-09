# app/views/admin.py
from flask import Blueprint, redirect, url_for, request, abort, render_template
from flask_admin.contrib.sqla import ModelView
from flask_admin import Admin, BaseView, expose  # 添加 BaseView 和 expose
from flask_login import current_user, login_required
from app.extensions import db, admin
from app.models.user import User
from app.models.regulation import LegalRegulation, LegalStructure, LegalCause, LegalPunishment, LegalRegulationVersion
from functools import wraps
from datetime import datetime
from wtforms import PasswordField

admin_bp = Blueprint('admin', __name__)

# 权限装饰器
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role != role:
                abort(403)  # 没有权限
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_required('admin')(f)

# 自定义安全的ModelView
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('auth.login', next=request.url))
    
    def on_model_change(self, form, model, is_created):
        if hasattr(model, 'updated_at'):
            model.updated_at = datetime.now()
        return super(SecureModelView, self).on_model_change(form, model, is_created)

# 条文管理视图
class LegalStructureView(SecureModelView):
    column_list = ['regulation.name', 'article', 'paragraph', 'item', 'section', 'content']
    column_searchable_list = ['content']
    column_filters = ['regulation.name', 'article']
    column_labels = {
        'regulation.name': '所属法规',
        'regulation': '所属法规',
        'article': '条',
        'paragraph': '款',
        'item': '项',
        'section': '目',
        'content': '内容',
        'original_text': '原文'
    }
    form_ajax_refs = {
        'regulation': {
            'fields': ['name'],
            'page_size': 10
        }
    }

# 法规管理视图
class LegalRegulationView(SecureModelView):
    # 添加删除确认消息
    delete_message = '删除此法规将同时删除其包含的所有条文、事由及处罚信息。您确定要继续吗？'

    # 调整显示列表以匹配新字段
    column_list = ['name', 'issuing_authority', 'publish_date', 'effective_date', 'hierarchy_level', 'validity_status']
    
    # 调整搜索字段
    column_searchable_list = ['name', 'issuing_authority']
    
    # 调整过滤字段
    column_filters = ['validity_status', 'publish_date', 'effective_date', 'hierarchy_level', 'province', 'city']
    
    # 排除关联字段，新增排除versions字段
    form_excluded_columns = ['structures', 'causes', 'versions']
    
    # 更新字段标签
    column_labels = {
        'name': '法规名称',
        'issuing_authority': '制定机关',
        'publish_date': '公布日期',
        'effective_date': '施行日期',
        'hierarchy_level': '法律效力位阶',
        'validity_status': '时效性',
        'province': '省',
        'city': '市',
        'original_enactment_date': '最初制定日期',
        'latest_revision_date': '最新修订日期',
        'current_version_id': '当前版本ID'
    }
    
    # 更新字段描述
    column_descriptions = {
        'name': '法规的完整名称',
        'issuing_authority': '制定或发布法规的机关',
        'validity_status': '时效性状态（有效、已废止、已修订等）'
    }
    
    # 更新批量操作
    action_list = [
        ('set_valid', '设为有效'),
        ('set_abolished', '设为已废止'),
        ('set_revised', '设为已修订')
    ]
    
    can_view_details = True  # 启用详情视图
    
    # 更新详情页显示的字段
    column_details_list = ['name', 'issuing_authority', 'publish_date', 'effective_date', 
                          'hierarchy_level', 'validity_status', 'province', 'city',
                          'original_enactment_date', 'latest_revision_date']
    
    @property
    def details_template(self):
        return 'admin/regulation_details.html'  # 保持现有的自定义模板

#法规版本管理视图
class LegalRegulationVersionView(SecureModelView):
    column_list = ['regulation.name', 'version_number', 'revision_date', 'status']
    column_searchable_list = ['regulation.name', 'version_number']
    column_filters = ['status', 'revision_date']
    form_ajax_refs = {
        'regulation': {
            'fields': ['name'],
            'page_size': 10
        }
    }
    column_labels = {
        'regulation.name': '法规名称',
        'regulation': '法规',
        'version_number': '版本号',
        'revision_date': '修订日期',
        'effective_date': '生效日期',
        'publish_date': '公布日期',
        'status': '状态',
        'changes_summary': '变更摘要'
    }

# 事由管理视图
class LegalCauseView(SecureModelView):
     # 添加删除确认消息
    delete_message = '删除此事由将同时删除其包含的所有处罚信息。您确定要继续吗？'

    column_list = ['regulation.name', 'code', 'description', 'violation_type', 'severity']
    column_searchable_list = ['code', 'description', 'violation_type']
    column_filters = ['regulation.name', 'severity', 'penalty_type']  # 添加了penalty_type字段
    form_excluded_columns = ['punishments']
    column_labels = {
        'regulation.name': '所属法规',
        'regulation': '所属法规',
        'code': '编号',
        'description': '事由描述',
        'violation_type': '违则类型',
        'violation_clause': '违则条款',
        'behavior': '行为',
        'illegal_behavior': '违法行为',
        'penalty_type': '罚则',
        'penalty_clause': '罚则条款',
        'severity': '严重程度'
    }
    form_ajax_refs = {
        'regulation': {
            'fields': ['name'],
            'page_size': 10
        }
    }

# 处罚管理视图
class LegalPunishmentView(SecureModelView):
    column_list = ['cause.description', 'punishment_type', 'circumstance', 'punishment_target']
    column_searchable_list = ['punishment_type', 'punishment_details']
    column_filters = ['cause.regulation.name', 'punishment_type', 'industry']
    column_labels = {
        'cause.description': '事由',
        'cause': '事由',
        'circumstance': '情形',
        'punishment_type': '处罚类型',
        'progressive_punishment': '递进处罚',
        'industry': '行业',
        'subject_level': '主体级别',
        'punishment_target': '处罚对象',
        'punishment_details': '处罚明细',
        'additional_notes': '行政行为'
    }
    form_ajax_refs = {
        'cause': {
            'fields': ['description', 'code'],
            'page_size': 10
        }
    }

# 用户管理视图
class UserView(SecureModelView):
    column_list = ['username', 'email', 'role']
    column_searchable_list = ['username', 'email']
    column_filters = ['role']
    form_excluded_columns = ['password_hash']
    column_labels = {
        'username': '用户名',
        'email': '邮箱',
        'role': '角色'
    }
    
    # 添加密码字段（因为我们不能直接编辑 password_hash）
    form_extra_fields = {
        'password': PasswordField('密码')
    }
    
    def on_model_change(self, form, model, is_created):
        # 如果提供了密码，则设置密码哈希
        if form.password.data:
            model.set_password(form.password.data)
        return super(UserView, self).on_model_change(form, model, is_created)

class DataStatsView(BaseView):
    @expose('/')
    def index(self):
        regulation_count = LegalRegulation.query.count()
        structure_count = LegalStructure.query.count()
        cause_count = LegalCause.query.count()
        punishment_count = LegalPunishment.query.count()
        
        # 每个法规的平均事由数
        avg_causes_per_regulation = db.session.query(
            func.avg(func.count(LegalCause.id))
        ).group_by(LegalCause.regulation_id).scalar() or 0
        
        # 每个事由的平均处罚数
        avg_punishments_per_cause = db.session.query(
            func.avg(func.count(LegalPunishment.id))
        ).group_by(LegalPunishment.cause_id).scalar() or 0
        
        return self.render('admin/stats.html',
                          regulation_count=regulation_count,
                          structure_count=structure_count,
                          cause_count=cause_count,
                          punishment_count=punishment_count,
                          avg_causes=avg_causes_per_regulation,
                          avg_punishments=avg_punishments_per_cause)


# 设置Admin
def setup_admin(app):
    admin.init_app(app)
    
    # 添加视图
    admin.add_view(LegalRegulationView(LegalRegulation, db.session, name='法规管理'))
    admin.add_view(LegalRegulationVersionView(LegalRegulationVersion, db.session, name='法规版本管理'))
    admin.add_view(LegalStructureView(LegalStructure, db.session, name='条文管理'))
    admin.add_view(LegalCauseView(LegalCause, db.session, name='事由管理'))
    admin.add_view(LegalPunishmentView(LegalPunishment, db.session, name='处罚管理'))
    admin.add_view(UserView(User, db.session, name='用户管理'))
    admin.add_view(DataStatsView(name='数据统计', endpoint='stats'))
    
    # 其他Admin视图...