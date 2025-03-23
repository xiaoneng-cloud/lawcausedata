from flask import Flask, render_template, redirect, url_for, request, abort, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_migrate import Migrate
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from functools import wraps
from sqlalchemy import func, distinct, case, literal
from collections import Counter, defaultdict
import json

from config import Config
from models import (
    db, User, LegalRegulation, LegalStructure, 
    LegalCause, LegalPunishment
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
class SecureModelView(ModelView):
    def is_accessible(self):
        return current_user.is_authenticated and current_user.role == 'admin'
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('login', next=request.url))

# 添加视图
admin.add_view(SecureModelView(LegalRegulation, db.session, name='法规管理'))
admin.add_view(SecureModelView(LegalStructure, db.session, name='条文管理'))
admin.add_view(SecureModelView(LegalCause, db.session, name='事由管理'))
admin.add_view(SecureModelView(LegalPunishment, db.session, name='处罚管理'))
admin.add_view(SecureModelView(User, db.session, name='用户管理'))

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
                LegalRegulation.name.like(f'%{keyword}%'),
                LegalRegulation.source.like(f'%{keyword}%')
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
    
    # 获取条文
    structures = LegalStructure.query.filter_by(regulation_id=regulation_id).all()
    
    # 获取事由
    causes = LegalCause.query.filter_by(regulation_id=regulation_id).all()
    
    return render_template('regulations/detail.html', 
                           regulation=regulation, 
                           structures=structures,
                           causes=causes)

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
    punishments = LegalPunishment.query.filter_by(cause_id=cause_id).all()
    
    return render_template('causes/detail.html', 
                           cause=cause, 
                           punishments=punishments)

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