"""
法律法规数据更新脚本
实现功能：
1. 从Excel文件读取最新数据
2. 支持单独导入法规基础信息、条文、事由和处罚信息
3. 支持按施行日期自动管理法规版本
4. 根据sheet名称中的年份（如"中华人民共和国统计法（2024）"中的2024）确认版本
5. 保留旧数据并与旧版本关联
6. 版本排序以施行时间为准
"""
import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

# 创建Flask应用上下文
from app import create_app
from app.extensions import db
from app.models.regulation import LegalRegulation, LegalRegulationVersion, LegalStructure, LegalCause, LegalPunishment

import logging
from datetime import datetime
import json
import re

# 配置日志
logging.basicConfig(
    filename=f'law_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def import_regulations_info(info_file):
    try:
        df_info = pd.read_excel(info_file)
        logger.info(f"从Excel中读取了 {len(df_info)} 条法规信息")
        count = 0
        for _, row in df_info.iterrows():
            name = row.get('法规名称', None)
            if pd.isna(name) or not name:
                continue
            regulation_data = {
                'name': str(name),
                'issuing_authority': str(row.get('制定机关', '')) if pd.notna(row.get('制定机关', None)) else '',
                'hierarchy_level': str(row.get('法律效力位阶', '')) if pd.notna(row.get('法律效力位阶', None)) else '',
                'validity_status': str(row.get('时效性', '有效')) if pd.notna(row.get('时效性', None)) else '有效',
                'province': str(row.get('省份', '')) if pd.notna(row.get('省份', None)) else '',
                'city': str(row.get('城市', '')) if pd.notna(row.get('城市', None)) else '',
            }
            date_fields = {'公布日期': 'publish_date', '施行日期': 'effective_date'}
            for excel_field, model_field in date_fields.items():
                if excel_field in row and pd.notna(row[excel_field]):
                    date_value = row[excel_field]
                    if isinstance(date_value, str):
                        try:
                            regulation_data[model_field] = datetime.strptime(date_value, '%Y年%m月%d日')
                        except:
                            try:
                                regulation_data[model_field] = datetime.strptime(date_value, '%Y-%m-%d')
                            except:
                                pass
                    elif isinstance(date_value, datetime):
                        regulation_data[model_field] = date_value
            if 'effective_date' not in regulation_data or not regulation_data['effective_date']:
                logger.warning(f"法规 {name} 未提供施行日期，使用当前日期替代")
                regulation_data['effective_date'] = datetime.now()
            
            existing_regulation = LegalRegulation.query.filter_by(name=name).first()
            current_effective_date = regulation_data['effective_date']
            version_year = current_effective_date.year
            
            if existing_regulation:
                logger.info(f"发现同名法规: {name}，准备更新")
                # 如果已有最初制定日期，比较并取最早的
                if existing_regulation.original_enactment_date:
                    existing_regulation.original_enactment_date = min(
                        existing_regulation.original_enactment_date,
                        current_effective_date
                    )
                else:
                    existing_regulation.original_enactment_date = current_effective_date
                # 更新其他字段
                for key, value in regulation_data.items():
                    if key not in ['id', 'original_enactment_date']:
                        setattr(existing_regulation, key, value)
                new_version = get_or_create_version(existing_regulation, version_year)
            else:
                regulation_data['original_enactment_date'] = current_effective_date
                regulation_data['latest_revision_date'] = current_effective_date
                new_regulation = LegalRegulation(**regulation_data)
                db.session.add(new_regulation)
                db.session.flush()
                initial_version = get_or_create_version(new_regulation, version_year)
                new_regulation.current_version_id = initial_version.id
            
            count += 1
            if count % 100 == 0:
                db.session.commit()
                logger.info(f"已处理 {count} 条法规基础信息")
        
        db.session.commit()
        logger.info(f"成功导入 {count} 条法规基础信息")
        return count
    except Exception as e:
        db.session.rollback()
        logger.error(f"导入法规基础信息时出错: {str(e)}")
        raise

def get_version_from_sheet_name(sheet_name):
    """从sheet名称中提取年份作为版本，支持全角和半角括号"""
    logger.debug(f"正在解析sheet名称: {repr(sheet_name)}")
    patterns = [
        r'\((\d{4})\)',  # 半角括号
        r'（(\d{4})）',  # 全角括号
    ]
    for pattern in patterns:
        match = re.search(pattern, sheet_name)
        if match:
            year = int(match.group(1))
            logger.debug(f"从sheet名称 {sheet_name} 中成功解析出版本年份: {year}")
            return year
    logger.warning(f"无法从sheet名称 {sheet_name} 中解析出版本年份")
    return None

def get_or_create_version(regulation, version_year):
    """获取或创建指定年份的版本，并根据施行时间确定当前版本"""
    version = LegalRegulationVersion.query.filter_by(
        regulation_id=regulation.id,
        version_number=f"{version_year}年版"
    ).first()
    
    if not version:
        effective_date = regulation.effective_date if regulation.effective_date else datetime(version_year, 1, 1)
        version = LegalRegulationVersion(
            regulation=regulation,
            version_number=f"{version_year}年版",
            revision_date=effective_date,
            publish_date=effective_date,
            effective_date=effective_date,
            status='current',  # 临时设置为current
            changes_summary=f"{version_year}年修订版本",
            step_id=1  # 默认设置step_id为1
        )
        db.session.add(version)
        db.session.flush()
    
    all_versions = LegalRegulationVersion.query.filter_by(
        regulation_id=regulation.id
    ).order_by(LegalRegulationVersion.effective_date.desc()).all()
    
    if all_versions:
        for v in all_versions:
            if v == all_versions[0]:
                v.status = 'current'
                regulation.current_version_id = v.id
                regulation.latest_revision_date = v.effective_date
            else:
                v.status = 'superseded'
    
    db.session.flush()
    return version

def import_regulations_structures(structure_file):
    try:
        xls_structure = pd.ExcelFile(structure_file)
        regulation_names = xls_structure.sheet_names
        logger.info(f"开始导入 {len(regulation_names)} 个法规的条文")
        
        regulation_count = 0
        total_structure_count = 0
        
        for sheet_name in regulation_names:
            try:
                version_year = get_version_from_sheet_name(sheet_name)
                if version_year is None:
                    continue
                regulation_name = sheet_name.replace(f"（{version_year}）", "").strip()
                
                regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
                if not regulation:
                    logger.warning(f"法规 {regulation_name} 不存在，请先导入法规基础信息")
                    continue
                
                version = get_or_create_version(regulation, version_year)
                
                # 清除该版本的现有条文
                existing_structures = LegalStructure.query.filter_by(
                    regulation_id=regulation.id,
                    version_id=version.id
                ).all()
                if existing_structures:
                    for structure in existing_structures:
                        db.session.delete(structure)
                    db.session.commit()
                    logger.info(f"已清除法规 {sheet_name} 的 {len(existing_structures)} 条旧条文")
                
                # 将旧版本的条文关联到最近的 superseded 版本
                old_versions = LegalRegulationVersion.query.filter(
                    LegalRegulationVersion.regulation_id == regulation.id,
                    LegalRegulationVersion.status == 'superseded'
                ).order_by(LegalRegulationVersion.revision_date.desc()).all()
                if old_versions:
                    old_structures = LegalStructure.query.filter(
                        LegalStructure.regulation_id == regulation.id,
                        LegalStructure.version_id.is_(None)
                    ).all()
                    for structure in old_structures:
                        structure.version_id = old_versions[0].id
                
                df_structure = pd.read_excel(structure_file, sheet_name=sheet_name)
                structure_count = 0
                
                for _, row in df_structure.iterrows():
                    try:
                        structure = LegalStructure(
                            regulation=regulation,
                            version_id=version.id,
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
                
                # 更新 step_id 为 2
                version.step_id = 2
                
                regulation_count += 1
                total_structure_count += structure_count
                logger.info(f"成功导入法规 {sheet_name} 的 {structure_count} 条条文")
                
                if regulation_count % 5 == 0:
                    db.session.commit()
                    logger.info(f"已处理 {regulation_count} 个法规的条文")
            
            except Exception as e:
                logger.error(f"导入法规 {sheet_name} 的条文时出错: {str(e)}")
        
        db.session.commit()
        logger.info(f"成功导入 {regulation_count} 个法规的共 {total_structure_count} 条条文")
        return regulation_count, total_structure_count
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"导入法规条文时出错: {str(e)}")
        raise

def import_regulations_causes(cause_file):
    try:
        xls_cause = pd.ExcelFile(cause_file)
        regulation_names = xls_cause.sheet_names
        logger.info(f"开始导入 {len(regulation_names)} 个法规的事由")
        
        regulation_count = 0
        total_cause_count = 0
        
        for sheet_name in regulation_names:
            try:
                version_year = get_version_from_sheet_name(sheet_name)
                if version_year is None:
                    continue
                regulation_name = sheet_name.replace(f"（{version_year}）", "").replace(f"({version_year})", "").strip()
                logger.debug(f"处理后的 regulation_name: {repr(regulation_name)}")
                
                                
                regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
                if not regulation:
                    logger.warning(f"法规 {regulation_name} 不存在，请先导入法规基础信息")
                    continue
                
                version = get_or_create_version(regulation, version_year)
                
                # 清除该版本的现有事由
                existing_causes = LegalCause.query.filter_by(
                    regulation_id=regulation.id,
                    version_id=version.id
                ).all()
                if existing_causes:
                    for cause in existing_causes:
                        db.session.delete(cause)
                    db.session.commit()
                    logger.info(f"已清除法规 {sheet_name} 的 {len(existing_causes)} 条旧事由")
                
                # 将旧版本的事由关联到最近的 superseded 版本
                old_versions = LegalRegulationVersion.query.filter(
                    LegalRegulationVersion.regulation_id == regulation.id,
                    LegalRegulationVersion.status == 'superseded'
                ).order_by(LegalRegulationVersion.revision_date.desc()).all()
                if old_versions:
                    old_causes = LegalCause.query.filter(
                        LegalCause.regulation_id == regulation.id,
                        LegalCause.version_id.is_(None)
                    ).all()
                    for cause in old_causes:
                        cause.version_id = old_versions[0].id
                
                df_cause = pd.read_excel(cause_file, sheet_name=sheet_name)
                cause_count = 0
                
                for _, row in df_cause.iterrows():
                    try:
                        cause = LegalCause(
                            regulation=regulation,
                            version_id=version.id,
                            code=str(row['编号']) if pd.notna(row.get('编号', None)) else '',
                            description=str(row['事由']) if pd.notna(row.get('事由', None)) else '',
                            violation_type=str(row['违则']) if pd.notna(row.get('违则', None)) else None,
                            violation_clause=str(row['违则条款']) if pd.notna(row.get('违则条款', None)) else None,
                            behavior=str(row['行为']) if pd.notna(row.get('行为', None)) else None,
                            illegal_behavior=str(row['违法行为']) if pd.notna(row.get('违法行为', None)) else None,
                            penalty_type=str(row['罚则']) if pd.notna(row.get('罚则', None)) else None,
                            penalty_clause=str(row['罚则条款']) if pd.notna(row.get('罚则条款', None)) else None,
                            severity='一般'
                        )
                        db.session.add(cause)
                        cause_count += 1
                    except Exception as e:
                        logger.warning(f"处理法规 {sheet_name} 的事由时出错: {str(e)}")
                
                # 更新 step_id 为 3
                version.step_id = 3
                
                regulation_count += 1
                total_cause_count += cause_count
                logger.info(f"成功导入法规 {sheet_name} 的 {cause_count} 条事由")
                
                if regulation_count % 5 == 0:
                    db.session.commit()
                    logger.info(f"已处理 {regulation_count} 个法规的事由")
            
            except Exception as e:
                logger.error(f"导入法规 {sheet_name} 的事由时出错: {str(e)}")
        
        db.session.commit()
        logger.info(f"成功导入 {regulation_count} 个法规的共 {total_cause_count} 条事由")
        return regulation_count, total_cause_count
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"导入法规事由时出错: {str(e)}")
        raise

def import_regulations_punishments(punishment_file):
    try:
        xls_punishment = pd.ExcelFile(punishment_file)
        regulation_names = xls_punishment.sheet_names
        logger.info(f"开始导入 {len(regulation_names)} 个法规的处罚")
        
        regulation_count = 0
        total_punishment_count = 0
        
        for sheet_name in regulation_names:
            try:
                version_year = get_version_from_sheet_name(sheet_name)
                if version_year is None:
                    continue
                regulation_name = sheet_name.replace(f"（{version_year}）", "").replace(f"({version_year})", "").strip()
                
                regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
                if not regulation:
                    logger.warning(f"法规 {regulation_name} 不存在，请先导入法规基础信息")
                    continue
                
                version = get_or_create_version(regulation, version_year)
                
                causes = LegalCause.query.filter_by(regulation_id=regulation.id, version_id=version.id).all()
                cause_dict = {cause.code: cause for cause in causes}
                
                if not causes:
                    logger.warning(f"法规 {sheet_name} 没有对应版本的事由信息，请先导入事由")
                    continue
                
                # 清除该版本的现有处罚
                existing_punishments = LegalPunishment.query.filter_by(version_id=version.id).all()
                if existing_punishments:
                    for punishment in existing_punishments:
                        db.session.delete(punishment)
                    db.session.commit()
                    logger.info(f"已清除法规 {sheet_name} 的 {len(existing_punishments)} 条旧处罚")
                
                # 将旧版本的处罚关联到最近的 superseded 版本
                old_versions = LegalRegulationVersion.query.filter(
                    LegalRegulationVersion.regulation_id == regulation.id,
                    LegalRegulationVersion.status == 'superseded'
                ).order_by(LegalRegulationVersion.revision_date.desc()).all()
                if old_versions:
                    old_punishments = LegalPunishment.query.filter(
                        LegalPunishment.version_id.is_(None),
                        LegalPunishment.cause_id.in_([c.id for c in regulation.causes])
                    ).all()
                    for punishment in old_punishments:
                        punishment.version_id = old_versions[0].id
                
                df_punishment = pd.read_excel(punishment_file, sheet_name=sheet_name)
                punishment_count = 0
                
                for _, row in df_punishment.iterrows():
                    try:
                        cause_code = str(row['编号']) if pd.notna(row.get('编号', None)) else None
                        if not cause_code or cause_code not in cause_dict:
                            logger.warning(f"法规 {sheet_name}: 未找到编号为 {cause_code} 的事由")
                            continue
                        cause = cause_dict[cause_code]
                        punishment = LegalPunishment(
                            cause=cause,
                            version_id=version.id,
                            circumstance=str(row['情形']) if pd.notna(row.get('情形', None)) else None,
                            punishment_type=str(row['处罚类型']) if pd.notna(row.get('处罚类型', None)) else None,
                            progressive_punishment=str(row['递进处罚']) if pd.notna(row.get('递进处罚', None)) else None,
                            industry=str(row['行业']) if pd.notna(row.get('行业', None)) else None,
                            subject_level=str(row['主体级别']) if pd.notna(row.get('主体级别', None)) else None,
                            punishment_target=str(row['处罚对象']) if pd.notna(row.get('处罚对象', None)) else None,
                            punishment_details=str(row['处罚明细']) if pd.notna(row.get('处罚明细', None)) else None,
                            additional_notes=str(row['行政行为']) if pd.notna(row.get('行政行为', None)) else None
                        )
                        db.session.add(punishment)
                        punishment_count += 1
                    except Exception as e:
                        logger.warning(f"处理法规 {sheet_name} 的处罚时出错: {str(e)}")
                
                # 更新 step_id 为 4 (完成所有导入)
                version.step_id = 4
                
                regulation_count += 1
                total_punishment_count += punishment_count
                logger.info(f"成功导入法规 {sheet_name} 的 {punishment_count} 条处罚")
                
                if regulation_count % 5 == 0:
                    db.session.commit()
                    logger.info(f"已处理 {regulation_count} 个法规的处罚")
            
            except Exception as e:
                logger.error(f"导入法规 {sheet_name} 的处罚时出错: {str(e)}")
        
        db.session.commit()
        logger.info(f"成功导入 {regulation_count} 个法规的共 {total_punishment_count} 条处罚")
        return regulation_count, total_punishment_count
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"导入法规处罚时出错: {str(e)}")
        raise

def delete_regulation_cascade(regulation_name):
    try:
        regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
        if not regulation:
            return False
        db.session.delete(regulation)
        db.session.commit()
        logger.info(f"成功删除法规: {regulation_name}")
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"删除法规 {regulation_name} 时出错: {str(e)}")
        return False

def update_legal_data(info_file, structure_file, cause_file, punish_file):
    try:
        reg_count = import_regulations_info(info_file)
        logger.info(f"成功导入 {reg_count} 条法规基础信息")
        reg_count, struct_count = import_regulations_structures(structure_file)
        logger.info(f"成功导入 {reg_count} 个法规的 {struct_count} 条条文")
        reg_count, cause_count = import_regulations_causes(cause_file)
        logger.info(f"成功导入 {reg_count} 个法规的 {cause_count} 条事由")
        reg_count, punish_count = import_regulations_punishments(punish_file)
        logger.info(f"成功导入 {reg_count} 个法规的 {punish_count} 条处罚")
        logger.info("法律法规数据更新完成")
    except Exception as e:
        logger.error(f"更新法律法规数据时出错: {str(e)}")
        raise

def main():
    import argparse
    parser = argparse.ArgumentParser(description='法律法规数据导入工具')
    parser.add_argument('--all', action='store_true', help='导入所有数据')
    parser.add_argument('--info', help='仅导入法规基础信息Excel文件路径')
    parser.add_argument('--structure', help='仅导入法规结构Excel文件路径')
    parser.add_argument('--cause', help='仅导入法规事由Excel文件路径')
    parser.add_argument('--punishment', help='仅导入法规处罚Excel文件路径')
    args = parser.parse_args()
    
    default_info_file = 'data/law_info.xlsx'
    default_structure_file = 'data/law_structure.xlsx'
    default_cause_file = 'data/law_cause.xlsx'
    default_punish_file = 'data/law_punish.xlsx'
    
    logger.info("开始导入法律法规数据")
    
    # 创建应用上下文
    app = create_app()
    
    with app.app_context():
        try:
            if args.all:
                update_legal_data(default_info_file, default_structure_file, default_cause_file, default_punish_file)
            else:
                if args.info:
                    count = import_regulations_info(args.info)
                    logger.info(f"成功导入 {count} 条法规基础信息")
                if args.structure:
                    reg_count, struct_count = import_regulations_structures(args.structure)
                    logger.info(f"成功导入 {reg_count} 个法规的 {struct_count} 条条文")
                if args.cause:
                    reg_count, cause_count = import_regulations_causes(args.cause)
                    logger.info(f"成功导入 {reg_count} 个法规的 {cause_count} 条事由")
                if args.punishment:
                    reg_count, punish_count = import_regulations_punishments(args.punishment)
                    logger.info(f"成功导入 {reg_count} 个法规的 {punish_count} 条处罚")
                if not (args.info or args.structure or args.cause or args.punishment):
                    parser.print_help()
            logger.info("法律法规数据导入完成")
            return 0
        except Exception as e:
            logger.error(f"数据导入过程中出错: {str(e)}")
            print(f"错误: {str(e)}")
            return 1

if __name__ == '__main__':
    import sys
    sys.exit(main())