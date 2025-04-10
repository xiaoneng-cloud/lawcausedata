import pandas as pd
import openpyxl
import json
import os
import logging
from cozepy import COZE_CN_BASE_URL, Coze, TokenAuth, Message, ChatEventType
from concurrent.futures import ThreadPoolExecutor, as_completed

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='process_clauses_to_excel.log'
)

def parse_clause(clause_str):
    """解析条款字符串，返回条、款、项、目，处理空格和格式不一致"""
    if not clause_str or pd.isna(clause_str):
        return None, None, None, None
    
    clause_str = str(clause_str).replace(".1", "").replace(" ", "").strip()
    if "《" in clause_str and "》" in clause_str:
        clause_str = clause_str.split("》")[1]
    
    parts = clause_str.split("第")
    strip, kuan, xiang, mu = None, None, None, None
    
    for part in parts[1:]:
        if part.endswith("条"):
            strip = part[:-1]
        elif part.endswith("款"):
            kuan = part[:-1]
        elif part.endswith("项"):
            xiang = part[:-1]
        elif part.endswith("目"):
            mu = part[:-1]
    
    strip = int(strip) if strip else 0
    kuan = int(kuan) if kuan else 0
    xiang = int(xiang) if xiang else 0
    mu = int(mu) if mu else 0
    
    return strip, kuan, xiang, mu

def find_content_in_law_structure(strip, kuan, xiang, mu, law_df):
    """查找条款内容，一律使用‘内容’字段"""
    if xiang != 0 or mu != 0:
        query = "条 == @strip and 款 == @kuan and 项 == @xiang and 目 == @mu"
    elif kuan != 0:
        query = "条 == @strip and 款 == @kuan and 项 == 0 and 目 == 0"
    else:
        return None
    
    results = law_df.query(query)
    if results.empty:
        return None
    return results["内容"].iloc[0]

def find_related_law(strip, kuan, xiang, mu, law_df):
    """查找条款对应的关联法律"""
    query = "条 == @strip and 款 == @kuan and 项 == @xiang and 目 == @mu"
    results = law_df.query(query)
    if results.empty:
        return None
    return results.iloc[0]["关联法律"] if "关联法律" in results.columns and not pd.isna(results.iloc[0]["关联法律"]) else None

def format_clause(strip, kuan, xiang, mu, related_law=None):
    """格式化条款字符串，支持带关联法律"""
    clause = f"第{strip}条"
    if kuan:
        clause += f"第{kuan}款"
    if xiang:
        clause += f"第{xiang}项"
    if mu:
        clause += f"第{mu}目"
    if related_law:
        clause = f"《{related_law}》{clause}"
    return clause

def process_clauses_to_string(clauses_str, law_structure_df):
    """处理条款字符串，返回‘条款 + 内容’格式的字符串，多项用分号连接，并返回解析后的条款列表"""
    try:
        clauses = str(clauses_str).split("|")
        clause_content_pairs = []
        clause_numbers = []
        
        for clause in clauses:
            strip, kuan, xiang, mu = parse_clause(clause)
            if not strip:
                continue
            if strip > 10000:
                related_law = find_related_law(strip, kuan, xiang, mu, law_structure_df)
                adjusted_strip = strip - (strip // 10000) * 10000
                formatted_clause = format_clause(adjusted_strip, kuan, xiang, mu, related_law)
            else:
                formatted_clause = format_clause(strip, kuan, xiang, mu)
            content = find_content_in_law_structure(strip, kuan, xiang, mu, law_structure_df)
            if content:
                clause_content_pairs.append(f"{formatted_clause}    {content}")
                clause_numbers.append((strip, kuan, xiang, mu))
        
        return ";".join(clause_content_pairs) if clause_content_pairs else None, clause_numbers
    except Exception as e:
        logging.error(f"Error processing clauses: {clauses_str}. Error message: {e}")
        return None, []

def are_clauses_equal(nums1, nums2):
    """检查两个条款列表是否完全相同（假设单条款情况）"""
    if not nums1 or not nums2:
        return False
    return len(nums1) == 1 and len(nums2) == 1 and nums1[0] == nums2[0]

def flatten_json(data, new_clause, clause_id):
    """将嵌套的JSON展平为表格格式"""
    flattened_records = []
    for item in data:
        situation = item.get("情形", "")
        penalties = item.get("处罚", [])
        
        for penalty in penalties:
            record = {
                "条款": new_clause,
                "情形": situation,
                "处罚类型": penalty.get("处罚类型", ""),
                "递进处罚": penalty.get("递进处罚", ""),
                "行业": penalty.get("行业", ""),
                "主体级别": penalty.get("主体级别", ""),
                "处罚对象": penalty.get("处罚对象", ""),
                "处罚明细": penalty.get("处罚明细", ""),
                "行政行为": penalty.get("行政行为", ""),
                "编号": clause_id
            }
            flattened_records.append(record)
    return flattened_records

def process_row(coze, bot_id, user_id, row, law_structure_df):
    """处理单条记录并发送API请求"""
    try:
        behavior_str, behavior_nums = process_clauses_to_string(row["行为"], law_structure_df)
        penalty_str, penalty_nums = process_clauses_to_string(row["罚则"], law_structure_df)
        violation_str, violation_nums = process_clauses_to_string(row["违则"], law_structure_df)
        clause_id = row['编号']
        cause = str(row["事由"])

        # 规则1：如果罚则为 null，则跳过
        if not penalty_str:
            return None, clause_id

        # 创建 JSON 条目
        entry = {"事由": cause}
        behavior_equals_penalty = are_clauses_equal(behavior_nums, penalty_nums)
        violation_equals_penalty = are_clauses_equal(violation_nums, penalty_nums)

        if behavior_equals_penalty or violation_equals_penalty:
            entry["罚则"] = penalty_str
        else:
            entry["行为"] = behavior_str
            if violation_str:
                entry["违则"] = violation_str
            entry["罚则"] = penalty_str

        # 发送 API 请求
        api_content = json.dumps(entry, ensure_ascii=False)
        logging.info(f"Sending API request for 编号 {clause_id}: {api_content}")
        full_response = ""
        for event in coze.chat.stream(
            bot_id=bot_id,
            user_id=user_id,
            additional_messages=[Message.build_user_question_text(api_content)],
        ):
            if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                full_response += event.message.content
            if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                logging.debug(f"Token usage for {clause_id}: {event.chat.usage.token_count}")

        # 解析返回的 JSON
        json_data = None
        try:
            data = json.loads(full_response)
            if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                json_data = data
        except json.JSONDecodeError:
            try:
                data = json.loads(full_response.strip().strip('```json').strip('```'))
                if isinstance(data, list) and all(isinstance(item, dict) for item in data):
                    json_data = data
            except json.JSONDecodeError:
                logging.error(f"未找到有效的JSON数据 for 编号 {clause_id}")

        if json_data:
            return flatten_json(json_data, penalty_str, clause_id), None
        else:
            return None, clause_id  # 返回 None 和 clause_id，表示需要删除

    except Exception as e:
        logging.error(f"处理 编号 {clause_id} 时发生错误: {e}")
        return None, clause_id

def main():
    # Coze API 配置
    coze_api_token = 'pat_sSMcUXlyKiF37mbQ5VmCK2ufcXFLamnAgUkzDtUbz4aWZp0uyQafjkUPnOLt6z8M'
    coze_api_base = COZE_CN_BASE_URL
    coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)
    bot_id = '7478622295620861964'
    user_id = 'zzs'

    # 文件路径
    law_ai_result_file = "result\\LawAIResult.xlsx"
    law_structure_file = "result\\law_structure_format_num_ex.xlsx"
    law_cause_file = "result\\law_cause.xlsx"
    output_file = "result\\law_punish.xlsx"

    # 加载法律结构文件
    wb_law_structure = openpyxl.load_workbook(law_structure_file)
    law_structure_sheets = {sheet.title: pd.read_excel(law_structure_file, sheet_name=sheet.title) 
                           for sheet in wb_law_structure.worksheets}

    # 创建 Excel Writer
    writer = pd.ExcelWriter(output_file, engine='openpyxl')
    has_data = False
    clauses_to_delete = set()

    # 读取 LawAIResult.xlsx 获取编号
    law_ai_df = pd.read_excel(law_ai_result_file, sheet_name=None)

    # 处理 law_cause.xlsx
    law_cause_df = pd.read_excel(law_cause_file, sheet_name=None)
    for sheet_name, df in law_cause_df.items():
        if sheet_name not in law_structure_sheets:
            logging.warning(f"Skipping sheet {sheet_name}: no matching sheet in {law_structure_file}")
            continue

        required_columns = ["事由", "行为", "罚则", "违则", "编号"]
        if not all(col in df.columns for col in required_columns):
            logging.warning(f"Skipping sheet {sheet_name}: missing required columns")
            continue

        law_structure_df = law_structure_sheets[sheet_name]
        sheet_results = []

        # 使用线程池处理记录
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_row = {executor.submit(process_row, coze, bot_id, user_id, row, law_structure_df): row 
                             for _, row in df.iterrows()}
            
            for future in as_completed(future_to_row):
                result, clause_id = future.result()
                if result:
                    sheet_results.extend(result)
                    has_data = True
                if clause_id:
                    clauses_to_delete.add(clause_id)

        # 将结果写入 Sheet
        if sheet_results:
            result_df = pd.DataFrame(sheet_results)
            column_order = ["编号", "条款", "情形", "处罚类型", "递进处罚", "行业", "主体级别", "处罚对象", "处罚明细", "行政行为"]
            result_df = result_df[column_order]
            result_df.to_excel(writer, sheet_name=sheet_name, index=False)
            logging.info(f"Sheet {sheet_name} 的分析结果已保存")

    # 保存 law_punish.xlsx
    if has_data:
        writer.close()
        logging.info(f"所有分析结果已保存到 {output_file}")
    else:
        writer.close()
        logging.info("没有生成任何记录")

    # 删除 law_cause.xlsx 中对应的记录
    if clauses_to_delete:
        processed_sheets = {}
        has_data = False
        for sheet_name, df in law_cause_df.items():
            if '编号' in df.columns:
                filtered_df = df[~df['编号'].isin(clauses_to_delete)]
                if not filtered_df.empty:
                    processed_sheets[sheet_name] = filtered_df
                    has_data = True
                    logging.info(f"Sheet {sheet_name} 已删除 {len(df) - len(filtered_df)} 条记录")
                else:
                    logging.warning(f"Sheet {sheet_name} 无剩余记录，将跳过")
            else:
                logging.warning(f"Sheet {sheet_name} 无 '编号' 列，跳过处理")

        if has_data:
            with pd.ExcelWriter(law_cause_file, engine='openpyxl') as writer:
                for sheet_name, df in processed_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            logging.info(f"已更新 {law_cause_file}，删除了 {len(clauses_to_delete)} 条记录")
        else:
            os.remove(law_cause_file)
            logging.info(f"无有效数据，删除 {law_cause_file}")

if __name__ == "__main__":
    main()