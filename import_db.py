import pandas as pd
from app import app, db
from models import (
    LegalRegulation, 
    LegalStructure, 
    LegalCause, 
    LegalPunishment
)

def import_punishments(xls_punish, regulation, cause_dict):
    """
    导入处罚信息
    :param xls_punish: Excel文件
    :param regulation: 当前法规
    :param cause_dict: 事由字典，用于快速查找对应事由
    """
    # 读取数据
    df_punish = pd.read_excel(xls_punish, sheet_name=regulation.name)
    
    # 处理处罚信息
    for _, row in df_punish.iterrows():
        # 使用编号找到对应的事由
        cause_code = str(row['编号']) if pd.notna(row['编号']) else None
        if not cause_code or cause_code not in cause_dict:
            print(f"Warning: No cause found for code {cause_code}")
            continue
        
        cause = cause_dict[cause_code]
        
        # 创建处罚记录
        punishment = LegalPunishment(
            cause=cause,
            circumstance=str(row['情形']) if pd.notna(row['情形']) else None,
            punishment_type=str(row['处罚类型']) if pd.notna(row['处罚类型']) else None,
            progressive_punishment=str(row['递进处罚']) if pd.notna(row['递进处罚']) else None,
            industry=str(row['行业']) if pd.notna(row['行业']) else None,
            subject_level=str(row['主体级别']) if pd.notna(row['主体级别']) else None,
            punishment_target=str(row['处罚对象']) if pd.notna(row['处罚对象']) else None,
            punishment_details=str(row['处罚明细']) if pd.notna(row['处罚明细']) else None,
            additional_notes=str(row['补充说明']) if pd.notna(row['补充说明']) else None
        )
        
        db.session.add(punishment)
    
    # 提交处罚信息
    db.session.commit()

def import_legal_data():
    """整体数据导入"""
    # 读取文件
    structure_file = 'law_structure.xlsx'
    cause_file = 'law_cause.xlsx'
    punish_file = 'law_punish.xlsx'

    # 处理法规主表
    xls_structure = pd.ExcelFile(structure_file)
    xls_cause = pd.ExcelFile(cause_file)
    xls_punish = pd.ExcelFile(punish_file)

    # 确保处理顺序：先法规，再事由，最后处罚
    for sheet_name in xls_structure.sheet_names:
        # 创建或获取法规
        regulation = LegalRegulation.query.filter_by(name=sheet_name).first()
        if not regulation:
            regulation = LegalRegulation(
                name=sheet_name,
                source='地方法规',
                status='active'
            )
            db.session.add(regulation)
        
        # 处理法规条文
        df_structure = pd.read_excel(structure_file, sheet_name=sheet_name)
        for _, row in df_structure.iterrows():
            structure = LegalStructure(
                regulation=regulation,
                article=int(row['条']) if pd.notna(row['条']) else None,
                paragraph=int(row['款']) if pd.notna(row['款']) else None,
                item=int(row['项']) if pd.notna(row['项']) else None,
                section=int(row['目']) if pd.notna(row['目']) else None,
                content=str(row['内容']) if pd.notna(row['内容']) else '',
                original_text=str(row['原条款']) if pd.notna(row['原条款']) else None
            )
            db.session.add(structure)
        
        # 处理事由，并创建事由字典以便快速查找
        cause_dict = {}
        df_cause = pd.read_excel(cause_file, sheet_name=sheet_name)
        for _, row in df_cause.iterrows():
            cause = LegalCause(
                regulation=regulation,
                code=str(row['编号']) if pd.notna(row['编号']) else '',
                description=str(row['事由']) if pd.notna(row['事由']) else '',
                violation_type=str(row['违则']) if pd.notna(row['违则']) else None,
                violation_clause=str(row['违则条款']) if pd.notna(row['违则条款']) else None,
                behavior=str(row['行为']) if pd.notna(row['行为']) else None,
                illegal_behavior=str(row['违法行为']) if pd.notna(row['违法行为']) else None,
                severity='一般'  # 默认设置
            )
            db.session.add(cause)
            cause_dict[cause.code] = cause
        
        # 提交法规、条文和事由
        db.session.commit()
        
        # 处理处罚
        import_punishments(punish_file, regulation, cause_dict)

def main():
    with app.app_context():
        # 清除已存在的数据（可选）
        db.drop_all()
        db.create_all()
        
        # 导入数据
        import_legal_data()
        print("数据导入完成！")

if __name__ == '__main__':
    main()