import pandas as pd
from sqlalchemy.exc import SQLAlchemyError
import logging
from datetime import datetime
import re
import argparse

# 创建Flask应用上下文
from app import create_app
from app.extensions import db
from app.models.regulation import LegalRegulation, LegalRegulationVersion

# 配置日志
logging.basicConfig(
    filename=f'law_update_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        effective_date = regulation.effective_date if regulation.effective_date else regulation.publish_date
        version = LegalRegulationVersion(
            regulation=regulation,
            version_number=f"{version_year}年版",
            revision_date=effective_date,
            publish_date=effective_date,
            effective_date=effective_date,
            status='current',  # 临时设置为current
            changes_summary=f"{version_year}年修订版本",
            step_id=1  # 设置 step_id 为1
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
                'city': str(row.get('城市', '')) if pd.notna(row.get('城市', None)) else ''
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
                logger.warning(f"法规 {name} 未提供施行日期，使用公布日期替代")
                regulation_data['effective_date'] = regulation_data.get('publish_date', datetime.now())
            
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

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='法律法规基础信息导入工具')
    parser.add_argument('--info', help='仅导入法规基础信息Excel文件路径')
    args = parser.parse_args()
    
    default_info_file = 'data/law_info.xlsx'
    logger.info("开始导入法律法规基础信息")
    
    # 创建应用上下文
    app = create_app()
    
    with app.app_context():
        try:
            if args.info:
                count = import_regulations_info(args.info)
                logger.info(f"成功导入 {count} 条法规基础信息")
            else:
                count = import_regulations_info(default_info_file)
                logger.info(f"成功导入 {count} 条法规基础信息")
            logger.info("法律法规基础信息导入完成")
        except Exception as e:
            logger.error(f"数据导入过程中出错: {str(e)}")
            print(f"错误: {str(e)}")


