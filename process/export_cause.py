import pandas as pd
import re
import json
import logging
import argparse

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def format_clause(record):
    clause_str = f"第{record['条']}条"
    for part in ['款', '项', '目']:
        # 检查 record[part] 是否为 nan
        if pd.notna(record[part]):
            # 将符合条件的 record[part] 转换为整数类型
            clause_str += f"第{int(record[part])}{part}"
    return clause_str

def extract_clause_numbers(clause): 
    parts = re.findall(r'\d+', clause)
    return {
        '条': int(parts[0]) if parts else 0,
        '款': int(parts[1]) if len(parts) > 1 else 0,
        '项': int(parts[2]) if len(parts) > 2 else 0,
        '目': int(parts[3]) if len(parts) > 3 else 0
    }

def filter_records(df, conditions):
    filter_conditions = pd.Series([True] * len(df))
    for key, value in conditions.items():
        if value:
            filter_conditions &= (df[key] == value)
    return df[filter_conditions]

def get_related_records(df, clauses):
    records = []
    for clause in clauses:
        conditions = extract_clause_numbers(clause)
        sub_df = filter_records(df, conditions)
        for _, row in sub_df.iterrows():
            records.append({
                '条': row['条'], '款': row['款'], '项': row['项'], '目': row['目'],
                '内容': row['内容']
            })
    return records

# 获取违法行为和对应的罚则
def get_current_and_article_records(df, row):
    current_record = {'条': row['条'], '款': row['款'], '项': row['项'], '目': row['目'], '内容': row['内容']}
    # 筛选出同条的记录
    same_article_df = df[df['条'] == row['条']]
    if same_article_df.equals(df.loc[[row.name]]):  # 如果同条记录只有当前行
        # 修改此处逻辑，将当前行加入到数组中
        article_records = [{'条': row['条'], '款': row['款'], '项': row['项'], '目': row['目'], '内容': row['内容']}]
    else:
        # 筛选出“罚则”列为1的记录
        article_records = [
            {'条': r['条'], '款': r['款'], '项': r['项'], '目': r['目'], '内容': r['内容']}
            for _, r in same_article_df[same_article_df['罚则'] == 1].iterrows()
        ]
    return current_record, article_records

def get_penalty_records(df, row):
    penalty_column = next((col for col in df.columns if '增加处罚' in col), None)
    if penalty_column:
        penalty_value = row.get(penalty_column)
    else:
        penalty_value = None
    
    if pd.notna(penalty_value) and str(penalty_value).strip() != "":
        # 获取相关记录
        related_records = get_related_records(df, str(penalty_value).split('|'))
        # 筛选出“罚则”列为1的记录
        penalty_records = []
        for record in related_records:
            # 查找原数据框中对应记录的“罚则”列值
            match_row = df[
                (df['条'] == record['条']) &
                (df['款'] == record['款']) &
                (df['项'] == record['项']) &
                (df['目'] == record['目'])
            ]
            if not match_row.empty and (match_row['罚则'].values[0] == 1 
            or (match_row['条'].values[0] > 1000 and re.search(r'罚款|责令改正|没收|吊销', match_row['内容'].values[0]))):
                penalty_records.append(record)
        return penalty_records
    return []

def generate_text(violation_record, penalty_records, violation_records, new_records=[]):
    text_content = (
        "具体违法行为：\n" + f"{format_clause(violation_record)} {violation_record['内容']}\n" +
        "罚则：\n" + "\n".join(f"{format_clause(r)} {r['内容']}" for r in penalty_records) + "\n" +
        "违则：\n" + "\n".join(f"{format_clause(r)} {r['内容']}" for r in violation_records) + "\n"
    )
    if new_records:
        text_content += (
            "参考：\n" + "\n".join(f"{format_clause(r)} {r['内容']}" for r in new_records) + "\n"
        )
    return {"条文": text_content}

def process_sheet(df, output_file):
    all_results = []

    # 定义行政处罚相关的正则表达式模式
    PUNISHMENT_PATTERNS = [
        re.compile(r'(?!.*行政处分)罚款'),
        re.compile(r'(?!.*行政处分)没收(违法所得|非法财物)'),
        re.compile(r'(?!.*行政处分)责令(改正|停产停业|停止|关闭)'),
        re.compile(r'(?!.*行政处分)暂扣|吊销(?!\s*(处|罚))(.*(许可证|执照|资格证书|资质证书|驾驶证|驾照|执照))'),
        re.compile(r'(?!.*行政处分)拘留|强制报废|强制排除妨碍'),
        re.compile(r'(?!.*行政处分)降低资质等级'),
        re.compile(r'(?!.*行政处分)限制从业')
    ]

    try:
        # 规范化列名（去掉多余空格）
        df.columns = df.columns.str.strip()

        # 确保基本列存在
        expected_columns = ['条', '款', '项', '目', '内容', '可能违则', '对应违则', '增加处罚', '违法情形', '条类型']
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None

        # 用于记录已处理的条款，避免重复
        processed_clauses = set()

        # 第一部分：处理违法情形为 1 的记录
        for _, row in df[df['违法情形'] == 1].iterrows():
            clause_key = (row['条'], row['款'], row['项'], row['目'])
            processed_clauses.add(clause_key)

            A = row['内容']
            related_records = []
            if pd.notna(row['可能违则']) and row['可能违则'] != "":
                if isinstance(row['可能违则'], str):
                    violation_clauses = row['可能违则'].split('|')
                    for clause in violation_clauses:
                        A = A.replace(clause, "")
                    if row.get('可能度') != '1' or row.get('条类型') == 311:
                        related_records = get_related_records(df, violation_clauses)
                    else:
                        for clause in violation_clauses:
                            single_related_records = get_related_records(df, [clause])
                            current_record, article_records = get_current_and_article_records(df, row)
                            penalty_records = article_records + get_penalty_records(df, row)
                            result = generate_text(current_record, penalty_records, single_related_records)
                            all_results.append(result)
                        continue

            current_record, article_records = get_current_and_article_records(df, row)
            for record in article_records:
                clause_str = format_clause(record)
                A = A.replace(clause_str, "")

            penalty_records = article_records + get_penalty_records(df, row)
            for record in penalty_records:
                clause_str = format_clause(record)
                A = A.replace(clause_str, "")

            pattern = r'第\d+条(?:第\d+款)?(?:第\d+项)?(?:第\d+目)?'
            new_records = []
            matches = re.findall(pattern, A)
            for match in matches:
                full_match = ''.join(match.split())
                conditions = extract_clause_numbers(full_match)
                sub_df = filter_records(df, conditions)
                for _, r in sub_df.iterrows():
                    new_records.append({'条': r['条'], '款': r['款'], '项': r['项'], '目': r['目'], '内容': r['内容']})

            for records in [related_records, article_records, penalty_records]:
                for record in records:
                    content = record['内容']
                    if isinstance(content, str):
                        content_matches = re.findall(pattern, content)
                        for match in content_matches:
                            full_match = ''.join(match.split())
                            conditions = extract_clause_numbers(full_match)
                            sub_df = filter_records(df, conditions)
                            for _, r in sub_df.iterrows():
                                new_record = {'条': r['条'], '款': r['款'], '项': r['项'], '目': r['目'], '内容': r['内容']}
                                if new_record not in new_records:
                                    new_records.append(new_record)

            if not related_records:
                result = generate_text(current_record, penalty_records, [current_record], new_records)
            else:
                result = generate_text(current_record, penalty_records, related_records, new_records)
            all_results.append(result)

            # 第二部分：处理条类型为 2 且未被处理的记录 
            for index, row in df[df['条类型'] == 2].iterrows():
                clause_key = (row['条'], row['款'], row['项'], row['目'])
                if clause_key in processed_clauses:
                    continue

                content = row['内容']
                if not isinstance(content, str):
                    continue

                # 定义分隔符列表
                separators = ['。',  '；', '，']
                sentences = [content]  # 初始为完整内容
                # 循环应用每个分隔符
                for sep in separators:
                    temp_sentences = []
                    for sentence in sentences:
                        split_sentences = re.split(re.escape(sep), sentence)
                        temp_sentences.extend([s.strip() for s in split_sentences if s.strip()])
                    sentences = temp_sentences

                for i, sentence in enumerate(sentences):
                    # 检查是否包含处罚关键词
                    punishment_detected = False
                    matched_pattern = None
                    for pattern in PUNISHMENT_PATTERNS:
                        if pattern.search(sentence):
                            #print(f"句子 '{sentence}' 匹配处罚模式: {pattern.pattern}")
                            punishment_detected = True
                            matched_pattern = pattern.pattern
                            break

                    if punishment_detected:
                        # 检查之前的所有句子是否有以“的”结尾
                        has_de = False
                        if i > 0:
                            for prev_sentence in sentences[:i]:
                                last_char = prev_sentence[-1] if prev_sentence else ''
                                if last_char == '的':
                                    has_de = True
                                    break

                        if has_de:
                            clause_str = format_clause(row)
                            # 假设违则记录为空列表，可根据实际情况修改
                            violation_records = []
                            result = {
                                "条文": (
                                    "具体违法行为：\n" +
                                    f"{clause_str} {content}\n" +
                                    "罚则：\n" +
                                    f"{clause_str} {content}\n"
                                )
                            }
                            all_results.append(result)
                            processed_clauses.add(clause_key)
                            break

        # 直接将结果写入指定文件
        json_str = json.dumps(all_results, ensure_ascii=False, indent=4)
        output_file.write(json_str)
        output_file.write('\n\n')

    except Exception as e:
        print(f"处理工作表时出现错误: {e}")

def main(file_path, output_txt_path):
    try:
        # 加载 Excel 文件
        excel_file = pd.ExcelFile(file_path)

        # 打开指定的输出文件
        with open(output_txt_path, 'w', encoding='utf-8') as output_file:
            # 逐个处理每个工作表
            for sheet_name in excel_file.sheet_names:
                df = excel_file.parse(sheet_name)
                process_sheet(df, output_file)

        # 增加日志输出
        logging.info(f"结果已保存至: {output_txt_path}")

    except FileNotFoundError:
        print(f"文件 {file_path} 未找到，请检查文件路径。")
    except Exception as e:
        print(f"处理文件时出现错误: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export cause data from Excel to JSON and txt.')
    parser.add_argument('input_excel_path', type=str, help='Path to the input Excel file.')
    parser.add_argument('output_txt_path', type=str, help='Path to the output txt file.')
    args = parser.parse_args()

    file_path = args.input_excel_path
    output_txt_path = args.output_txt_path

    main(file_path, output_txt_path)