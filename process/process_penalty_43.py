import pandas as pd
import re

def check_text_in_array(target_text, text_array):
    for index, text in enumerate(text_array):
        if target_text in text:
            return 1  # 返回元素在数组中的序号（从 1 开始）
    return 0  # 如果未找到匹配项，返回 0

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

            # 筛选符合条件的记录
            filtered_df = df[
                (df['罚则'] == 1) &  # 涉及处罚
                (df['违法情形'] == 1) &  # 描述违法情况
                ~(df['内容'].str.contains('下列', na=False))  # 不含特定短语
            ]

            # 定义正则表达式模式
            overall_pattern = r'(依照|按照)(.*?)(条|款)(.*?)(处罚|罚款|责令改正)'  # 匹配处罚引用文本
            clause_pattern = r'第(\d+)条(?:第(\d+)款)?(?:第(\d+)项)?'  # 提取条款编号

            # 处理筛选出的记录
            for index, row in filtered_df.iterrows():
                content = row['内容']
                #print(f"当前处理行索引: {index}")
                overall_matches = re.findall(overall_pattern, content)

                # 分析每个匹配的引用
                for overall_match in overall_matches:
                    overall_text = ''.join(overall_match)
                    clause_matches = re.findall(clause_pattern, overall_text)

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

                        # 如果 paragraph_num 和 item_num 都为 0，查找同条号下罚则为 1 的记录
                        if paragraph_num == 0 and item_num == 0:
                            penalty_records = df[
                                (df['条'] == article_num) & 
                                (df['罚则'] == 1)
                            ]
                            #如果不为空，则遍历罚则为1的记录，将条号和款号拼接成字符串
                            if not penalty_records.empty:
                                ref_texts = []
                                for _, penalty_row in penalty_records.iterrows():
                                    penalty_article = int(penalty_row['条'])
                                    penalty_paragraph = int(penalty_row['款']) if pd.notna(penalty_row['款']) else 0
                                    if penalty_paragraph > 0:  # 只添加有款号的记录
                                        #如果当前存储的记录，其本身带有“增加处罚”，而且增加处罚又与本身文本中包括的相同
                                        #境外金融机构违反本法第49条规定，依照本法第54条、第56条规定进行处罚。而54条中又在“增加处罚”中提到了56条
                                        if check_text_in_array(f"第{penalty_article}条", ref_texts) == 0:
                                            ref_texts.append(f"第{penalty_article}条第{penalty_paragraph}款")
                                        penalty_value = penalty_row['增加处罚']
                                        if pd.notna(penalty_value):  # 检查是否不是 NaN
                                            ref_texts.append(str(penalty_value))  # 强制转换为字符串
                                if ref_texts:
                                    ref_text = "|".join(ref_texts)
                        

                        # 更新当前行的“增加处罚”列
                        existing_content = str(df.at[index, '增加处罚'])
                        if existing_content and existing_content != 'nan':
                            if ref_text not in existing_content:
                                df.at[index, '增加处罚'] = f"{existing_content}|{ref_text}"
                        else:
                            df.at[index, '增加处罚'] = ref_text
                    # 更新当前行的“条类型”
                    current_type = df.at[index, '条类型']
                    if pd.notna(current_type) and int(current_type) == 41:
                        df.at[index, '条类型'] = 43
                    else:
                        df.at[index, '条类型'] = 42

                # 将修改后的数据写回当前工作表
                #print(f"将修改后的数据写入工作表: {sheet_name}")
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                #print(f"处理完成: {sheet_name}")

if __name__ == "__main__":
    file_path = 'result\\law_structure_format_num_ex.xlsx'
    print(f"开始处理文件: {file_path}")
    process_law_penalty(file_path)
    print("全部处理完成")