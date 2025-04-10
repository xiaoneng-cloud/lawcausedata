import pandas as pd
import re
import os
import logging
from openpyxl.styles import Alignment

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# 中文数字转阿拉伯数字的函数 - 修正版
def chinese_to_arabic(chinese_str):
    chinese_dict = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '万': 10000, '亿': 100000000,
        '两': 2
    }
    
    # 处理括号格式
    bracket_pattern = r'第\(([零一二三四五六七八九十百千万亿两]+)\)([条款项目])'
    def replace_brackets(match):
        num = match.group(1)
        unit = match.group(2)
        return f'第{num}{unit}'
    result = re.sub(bracket_pattern, replace_brackets, chinese_str)
    
    patterns = [
        r'第([零一二三四五六七八九十百千万亿两]+)条',
        r'第([零一二三四五六七八九十百千万亿两]+)款',
        r'第([零一二三四五六七八九十百千万亿两]+)项',
        r'第([零一二三四五六七八九十百千万亿两]+)目'
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.finditer(pattern, result)
        for match in matches:
            chinese_num = match.group(1)
            full_match = match.group(0)
            start, end = match.span()
            unit_type = full_match[len('第') + len(chinese_num):]
            
            # 处理中文数字
            if chinese_num == '十':
                total = 10
            elif chinese_num.startswith('十'):
                total = 10 + chinese_dict[chinese_num[1]]
            elif chinese_num.endswith('十'):
                total = chinese_dict[chinese_num[0]] * 10
            else:
                total = 0
                temp = 0  # 用于累积当前单位的数字
                unit = 1  # 当前单位
                for c in reversed(chinese_num):
                    if c in '零一二三四五六七八九两':
                        temp = chinese_dict[c] * unit
                    elif c in '十百千万亿':
                        if temp == 0:  # 处理单独的“十”、“百”等
                            temp = 1 * unit
                        total += temp
                        unit = chinese_dict[c]
                        temp = 0
                if temp != 0:  # 处理剩余的最高位
                    total += temp
            
            arabic_num = total
            replacement = f'第{arabic_num}{unit_type}'
            if isinstance(arabic_num, int):
                all_matches.append((start, end, replacement))
    
    all_matches.sort(key=lambda x: x[0], reverse=True)
    for start, end, replacement in all_matches:
        result = result[:start] + replacement + result[end:]
    
    return result

# 处理"本条"、"本款"引用
def handle_self_references(text, current_tiao, current_kuan):
    # 使用正则表达式的负向前瞻确保不会匹配到"本条例"等
    new_text = re.sub(r'本条(?!例)', f'第{current_tiao}条', text)
    new_text = re.sub(r'本款', f'第{current_tiao}条第{current_kuan}款', new_text)
    return new_text

# 处理"前款"或"前X款"引用
def handle_previous_references(text, current_tiao, current_kuan):
    # 处理"前款"
    text = re.sub(r'前款', f'第{current_tiao}条第{current_kuan - 1}款', text)
    # 处理"前X款"
    def replace_previous_x_kuan(match):
        x = int(match.group(1))
        previous_kuan = []
        for i in range(current_kuan - x, current_kuan):
            if i > 0:  # 确保款号大于0
                previous_kuan.append(f'第{current_tiao}条第{i}款')
        return '、'.join(previous_kuan)

    text = re.sub(r'前(\d+)款', replace_previous_x_kuan, text)
    return text

# 处理范围引用（使用"至"连接）
def handle_range_references(text):
    patterns = [
        r'(第\d+条)至(第\d+条)',  # 条范围
        r'(第\d+条第\d+款)至(第\d+条第\d+款)',  # 款范围
        r'(第\d+条第\d+款第\d+项)至(第\d+条第\d+款第\d+项)',  # 完整项范围
        r'(第\d+条第\d+款第\d+项)至第(\d+)项',  # 简写项范围
        r'(第\d+条第\d+款第\d+项第\d+目)至(第\d+条第\d+款第\d+项第\d+目)'  # 目范围
    ]
    
    for pattern in patterns:
        matches = list(re.finditer(pattern, text))
        for match in reversed(matches):
            start_ref = match.group(1)
            end_ref = match.group(2)
            full_match = match.group(0)
            print(text)

            if '目' in start_ref:  # 处理到"目"级别
                start_tiao = int(re.search(r'第(\d+)条', start_ref).group(1))
                start_kuan = int(re.search(r'第\d+条第(\d+)款', start_ref).group(1))
                start_xiang = int(re.search(r'第\d+条第\d+款第(\d+)项', start_ref).group(1))
                start_mu = int(re.search(r'第\d+条第\d+款第\d+项第(\d+)目', start_ref).group(1))
                
                end_tiao = int(re.search(r'第(\d+)条', end_ref).group(1))
                end_kuan = int(re.search(r'第\d+条第(\d+)款', end_ref).group(1))
                end_xiang = int(re.search(r'第\d+条第\d+款第(\d+)项', end_ref).group(1))
                end_mu = int(re.search(r'第\d+条第\d+款第\d+项第(\d+)目', end_ref).group(1))
                
                if start_tiao == end_tiao and start_kuan == end_kuan and start_xiang == end_xiang:
                    expanded_refs = []
                    for mu in range(start_mu, end_mu + 1):
                        expanded_refs.append(f'第{start_tiao}条第{start_kuan}款第{start_xiang}项第{mu}目')
                    expanded_text = '、'.join(expanded_refs)
                    text = text.replace(full_match, expanded_text)
            
            elif pattern == r'(第\d+条第\d+款第\d+项)至第(\d+)项':  # 处理简写项范围
                start_tiao = int(re.search(r'第(\d+)条', start_ref).group(1))
                start_kuan = int(re.search(r'第\d+条第(\d+)款', start_ref).group(1))
                start_xiang = int(re.search(r'第\d+条第\d+款第(\d+)项', start_ref).group(1))
                end_xiang = int(end_ref)  # end_ref 已经是数字，直接使用
                
                expanded_refs = []
                for xiang in range(start_xiang, end_xiang + 1):
                    expanded_refs.append(f'第{start_tiao}条第{start_kuan}款第{xiang}项')
                expanded_text = '、'.join(expanded_refs)
                text = text.replace(full_match, expanded_text)
            
            elif '项' in start_ref:  # 处理完整项范围
                start_tiao = int(re.search(r'第(\d+)条', start_ref).group(1))
                start_kuan = int(re.search(r'第\d+条第(\d+)款', start_ref).group(1))
                start_xiang = int(re.search(r'第\d+条第\d+款第(\d+)项', start_ref).group(1))
                
                end_tiao = int(re.search(r'第(\d+)条', end_ref).group(1))
                end_kuan = int(re.search(r'第\d+条第(\d+)款', end_ref).group(1))
                end_xiang = int(re.search(r'第\d+条第\d+款第(\d+)项', end_ref).group(1))
                
                if start_tiao == end_tiao and start_kuan == end_kuan:
                    expanded_refs = []
                    for xiang in range(start_xiang, end_xiang + 1):
                        expanded_refs.append(f'第{start_tiao}条第{start_kuan}款第{xiang}项')
                    expanded_text = '、'.join(expanded_refs)
                    text = text.replace(full_match, expanded_text)
            
            elif '款' in start_ref:  # 处理到"款"级别
                start_tiao = int(re.search(r'第(\d+)条', start_ref).group(1))
                start_kuan = int(re.search(r'第\d+条第(\d+)款', start_ref).group(1))
                
                end_tiao = int(re.search(r'第(\d+)条', end_ref).group(1))
                end_kuan = int(re.search(r'第\d+条第(\d+)款', end_ref).group(1))
                
                if start_tiao == end_tiao:
                    expanded_refs = []
                    for kuan in range(start_kuan, end_kuan + 1):
                        expanded_refs.append(f'第{start_tiao}条第{kuan}款')
                    expanded_text = '、'.join(expanded_refs)
                    text = text.replace(full_match, expanded_text)
            
            else:  # 处理"条"级别
                start_tiao = int(re.search(r'第(\d+)条', start_ref).group(1))
                end_tiao = int(re.search(r'第(\d+)条', end_ref).group(1))
                
                expanded_refs = []
                for tiao in range(start_tiao, end_tiao + 1):
                    expanded_refs.append(f'第{tiao}条')
                expanded_text = '、'.join(expanded_refs)
                text = text.replace(full_match, expanded_text)
    
    return text
    
#补全款项，针对比如：违反第1款第1项、第5项规定
def handle_standalone_clauses(content, df, current_tiao):
    if not isinstance(content, str):
        return str(content) if content is not None else ""

    try:
        # 定义匹配模式
        kuan_pattern = r'第(\d+)款'  # 匹配“第X款”
        xiang_pattern = r'第(\d+)项'  # 匹配“第X项”
        tiao_pattern = r'第(\d+)条'  # 匹配“第X条”
        tiao_kuan_pattern = r'第(\d+)条第(\d+)款'  # 匹配“第Z条第Y款”
        tiao_kuan_xiang_pattern = r'第(\d+)条第(\d+)款第(\d+)项'  # 匹配“第Z条第Y款第X项”

        # 查找所有“第X款”和“第X项”
        kuan_matches = list(re.finditer(kuan_pattern, content))
        xiang_matches = list(re.finditer(xiang_pattern, content))
        
        # 合并所有匹配，按位置从后向前处理
        all_matches = []
        for match in kuan_matches:
            all_matches.append(('kuan', match))
        for match in xiang_matches:
            all_matches.append(('xiang', match))
        all_matches.sort(key=lambda x: x[1].start(), reverse=True)

        # 处理每个匹配
        for match_type, match in all_matches:
            full_text = match.group(0)  # 如“第5款”或“第5项”
            num = match.group(1)       # 如“5”
            start_pos = match.start()  # 匹配起始位置
            
            # 获取匹配前的子字符串
            substring_before = content[:start_pos]
            
            if match_type == 'kuan':
                # 检查“第X款”前是否紧跟“第Y条”
                if re.search(tiao_pattern + r'\s*$', substring_before):
                    continue
                
                # 向前查找最近的“第Y条”
                tiao_matches = list(re.finditer(tiao_pattern, substring_before))
                if tiao_matches:
                    last_tiao_match = tiao_matches[-1]
                    tiao_num = last_tiao_match.group(1)
                    replacement = f'第{tiao_num}条第{num}款'
                    content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                else:
                    # 查找同条号的第一款内容
                    first_kuan = df[(df['条'] == current_tiao) & (df['款'] == 1)]
                    if not first_kuan.empty and pd.notna(first_kuan.iloc[0]['内容']):
                        first_kuan_content = str(first_kuan.iloc[0]['内容'])
                        # 查找第一个独立的“第Z条”（后面不紧跟“第X款”）
                        tiao_matches_in_first = list(re.finditer(tiao_pattern, first_kuan_content))
                        for tiao_match in tiao_matches_in_first:
                            tiao_num = tiao_match.group(1)
                            tiao_end_pos = tiao_match.end()
                            if not re.search(r'第\d+款', first_kuan_content[tiao_end_pos:tiao_end_pos+5]):  # 检查后5个字符
                                replacement = f'第{tiao_num}条第{num}款'
                                content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                                break
                            else:
                                logging.info(f"独立款项 '{full_text}' 没有找到匹配的条号前级，位置: {start_pos}")
                    else:
                        logging.info(f"独立款项 '{full_text}' 没有找到匹配的条号前级，位置: {start_pos}")

            elif match_type == 'xiang':
                # 检查“第X项”前是否已经是“第Z条第Y款第X项”完整模式（包括后面有逗号的情况）
                recent_text = substring_before[-20:]  # 检查前20个字符，避免过长
                if re.search(tiao_kuan_pattern + r'\s*,?\s*$', recent_text):
                    continue  # 如果前文已经是完整引用，跳过处理

                # 情况1：检查“第X项”前是否有“第Z条第Y款”（如“第40条第1款 第5项”）
                tiao_kuan_matches = list(re.finditer(tiao_kuan_pattern, substring_before))
                if tiao_kuan_matches:
                    # 取最近的“第Z条第Y款”
                    last_tiao_kuan_match = tiao_kuan_matches[-1]
                    tiao_num = last_tiao_kuan_match.group(1)
                    kuan_num = last_tiao_kuan_match.group(2)
                    # 检查“第Z条第Y款”是否属于一个完整引用的一部分
                    tiao_kuan_end_pos = last_tiao_kuan_match.end()
                    # 如果“第Z条第Y款”后面紧跟“第W项”，说明它已经是完整引用的一部分
                    if re.search(tiao_kuan_xiang_pattern + r'\s*,?\s*$', substring_before[:tiao_kuan_end_pos]):
                        continue  # 跳过处理，避免重复补全
                    # 否则，使用最近的“第Z条第Y款”补全
                    replacement = f'第{tiao_num}条第{kuan_num}款第{num}项'
                    content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                    continue  # 已处理，跳过后续逻辑
                
                # 情况2：检查“第X项”前是否紧跟“第Y款”（如“第2款 第5项”）
                kuan_matches_before = list(re.finditer(kuan_pattern, substring_before))
                if kuan_matches_before:
                    last_kuan_match = kuan_matches_before[-1]
                    kuan_num = last_kuan_match.group(1)
                    # 查找“第Y款”前的“第Z条”
                    kuan_start_pos = last_kuan_match.start()
                    tiao_matches_before_kuan = list(re.finditer(tiao_pattern, substring_before[:kuan_start_pos]))
                    if tiao_matches_before_kuan:
                        last_tiao_match = tiao_matches_before_kuan[-1]
                        tiao_num = last_tiao_match.group(1)
                        replacement = f'第{tiao_num}条第{kuan_num}款第{num}项'
                    else:
                        replacement = f'第{kuan_num}款第{num}项'
                    content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                    continue  # 已处理，跳过后续逻辑
                
                # 情况3：前文无“第Y款”，需要推断
                first_kuan = df[(df['条'] == current_tiao) & (df['款'] == 1)]
                if not first_kuan.empty and pd.notna(first_kuan.iloc[0]['内容']) and '下列' in first_kuan.iloc[0]['内容']:
                    first_kuan_content = str(first_kuan.iloc[0]['内容'])
                    # 寻找“第X条”或者“第X条第X款”
                    tiao_matches = list(re.finditer(tiao_pattern, first_kuan_content))
                    kuan_tiao_matches = list(re.finditer(r'第(\d+)条第(\d+)款', first_kuan_content))
                    if kuan_tiao_matches:
                        last_kuan_tiao_match = kuan_tiao_matches[-1]
                        tiao_num = last_kuan_tiao_match.group(1)
                        kuan_num = last_kuan_tiao_match.group(2)
                        replacement = f'第{tiao_num}条第{kuan_num}款第{num}项'
                        content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                    elif tiao_matches:
                        last_tiao_match = tiao_matches[-1]
                        tiao_num = last_tiao_match.group(1)
                        replacement = f'第{tiao_num}条第1款第{num}项'
                        content = content[:start_pos] + replacement + content[start_pos + len(full_text):]
                    else:
                        logging.info(f"独立款项 '{full_text}' 没有找到匹配的条号或款号前级，位置: {start_pos}")
                else:
                    logging.info(f"独立款项 '{full_text}' 没有找到匹配的款号前级，位置: {start_pos}")

    except Exception as e:
        logging.error(f"处理单独款项时出错: {str(e)}")
    
    return content

def handle_standalone_sections(content):
    if not isinstance(content, str):
        return str(content) if content is not None else ""
    try:
        # 查找所有"第X款"
        kuan_pattern = r'第(\d+)款'
        kuan_matches = list(re.finditer(kuan_pattern, content))
        
        # 从后向前处理每个匹配
        for match in reversed(kuan_matches):
            kuan_text = match.group(0)
            kuan_num = match.group(1)
            start_pos = match.start()
            
            # 检查前面是否紧跟"第X条"
            tiao_pattern = r'第(\d+)条'
            substring_before = content[:start_pos]
            if re.search(tiao_pattern + r'\s*$', substring_before):
                continue
            
            # 向前查找最近的"第X条"
            tiao_matches = list(re.finditer(tiao_pattern, substring_before))
            
            if tiao_matches:
                last_tiao_match = tiao_matches[-1]
                tiao_num = last_tiao_match.group(1)
                replacement = f'第{tiao_num}条第{kuan_num}款'
                content = content[:start_pos] + replacement + content[start_pos + len(kuan_text):]
    
    except Exception as e:
        print(f"处理单独段落时出错: {str(e)}")
        pass
    
    return content

# 新增函数：处理“第X条第X项”为“第X第一条第X项”
def handle_article_item_reference(content):
    pattern = r'第(\d+)条第(\d+)项'
    def replace_match(match):
        tiao_num = match.group(1)
        xiang_num = match.group(2)
        return f'第{tiao_num}条第1款第{xiang_num}项'
    return re.sub(pattern, replace_match, content)

# 主函数处理Excel文件
def process_legal_document(file_path, output_path):
    # 读取Excel文件
    xls = pd.ExcelFile(file_path)
    # 创建一个ExcelWriter对象以写入处理后的数据
    with pd.ExcelWriter(output_path) as writer:
        # 遍历所有sheet
        for sheet_name in xls.sheet_names:
            # 读取当前sheet
            df = xls.parse(sheet_name)

            # 确保必要的列存在
            required_columns = ['条', '款', '项', '目', '内容']
            if not all(col in df.columns for col in required_columns):
                print(f"Sheet {sheet_name} 缺少必要的列，跳过处理")
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                continue

            # 处理每一行数据
            for idx, row in df.iterrows():
                content = row['内容']
                current_tiao = row['条']
                current_kuan = row['款'] if not pd.isna(row['款']) else 0
                current_xiang = row['项'] if not pd.isna(row['项']) else 0
                current_mu = row['目'] if not pd.isna(row['目']) else 0
                #print(f"处理前第 {idx} 行内容: {content}")

                # 步骤1：将中文数字转换为阿拉伯数字
                content = chinese_to_arabic(content)

                # 步骤2：处理"本条"、"本款"引用
                content = handle_self_references(content, current_tiao, current_kuan)

                # 步骤3：处理"前款"或"前X款"引用
                if current_kuan > 0:  # 确保是在有款号的情况下处理
                    content = handle_previous_references(content, current_tiao, current_kuan)               

                # 步骤5：处理文本中的单独"第X款"
                content = handle_standalone_sections(content)

                 # 步骤5.1：处理“第X条第X项”为“第X条第1款第X项”
                content = handle_article_item_reference(content)


                # 步骤5.2：处理单独的“第X款”或“第X项”，补全上下文
                content = handle_standalone_clauses(content, df, current_tiao)

               

                # 步骤6：如果paragraph_num和item_num都为0，查找同号下的罚则为1的记录
                if current_kuan == 0 and current_xiang == 0:
                    # 查找同号下的罚则为1的记录
                    penalty_records = df[
                        (df['条'] == current_tiao) & 
                        (df['罚则'] == 1)
                    ]
                    
                    if not penalty_records.empty:
                        # 获取所有罚则记录的款号
                        penalty_kuans = penalty_records['款'].dropna().astype(int).tolist()
                        if penalty_kuans:
                            # 将款号排序
                            penalty_kuans.sort()
                            # 构建罚则引用文本
                            penalty_refs = [f'第{current_tiao}条第{kuan}款' for kuan in penalty_kuans]
                            # 用"|"连接所有罚则引用
                            penalty_text = '|'.join(penalty_refs)
                            # 将罚则引用添加到内容末尾
                            content = f"{content} {penalty_text}"

                 # 步骤4：处理范围引用（使用"至"连接）
                content = handle_range_references(content)
                # 更新处理后的内容
                df.at[idx, '内容'] = content
                #print(f"处理后第 {idx} 行内容: {content}")

            # 将处理后的数据写入新的Excel文件
            df.to_excel(writer, sheet_name=sheet_name, index=False) 

        
            
            

    print(f"处理完成，结果已保存至: {output_path}")

# 使用示例
if __name__ == "__main__":
    input_file = "D:\\lawproject\\test\\result\\law_structure.xlsx"
    output_file = "D:\\lawproject\\test\\result\\law_structure_format_num.xlsx"
    if os.path.exists(input_file):
        process_legal_document(input_file, output_file)
    else:
        print(f"输入文件 {input_file} 不存在，请检查文件路径。")