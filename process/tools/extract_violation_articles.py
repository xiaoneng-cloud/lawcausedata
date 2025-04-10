import re

# 基础中文数字映射
BASE_NUM = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10, '百': 100, '千': 1000
}
PENALTY_TYPES = ["处罚", "罚款", "改正", "吊销", "责令", "逾期", "限期", "处**罚款", "没收", "降低资质", "查封", "强制", "情节**", "通报批评", "处分", "依法给予"]


def process_standalone_sections(array_B):
    """
    处理单独的"第X款"，将其与前面的"第X条"关联
    """
    #print("\n开始处理单独的款号...")
    result = []
    last_article = None
    
    for clause in array_B:
        # 如果当前条款有Article，更新last_article
        if 'Article' in clause:
            last_article = clause['Article']
            result.append(clause)
            #print(f"找到条款号：{last_article}")
        # 如果当前条款只有Section，且前面有last_article
        elif 'Section' in clause and last_article is not None:
            # 创建新的条款对象，包含Article和Section
            new_clause = {
                'Article': last_article,
                'Section': clause['Section'],
                'Item': clause.get('Item'),
                'Subitem': clause.get('Subitem')
            }
            result.append(new_clause)
            #print(f"将单独的款号 {clause['Section']} 关联到条款号 {last_article}")
        else:
            # 其他情况直接添加
            result.append(clause)
    
    #print(f"处理后的条款数组：{result}")
    return result

def get_clause_array(text):
    """
    从文本中提取条款数组，比如提取出"第X条"、"第X条第Y款"、"第X条第Y款第Z项"等
    参数:
        text (str): 需要处理的文本
    返回:
        list: 包含提取到的条款的数组
    """
    #print(f"\n开始处理文本：{text}")
    
    # Use regex to match "Article X", "Section X", "Item X" with Arabic numerals
    pattern = r'第\d+(?:条(?:第\d+款(?:第\d+项)?)?|款(?:第\d+项)?|项)'
    array_A = re.findall(pattern, text)
    #print(f"提取到的条款数组：{array_A}")
    array_B = []
    last_tiao = None
    last_kuan = None
    
    for clause in array_A:
        obj = {}
        tiao_match = re.search(r'第(\d+)条', clause)
        kuan_match = re.search(r'第(\d+)款', clause)
        xiang_match = re.search(r'第(\d+)项', clause)
        
        if tiao_match:
            obj['Article'] = tiao_match.group(1)
            last_tiao = obj['Article']
            last_kuan = None
            #print(f"提取到条款：{obj['Article']}")

        if kuan_match:
            obj['Section'] = kuan_match.group(1)
            if 'Article' not in obj and last_tiao:
                obj['Article'] = last_tiao
            last_kuan = obj['Section']
            #print(f"提取到款：{obj['Section']}")

        if xiang_match:
            obj['Item'] = xiang_match.group(1)
            if 'Article' not in obj and last_tiao:
                obj['Article'] = last_tiao
            if 'Section' not in obj and last_kuan:
                obj['Section'] = last_kuan
            #print(f"提取到项：{obj['Item']}")
        array_B.append(obj)
    #print(f"提取到的条款数组：{array_B}")
    
    # 处理单独的款号，有些文本中是单独的"第X款"，需要将其与前面的"第X条"关联
    array_B = process_standalone_sections(array_B)
    
    return array_B
    
#找出罚则词，保留该词之前的部分，如果前面有情形的描述，则保留情形描述之前的部分
def find_associated_body(text):
    min_index = len(text)
    split_word = None
    # 遍历所有罚则词，找出最靠前出现的词及其位置
    for penalty in PENALTY_TYPES:
        index = text.find(penalty)
        if index != -1 and index < min_index:
            min_index = index
            split_word = penalty

    # 如果找到了罚则词，保留该词之前的部分
    if split_word:
        part_before_penalty = text[:min_index]
        # 定义情形描述的正则表达式模式
        pattern = r'情节[^严重]*严重|造成[^后果]*后果'
        match = re.search(pattern, part_before_penalty)
        if match:
            return part_before_penalty[:match.start()]
        return part_before_penalty
    # 若未找到罚则词，保留全部文本
    return text

    
def check_text_pattern(text):
    """
    在文本中检查包含关键词的句子前面是否有以"的"结尾的句子
    
    参数:
        text (str): 需要分析的文本
    
    返回:
        int: 如果包含关键词的句子前面有以"的"结尾的句子，返回1；否则返回0
    """
    # 以标点符号分割文本成数组
    punctuations = ['。', '！', '？', '；', '，', '.', '!', '?', ';', ',']
    segments = []
    current_segment = ""
    
    for char in text:
        current_segment += char
        if char in punctuations:
            segments.append(current_segment.strip())
            current_segment = ""
    
    # 如果最后一段没有标点符号结尾，也添加到数组中
    if current_segment.strip():
        segments.append(current_segment.strip())
    
    # 查找包含关键词的句子
    for i, segment in enumerate(segments):
        # 检查是否包含任一关键词
        if any(keyword in segment for keyword in PENALTY_TYPES):
            # 如果关键词出现在第一句话中，前面没有句子，直接返回0
            if i == 0:
                return 0
                
            # 检查前面的句子是否有以"的"结尾的
            for j in range(i):
                prev_segment = segments[j]
                # 去除标点符号后检查是否以"的"结尾
                clean_segment = prev_segment
                while clean_segment and clean_segment[-1] in punctuations:
                    clean_segment = clean_segment[:-1]
                
                if clean_segment.endswith("的"):
                    return 1
    
    return 0
# 定义正则表达式模式的函数
def get_violation_pattern():
    pattern = r'(?:未依照|依照|未经许可|未按照|违反)\s*(?:本法|本条例|本办法)?\s*((?:(?:第\d+条)?(?:第\d+款)?(?:第\d+项)?(?:、(?:第\d+条)?(?:第\d+款)?(?:第\d+项)?)*))|' \
          r'有\s*(?:本法)?\s*((?:第\d+条(?:第\d+款)?(?:第\d+项)?(?:、第\d+条(?:第\d+款)?(?:第\d+项)?)*)).*?行为.*?的，'
    return pattern


if __name__ == "__main__":
    # 测试文本
    test_text = "违反第三十七条、第一百二十三条"
    for result in results:
        print(result)