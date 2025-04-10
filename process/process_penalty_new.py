import pandas as pd
import re

#判断找出罚则中的所有5，即是否为别的款的额外处罚
def process_law_penalty_new(file_path):
    # 读取 Excel 文件
    excel_file = pd.ExcelFile(file_path)
    sheet_names = excel_file.sheet_names

    # 创建一个 ExcelWriter 对象，用于写入修改后的数据到原文件
    with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        # 遍历每个 sheet
        for sheet_name in sheet_names:
            print(f"\n处理工作表: {sheet_name}")
            df = excel_file.parse(sheet_name)

            if '增加处罚' not in df.columns:
                df['增加处罚'] = ''

            # 筛选出"罚则"为 1 且"内容"文本中没有“下列情形”“下列情况”“下列行为”之一的记录
            filtered_df = df[
                (df['罚则'] == 1) &
                (df['违法情形'] == 0) & 
                ~(df['内容'].str.contains('下列', na=False))
            ]

            # 定义正则表达式模式，用于匹配包含处罚引用的总体文本
            overall_pattern = r'(依照|按照)(.*?)(条|款)(.*?)(处罚|罚款)'
            # 定义正则表达式模式，用于匹配具体的条款号
            clause_pattern = r'第(\d+)条(?:第(\d+)款)?(?:第(\d+)项)?'

            # 遍历筛选后的记录
            for index, row in filtered_df.iterrows():
                content = row['内容']
                #print(f"当前处理行索引: {index}")
                overall_matches = re.findall(overall_pattern, content)
                for overall_match in overall_matches:
                    overall_text = ''.join(overall_match)
                    #print(f"overall_text: {overall_text}")
                    clause_matches = re.findall(clause_pattern, overall_text)
                    #print(f"clause_matches: {clause_matches}")
                    for match in clause_matches:
                        # 提取引用的条款项信息
                        article_num = int(match[0])
                        paragraph_num = int(match[1]) if match[1] else 0
                        item_num = int(match[2]) if match[2] else 0

                        # 构建引用文本
                        ref_text = f"第{article_num}条"
                        if paragraph_num > 0:
                            ref_text += f"第{paragraph_num}款"
                        if item_num > 0:
                            ref_text += f"第{item_num}项"

                        # 查找对应的记录
                        query_conditions = (df['条'] == article_num)
                        if paragraph_num > 0:
                            query_conditions &= (df['款'] == paragraph_num)
                        if item_num > 0:
                            query_conditions &= (df['项'] == item_num)

                        related_records = df[query_conditions]

                        # 构建当前记录的条款项号
                        current_article = row['条']
                        current_paragraph = row['款']
                        current_item = row['项']
                        current_ref_parts = [f"第{current_article}条"]
                        if current_paragraph > 0:
                            current_ref_parts.append(f"第{current_paragraph}款")
                        if current_item > 0:
                            current_ref_parts.append(f"第{current_item}项")
                        current_ref = ''.join(current_ref_parts)

                        # 更新对应的"增加处罚"列
                        df.at[index, '条类型'] = 5
                        for related_index in related_records.index:
                            existing_content = str(df.at[related_index, '增加处罚'])
                            if existing_content and existing_content != 'nan':
                                if current_ref not in existing_content:
                                    df.at[related_index, '增加处罚'] = f"{existing_content}|{current_ref}"
                            else:
                                df.at[related_index, '增加处罚'] = current_ref

            # 将修改后的 DataFrame 写入到原文件的对应工作表中
            print(f"将修改后的数据写入工作表: {sheet_name}")
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"处理完成: {sheet_name}")

if __name__ == "__main__":
    file_path = 'result\\law_structure_format_num_ex.xlsx'
    print(f"开始处理文件: {file_path}")
    process_law_penalty_new(file_path)
    print("全部处理完成")