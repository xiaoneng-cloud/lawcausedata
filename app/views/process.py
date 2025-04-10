# app/views/process.py
from flask import Blueprint, jsonify, request, current_app, render_template
from flask_login import login_required, current_user
from app.models import LegalRegulation, LegalStructure, LegalCause, LegalPunishment
from app.extensions import db
import os
import tempfile
import pandas as pd
import uuid
import logging
import sys
from datetime import datetime
from flask import session

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

process_bp = Blueprint('process', __name__, url_prefix='/process')

# 存储处理任务状态
processing_tasks = {}

@process_bp.route('/run/<int:regulation_id>/<step_name>', methods=['POST'])
@login_required
def run_processing_step(regulation_id, step_name):
    if current_user.role != 'admin':
        return jsonify(success=False, message='无权执行此操作'), 403
    
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    task_id = str(uuid.uuid4())
    
    processing_tasks[task_id] = {
        'status': 'pending',
        'step': step_name,
        'regulation_id': regulation_id,
        'start_time': datetime.now().timestamp(),
        'message': '任务准备中'
    }
    
    try:
        processing_tasks[task_id]['status'] = 'running'
        processing_tasks[task_id]['message'] = '正在导出法规数据...'
        
        temp_dir = tempfile.mkdtemp()
        logger.info(f"创建临时目录: {temp_dir}")
        
        input_file = os.path.join(temp_dir, f"regulation_{regulation_id}.xlsx")
        output_file = os.path.join(temp_dir, f"regulation_{regulation_id}_processed.xlsx")
        ex_output_file = os.path.join(temp_dir, f"regulation_{regulation_id}_processed_ex.xlsx")
        output_txt_path = os.path.join(temp_dir, f"{regulation.name}.txt")
        ai_output_file = os.path.join(temp_dir, f"regulation_{regulation_id}_processed_ai.xlsx")
        cause_file = os.path.join(temp_dir, f"regulation_{regulation_id}_causes.xlsx")
        punish_file = os.path.join(temp_dir, f"regulation_{regulation_id}_punishments.xlsx")
        
        processing_tasks[task_id]['message'] = '正在导出法规数据到Excel...'
        logger.info(f"开始导出法规 {regulation_id} 到 {input_file}")
        structure_count = export_regulation_to_excel(regulation, input_file)
        logger.info(f"导出完成，共 {structure_count} 条记录")
        
        processing_tasks[task_id]['message'] = '正在执行数据处理...'
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        
        if step_name == 'format_num':
            logger.info(f"开始处理脚本 format_num")
            from process.law_format_num import process_legal_document
            process_legal_document(input_file, output_file)
            
            if os.path.exists(output_file):
                logger.info(f"处理后第一步文件生成成功: {output_file}")
                session['last_processed_file'] = output_file  # 现在 session 已定义
                processing_tasks[task_id]['output_file'] = output_file
            else:
                logger.error(f"处理后第一步文件不存在: {output_file}")
                processing_tasks[task_id]['status'] = 'error'
                processing_tasks[task_id]['message'] = '处理失败：输出文件未生成'
                return jsonify(success=False, message='处理失败：输出文件未生成')

            logger.info(f"开始处理脚本 format_num_ex")
            last_file = session.get('last_processed_file')
            if last_file is None or not os.path.exists(last_file):
                logger.error("无法找到上一步的输出文件")
                processing_tasks[task_id]['status'] = 'error'
                processing_tasks[task_id]['message'] = '处理失败：无法找到上一步的输出文件'
                return jsonify(success=False, message='处理失败：无法找到上一步的输出文件'), 500

            rel_file = os.path.join(current_app.root_path, 'static', 'data', 'rel.xlsx')
            if not os.path.exists(rel_file):
                logger.warning(f"关联文件不存在: {rel_file}，创建空文件")
                os.makedirs(os.path.dirname(rel_file), exist_ok=True)
                pd.DataFrame().to_excel(rel_file, index=False)
            
            from process.law_format_num_ex import process_legal_document as process_legal_document_ex
            process_legal_document_ex(last_file, ex_output_file, rel_file)

            from process.add_evidence import update_excel
            update_excel(ex_output_file)

            from process.process_complex import process_excel
            process_excel(ex_output_file)
            
            from process.add_vio_ass import update_excel as update_excel_vio_ass
            from process.add_vio_ass import load_pretrained_model
            model = load_pretrained_model()
            update_excel_vio_ass(ex_output_file, model)

            
            from process.process_penalty_new import process_law_penalty_new
            process_law_penalty_new(ex_output_file)

            from process.process_penalty_43 import process_law_penalty
            process_law_penalty(ex_output_file)

            from process.process_penalty_6 import process_law_penalty as process_law_penalty_ex
            process_law_penalty_ex(ex_output_file)

            from process.export_cause import main as main_export_cause
            main_export_cause(ex_output_file,output_txt_path)

            from process.get_coze_ai_message_ex import main as main_get_coze_ai_message_ex
            #main_get_coze_ai_message_ex(output_txt_path,ai_output_file)

            from process.format_law_result import update_law_result
            #update_law_result(ai_output_file,ex_output_file,cause_file)

            from process.get_coze_discretion import main as main_get_coze_discretion
            #main_get_coze_discretion(ai_output_file,ex_output_file,cause_file,punish_file)

            if os.path.exists(ai_output_file):
                logger.info(f"处理第二步后文件生成成功: {ai_output_file}")
                session['last_processed_file'] = ai_output_file
                processing_tasks[task_id]['output_file'] = ai_output_file
            else:
                logger.error(f"处理第二步后文件不存在: {ai_output_file}")
                processing_tasks[task_id]['status'] = 'error'
                processing_tasks[task_id]['message'] = '处理失败：输出文件未生成'
                return jsonify(success=False, message='处理失败：输出文件未生成')
        
        # 更新任务状态
        processing_tasks[task_id]['status'] = 'completed'
        processing_tasks[task_id]['message'] = '处理完成'
        processing_tasks[task_id]['end_time'] = datetime.now().timestamp()
        
    except Exception as e:
        processing_tasks[task_id]['status'] = 'error'
        processing_tasks[task_id]['message'] = f'处理错误: {str(e)}'
        import traceback
        processing_tasks[task_id]['traceback'] = traceback.format_exc()
        logger.error(f"处理任务出错: {traceback.format_exc()}")
        return jsonify(success=False, message=f'处理错误: {str(e)}'), 500
    
    return jsonify(success=True, task_id=task_id)

@process_bp.route('/status/<task_id>', methods=['GET'])
@login_required
def get_task_status(task_id):
    if task_id not in processing_tasks:
        return jsonify(success=False, message='任务不存在'), 404
    
    return jsonify(success=True, task=processing_tasks[task_id])

def export_regulation_to_excel(regulation, output_path):
    """将法规数据导出到Excel"""
    with current_app.app_context():
        # 获取法规条文
        structures = LegalStructure.query.filter_by(regulation_id=regulation.id).all()
        
        # 准备DataFrame数据
        data = []
        for structure in structures:
            row = {
                '条': structure.article,
                '款': structure.paragraph,
                '项': structure.item,
                '目': structure.section,
                '内容': structure.content,
                '罚则': 0  # 默认值
            }
            data.append(row)
        
        # 标记罚则条款
        causes = LegalCause.query.filter_by(regulation_id=regulation.id).all()
        for cause in causes:
            # 对于每个处罚事由，尝试找到对应的法规条款
            punishments = LegalPunishment.query.filter_by(cause_id=cause.id).all()
            if punishments:
                # 如果有处罚信息，尝试解析条款引用
                import re
                ref_matches = []
                if cause.penalty_clause:
                    ref_matches = re.findall(r'第(\d+)条第(\d+)款', cause.penalty_clause)
                
                for tiao, kuan in ref_matches:
                    for row in data:
                        if row['条'] == int(tiao) and row['款'] == int(kuan):
                            row['罚则'] = 1
        
        # 创建DataFrame并导出
        df = pd.DataFrame(data)
        
        # 如果数据为空，创建一个带有必要列的空DataFrame
        if len(data) == 0:
            df = pd.DataFrame(columns=['条', '款', '项', '目', '内容', '罚则'])
        
        # 确保所有列都存在
        for col in ['条', '款', '项', '目', '内容', '罚则']:
            if col not in df.columns:
                df[col] = None
        
        # 生成sheet名称
        sheet_name = f"{regulation.name}"
        # 导出到Excel，设置 sheet 名称为法律法规的名称加上版本的年
        df.to_excel(output_path, index=False, sheet_name=sheet_name)

def import_processed_data(regulation, input_path):
    """从处理后的Excel导入数据回数据库"""
    with current_app.app_context():
        # 读取处理后的数据
        df = pd.read_excel(input_path)
        
        # 获取现有条文
        existing_structures = LegalStructure.query.filter_by(regulation_id=regulation.id).all()
        
        # 创建映射以快速查找
        structure_map = {}
        for structure in existing_structures:
            key = (
                structure.article if structure.article is not None else 0,
                structure.paragraph if structure.paragraph is not None else 0,
                structure.item if structure.item is not None else 0,
                structure.section if structure.section is not None else 0
            )
            structure_map[key] = structure
        
        # 更新条文内容
        for _, row in df.iterrows():
            article = int(row['条']) if pd.notna(row['条']) else None
            paragraph = int(row['款']) if pd.notna(row['款']) else None
            item = int(row['项']) if pd.notna(row['项']) else None
            section = int(row['目']) if pd.notna(row['目']) else None
            content = row['内容'] if pd.notna(row['内容']) else ""
            
            key = (
                article if article is not None else 0,
                paragraph if paragraph is not None else 0,
                item if item is not None else 0,
                section if section is not None else 0
            )
            
            if key in structure_map:
                # 更新现有条文
                structure = structure_map[key]
                structure.content = content
            else:
                # 创建新条文
                new_structure = LegalStructure(
                    regulation_id=regulation.id,
                    article=article,
                    paragraph=paragraph,
                    item=item,
                    section=section,
                    content=content
                )
                db.session.add(new_structure)
    
    # 提交更改
    db.session.commit()