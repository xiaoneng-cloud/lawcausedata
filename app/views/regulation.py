# app/views/regulation.py
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from app.models import LegalRegulation, LegalStructure, LegalCause, LegalPunishment, LegalRegulationVersion
from app.extensions import db
from sqlalchemy import or_
from datetime import datetime
import logging

regulation_bp = Blueprint('regulation', __name__)

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('law_regulation_debug.log')  # 输出到文件
    ]
)
logger = logging.getLogger(__name__)

@regulation_bp.route('/')
def index():
    """首页"""
    # 统计数据
    stats = {
        'regulation_count': LegalRegulation.query.count(),
        'cause_count': LegalCause.query.count(),
        'punishment_count': LegalPunishment.query.count()
    }
    return render_template('index.html', **stats)

# 法规搜索
@regulation_bp.route('/search/regulations')
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
#法规详情
@regulation_bp.route('/regulations/<int:regulation_id>')
def regulation_detail(regulation_id):
    logger.info(f"开始处理法规详情请求: regulation_id={regulation_id}")
    
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    logger.info(f"已获取法规信息: {regulation.name}")
    
    # 获取版本参数，如果未指定则默认使用当前版本
    version_id = request.args.get('version_id', type=int)
    logger.debug(f"请求参数 version_id: {version_id}")
    
    # 确定要显示的版本
    if not version_id and regulation.current_version_id:
        version = LegalRegulationVersion.query.get(regulation.current_version_id)
        logger.debug(f"使用当前版本: id={regulation.current_version_id}")
    elif version_id:
        version = LegalRegulationVersion.query.get_or_404(version_id)
        if version.regulation_id != regulation.id:
            logger.error(f"版本与法规不匹配: version_id={version_id}, regulation_id={regulation.id}")
            abort(404)
        logger.debug(f"使用指定版本: id={version_id}")
    else:
        # 找到最新版本
        version = LegalRegulationVersion.query.filter_by(
            regulation_id=regulation.id,
            status='current'
        ).first() or LegalRegulationVersion.query.filter_by(
            regulation_id=regulation.id
        ).order_by(LegalRegulationVersion.revision_date.desc()).first()
        logger.debug(f"使用最新版本: id={version.id if version else None}")
    
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
    logger.info(f"已查询到条文数量: {len(structures)}")
    
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
    logger.info(f"已查询到事由数量: {len(causes)}")
    
    # 获取所有版本
    versions = LegalRegulationVersion.query.filter_by(
        regulation_id=regulation.id
    ).order_by(LegalRegulationVersion.revision_date.desc()).all()
    logger.info(f"已查询到版本数量: {len(versions)}")
    
    # 新增代码：确定每个条文的角色
    structure_roles = {}
    structure_causes = {}
    
    logger.info("开始分析条文角色和关联关系...")
    
    # 遍历所有事由，确定条文角色并建立条文与事由的关联
    for cause in causes:
        logger.debug(f"处理事由: id={cause.id}, code={cause.code}")
        
        # 解析违则条款，查找对应的条文
        if cause.violation_type:
            logger.debug(f"事由 {cause.code} 的违则条款: {cause.violation_type}")
            article_refs = extract_article_references(cause.violation_type)
            logger.debug(f"从违则条款中提取的条文引用: {article_refs}")
            
            for article_ref in article_refs:
                # 查找对应的条文
                for structure in structures:
                    if match_structure(structure, article_ref):
                        logger.debug(f"找到匹配的违则条文: structure_id={structure.id}, article={structure.article}")
                        # 标记为违则条文
                        if structure.id not in structure_roles:
                            structure_roles[structure.id] = []
                        if 'violation' not in structure_roles[structure.id]:
                            structure_roles[structure.id].append('violation')
                        
                        # 关联事由到条文
                        if structure.id not in structure_causes:
                            structure_causes[structure.id] = []
                        if cause not in structure_causes[structure.id]:
                            structure_causes[structure.id].append(cause)
        
        # 解析罚则条款，查找对应的条文
        if cause.penalty_type:
            logger.debug(f"事由 {cause.code} 的罚则条款: {cause.penalty_type}")
            article_refs = extract_article_references(cause.penalty_type)
            logger.debug(f"从罚则条款中提取的条文引用: {article_refs}")
            
            for article_ref in article_refs:
                # 查找对应的条文
                for structure in structures:
                    if match_structure(structure, article_ref):
                        logger.debug(f"找到匹配的罚则条文: structure_id={structure.id}, article={structure.article}")
                        # 标记为罚则条文
                        if structure.id not in structure_roles:
                            structure_roles[structure.id] = []
                        if 'punishment' not in structure_roles[structure.id]:
                            structure_roles[structure.id].append('punishment')
                        
                        # 关联事由到条文
                        if structure.id not in structure_causes:
                            structure_causes[structure.id] = []
                        if cause not in structure_causes[structure.id]:
                            structure_causes[structure.id].append(cause)

        # 解析行为条款，查找对应的条文
        if cause.behavior:
            logger.debug(f"事由 {cause.code} 的行为条款: {cause.behavior}")
            article_refs = extract_article_references(cause.behavior)
            logger.debug(f"从行这条款中提取的条文引用: {article_refs}")
            
            for article_ref in article_refs:
                # 查找对应的条文
                for structure in structures:
                    if match_structure(structure, article_ref):
                        logger.debug(f"找到匹配的行为条文: structure_id={structure.id}, article={structure.article}")
                        # 标记为行为条文
                        if structure.id not in structure_roles:
                            structure_roles[structure.id] = []
                        if 'behavior' not in structure_roles[structure.id]:
                            structure_roles[structure.id].append('behavior')
                        
                        # 关联事由到条文
                        if structure.id not in structure_causes:
                            structure_causes[structure.id] = []
                        if cause not in structure_causes[structure.id]:
                            structure_causes[structure.id].append(cause)
    
    
    # 记录详细的角色分配情况
    role_distribution = {'violation': 0, 'punishment': 0, 'behavior': 0}
    for roles in structure_roles.values():
        for role in roles:
            role_distribution[role] += 1
    logger.info(f"角色统计: 违则={role_distribution['violation']}, 罚则={role_distribution['punishment']}, 行为={role_distribution['behavior']}")
    
    # 记录一些关联的事由数量信息用于调试
    if structure_causes:
        related_counts = [len(causes) for causes in structure_causes.values()]
        max_related = max(related_counts) if related_counts else 0
        avg_related = sum(related_counts) / len(related_counts) if related_counts else 0
        logger.info(f"每个条文关联的平均事由数: {avg_related:.2f}, 最大关联数: {max_related}")
    
    return render_template('regulations/detail.html', 
                           regulation=regulation, 
                           structures=structures,
                           causes=causes,
                           current_version=version,
                           all_versions=versions,
                           structure_roles=structure_roles,
                           structure_causes=structure_causes)

# 辅助函数：从条款文本中提取条文引用
def extract_article_references(text):
    if not text:
        return []
    
    references = []
    
    logger.debug(f"开始从文本中提取条文引用: {text}")
    
    # 简单的正则匹配可能不足以处理所有情况，这里只是示例
    # 匹配常见的引用模式，如"第x条"、"第x条第y款"等
    import re
    
    # 匹配"第X条"模式
    pattern1 = r'第(\d+)条'
    matches1 = re.findall(pattern1, text)
    for match in matches1:
        reference = {
            'article': int(match),
            'paragraph': None,
            'item': None
        }
        references.append(reference)
        logger.debug(f"提取到引用: 第{match}条")
    
    # 匹配"第X条第Y款"模式
    pattern2 = r'第(\d+)条第(\d+)款'
    matches2 = re.findall(pattern2, text)
    for match in matches2:
        reference = {
            'article': int(match[0]),
            'paragraph': int(match[1]),
            'item': None
        }
        references.append(reference)
        logger.debug(f"提取到引用: 第{match[0]}条第{match[1]}款")
    
    # 匹配"第X条第Y款第Z项"模式
    pattern3 = r'第(\d+)条第(\d+)款第(\d+)项'
    matches3 = re.findall(pattern3, text)
    for match in matches3:
        reference = {
            'article': int(match[0]),
            'paragraph': int(match[1]),
            'item': int(match[2])
        }
        references.append(reference)
        logger.debug(f"提取到引用: 第{match[0]}条第{match[1]}款第{match[2]}项")
    
    logger.debug(f"提取完成，共找到 {len(references)} 个条文引用")
    return references

# 辅助函数：判断条文是否匹配引用
def match_structure(structure, reference):
    # 匹配条
    if structure.article != reference['article']:
        return False
    
    # 如果引用指定了款，但条文不匹配，则不匹配
    if reference['paragraph'] is not None and structure.paragraph != reference['paragraph']:
        return False
    
    # 如果引用指定了项，但条文不匹配，则不匹配
    if reference['item'] is not None and structure.item != reference['item']:
        return False
    
    logger.debug(f"条文匹配成功: structure_id={structure.id}, article={structure.article}, paragraph={structure.paragraph}, item={structure.item}")
    return True

@regulation_bp.route('/regulations/level/<level>')
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

# 新增统计图表路由
@regulation_bp.route('/regulations/<int:regulation_id>/stats')
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

# 添加辅助函数来获取处罚计数
def get_punishment_count(regulation_id):
    """获取特定法规的处罚总数"""
    return db.session.query(LegalPunishment).\
        join(LegalCause).\
        filter(LegalCause.regulation_id == regulation_id).\
        count()

# 添加处罚计数辅助函数到应用上下文
@regulation_bp.context_processor
def utility_processor():
    return {
        'get_punishment_count': get_punishment_count
    }

#法规编辑
@regulation_bp.route('/regulations/<int:regulation_id>/edit', methods=['GET', 'POST'])
@login_required
def regulation_edit(regulation_id):
    logger.info(f"Received request for regulation_id={regulation_id}")
    regulation = LegalRegulation.query.get(regulation_id)
    if not regulation:
        logger.error(f"Regulation with id={regulation_id} not found")
        abort(404)
    logger.info(f"Found regulation: {regulation.name}")
    # 检查用户是否有权限编辑
    if current_user.role != 'admin':
        flash('您没有权限编辑法规', 'danger')
        return redirect(url_for('regulation_detail', regulation_id=regulation_id))
    
    # 获取法规及其当前版本
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    logger.info(f"Found current_version_id: {regulation.current_version_id}")
    # 获取当前版本ID（从请求参数或使用默认当前版本）
    version_id = request.args.get('version_id', type=int) or regulation.current_version_id
    
    if not version_id:
        # 如果没有版本，创建一个初始版本
        new_version = LegalRegulationVersion(
            regulation=regulation,
            version_number=f"{datetime.now().year}年版",
            revision_date=datetime.now(),
            effective_date=regulation.effective_date or datetime.now(),
            publish_date=regulation.publish_date or datetime.now(),
            status='current',
            changes_summary=f"初始版本"
        )
        db.session.add(new_version)
        db.session.flush()
        regulation.current_version_id = new_version.id
        db.session.commit()
        version_id = new_version.id
    
    # 获取指定版本
    current_version = LegalRegulationVersion.query.get_or_404(version_id)
    
    # 获取该版本的条文和事由
    structures = LegalStructure.query.filter_by(
        regulation_id=regulation_id,
        version_id=current_version.id
    ).all()
    
    causes = LegalCause.query.filter_by(
        regulation_id=regulation_id,
        version_id=current_version.id
    ).all()
    
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
        
        elif form_type == 'version':
            # 处理版本信息的更新
            current_version.version_number = request.form.get('version_number')
            
            # 处理日期字段
            if request.form.get('revision_date'):
                current_version.revision_date = datetime.strptime(request.form.get('revision_date'), '%Y-%m-%d')
            if request.form.get('effective_date'):
                current_version.effective_date = datetime.strptime(request.form.get('effective_date'), '%Y-%m-%d')
            if request.form.get('publish_date'):
                current_version.publish_date = datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d')
            
            current_version.status = request.form.get('status')
            current_version.changes_summary = request.form.get('changes_summary')
            
            # 如果设置为当前版本，更新法规的current_version_id
            if current_version.status == 'current':
                regulation.current_version_id = current_version.id
                regulation.latest_revision_date = current_version.revision_date
                
                # 将其他版本改为非当前
                other_versions = LegalRegulationVersion.query.filter(
                    LegalRegulationVersion.regulation_id == regulation.id,
                    LegalRegulationVersion.id != current_version.id
                ).all()
                for v in other_versions:
                    v.status = 'superseded'
            
            try:
                db.session.commit()
                flash('版本信息已成功更新', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'更新版本失败: {str(e)}', 'danger')
        
        elif form_type == 'structure':
            # 处理条文更新
            structure_id = request.form.get('structure_id')
            structure = LegalStructure.query.get_or_404(structure_id)
            
            # 确保条文属于当前法规和版本
            if structure.regulation_id != regulation.id or structure.version_id != current_version.id:
                flash('无权编辑此条文', 'danger')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
            
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
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id, _anchor='structure-' + structure_id))
            except Exception as e:
                db.session.rollback()
                flash(f'更新条文失败: {str(e)}', 'danger')
        
        elif form_type == 'cause':
            # 处理事由更新
            cause_id = request.form.get('cause_id')
            cause = LegalCause.query.get_or_404(cause_id)
            
            # 确保事由属于当前法规和版本
            if cause.regulation_id != regulation.id or cause.version_id != current_version.id:
                flash('无权编辑此事由', 'danger')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
            
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
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id, _anchor='cause-' + cause_id))
            except Exception as e:
                db.session.rollback()
                flash(f'更新事由失败: {str(e)}', 'danger')
        
        elif form_type == 'new_structure':
            # 创建新条文
            try:
                new_structure = LegalStructure(
                    regulation_id=regulation.id,
                    version_id=current_version.id,
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
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id, _anchor=f'structure-{new_structure.id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'添加条文失败: {str(e)}', 'danger')
        
        elif form_type == 'new_cause':
            # 创建新事由
            try:
                new_cause = LegalCause(
                    regulation_id=regulation.id,
                    version_id=current_version.id,
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
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id, _anchor=f'cause-{new_cause.id}'))
            except Exception as e:
                db.session.rollback()
                flash(f'添加事由失败: {str(e)}', 'danger')
        
        elif form_type == 'delete_structure':
            # 删除条文
            structure_id = request.form.get('structure_id')
            structure = LegalStructure.query.get_or_404(structure_id)
            
            # 确保条文属于当前法规和版本
            if structure.regulation_id != regulation.id or structure.version_id != current_version.id:
                flash('无权删除此条文', 'danger')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
            
            try:
                db.session.delete(structure)
                db.session.commit()
                flash('条文已成功删除', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'删除条文失败: {str(e)}', 'danger')
        
        elif form_type == 'delete_cause':
            # 删除事由
            cause_id = request.form.get('cause_id')
            cause = LegalCause.query.get_or_404(cause_id)
            
            # 确保事由属于当前法规和版本
            if cause.regulation_id != regulation.id or cause.version_id != current_version.id:
                flash('无权删除此事由', 'danger')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
            
            try:
                # 检查相关的处罚数量
                punishment_count = LegalPunishment.query.filter_by(cause_id=cause.id).count()
                
                # 删除相关的处罚信息
                LegalPunishment.query.filter_by(cause_id=cause.id).delete()
                
                # 删除事由
                db.session.delete(cause)
                db.session.commit()
                flash('事由已成功删除', 'success')
                
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
            except Exception as e:
                db.session.rollback()
                flash(f'删除事由失败: {str(e)}', 'danger')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=current_version.id))
        
        # 处理创建新版本
        elif form_type == 'new_version':
            try:
                # 创建新版本
                new_version = LegalRegulationVersion(
                    regulation_id=regulation.id,
                    version_number=request.form.get('version_number'),
                    revision_date=datetime.strptime(request.form.get('revision_date'), '%Y-%m-%d') if request.form.get('revision_date') else datetime.now(),
                    effective_date=datetime.strptime(request.form.get('effective_date'), '%Y-%m-%d') if request.form.get('effective_date') else datetime.now(),
                    publish_date=datetime.strptime(request.form.get('publish_date'), '%Y-%m-%d') if request.form.get('publish_date') else datetime.now(),
                    status=request.form.get('status', 'draft'),
                    changes_summary=request.form.get('changes_summary', '')
                )
                db.session.add(new_version)
                db.session.flush()  # 获取新创建版本的ID
                
                # 如果设置为当前版本，更新法规的current_version_id
                if new_version.status == 'current':
                    regulation.current_version_id = new_version.id
                    regulation.latest_revision_date = new_version.revision_date
                    
                    # 将其他版本改为非当前
                    other_versions = LegalRegulationVersion.query.filter(
                        LegalRegulationVersion.regulation_id == regulation.id,
                        LegalRegulationVersion.id != new_version.id
                    ).all()
                    for v in other_versions:
                        v.status = 'superseded'
                
                # 处理内容复制选项
                copy_option = request.form.get('copy_option')
                if copy_option == 'copy_current':
                    # 复制当前版本的内容到新版本
                    for structure in structures:
                        new_structure = LegalStructure(
                            regulation_id=regulation.id,
                            version_id=new_version.id,
                            article=structure.article,
                            paragraph=structure.paragraph,
                            item=structure.item,
                            section=structure.section,
                            content=structure.content,
                            original_text=structure.original_text
                        )
                        db.session.add(new_structure)
                    
                    for cause in causes:
                        new_cause = LegalCause(
                            regulation_id=regulation.id,
                            version_id=new_version.id,
                            code=cause.code,
                            description=cause.description,
                            violation_type=cause.violation_type,
                            violation_clause=cause.violation_clause,
                            behavior=cause.behavior,
                            illegal_behavior=cause.illegal_behavior,
                            penalty_type=cause.penalty_type,
                            penalty_clause=cause.penalty_clause,
                            severity=cause.severity
                        )
                        db.session.add(new_cause)
                        db.session.flush()  # 获取新事由ID
                        
                        # 复制处罚信息
                        punishments = LegalPunishment.query.filter_by(cause_id=cause.id).all()
                        for punishment in punishments:
                            new_punishment = LegalPunishment(
                                cause_id=new_cause.id,
                                version_id=new_version.id,
                                circumstance=punishment.circumstance,
                                punishment_type=punishment.punishment_type,
                                progressive_punishment=punishment.progressive_punishment,
                                industry=punishment.industry,
                                subject_level=punishment.subject_level,
                                punishment_target=punishment.punishment_target,
                                punishment_details=punishment.punishment_details,
                                additional_notes=punishment.additional_notes
                            )
                            db.session.add(new_punishment)
                
                db.session.commit()
                flash('新版本已成功创建', 'success')
                return redirect(url_for('regulation.regulation_edit', regulation_id=regulation_id, version_id=new_version.id))
            except Exception as e:
                db.session.rollback()
                flash(f'创建新版本失败: {str(e)}', 'danger')

    # 获取所有版本
    all_versions = LegalRegulationVersion.query.filter_by(regulation_id=regulation.id).order_by(LegalRegulationVersion.revision_date.desc()).all()
    
    # 对条文和事由进行排序，以便在界面上更好地显示
    structures = sorted(structures, key=lambda x: (x.article or 0, x.paragraph or 0, x.item or 0, x.section or 0))
    causes = sorted(causes, key=lambda x: x.code)
    
    return render_template('regulations/edit/edit.html', 
                           regulation=regulation,
                           current_version=current_version,
                           all_versions=all_versions,
                           structures=structures,
                           causes=causes,
                           datetime=datetime)  # 传递datetime对象到模板


@regulation_bp.route('/causes/<int:cause_id>/punishments', methods=['GET', 'POST'])
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



# 事由详情
@regulation_bp.route('/causes/<int:cause_id>')
def cause_detail(cause_id):
    cause = LegalCause.query.get_or_404(cause_id)
    regulation = cause.regulation  # 确保提供regulation变量
    punishments = LegalPunishment.query.filter_by(cause_id=cause_id).all()
    
    return render_template('causes/detail.html', 
                           cause=cause, 
                           regulation=regulation,  # 传递regulation变量
                           punishments=punishments)

