import pandas as pd
import re
import os
import logging
from openpyxl.styles import Alignment

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 处理法律引用并补全上下文
def handle_legal_references(content):
    pattern = r'《([^》]+)》(第\d+条(?:第\d+款)?(?:第\d+项)?)(?=[^\w《]*第\d+条(?:第\d+款)?(?:第\d+项)?)'
    matches = list(re.finditer(pattern, content))
    for match in reversed(matches):
        law_name = match.group(1)
        ref = match.group(2)
        full_match = match.group(0)
        rest_text = content[match.end():]
        next_refs = re.findall(r'第\d+条(?:第\d+款)?(?:第\d+项)?', rest_text)
        if next_refs:
            logging.info(f"找到引用补全: {full_match} 后跟 {next_refs}")
            expanded_refs = [f'《{law_name}》{next_ref}' for next_ref in next_refs]
            # 找到 next_refs 最后一个引用的结束位置
            last_ref_end = match.end()
            for next_ref in next_refs:
                last_ref_end = content.find(next_ref, last_ref_end) + len(next_ref)
            # 拼接新的内容
            content = content[:match.end()] + '、' + '、'.join(expanded_refs) + content[last_ref_end:]
            logging.info(f"找到引用补全content:  {content}")
    return content

# 主函数处理Excel文件
def process_legal_document(file_path, output_path, rel_file_path):
    xls = pd.ExcelFile(file_path)
    with pd.ExcelWriter(output_path) as writer:
        for sheet_name in xls.sheet_names:
            df = xls.parse(sheet_name)
            
            # 确保“关联法律”列存在，若不存在则添加
            if '关联法律' not in df.columns:
                df['关联法律'] = ''
            # “条类型”列假设已存在，不新建

            logging.info(f"开始处理 sheet: {sheet_name}")

            # 步骤1：处理法律引用并补全上下文
            for idx, row in df.iterrows():
                content = str(row['内容'])
                original_content = content
                content = handle_legal_references(content)
                if content != original_content:
                    logging.info(f"行 {idx} 内容更新: {original_content} -> {content}")
                df.at[idx, '内容'] = content

            # 步骤2：收集所有“《XXX》第X条”的引用并编号法律
            legal_refs = []
            law_names = []
            for idx, row in df.iterrows():
                content = str(row['内容'])
                matches = re.findall(r'《([^》]+)》第(\d+)条', content)
                for law_name, tiao_num in matches:
                    legal_refs.append(f'《{law_name}》第{tiao_num}条')
                    if law_name not in law_names:
                        law_names.append(law_name)

            # 步骤3：去重引用并为法律分配编号
            legal_refs = list(set(legal_refs))
            law_number_map = {law_name: i + 1 for i, law_name in enumerate(law_names)}  # 从1开始编号
            logging.info(f"找到唯一法律引用: {legal_refs}")
            logging.info(f"法律编号映射: {law_number_map}")

            # 步骤4：处理关联法律并拷贝记录
            rel_xls = pd.ExcelFile(rel_file_path)
            for ref in legal_refs:
                law_name = re.search(r'《([^》]+)》', ref).group(1)
                tiao_num = int(re.search(r'第(\d+)条', ref).group(1))
                law_number = law_number_map[law_name]
                new_tiao_num = law_number * 10000 + tiao_num
                
                # 在rel.xlsx中查找对应的sheet
                if law_name in rel_xls.sheet_names:
                    rel_df = rel_xls.parse(law_name)
                    # 查找条号为tiao_num的记录
                    matched_records = rel_df[rel_df['条'] == tiao_num]
                    if not matched_records.empty:
                        logging.info(f"从 {law_name} (编号 {law_number}) 拷贝条号 {tiao_num} 的记录，调整为 {new_tiao_num}")
                        # 只拷贝指定列
                        columns_to_copy = ['条', '款', '项', '目', '内容', '原条款', '条款']
                        new_records = matched_records[columns_to_copy].copy()
                        new_records['条'] = new_tiao_num
                        # 确保目标df包含这些列，若缺少则添加空列
                        for col in columns_to_copy:
                            if col not in df.columns:
                                df[col] = pd.NA
                        # 设置“关联法律”和“条类型”
                        new_records['关联法律'] = law_name
                        new_records['条类型'] = law_number * 10000  # 使用法律编号*10000作为条类型
                        # 追加到当前sheet末尾
                        df = pd.concat([df, new_records], ignore_index=True)
                        
                        # 更新当前sheet中的引用
                        for idx, row in df.iterrows():
                            content = str(row['内容'])
                            old_ref = f'《{law_name}》第{tiao_num}条'
                            new_ref = f'第{new_tiao_num}条'
                            if old_ref in content:
                                df.at[idx, '内容'] = content.replace(old_ref, new_ref)
                                df.at[idx, '关联法律'] = law_name
                                logging.info(f"行 {idx} 替换引用: {old_ref} -> {new_ref}")
                    else:
                        logging.warning(f"在 {law_name} 中未找到条号 {tiao_num} 的记录")
                else:
                    logging.warning(f"未找到 sheet: {law_name}")

            # 写入处理后的数据
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            

    logging.info(f"处理完成，结果已保存至: {output_path}")
    print(f"处理完成，结果已保存至: {output_path}")

# 使用示例
if __name__ == "__main__":
    input_file = "D:\\lawproject\\test\\result\\law_structure_format_num.xlsx"
    output_file = "D:\\lawproject\\test\\result\\law_structure_format_num_ex.xlsx"
    rel_file = "D:\\lawproject\\test\\result\\processed\\temp\\rel.xlsx"
    if os.path.exists(input_file) and os.path.exists(rel_file):
        process_legal_document(input_file, output_file, rel_file)
    else:
        print(f"输入文件 {input_file} 或关联文件 {rel_file} 不存在，请检查文件路径。")