from flask import Flask, render_template, redirect, url_for, request, abort, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from functools import wraps
from sqlalchemy import func, distinct, case, literal
from collections import Counter, defaultdict
from flask_admin import Admin, BaseView, expose
from flask import flash
import json
from datetime import datetime
from wtforms import PasswordField

from config import Config
from models import (
    db, User, LegalRegulation, LegalStructure, 
    LegalCause, LegalPunishment, LegalRegulationVersion
)

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(Config)

# 初始化数据库
db.init_app(app)
migrate = Migrate(app, db)

# 初始化LoginManager
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 在 app 初始化之后添加这段代码
@app.template_filter('nl2br')
def nl2br_filter(text):
    """将换行符转换为 HTML <br> 标签"""
    if not text:
        return ""
    return text.replace('\n', '<br>')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 权限装饰器
def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login', next=request.url))
            if current_user.role != role:
                abort(403)  # 没有权限
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return role_required('admin')(f)

# 创建Admin实例
admin = Admin(app, name='法律法规管理平台', template_mode='bootstrap4')

# 自定义安全的ModelView
# 修改当前的 SecureModelView，增强功能
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))
    
    # 添加记录变更功能
    def on_model_change(self, form, model, is_created):
        # 可以在这里添加修改记录跟踪
        # 例如：如果模型有 updated_at 字段，可以自动更新
        if hasattr(model, 'updated_at'):
            model.updated_at = datetime.now()
        return super(SecureModelView, self).on_model_change(form, model, is_created)


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

# 添加到admin
admin.add_view(LegalRegulationVersionView(LegalRegulationVersion, db.session, name='法规版本管理'))    
   

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

# 注册视图
admin.add_view(DataStatsView(name='数据统计', endpoint='stats'))
# 添加视图
# 替换原来的 admin 视图注册代码
admin.add_view(LegalRegulationView(LegalRegulation, db.session, name='法规管理'))
admin.add_view(LegalStructureView(LegalStructure, db.session, name='条文管理'))
admin.add_view(LegalCauseView(LegalCause, db.session, name='事由管理'))
admin.add_view(LegalPunishmentView(LegalPunishment, db.session, name='处罚管理'))
admin.add_view(UserView(User, db.session, name='用户管理'))



# 添加辅助函数来获取处罚计数
def get_punishment_count(regulation_id):
    """获取特定法规的处罚总数"""
    return db.session.query(LegalPunishment).\
        join(LegalCause).\
        filter(LegalCause.regulation_id == regulation_id).\
        count()

# 添加处罚计数辅助函数到应用上下文
@app.context_processor
def utility_processor():
    return {
        'get_punishment_count': get_punishment_count
    }

# 创建主页路由
@app.route('/')
def index():
    # 统计数据
    stats = {
        'regulation_count': LegalRegulation.query.count(),
        'cause_count': LegalCause.query.count(),
        'punishment_count': LegalPunishment.query.count()
    }
    return render_template('index.html', **stats)

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        
        return render_template('login.html', error="用户名或密码错误")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

# 法规搜索
@app.route('/search/regulations')
def search_regulations():
    keyword = request.args.get('keyword', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10

    query = LegalRegulation.query
    if keyword:
        query = query.filter(
            db.or_(
                LegalRegulation.name.like(f'%{keyword}%')
            )
        )
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    regulations = pagination.items

    return render_template('regulations/list.html', 
                           regulations=regulations, 
                           pagination=pagination, 
                           keyword=keyword)

# 法规详情
@app.route('/regulations/<int:regulation_id>')
def regulation_detail(regulation_id):
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    
    # 获取版本参数，如果未指定则默认使用当前版本
    version_id = request.args.get('version_id', type=int)
    
    # 确定要显示的版本
    if not version_id and regulation.current_version_id:
        version = LegalRegulationVersion.query.get(regulation.current_version_id)
    elif version_id:
        version = LegalRegulationVersion.query.get_or_404(version_id)
        if version.regulation_id != regulation.id:
            abort(404)
    else:
        # 找到最新版本
        version = LegalRegulationVersion.query.filter_by(
            regulation_id=regulation.id,
            status='current'
        ).first() or LegalRegulationVersion.query.filter_by(
            regulation_id=regulation.id
        ).order_by(LegalRegulationVersion.revision_date.desc()).first()
    
    # 查询条件：条文关联到当前法规
    structures_query = LegalStructure.query.filter_by(regulation_id=regulation.id)
    
    # 如果版本ID存在，则进一步筛选版本相关的条文
    if version and version.id:
        structures_query = structures_query.filter(
            db.or_(
                LegalStructure.version_id == version.id,
                LegalStructure.version_id.is_(None)  # 兼容尚未关联版本的旧数据
            )
        )
    
    structures = structures_query.all()
    
    # 类似地查询事由
    causes_query = LegalCause.query.filter_by(regulation_id=regulation.id)
    
    if version and version.id:
        causes_query = causes_query.filter(
            db.or_(
                LegalCause.version_id == version.id,
                LegalCause.version_id.is_(None)  # 兼容尚未关联版本的旧数据
            )
        )
    
    causes = causes_query.all()
    
    # 获取所有版本
    versions = LegalRegulationVersion.query.filter_by(
        regulation_id=regulation.id
    ).order_by(LegalRegulationVersion.revision_date.desc()).all()
    
    return render_template('regulations/detail.html', 
                           regulation=regulation, 
                           structures=structures,
                           causes=causes,
                           current_version=version,
                           all_versions=versions)

@app.route('/regulations/<int:regulation_id>/edit', methods=['GET', 'POST'])
@login_required
def regulation_edit(regulation_id):
    # 检查用户是否有权限编辑
    if current_user.role != 'admin':
        flash('您没有权限编辑法规', 'danger')
        return redirect(url_for('regulation_detail', regulation_id=regulation_id))
    # 获取法规
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    
    # 获取条文和事由
    structures = LegalStructure.query.filter_by(regulation_id=regulation_id).all()
    causes = LegalCause.query.filter_by(regulation_id=regulation_id).all()
    
    # 如果是POST请求，处理表单提交
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        if form_type == 'regulation':
             # 处理法规基本信息的更新
            regulation.name = request.form.get('name')
            regulation.issuing_authority = request.form.get('issuing_authority')
            regulation.hierarchy_level = request.form.get('hierarchy_level')
            
            # 处理日期字段
            if request.form.get('publish_date'):
                regulation.publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d')
            if request.form.get('effective_date'):
                regulation.effective_date = datetime.strptime(request.form.get('effective_date'), '%Y-%m-%d')
            if request.form.get('original_enactment_date'):
                regulation.original_enactment_date = datetime.strptime(request.form.get('original_enactment_date'), '%Y-%m-%d')
            if request.form.get('latest_revision_date'):
                regulation.latest_revision_date = datetime.strptime(request.form.get('latest_revision_date'), '%Y-%m-%d')
            
            # 更新其他字段
            regulation.province = request.form.get('province')
            regulation.city = request.form.get('city')
            regulation.validity_status = request.form.get('validity_status')
            
            try:
                db.session.commit()
                flash('法规信息已成功更新', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'更新法规失败: {str(e)}', 'danger')
        
        elif form_type == 'structure':
            # 处理条文更新
            structure_id = request.form.get('structure_id')
            structure = LegalStructure.query.get_or_404(structure_id)
            
            # 确保条文属于当前法规
            if structure.regulation_id != regulation.id:
                flash('无权编辑此条文', 'danger')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))
            
            # 更新条文字段
            structure.article = request.form.get('article', type=int)
            structure.paragraph = request.form.get('paragraph', type=int)
            structure.item = request.form.get('item', type=int)
            structure.section = request.form.get('section', type=int)
            structure.content = request.form.get('content')
            structure.original_text = request.form.get('original_text')
            
            try:
                db.session.commit()
                flash('条文信息已成功更新', 'success')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id, _anchor='structure-' + structure_id))
            except Exception as e:
                db.session.rollback()
                flash(f'更新条文失败: {str(e)}', 'danger')
        
        elif form_type == 'cause':
            # 处理事由更新
            cause_id = request.form.get('cause_id')
            cause = LegalCause.query.get_or_404(cause_id)
            
            # 确保事由属于当前法规
            if cause.regulation_id != regulation.id:
                flash('无权编辑此事由', 'danger')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))
            
            # 更新事由字段
            cause.code = request.form.get('code')
            cause.description = request.form.get('description')
            cause.violation_type = request.form.get('violation_type')
            cause.violation_clause = request.form.get('violation_clause')
            cause.behavior = request.form.get('behavior')
            cause.illegal_behavior = request.form.get('illegal_behavior')
            cause.penalty_type = request.form.get('penalty_type')
            cause.penalty_clause = request.form.get('penalty_clause')
            cause.severity = request.form.get('severity')
            
            try:
                db.session.commit()
                flash('事由信息已成功更新', 'success')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id, _anchor='cause-' + cause_id))
            except Exception as e:
                db.session.rollback()
                flash(f'更新事由失败: {str(e)}', 'danger')
        elif form_type == 'new_structure':
            # 创建新条文
            try:
                new_structure = LegalStructure(
                    regulation_id=regulation.id,
                    article=request.form.get('article', type=int),
                    paragraph=request.form.get('paragraph', type=int),
                    item=request.form.get('item', type=int),
                    section=request.form.get('section', type=int),
                    content=request.form.get('content'),
                    original_text=request.form.get('original_text')
                )
                db.session.add(new_structure)
                db.session.flush()  # 获取新创建条文的ID
                
                db.session.commit()
                flash('新条文已成功添加', 'success')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id, _anchor=f'structure-{new_structure.id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'添加条文失败: {str(e)}', 'danger')
        
        elif form_type == 'new_cause':
            # 创建新事由
            try:
                new_cause = LegalCause(
                    regulation_id=regulation.id,
                    code=request.form.get('code'),
                    description=request.form.get('description'),
                    violation_type=request.form.get('violation_type'),
                    violation_clause=request.form.get('violation_clause'),
                    behavior=request.form.get('behavior'),
                    illegal_behavior=request.form.get('illegal_behavior'),
                    penalty_type=request.form.get('penalty_type'),
                    penalty_clause=request.form.get('penalty_clause'),
                    severity=request.form.get('severity', '一般')
                )
                db.session.add(new_cause)
                db.session.flush()  # 获取新创建事由的ID
                
                db.session.commit()
                flash('新事由已成功添加', 'success')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id, _anchor=f'cause-{new_cause.id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'添加事由失败: {str(e)}', 'danger')
        
        elif form_type == 'delete_structure':
            # 删除条文
            structure_id = request.form.get('structure_id')
            structure = LegalStructure.query.get_or_404(structure_id)
            
            # 确保条文属于当前法规
            if structure.regulation_id != regulation.id:
                flash('无权删除此条文', 'danger')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))
            
            try:
                db.session.delete(structure)
                db.session.commit()
                flash('条文已成功删除', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'删除条文失败: {str(e)}', 'danger')
        
        # 在app.py的删除事由部分添加详细日志
        elif form_type == 'delete_cause':
            # 删除事由
            cause_id = request.form.get('cause_id')
            print(f"尝试删除事由，ID: {cause_id}")
            
            cause = LegalCause.query.get_or_404(cause_id)
            print(f"找到事由: {cause.description}, 关联法规ID: {cause.regulation_id}")
            
            # 确保事由属于当前法规
            if cause.regulation_id != regulation.id:
                print(f"无权删除: 事由的regulation_id({cause.regulation_id}) != 当前regulation.id({regulation.id})")
                flash('无权删除此事由', 'danger')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))
            
            try:
                # 检查相关的处罚数量
                punishment_count = LegalPunishment.query.filter_by(cause_id=cause.id).count()
                print(f"将删除 {punishment_count} 条相关处罚记录")
                
                # 删除相关的处罚信息
                LegalPunishment.query.filter_by(cause_id=cause.id).delete()
                
                # 删除事由
                db.session.delete(cause)
                print("事由标记为删除，准备提交事务")
                db.session.commit()
                print("事务已提交，事由删除成功")
                flash('事由已成功删除', 'success')
                
                # 修改：使用重定向而不是继续处理
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))
            except Exception as e:
                db.session.rollback()
                print(f"删除事由失败，异常信息: {str(e)}")
                flash(f'删除事由失败: {str(e)}', 'danger')
                return redirect(url_for('regulation_edit', regulation_id=regulation_id))

    
    # 对条文和事由进行排序，以便在界面上更好地显示
    structures = sorted(structures, key=lambda x: (x.article or 0, x.paragraph or 0, x.item or 0, x.section or 0))
    causes = sorted(causes, key=lambda x: x.code)
    
    return render_template('regulations/edit/edit.html', 
                           regulation=regulation,
                           structures=structures,
                           causes=causes)
    
    # 获取条文和事由，以便在编辑页面显示相关信息
    structures = LegalStructure.query.filter_by(regulation_id=regulation_id).all()
    causes = LegalCause.query.filter_by(regulation_id=regulation_id).all()
    
    return render_template('regulations/edit/edit.html', 
                           regulation=regulation,
                           structures=structures,
                           causes=causes)

@app.route('/causes/<int:cause_id>/punishments', methods=['GET', 'POST'])
@login_required
def punishment_edit(cause_id):
    # 检查用户是否有权限编辑
    if current_user.role != 'admin':
        flash('您没有权限编辑处罚措施', 'danger')
        return redirect(url_for('cause_detail', cause_id=cause_id))
    
        # 获取事由信息
    cause = LegalCause.query.get_or_404(cause_id)
    regulation = cause.regulation  # 这里确保获取了regulation变量
    
    # 获取该事由下的所有处罚措施
    punishments = LegalPunishment.query.filter_by(cause_id=cause_id).all()
    
    # 处理表单提交
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        
        # 编辑现有处罚措施
        if form_type == 'punishment':
            punishment_id = request.form.get('punishment_id')
            punishment = LegalPunishment.query.get_or_404(punishment_id)
            
            # 确保处罚属于当前事由
            if punishment.cause_id != cause.id:
                flash('无权编辑此处罚', 'danger')
                return redirect(url_for('punishment_edit', cause_id=cause_id))
            
            # 更新处罚信息
            punishment.circumstance = request.form.get('circumstance')
            punishment.punishment_type = request.form.get('punishment_type')
            punishment.progressive_punishment = request.form.get('progressive_punishment')
            punishment.industry = request.form.get('industry')
            punishment.subject_level = request.form.get('subject_level')
            punishment.punishment_target = request.form.get('punishment_target')
            punishment.punishment_details = request.form.get('punishment_details')
            punishment.additional_notes = request.form.get('additional_notes')
            
            try:
                db.session.commit()
                flash('处罚信息已成功更新', 'success')
                return redirect(url_for('punishment_edit', cause_id=cause_id, _anchor=f'punishment-{punishment_id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'更新处罚失败: {str(e)}', 'danger')
        
        # 新增处罚措施
        elif form_type == 'new_punishment':
            try:
                new_punishment = LegalPunishment(
                    cause_id=cause.id,
                    circumstance=request.form.get('circumstance'),
                    punishment_type=request.form.get('punishment_type'),
                    progressive_punishment=request.form.get('progressive_punishment'),
                    industry=request.form.get('industry'),
                    subject_level=request.form.get('subject_level'),
                    punishment_target=request.form.get('punishment_target'),
                    punishment_details=request.form.get('punishment_details'),
                    additional_notes=request.form.get('additional_notes')
                )
                db.session.add(new_punishment)
                db.session.flush()  # 获取新创建处罚的ID
                
                db.session.commit()
                flash('新处罚已成功添加', 'success')
                return redirect(url_for('punishment_edit', cause_id=cause_id, _anchor=f'punishment-{new_punishment.id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'添加处罚失败: {str(e)}', 'danger')
        
        # 删除处罚措施
        elif form_type == 'delete_punishment':
            punishment_id = request.form.get('punishment_id')
            punishment = LegalPunishment.query.get_or_404(punishment_id)
            
            # 确保处罚属于当前事由
            if punishment.cause_id != cause.id:
                flash('无权删除此处罚', 'danger')
                return redirect(url_for('punishment_edit', cause_id=cause_id))
            
            try:
                db.session.delete(punishment)
                db.session.commit()
                flash('处罚已成功删除', 'success')
                return redirect(url_for('punishment_edit', cause_id=cause_id))
            except Exception as e:
                db.session.rollback()
                flash(f'删除处罚失败: {str(e)}', 'danger')
    
    return render_template('punishments/edit.html',
                          cause=cause,
                          regulation=regulation,  # 确保传递regulation变量
                          punishments=punishments)

# 新增统计图表路由
@app.route('/regulations/<int:regulation_id>/stats')
def regulation_stats(regulation_id):
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    
    # 获取统计数据
    causes_count = LegalCause.query.filter_by(regulation_id=regulation_id).count()
    structures_count = LegalStructure.query.filter_by(regulation_id=regulation_id).count()
    
    # 获取该法规的所有处罚
    punishments = db.session.query(LegalPunishment).\
        join(LegalCause).\
        filter(LegalCause.regulation_id == regulation_id).\
        all()
    
    punishments_count = len(punishments)
    
    # 处罚类型统计
    punishment_types = []
    if punishments:
        type_counter = Counter()
        for p in punishments:
            if p.punishment_type:
                # 分割处罚类型
                types = [type_str.strip() for type_str in p.punishment_type.split('、')]
                for t in types:
                    if t:  # 确保不是空字符串
                        type_counter[t] += 1
            else:
                type_counter["未指定"] += 1
        
        punishment_types = [{"type": t, "count": c} for t, c in type_counter.most_common()]
    
    # 处罚对象统计
    punishment_targets = []
    if punishments:
        target_counter = Counter()
        for p in punishments:
            if p.punishment_target:
                # 分割处罚对象
                targets = [target_str.strip() for target_str in p.punishment_target.split('、')]
                for t in targets:
                    if t:  # 确保不是空字符串
                        target_counter[t] += 1
            else:
                target_counter["未指定"] += 1
        
        punishment_targets = [{"target": t, "count": c} for t, c in target_counter.most_common()]
    
    # 事由与处罚关系统计（改为显示事由名称）
    punishment_by_cause = []
    if punishments:
        cause_dict = {}
        # 获取所有事由的信息
        causes = LegalCause.query.filter_by(regulation_id=regulation_id).all()
        for cause in causes:
            # 使用事由描述而非编号
            truncated_desc = cause.description[:30] + "..." if len(cause.description) > 30 else cause.description
            cause_dict[cause.id] = {
                "cause_code": cause.code,  # 保留编号但不展示
                "cause_desc": truncated_desc,  # 使用事由名称
                "count": 0
            }
        
        # 计算每个事由的处罚数量
        for p in punishments:
            if p.cause_id in cause_dict:
                cause_dict[p.cause_id]["count"] += 1
        
        # 过滤掉没有处罚的事由，并排序
        punishment_by_cause = sorted(
            [v for v in cause_dict.values() if v["count"] > 0],
            key=lambda x: x["count"],
            reverse=True
        )
        
        # 如果事由太多，只展示前10个
        if len(punishment_by_cause) > 10:
            punishment_by_cause = punishment_by_cause[:10]
    
    return render_template('regulations/stats.html',
                          regulation=regulation,
                          causes_count=causes_count,
                          structures_count=structures_count,
                          punishments_count=punishments_count,
                          punishment_types=punishment_types,
                          punishment_targets=punishment_targets,
                          punishment_by_cause=punishment_by_cause)

# 事由详情
@app.route('/causes/<int:cause_id>')
def cause_detail(cause_id):
    cause = LegalCause.query.get_or_404(cause_id)
    regulation = cause.regulation  # 确保提供regulation变量
    punishments = LegalPunishment.query.filter_by(cause_id=cause_id).all()
    
    return render_template('causes/detail.html', 
                           cause=cause, 
                           regulation=regulation,  # 传递regulation变量
                           punishments=punishments)

@app.route('/regulations/level/<level>')
def regulations_by_level(level):
    page = request.args.get('page', 1, type=int)
    per_page = 10
    keyword = request.args.get('keyword', '')
    sort = request.args.get('sort', 'date_desc')
    
    # 构建基本查询
    if level == '地方性法规':
        base_query = LegalRegulation.query.filter(
            db.or_(
                LegalRegulation.hierarchy_level == '地方性法规',
                LegalRegulation.hierarchy_level == '自治条例',
                LegalRegulation.hierarchy_level == '单行条例'
            )
        )
    else:
        base_query = LegalRegulation.query.filter_by(hierarchy_level=level)
    
    # 添加关键词搜索
    if keyword:
        # 更新查询使用现有字段
        base_query = base_query.filter(
            db.or_(
                LegalRegulation.name.like(f'%{keyword}%'),
                LegalRegulation.issuing_authority.like(f'%{keyword}%')
            )
        )
    
    # 添加排序
    if sort == 'date_asc':
        base_query = base_query.order_by(LegalRegulation.publish_date.asc())
    elif sort == 'name':
        base_query = base_query.order_by(LegalRegulation.name.asc())
    else:  # 默认为date_desc
        base_query = base_query.order_by(LegalRegulation.publish_date.desc())
    
    pagination = base_query.paginate(page=page, per_page=per_page, error_out=False)
    regulations = pagination.items
    
    return render_template('regulations/level_list.html', 
                           regulations=regulations, 
                           pagination=pagination, 
                           current_level=level)


# 高级搜索
@app.route('/advanced_search', methods=['GET'])
def advanced_search():
    regulation_name = request.args.get('regulation_name')
    cause_keyword = request.args.get('cause_keyword')
    punishment_type = request.args.get('punishment_type')
    
    # 构建查询
    query = LegalCause.query
    
    if regulation_name:
        query = query.join(LegalRegulation).filter(LegalRegulation.name.like(f'%{regulation_name}%'))
    
    if cause_keyword:
        query = query.filter(
            db.or_(
                LegalCause.description.like(f'%{cause_keyword}%'),
                LegalCause.code.like(f'%{cause_keyword}%')
            )
        )
    
    if punishment_type:
        query = query.join(LegalPunishment).filter(LegalPunishment.punishment_type.like(f'%{punishment_type}%'))
    
    causes = query.all()
    
    return render_template('search_results.html', causes=causes)


# 初始化命令
@app.cli.command('init-db')
def init_db():
    """初始化数据库"""
    db.create_all()
    print('数据库表已创建。')

# 创建管理员命令
@app.cli.command('create-admin')
def create_admin():
    """创建管理员用户"""
    username = input("输入管理员用户名: ")
    email = input("输入管理员邮箱: ")
    password = input("输入管理员密码: ")
    
    user = User.query.filter((User.username == username) | (User.email == email)).first()
    if user:
        print("用户名或邮箱已存在")
        return
    
    admin = User(username=username, email=email, role='admin')
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print("管理员用户创建成功!")

if __name__ == '__main__':
    app.run(debug=True)