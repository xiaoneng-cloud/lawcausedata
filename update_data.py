"""
法律法规数据更新脚本
实现功能：
1. 从三个Excel文件读取最新数据
2. 当遇到同名法规时，删除旧数据并导入新数据
3. 保留新增的法规数据
"""
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
from app import app, db
from models import (
    LegalRegulation, 
    LegalStructure, 
    LegalCause, 
    LegalPunishment
)
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    filename=f'law_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def process_regulation_data(sheet_name, xls_structure):
    """处理法规基本数据，返回新的法规对象"""
    try:
        # 尝试获取第一行数据，用于提取法规基本信息
        df_meta = pd.read_excel(xls_structure, sheet_name=sheet_name, nrows=1)
        
        # 构建法规基本信息
        regulation_data = {
            'name': sheet_name,
            # 如果Excel中包含这些列，则提取它们的值
            'issued_by': df_meta.get('发布部门', [''])[0] if '发布部门' in df_meta else '',
            'document_number': df_meta.get('发布文号', [''])[0] if '发布文号' in df_meta else '',
            'hierarchy_level': df_meta.get('效力位阶', [''])[0] if '效力位阶' in df_meta else '',
            'industry_category': df_meta.get('行业类别', [''])[0] if '行业类别' in df_meta else '',
            'validity': df_meta.get('有效性', ['现行有效'])[0] if '有效性' in df_meta else '现行有效',
            'status': 'active'
        }
        
        # 处理日期字段
        if '发布日期' in df_meta:
            issued_date = df_meta['发布日期'][0]
            if pd.notna(issued_date):
                if isinstance(issued_date, str):
                    try:
                        regulation_data['issued_date'] = datetime.strptime(issued_date, '%Y-%m-%d')
                    except:
                        pass
                elif isinstance(issued_date, datetime):
                    regulation_data['issued_date'] = issued_date
        
        if '生效日期' in df_meta:
            effective_date = df_meta['生效日期'][0]
            if pd.notna(effective_date):
                if isinstance(effective_date, str):
                    try:
                        regulation_data['effective_date'] = datetime.strptime(effective_date, '%Y-%m-%d')
                    except:
                        pass
                elif isinstance(effective_date, datetime):
                    regulation_data['effective_date'] = effective_date
        
        return regulation_data
    except Exception as e:
        logger.error(f"处理法规 {sheet_name} 基本数据时出错: {str(e)}")
        # 返回只包含名称的基本信息
        return {'name': sheet_name, 'status': 'active'}

def import_punishments(xls_punish, regulation, cause_dict):
    """
    导入处罚信息
    :param xls_punish: Excel文件
    :param regulation: 当前法规
    :param cause_dict: 事由字典，用于快速查找对应事由
    """
    try:
        # 读取数据
        df_punish = pd.read_excel(xls_punish, sheet_name=regulation.name)
        
        # 处理处罚信息
        for _, row in df_punish.iterrows():
            # 使用编号找到对应的事由
            cause_code = str(row['编号']) if pd.notna(row.get('编号', None)) else None
            if not cause_code or cause_code not in cause_dict:
                logger.warning(f"法规 {regulation.name}: 未找到编号为 {cause_code} 的事由")
                continue
            
            cause = cause_dict[cause_code]
            
            # 创建处罚记录
            punishment = LegalPunishment(
                cause=cause,
                circumstance=str(row['情形']) if pd.notna(row.get('情形', None)) else None,
                punishment_type=str(row['处罚类型']) if pd.notna(row.get('处罚类型', None)) else None,
                progressive_punishment=str(row['递进处罚']) if pd.notna(row.get('递进处罚', None)) else None,
                industry=str(row['行业']) if pd.notna(row.get('行业', None)) else None,
                subject_level=str(row['主体级别']) if pd.notna(row.get('主体级别', None)) else None,
                punishment_target=str(row['处罚对象']) if pd.notna(row.get('处罚对象', None)) else None,
                punishment_details=str(row['处罚明细']) if pd.notna(row.get('处罚明细', None)) else None,
                additional_notes=str(row['补充说明']) if pd.notna(row.get('补充说明', None)) else None
            )
            
            db.session.add(punishment)
        
        # 提交处罚信息
        db.session.commit()
        logger.info(f"成功导入法规 {regulation.name} 的处罚信息")
    except Exception as e:
        db.session.rollback()
        logger.error(f"导入法规 {regulation.name} 的处罚信息时出错: {str(e)}")

def delete_regulation_cascade(regulation_name):
    """
    级联删除法规及其相关数据
    :param regulation_name: 法规名称
    :return: 成功删除返回True，否则返回False
    """
    try:
        # 查找法规
        regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
        if not regulation:
            return False
        
        # 删除法规（级联删除会自动删除相关的结构、事由和处罚）
        db.session.delete(regulation)
        db.session.commit()
        logger.info(f"成功删除法规: {regulation_name}")
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"删除法规 {regulation_name} 时出错: {str(e)}")
        return False

def update_legal_data(structure_file, cause_file, punish_file):
    """
    更新法律法规数据
    :param structure_file: 法规结构Excel文件路径
    :param cause_file: 法规事由Excel文件路径
    :param punish_file: 法规处罚Excel文件路径
    """
    try:
        # 读取文件
        xls_structure = pd.ExcelFile(structure_file)
        xls_cause = pd.ExcelFile(cause_file)
        xls_punish = pd.ExcelFile(punish_file)
        
        # 获取所有法规名称（从结构Excel的sheet名称获取）
        regulation_names = xls_structure.sheet_names
        logger.info(f"开始更新 {len(regulation_names)} 个法规")
        
        # 确保处理顺序：先法规，再事由，最后处罚
        for sheet_name in regulation_names:
            try:
                # 检查是否存在同名法规
                existing_regulation = LegalRegulation.query.filter_by(name=sheet_name).first()
                if existing_regulation:
                    logger.info(f"发现同名法规: {sheet_name}，准备删除旧数据")
                    # 删除现有法规及关联数据
                    delete_regulation_cascade(sheet_name)
                
                # 获取法规基本信息
                regulation_data = process_regulation_data(sheet_name, xls_structure)
                
                # 创建新法规
                regulation = LegalRegulation(**regulation_data)
                db.session.add(regulation)
                db.session.flush()  # 获取regulation.id
                
                # 处理法规条文
                df_structure = pd.read_excel(structure_file, sheet_name=sheet_name)
                structure_count = 0
                for _, row in df_structure.iterrows():
                    try:
                        structure = LegalStructure(
                            regulation=regulation,
                            article=int(row['条']) if pd.notna(row.get('条', None)) else None,
                            paragraph=int(row['款']) if pd.notna(row.get('款', None)) else None,
                            item=int(row['项']) if pd.notna(row.get('项', None)) else None,
                            section=int(row['目']) if pd.notna(row.get('目', None)) else None,
                            content=str(row['内容']) if pd.notna(row.get('内容', None)) else '',
                            original_text=str(row['原条款']) if pd.notna(row.get('原条款', None)) else None
                        )
                        db.session.add(structure)
                        structure_count += 1
                    except Exception as e:
                        logger.warning(f"处理法规 {sheet_name} 的条文时出错: {str(e)}")
                
                # 处理事由，并创建事由字典以便快速查找
                cause_dict = {}
                if sheet_name in xls_cause.sheet_names:
                    df_cause = pd.read_excel(cause_file, sheet_name=sheet_name)
                    cause_count = 0
                    for _, row in df_cause.iterrows():
                        try:
                            cause = LegalCause(
                                regulation=regulation,
                                code=str(row['编号']) if pd.notna(row.get('编号', None)) else '',
                                description=str(row['事由']) if pd.notna(row.get('事由', None)) else '',
                                violation_type=str(row['违则']) if pd.notna(row.get('违则', None)) else None,
                                violation_clause=str(row['违则条款']) if pd.notna(row.get('违则条款', None)) else None,
                                behavior=str(row['行为']) if pd.notna(row.get('行为', None)) else None,
                                illegal_behavior=str(row['违法行为']) if pd.notna(row.get('违法行为', None)) else None,
                                severity='一般'  # 默认设置
                            )
                            db.session.add(cause)
                            cause_dict[cause.code] = cause
                            cause_count += 1
                        except Exception as e:
                            logger.warning(f"处理法规 {sheet_name} 的事由时出错: {str(e)}")
                else:
                    logger.warning(f"事由Excel中不存在法规 {sheet_name} 的sheet")
                
                # 提交法规、条文和事由
                db.session.commit()
                logger.info(f"成功导入法规 {sheet_name}，包含 {structure_count} 条条文和 {len(cause_dict)} 条事由")
                
                # 处理处罚
                if sheet_name in xls_punish.sheet_names:
                    import_punishments(xls_punish, regulation, cause_dict)
                else:
                    logger.warning(f"处罚Excel中不存在法规 {sheet_name} 的sheet")
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"处理法规 {sheet_name} 时出错: {str(e)}")
    
    except Exception as e:
        logger.error(f"更新法律法规数据时出错: {str(e)}")
        raise

def main():
    """主函数"""
    structure_file = 'data/law_structure.xlsx'
    cause_file = 'data/law_cause.xlsx'
    punish_file = 'data/law_punish.xlsx'
    
    logger.info("开始更新法律法规数据")
    
    with app.app_context():
        try:
            update_legal_data(structure_file, cause_file, punish_file)
            logger.info("法律法规数据更新完成")
        except Exception as e:
            logger.error(f"数据更新过程中出错: {str(e)}")
            print(f"错误: {str(e)}")
            return 1
    
    print("数据更新成功！详细信息请查看日志文件。")
    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())