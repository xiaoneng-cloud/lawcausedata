import pandas as pd
import re

def process_law_penalty(file_path):
    # 打开 Excel 文件并获取所有工作表名称
    excel_file = pd.ExcelFile(file_path)
    sheet_names = excel_file.sheet_names

    # 创建 ExcelWriter 对象，用于将修改后的数据写回原文件
    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        # 逐个处理每个工作表
        for sheet_name in sheet_names:
            print(f"\n处理工作表: {sheet_name}")
            # 读取当前工作表数据
            df = excel_file.parse(sheet_name)

            # 如果没有“增加处罚”列，则添加一个空列
            if '增加处罚' not in df.columns:
                df['增加处罚'] = ''

            # 筛选符合条件的记录：条类型等于 6
            filtered_df = df[df['条类型'] == 6]

            # 定义正则表达式模式
            overall_pattern = r'(依照|按照)(.*?)(条|款)(.*?)(处罚|罚款|责令改正)'  # 匹配处罚引用文本
            clause_pattern = r'第(\d+)条(?:第(\d+)款)?(?:第(\d+)项)?'  # 提取条款编号
            penalty_keywords = r'(罚款|责令改正|没收|吊销)'  # 处罚相关关键词

            # 处理筛选出的记录
            for index, row in filtered_df.iterrows():
                content = row['内容']
                overall_matches = re.findall(overall_pattern, content)

                # 构建引用文本 B1
                ref_text_B1 = []
                for overall_match in overall_matches:
                    overall_text = ''.join(overall_match)
                    clause_matches = re.findall(clause_pattern, overall_text)
                    #print(f"在处罚引用文本 {overall_text} 中找到 {len(clause_matches)} 个条款编号")

                    # 提取并整理条款信息
                    for match in clause_matches:
                        article_num = int(match[0])  # 条号
                        paragraph_num = int(match[1]) if match[1] else 0  # 款号
                        item_num = int(match[2]) if match[2] else 0  # 项号

                        # 构建引用文本
                        ref_text = f"第{article_num}条"
                        if paragraph_num > 0:
                            ref_text += f"第{paragraph_num}款"
                        if item_num > 0:
                            ref_text += f"第{item_num}项"

                        # 查找相关记录，要求包含处罚关键词
                        related_records = df[
                            (df['条'] == article_num) &
                            (df['款'] == paragraph_num if paragraph_num > 0 else True) &
                            (df['项'] == item_num if item_num > 0 else True) &
                            (df['内容'].str.contains(penalty_keywords, na=False))
                        ]
                        if not related_records.empty:
                            for _, related_row in related_records.iterrows():
                                rel_article = int(related_row['条'])
                                rel_paragraph = int(related_row['款']) if pd.notna(related_row['款']) else 0
                                rel_item = int(related_row['项']) if pd.notna(related_row['项']) else 0
                                rel_ref = f"第{rel_article}条"
                                if rel_paragraph > 0:
                                    rel_ref += f"第{rel_paragraph}款"
                                else:
                                    rel_ref += "第1款"
                                if rel_item > 0:
                                    rel_ref += f"第{rel_item}项"
                                if rel_ref not in ref_text_B1:
                                    ref_text_B1.append(rel_ref)
                        else:
                            print(f"在 {sheet_name} 中，未找到与 {ref_text} 相关的处罚引用，有可能法律法规已经变更")

                # 将引用文本列表拼接为 B1
                B1 = "|".join(ref_text_B1) if ref_text_B1 else ""

                # 更新同号同款记录的“增加处罚”列，但不对“条类型”为 6 的记录自身操作
                same_clause_records = df[
                    (df['条'] == row['条']) &
                    (df['款'] == (row['款'] if pd.notna(row['款']) else 0)) 
                ]
                for same_index, same_row in same_clause_records.iterrows():
                    existing_content = str(df.at[same_index, '增加处罚'])
                    if existing_content and existing_content != 'nan':
                        if B1 and B1 not in existing_content:
                            df.at[same_index, '增加处罚'] = f"{existing_content}|{B1}"
                    else:
                        df.at[same_index, '增加处罚'] = B1

                # 更新“条类型”列
                current_type = row['条类型']
                if pd.notna(current_type):
                    if int(current_type) == 3:
                        df.at[index, '条类型'] = 312
                    elif int(current_type) == 311:
                        df.at[index, '条类型'] = 313

            # 将修改后的数据写回当前工作表
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"处理完成: {sheet_name}")

if __name__ == "__main__":
    file_path = 'result\\law_structure_format_num_ex.xlsx'
    print(f"开始处理文件: {file_path}")
    process_law_penalty(file_path)
    print("全部处理完成")