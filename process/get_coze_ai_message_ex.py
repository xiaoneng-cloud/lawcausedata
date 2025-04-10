import os
import time
import pandas as pd
import json
import argparse
from cozepy import Coze, TokenAuth, Message, ChatEventType, COZE_CN_BASE_URL
from pypinyin import lazy_pinyin

# 初始化 Coze 客户端的全局变量
coze_api_token = 'pat_sSMcUXlyKiF37mbQ5VmCK2ufcXFLamnAgUkzDtUbz4aWZp0uyQafjkUPnOLt6z8M'
coze_api_base = COZE_CN_BASE_URL
bot_id = '7488290236196782121'
user_id = 'zhousheng2235'

def process_file(file_path, sheet_name):
    """处理单个文件的函数"""
    coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=coze_api_base)
    file_results = pd.DataFrame()
    
    try:
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            data_list = json.loads(content)
        
        print(f"开始处理文件: {file_path}")
        counter = 0
        # 遍历数组，依次处理每个法律条文信息
        for item in data_list:
            long_message = item.get("条文", "")
            if long_message:
                try:
                    full_response = ""
                    # 记录发送到服务端的内容
                    print(f"发送到服务端的内容: {long_message}")
                    # 使用 coze.chat.stream 方法进行流式调用
                    for event in coze.chat.stream(
                        bot_id=bot_id,
                        user_id=user_id,
                        additional_messages=[
                            Message.build_user_question_text(long_message),
                        ],
                        temperature=0,
                    ):
                        if event.event == ChatEventType.CONVERSATION_MESSAGE_DELTA:
                            full_response += event.message.content
                        if event.event == ChatEventType.CONVERSATION_CHAT_COMPLETED:
                            time.sleep(1)
                            
                            # 提取 JSON 数据
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
                                        print(f"JSON 数据: {json_data}")
                                except json.JSONDecodeError:
                                    print(f"文件 {file_path} 未找到有效的 JSON 数据。")

                            if json_data is not None:
                                # 处理 JSON 数据中的空值
                                for item in json_data:
                                    for key, value in item.items():
                                        if value is None:
                                            item[key] = ""

                                # 将 JSON 数据转换为 DataFrame
                                df = pd.DataFrame(json_data)
                                pinyin_initial = ''.join([i[0] for i in lazy_pinyin(sheet_name)])
                                df['编号'] = [f'{pinyin_initial}{counter + i + 1}' for i in range(len(df))]
                                counter += len(df)
                                file_results = pd.concat([file_results, df], ignore_index=True)

                except Exception as e:
                    print(f"处理文件 {file_path} 的法律条文信息时发生错误: {e}")

        # 打印处理结果
        if not file_results.empty:
            print(f"文件 {file_path} 处理完成，结果如下：")
            print(f"共 {len(file_results)} 条记录")
        else:
            print(f"文件 {file_path} 处理完成，但没有有效数据。")

        # 删除已处理的 txt 文件
        os.remove(file_path)
        print(f"已删除文件: {file_path}")

        return sheet_name, file_results

    except Exception as e:
        print(f"读取或处理文件 {file_path} 时发生错误: {e}")
        return sheet_name, pd.DataFrame()  # 返回空的 DataFrame

def main(txt_file, excel_file):
    sheet_name = os.path.splitext(os.path.basename(txt_file))[0]

    # 创建 ExcelWriter 对象
    writer = pd.ExcelWriter(excel_file, engine='openpyxl')
    
    # 处理单个文件并获取结果
    sheet_name, file_results = process_file(txt_file, sheet_name)
    
    # 将结果写入 Excel
    if not file_results.empty:
        file_results.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"数据已保存到 {excel_file} 的 {sheet_name} 工作表中")

    # 保存 Excel 文件
    writer.close()
    if not file_results.empty:
        print(f"所有数据已成功保存到 {excel_file}")
    else:
        print("没有有效的数据需要保存到 Excel 文件。")

if __name__ == "__main__":
    # 可以在这里修改为你实际的文件路径
    txt_file = "your_txt_file.txt"
    excel_file = "your_excel_file.xlsx"
    main(txt_file, excel_file)