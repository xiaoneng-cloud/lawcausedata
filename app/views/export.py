# app/views/export.py
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, Response, request  # 新增导入 request
from flask_login import login_required
from app.models import LegalRegulation, LegalCause, LegalPunishment, LegalRegulationVersion
from app.extensions import db
from sqlalchemy import or_
from datetime import datetime
import pandas as pd
import tempfile
import zipfile
from io import BytesIO, StringIO
import csv

export_bp = Blueprint('export', __name__)

@export_bp.route('/export/<int:regulation_id>', methods=['GET'])
def export_regulation_page(regulation_id):
    print(f"开始处理导出页面请求：regulation_id={regulation_id}")
    try:
        """导出法规数据页面"""
        regulation = LegalRegulation.query.get_or_404(regulation_id)
        
        # 获取该法规的所有版本
        versions = LegalRegulationVersion.query.filter_by(regulation_id=regulation.id).order_by(
            LegalRegulationVersion.revision_date.desc()
        ).all()
        
        # 获取可选字段
        cause_fields = [
            {'id': 'code', 'name': '编号', 'default': True},
            {'id': 'description', 'name': '事由', 'default': True},
            {'id': 'violation_type', 'name': '违则', 'default': True},
            {'id': 'violation_clause', 'name': '违则条款', 'default': True},
            {'id': 'behavior', 'name': '行为', 'default': True},
            {'id': 'illegal_behavior', 'name': '违法行为', 'default': True},
            {'id': 'penalty_type', 'name': '罚则', 'default': True},
            {'id': 'penalty_clause', 'name': '罚则条款', 'default': True},
            {'id': 'severity', 'name': '严重程度', 'default': True}
        ]
        
        punishment_fields = [
            {'id': 'cause_code', 'name': '事由编号', 'default': True},
            {'id': 'cause_description', 'name': '事由', 'default': True},
            {'id': 'circumstance', 'name': '情形', 'default': True},
            {'id': 'punishment_type', 'name': '处罚类型', 'default': True},
            {'id': 'progressive_punishment', 'name': '递进处罚', 'default': True},
            {'id': 'industry', 'name': '行业', 'default': True},
            {'id': 'subject_level', 'name': '主体级别', 'default': True},
            {'id': 'punishment_target', 'name': '处罚对象', 'default': True},
            {'id': 'punishment_details', 'name': '处罚明细', 'default': True},
            {'id': 'additional_notes', 'name': '行政行为', 'default': True}
        ]
        
        # 统计数据量
        current_version_id = regulation.current_version_id
        causes_count = LegalCause.query.filter_by(
            regulation_id=regulation.id, 
            version_id=current_version_id
        ).count()
        
        punishments_count = LegalPunishment.query.join(
            LegalCause, LegalPunishment.cause_id == LegalCause.id
        ).filter(
            LegalCause.regulation_id == regulation.id,
            LegalCause.version_id == current_version_id
        ).count()
        print("准备渲染export_regulation.html模板")
        return render_template('export_regulation.html', 
                            regulation=regulation, 
                            versions=versions,
                            cause_fields=cause_fields,
                            punishment_fields=punishment_fields,
                            causes_count=causes_count,
                            punishments_count=punishments_count)
    except Exception as e:
        print(f"处理导出页面时出错：{str(e)}")
        import traceback
        print(traceback.format_exc())
        # 临时直接返回错误信息而不是重定向
        return f"导出页面错误：{str(e)}"

# 修复后的export_as_excel函数
def export_as_excel(regulation, version, version_condition, export_content, 
                   cause_fields, punishment_fields, filename_base):
    """导出为Excel格式"""
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
    temp_path = temp_file.name
    temp_file.close()
    
    # 使用xlsxwriter引擎创建Excel文件
    writer = pd.ExcelWriter(temp_path, engine='xlsxwriter')
    
    try:
        # 导出事由表
        if 'causes' in export_content and cause_fields:
            # 构建字段映射
            field_map = {
                'code': '编号',
                'description': '事由',
                'violation_type': '违则',
                'violation_clause': '违则条款',
                'behavior': '行为',
                'illegal_behavior': '违法行为',
                'penalty_type': '罚则',
                'penalty_clause': '罚则条款',
                'severity': '严重程度'
            }
            
            # 只选择需要的字段
            selected_fields = {field: field_map[field] for field in cause_fields if field in field_map}
            
            # 分批查询数据，避免一次性加载过多数据
            BATCH_SIZE = 500
            causes_data = []
            query = LegalCause.query.filter(
                LegalCause.regulation_id == regulation.id,
                version_condition
            )
            
            # 获取总数
            total_count = query.count()
            
            # 分批处理
            for offset in range(0, total_count, BATCH_SIZE):
                batch = query.limit(BATCH_SIZE).offset(offset).all()
                
                for cause in batch:
                    cause_data = {}
                    for field_id, field_name in selected_fields.items():
                        cause_data[field_name] = getattr(cause, field_id, '')
                    causes_data.append(cause_data)
            
            if causes_data:
                df_causes = pd.DataFrame(causes_data)
                df_causes.to_excel(writer, sheet_name='事由表', index=False)
                
                # 获取xlsxwriter工作簿和工作表对象，用于格式化
                workbook = writer.book
                worksheet = writer.sheets['事由表']
                
                # 设置列宽
                for i, column in enumerate(df_causes.columns):
                    column_width = max(df_causes[column].astype(str).map(len).max(), len(column)) + 2
                    worksheet.set_column(i, i, column_width)
        
        # 导出处罚表
        if 'punishments' in export_content and punishment_fields:
            # 构建字段映射
            field_map = {
                'cause_code': '事由编号',
                'cause_description': '事由',
                'circumstance': '情形',
                'punishment_type': '处罚类型',
                'progressive_punishment': '递进处罚',
                'industry': '行业',
                'subject_level': '主体级别',
                'punishment_target': '处罚对象',
                'punishment_details': '处罚明细',
                'additional_notes': '行政行为'
            }
            
            # 只选择需要的字段
            selected_fields = {field: field_map[field] for field in punishment_fields if field in field_map}
            
            # 分批查询处罚数据
            BATCH_SIZE = 500
            punishments_data = []
            
            query = db.session.query(
                LegalPunishment, LegalCause
            ).join(
                LegalCause, LegalPunishment.cause_id == LegalCause.id
            ).filter(
                LegalCause.regulation_id == regulation.id,
                version_condition
            )
            
            # 获取总数
            total_count = query.count()
            
            # 分批处理
            for offset in range(0, total_count, BATCH_SIZE):
                batch = query.limit(BATCH_SIZE).offset(offset).all()
                
                for punishment, cause in batch:
                    punishment_data = {}
                    for field_id, field_name in selected_fields.items():
                        if field_id == 'cause_code':
                            punishment_data[field_name] = cause.code
                        elif field_id == 'cause_description':
                            punishment_data[field_name] = cause.description
                        else:
                            punishment_data[field_name] = getattr(punishment, field_id, '')
                    punishments_data.append(punishment_data)
            
            if punishments_data:
                df_punishments = pd.DataFrame(punishments_data)
                df_punishments.to_excel(writer, sheet_name='处罚表', index=False)
                
                # 获取xlsxwriter工作簿和工作表对象，用于格式化
                workbook = writer.book
                worksheet = writer.sheets['处罚表']
                
                # 设置列宽
                for i, column in enumerate(df_punishments.columns):
                    column_width = max(df_punishments[column].astype(str).map(len).max(), len(column)) + 2
                    worksheet.set_column(i, i, column_width)
        
        # 保存文件
        writer.close()
        
        # 发送文件
        return send_file(
            temp_path,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f"{filename_base}.xlsx"
        )
    
    except Exception as e:
        # 如果发生错误，确保关闭writer并删除临时文件
        try:
            writer.close()
        except:
            pass
        
        import os
        try:
            os.unlink(temp_path)
        except:
            pass
        
        flash(f'导出Excel失败: {str(e)}', 'error')
        return redirect(url_for('regulation_detail', regulation_id=regulation.id))

# 修复后的export_as_csv函数
def export_as_csv(regulation, version, version_condition, export_content, 
                 cause_fields, punishment_fields, filename_base):
    """导出为CSV格式"""
    # 如果要导出多个表，创建一个ZIP文件
    if len(export_content) > 1:
        import zipfile
        memory_file = BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w') as zf:
            # 导出事由表
            if 'causes' in export_content and cause_fields:
                # 构建字段映射
                field_map = {
                    'code': '编号',
                    'description': '事由',
                    'violation_type': '违则',
                    'violation_clause': '违则条款',
                    'behavior': '行为',
                    'illegal_behavior': '违法行为',
                    'penalty_type': '罚则',
                    'penalty_clause': '罚则条款',
                    'severity': '严重程度'
                }
                
                # 只选择需要的字段
                selected_fields = {field: field_map[field] for field in cause_fields if field in field_map}
                
                # 准备CSV文件
                csv_output = StringIO()
                csv_writer = csv.writer(csv_output)
                
                # 写入表头
                csv_writer.writerow(selected_fields.values())
                
                # 分批查询数据
                BATCH_SIZE = 500
                query = LegalCause.query.filter(
                    LegalCause.regulation_id == regulation.id,
                    version_condition
                )
                
                # 获取总数
                total_count = query.count()
                
                # 分批处理
                for offset in range(0, total_count, BATCH_SIZE):
                    batch = query.limit(BATCH_SIZE).offset(offset).all()
                    
                    for cause in batch:
                        row = []
                        for field_id in selected_fields.keys():
                            row.append(getattr(cause, field_id, ''))
                        csv_writer.writerow(row)
                
                # 添加到ZIP文件
                zf.writestr('事由表.csv', csv_output.getvalue().encode('utf-8-sig'))  # 使用BOM标记以支持Excel中文显示
            
            # 导出处罚表
            if 'punishments' in export_content and punishment_fields:
                # 构建字段映射
                field_map = {
                    'cause_code': '事由编号',
                    'cause_description': '事由',
                    'circumstance': '情形',
                    'punishment_type': '处罚类型',
                    'progressive_punishment': '递进处罚',
                    'industry': '行业',
                    'subject_level': '主体级别',
                    'punishment_target': '处罚对象',
                    'punishment_details': '处罚明细',
                    'additional_notes': '行政行为'
                }
                
                # 只选择需要的字段
                selected_fields = {field: field_map[field] for field in punishment_fields if field in field_map}
                
                # 准备CSV文件
                csv_output = StringIO()
                csv_writer = csv.writer(csv_output)
                
                # 写入表头
                csv_writer.writerow(selected_fields.values())
                
                # 分批查询处罚数据
                BATCH_SIZE = 500
                query = db.session.query(
                    LegalPunishment, LegalCause
                ).join(
                    LegalCause, LegalPunishment.cause_id == LegalCause.id
                ).filter(
                    LegalCause.regulation_id == regulation.id,
                    version_condition
                )
                
                # 获取总数
                total_count = query.count()
                
                # 分批处理
                for offset in range(0, total_count, BATCH_SIZE):
                    batch = query.limit(BATCH_SIZE).offset(offset).all()
                    
                    for punishment, cause in batch:
                        row = []
                        for field_id in selected_fields.keys():
                            if field_id == 'cause_code':
                                row.append(cause.code)
                            elif field_id == 'cause_description':
                                row.append(cause.description)
                            else:
                                row.append(getattr(punishment, field_id, ''))
                        csv_writer.writerow(row)
                
                # 添加到ZIP文件
                zf.writestr('处罚表.csv', csv_output.getvalue().encode('utf-8-sig'))
        
        # 准备返回响应
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{filename_base}.zip"
        )
    
    # 如果只导出一个表，直接返回CSV文件
    csv_output = StringIO()
    csv_writer = csv.writer(csv_output)
    
    # 导出事由表
    if 'causes' in export_content and cause_fields:
        # 构建字段映射
        field_map = {
            'code': '编号',
            'description': '事由',
            'violation_type': '违则',
            'violation_clause': '违则条款',
            'behavior': '行为',
            'illegal_behavior': '违法行为',
            'penalty_type': '罚则',
            'penalty_clause': '罚则条款',
            'severity': '严重程度'
        }
        
        # 只选择需要的字段
        selected_fields = {field: field_map[field] for field in cause_fields if field in field_map}
        
        # 写入表头
        csv_writer.writerow(selected_fields.values())
        
        # 分批查询数据
        BATCH_SIZE = 500
        query = LegalCause.query.filter(
            LegalCause.regulation_id == regulation.id,
            version_condition
        )
        
        # 获取总数
        total_count = query.count()
        
        # 分批处理
        for offset in range(0, total_count, BATCH_SIZE):
            batch = query.limit(BATCH_SIZE).offset(offset).all()
            
            for cause in batch:
                row = []
                for field_id in selected_fields.keys():
                    row.append(getattr(cause, field_id, ''))
                csv_writer.writerow(row)
        
        # 返回CSV文件
        output = csv_output.getvalue().encode('utf-8-sig')
        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename={filename_base}_事由.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    
    # 导出处罚表
    elif 'punishments' in export_content and punishment_fields:
        # 构建字段映射
        field_map = {
            'cause_code': '事由编号',
            'cause_description': '事由',
            'circumstance': '情形',
            'punishment_type': '处罚类型',
            'progressive_punishment': '递进处罚',
            'industry': '行业',
            'subject_level': '主体级别',
            'punishment_target': '处罚对象',
            'punishment_details': '处罚明细',
            'additional_notes': '行政行为'
        }
        
        # 只选择需要的字段
        selected_fields = {field: field_map[field] for field in punishment_fields if field in field_map}
        
        # 写入表头
        csv_writer.writerow(selected_fields.values())
        
        # 分批查询处罚数据
        BATCH_SIZE = 500
        query = db.session.query(
            LegalPunishment, LegalCause
        ).join(
            LegalCause, LegalPunishment.cause_id == LegalCause.id
        ).filter(
            LegalCause.regulation_id == regulation.id,
            version_condition
        )
        
        # 获取总数
        total_count = query.count()
        
        # 分批处理
        for offset in range(0, total_count, BATCH_SIZE):
            batch = query.limit(BATCH_SIZE).offset(offset).all()
            
            for punishment, cause in batch:
                row = []
                for field_id in selected_fields.keys():
                    if field_id == 'cause_code':
                        row.append(cause.code)
                    elif field_id == 'cause_description':
                        row.append(cause.description)
                    else:
                        row.append(getattr(punishment, field_id, ''))
                csv_writer.writerow(row)
        
        # 返回CSV文件
        output = csv_output.getvalue().encode('utf-8-sig')
        return Response(
            output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment;filename={filename_base}_处罚.csv',
                'Content-Type': 'text/csv; charset=utf-8-sig'
            }
        )
    
    # 默认返回到详情页
    flash('未选择导出内容', 'error')
    return redirect(url_for('regulation_detail', regulation_id=regulation.id))

@export_bp.route('/export/data', methods=['POST'])
def export_regulation_data():
    """处理导出法规数据的请求"""
    print("开始处理导出请求")
    print(f"表单数据: {request.form}")
    
    regulation_id = request.form.get('regulation_id', type=int)
    version_id = request.form.get('version_id', type=int)
    export_format = request.form.get('format', 'excel')
    export_content = request.form.getlist('content')
    
    print(f"regulation_id: {regulation_id}, version_id: {version_id}")
    print(f"export_format: {export_format}, export_content: {export_content}")
    
    # 获取选择的字段
    cause_fields = request.form.getlist('cause_fields')
    punishment_fields = request.form.getlist('punishment_fields')
    
    if not regulation_id:
        flash('未指定法规ID', 'error')
        return redirect(url_for('regulation.search_regulations'))
    
    # 获取法规和版本信息
    regulation = LegalRegulation.query.get_or_404(regulation_id)
    version = None
    
    if version_id:
        version = LegalRegulationVersion.query.get_or_404(version_id)
        if version.regulation_id != regulation.id:
            flash('版本与法规不匹配', 'error')
            return redirect(url_for('regulation_detail', regulation_id=regulation_id))
    else:
        # 如果没有指定版本，使用当前版本
        if regulation.current_version_id:
            version = LegalRegulationVersion.query.get(regulation.current_version_id)
    
    # 准备版本条件
    version_condition = None
    if version:
        version_condition = LegalCause.version_id == version.id
    else:
        # 如果没有版本信息，则导出所有数据
        version_condition = or_(LegalCause.version_id.is_(None), LegalCause.version_id != None)
    
    # 准备文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    version_str = f"_v{version.version_number}" if version else ""
    filename_base = f"{regulation.name}{version_str}_{timestamp}"
    
    # 根据导出格式选择不同的处理方式
    if export_format == 'excel':
        return export_as_excel(regulation, version, version_condition, 
                              export_content, cause_fields, punishment_fields,
                              filename_base)
    elif export_format == 'csv':
        return export_as_csv(regulation, version, version_condition, 
                            export_content, cause_fields, punishment_fields,
                            filename_base)
    
    # 默认返回到详情页
    flash('导出格式不支持', 'error')
    return redirect(url_for('regulation_detail', regulation_id=regulation_id))