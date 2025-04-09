import os
import re
import logging
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from tqdm import tqdm
import docx

# 创建Flask应用上下文
from app import create_app
from app.extensions import db
from app.models.regulation import LegalRegulation, LegalRegulationVersion, LegalStructure

# 中文数字转阿拉伯数字的映射
CHINESE_NUMBERS = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100, '千': 1000, '万': 10000, '亿': 100000000
}

# 配置日志
logging.basicConfig(
    filename=f'law_import_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def chinese_to_arabic(chinese_str):
    """将中文数字转换为阿拉伯数字，支持带'零'的情况"""
    if not chinese_str or not any(c in CHINESE_NUMBERS for c in chinese_str):
        return chinese_str

    chinese_str = re.sub(r'[条章款项目]', '', chinese_str.strip())
    if len(chinese_str) == 1 and chinese_str in CHINESE_NUMBERS:
        return str(CHINESE_NUMBERS[chinese_str])

    total = 0
    current_section = 0
    last_unit = 1

    for char in chinese_str:
        if char not in CHINESE_NUMBERS:
            continue
        value = CHINESE_NUMBERS[char]
        if value >= 10:
            if current_section == 0:
                current_section = 1
            current_section *= value
            last_unit = value
        else:
            if last_unit >= 10:
                total += current_section
                current_section = value
                last_unit = 1
            else:
                current_section = current_section * 10 + value
    total += current_section
    return str(total) if total > 0 else chinese_str

def extract_law_structure_from_docx(file_path):
    """从DOCX文件中提取法律文本的结构，识别条、款、项、目"""
    try:
        doc = docx.Document(file_path)
        lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    except Exception as e:
        logger.error(f"无法读取DOCX文件 {file_path}: {str(e)}")
        return []

    article_pattern = re.compile(r'^第\s*([零一二三四五六七八九十百千万]+)\s*条')
    item_pattern = re.compile(r'^\s*\(\s*([一二三四五六七八九十]+)\s*\)')
    subitem_pattern = re.compile(r'^\s*(\d+)\s*[\.、]')
    chapter_pattern = re.compile(r'第\s*([零一二三四五六七八九十百千万]+)\s*(章|节)')

    law_data = []
    current_article = None
    current_paragraph = 0
    current_item = None
    current_subitem = None

    for line in lines:
        line = line.replace('（', '(').replace('）', ')')
        if not line:
            continue

        chapter_match = chapter_pattern.search(line)
        if chapter_match:
            continue

        article_match = article_pattern.search(line)
        if article_match:
            chinese_num = article_match.group(1)
            current_article = chinese_to_arabic(chinese_num)
            current_paragraph = 1
            current_item = None
            current_subitem = None
            content = line[article_match.end():].strip()
            if content:
                law_data.append({
                    "条": current_article,
                    "款": str(current_paragraph),
                    "项": "",
                    "目": "",
                    "内容": content
                })
            continue

        if current_article is None:
            continue

        item_match = item_pattern.match(line)
        if item_match:
            chinese_num = item_match.group(1)
            current_item = chinese_to_arabic(chinese_num)
            current_subitem = None
            content = line[item_match.end():].strip()
            if content:
                law_data.append({
                    "条": current_article,
                    "款": str(current_paragraph),
                    "项": current_item,
                    "目": "",
                    "内容": content
                })
            continue

        subitem_match = subitem_pattern.match(line)
        if subitem_match and current_item is not None:
            current_subitem = subitem_match.group(1)
            content = line[subitem_match.end():].strip()
            if content:
                law_data.append({
                    "条": current_article,
                    "款": str(current_paragraph),
                    "项": current_item,
                    "目": current_subitem,
                    "内容": content
                })
            continue

        current_paragraph += 1
        current_item = None
        current_subitem = None
        law_data.append({
            "条": current_article,
            "款": str(current_paragraph),
            "项": "",
            "目": "",
            "内容": line
        })

    return law_data

def parse_filename(filename):
    """从文件名中提取法规名称和版本年份"""
    pattern = r'^(.*?)(?:[（(](\d{4})[）)])?\.docx$'
    match = re.match(pattern, filename)
    if match:
        regulation_name = match.group(1)
        year = match.group(2)
        version_number = f"{year}年版" if year else None
        return regulation_name, version_number
    return None, None

def format_clause(row):
    """格式化条款编号"""
    parts = []
    if row['条'] and row['条'] != '0':
        parts.append(f"第{row['条']}条")
    if row['款'] and row['款'] != '0':
        parts.append(f"第{row['款']}款")
    if row['项'] and row['项'] != '0':
        parts.append(f"第{row['项']}项")
    if row['目'] and row['目'] != '0':
        parts.append(f"第{row['目']}目")
    return ''.join(parts)

def format_only_article(row):
    """仅格式化独立条的条款编号"""
    return f"第{row['条']}条" if row['条'] and row['条'] != '0' else ''

def import_law_structure_to_db(file_path, app=None):
    """从DOCX文件导入法律结构到数据库，并更新step_id"""
    filename = os.path.basename(file_path)
    regulation_name, version_number = parse_filename(filename)
    if not regulation_name:
        logger.warning(f"无法从文件名 {filename} 解析法规名称，跳过")
        return 0

    logger.info(f"开始处理文件: {filename}, 法规名: {regulation_name}, 版本: {version_number}")
    
    law_data = extract_law_structure_from_docx(file_path)
    if not law_data:
        logger.warning(f"文件 {file_path} 未提取到有效内容")
        return 0

    # 计算每个"条"的出现次数，用于判断独立条
    article_counts = {}
    for row in law_data:
        article = row['条']
        if article:
            article_counts[article] = article_counts.get(article, 0) + 1
    single_articles = {article for article, count in article_counts.items() if count == 1}

    # 使用已有的应用上下文或创建新的
    need_app_context = app is None
    if need_app_context:
        app = create_app()
    
    with app.app_context() if need_app_context else nullcontext():
        try:
            # 检查法规是否存在
            regulation = LegalRegulation.query.filter_by(name=regulation_name).first()
            if not regulation:
                logger.warning(f"法规 {regulation_name} 不存在，跳过导入")
                return 0

            # 检查版本是否存在
            if version_number:
                version = LegalRegulationVersion.query.filter_by(
                    regulation_id=regulation.id,
                    version_number=version_number
                ).first()
                if not version:
                    logger.warning(f"法规 {regulation_name} 的版本 {version_number} 不存在，跳过导入")
                    return 0
            else:
                if not regulation.current_version_id:
                    logger.warning(f"法规 {regulation_name} 没有当前版本且文件名未指定版本，跳过导入")
                    return 0
                version = LegalRegulationVersion.query.get(regulation.current_version_id)

            # 清除该版本的现有条文
            existing_structures = LegalStructure.query.filter_by(
                regulation_id=regulation.id,
                version_id=version.id
            ).all()
            
            for structure in existing_structures:
                db.session.delete(structure)
            
            db.session.commit()
            logger.info(f"已清除法规 {regulation_name} 版本 {version.version_number} 的 {len(existing_structures)} 条旧条文")

            structure_count = 0
            for row in law_data:
                original_text = format_only_article(row) if row['条'] in single_articles else format_clause(row)
                structure = LegalStructure(
                    regulation_id=regulation.id,
                    version_id=version.id,
                    article=int(row['条']) if row['条'] else None,
                    paragraph=int(row['款']) if row['款'] else None,
                    item=int(row['项']) if row['项'] else None,
                    section=int(row['目']) if row['目'] else None,
                    content=row['内容'],
                    original_text=original_text
                )
                db.session.add(structure)
                structure_count += 1

            db.session.commit()
            logger.info(f"成功导入法规 {regulation_name} 版本 {version.version_number} 的 {structure_count} 条条文")

            # 更新 step_id 为 2
            version.step_id = 2
            db.session.commit()
            logger.info(f"成功更新法规 {regulation_name} 版本 {version.version_number} 的 step_id 为 2")

            return structure_count
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"导入 {regulation_name} 时出错: {str(e)}")
            return 0
        except Exception as e:
            logger.error(f"处理 {filename} 时发生未知错误: {str(e)}")
            db.session.rollback()
            return 0

# 添加空上下文管理器以简化代码
class nullcontext:
    def __enter__(self): pass
    def __exit__(self, *args): pass

def process_law_files(folder_path):
    """处理文件夹中的所有DOCX文件并直接入库"""
    if not os.path.exists(folder_path):
        logger.error(f"文件夹 {folder_path} 不存在")
        return
        
    docx_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.docx')]
    if not docx_files:
        logger.info(f"在 {folder_path} 中没有找到docx文件")
        return

    # 创建一个应用实例，所有导入共用同一个实例以提高性能
    app = create_app()
    
    total_structures = 0
    successful_files = 0
    failed_files = 0
    
    with app.app_context():
        for file_name in tqdm(docx_files, desc="处理法律文件"):
            file_path = os.path.join(folder_path, file_name)
            try:
                structure_count = import_law_structure_to_db(file_path, app)
                if structure_count > 0:
                    total_structures += structure_count
                    successful_files += 1
                else:
                    failed_files += 1
            except Exception as e:
                logger.error(f"处理文件 {file_name} 时发生异常: {str(e)}")
                failed_files += 1

    logger.info(f"所有文件处理完成，成功处理 {successful_files} 个文件，失败 {failed_files} 个文件，共导入 {total_structures} 条条文")
    print(f"处理完成! 成功: {successful_files}, 失败: {failed_files}, 总条文: {total_structures}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='法律法规结构导入工具')
    parser.add_argument('--folder', default='laws_folder', help='包含法律DOCX文件的文件夹路径')
    parser.add_argument('--file', help='单个要导入的DOCX文件路径')
    
    args = parser.parse_args()
    
    if args.file:
        # 导入单个文件
        if not os.path.exists(args.file):
            print(f"文件 {args.file} 不存在!")
            logger.error(f"文件 {args.file} 不存在")
        else:
            app = create_app()
            with app.app_context():
                count = import_law_structure_to_db(args.file, app)
                print(f"导入完成! 条文数: {count}")
    else:
        # 导入整个文件夹
        folder_path = args.folder
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.info(f"已创建文件夹 {folder_path}，请将法律DOCX文件放入其中，然后重新运行程序")
            print(f"已创建文件夹 {folder_path}，请将法律DOCX文件放入其中，然后重新运行程序")
        else:
            process_law_files(folder_path)