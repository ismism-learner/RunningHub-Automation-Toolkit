#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import json
import re
import time
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

# ==================== 配置区域 ====================

# VVVVVV 【用户只需要修改和粘贴 curl 命令的地方】 VVVVVV
CURL_COMMAND_TEMPLATE = """

"""
# ^^^^^^ 【用户只需要修改和粘贴 curl 命令的地方】 ^^^^^^

BASE_URL = "https://www.runninghub.cn"
UPLOAD_URL = f"{BASE_URL}/task/openapi/upload"
WORKFLOW_URL = f"{BASE_URL}/task/openapi/ai-app/run"

# 动态配置变量
WEBAPP_ID = None
API_KEY = None
WORKFLOW_NODE_TEMPLATE = None 
BATCH_SIZE = 0     
IMAGE_STRIDE = 1   

# 日志文件路径
ERROR_LOG_FILE = 'error_log.txt'

# 等待时间（秒）
WAIT_TIME = 60
RETRY_WAIT_TIME = 30
WORKFLOW_RETRY_COUNT = 6

# ==================== 提示词处理函数 (新增/修改) ====================

def get_combined_txt_content() -> str:
    """
    读取当前目录下所有 .txt 文件的内容并合并，不进行解析。
    用于：1. Image 模式下的通用 Prompt； 2. T2I 模式下的批次解析。
    """
    prompt_text = ""
    txt_files = sorted([f for f in os.listdir('.') if os.path.isfile(f) and f.lower().endswith('.txt')])
    
    if not txt_files:
        return ""
    
    print("\n[提示词] 发现以下 TXT 文件:")
    for txt_file in txt_files:
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                content = f.read()
                prompt_text += content + "\n"
                print(f"  - 读取 {txt_file} 成功")
        except Exception as e:
            print(f"  ✗ 读取 {txt_file} 失败: {e}")
            log_error("FileRead", f"无法读取 TXT 文件: {txt_file}", {"exception": str(e)})
            
    return prompt_text.strip()


def parse_prompt_batches(combined_content: str) -> List[str]:
    """
    根据 '=== 组合提示词 - NO. X ===' 模式解析出提示词批次列表。
    """
    if not combined_content:
        return []
        
    # 正则表达式：匹配开头，并在匹配的标记处进行分割
    # \s* 匹配可选的空白符
    pattern = re.compile(r'^\s*=== 组合提示词 - NO\.\s*\d+\s*===\s*', re.MULTILINE)
    
    # 1. 以标记分割内容
    sections = pattern.split(combined_content)
    
    # 2. 过滤掉分割后的空字符串（通常是文件开头的部分），只保留实际的提示词内容
    prompt_list = [s.strip() for s in sections if s.strip()]
    
    return prompt_list


# ==================== 通用工具函数 (不变) ====================

def log_error(error_type: str, message: str, details: Optional[Dict[str, Any]] = None):
    """记录错误日志到 error_log.txt 文件。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{error_type} ERROR]\n"
    log_entry += f"  Message: {message}\n"
    if details:
        log_entry += "  Details:\n"
        for key, value in details.items():
            value_str = str(value)
            if len(value_str) > 200:
                value_str = value_str[:200] + "..."
            log_entry += f"    - {key}: {value_str}\n"
    log_entry += "-" * 50 + "\n"
    try:
        with open(ERROR_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
        print(f"  [日志记录] 错误已写入 {ERROR_LOG_FILE}")
    except Exception as e:
        print(f"  [日志失败] 写入错误日志文件时发生异常: {e}")

def parse_curl_command(curl_string: str) -> Dict[str, Any]:
    """解析 curl 命令字符串，提取 JSON 负载，并修复复制粘贴导致的隐藏字符问题。"""
    match = re.search(r'--data-raw\s+\'(.+?)\'|--data\s+\'(.+?)\'', curl_string, re.DOTALL)
    if not match:
        raise ValueError("无法在 curl 命令中找到 --data-raw 或 --data 部分。")
    json_string = match.group(1) or match.group(2)
    json_string = json_string.replace('\n', '').replace('\\', '')
    json_string = json_string.replace('\xa0', ' ').replace('\u3000', ' ').strip()
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"无法解析提取的 JSON 负载: {e}.", e.doc, e.pos)

def determine_processing_logic(node_template: List[Dict[str, Any]]) -> Tuple[int, int]:
    """确定批次大小和序列步长。"""
    image_nodes = [node for node in node_template if node.get("fieldName") == "image"]
    batch_size = len(image_nodes)
    if batch_size == 0: stride = 0 
    elif batch_size == 1: stride = 1
    elif batch_size == 2: stride = 1
    elif batch_size == 3: stride = 2
    else: stride = batch_size 
    print(f"**处理逻辑确定:**")
    print(f"  - 每个任务图片数 (Batch Size): {batch_size}")
    print(f"  - 序列步长 (Stride): {stride}")
    return batch_size, stride

def natural_sort_key(s):
    """创建一个排序键，将文件名中的数字视为数字，实现自然数字排序。"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def get_image_files_categorized() -> Tuple[List[str], List[str], Dict[int, str], Optional[str]]:
    """获取所有图片文件，并根据前缀 '#'、'##' 或 '###' 进行分类。"""
    extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    all_files = []
    for f in os.listdir('.'):
        if os.path.isfile(f):
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                all_files.append(f)
    
    sorted_all_files = sorted(all_files, key=natural_sort_key)
    sequential_files = []
    fixed_files_map: Dict[int, str] = {} 
    
    for f in sorted_all_files:
        filename_without_ext = os.path.splitext(f)[0]
        fixed_pos = 0 
        
        if filename_without_ext.startswith('###'): fixed_pos = 3
        elif filename_without_ext.startswith('##'): fixed_pos = 2
        elif filename_without_ext.startswith('#'): fixed_pos = 1
        
        if fixed_pos > 0:
            if fixed_pos in fixed_files_map:
                conflict_msg = f"冲突: 存在多个文件试图固定在第 {fixed_pos} 个图片接口 ({fixed_files_map[fixed_pos]} 和 {f})。已禁用模式二。"
                return sorted_all_files, [], {}, conflict_msg
            fixed_files_map[fixed_pos] = f
        else:
            sequential_files.append(f)
            
    return sorted_all_files, sequential_files, fixed_files_map, None

def handle_mode_selection(is_mode2_eligible: bool) -> int:
    """处理交互式模式选择，等待用户输入 1 或 2，或按回车。"""
    print("\n" + "=" * 60)
    print("📢 发现固定图片标识符 (# / ## / ###)，请选择处理模式：")
    print("=" * 60)
    print("【1】 模式一 (默认/序列模式)：使用自动步长和重叠处理所有图片。")
    if is_mode2_eligible:
        print("【2】 模式二 (固定图片模式)：将固定图片与每个序列图片单独配对。")
        print("      - # : 固定在 API 第 1 个图片接口。")
        print("      - ##: 固定在 API 第 2 个图片接口。")
        print("      - ###: 固定在 API 第 3 个图片接口。")
    else:
        print("【2】 模式二 (固定图片模式)：(当前 API BATCH_SIZE 不支持，已禁用)")
    
    print("-" * 60)
    
    while True:
        try:
            user_input = input("▶️ 您的选择 (键入 1 或 2，或直接回车 [默认 1]): ").strip()
        except Exception:
            user_input = ""

        if user_input == "" or user_input == '1':
            return 1 
        elif user_input == '2':
            if is_mode2_eligible:
                return 2
            else:
                print("   模式二当前不适用，请选择 1 或按回车。")
        else:
            print("   无效输入，请重新输入 1 或 2。")

def upload_image_once(image_path: str) -> Tuple[Optional[str], Optional[str]]:
    """单次上传图片到RunningHub"""
    global API_KEY
    if not API_KEY: return None, "API_KEY 未设置"
    try:
        with open(image_path, 'rb') as f:
            files = {'file': (image_path, f, 'image/jpeg')} 
            data = {'apiKey': API_KEY}
            response = requests.post(UPLOAD_URL, data=data, files=files, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    filename = result.get('data', {}).get('fileName')
                    if filename: return filename, None
        error_msg = f"上传失败，返回状态码: {response.status_code}"
        log_error("UploadFail", error_msg, {"image_path": image_path, "response_text": response.text})
        return None, error_msg
    except Exception as e:
        log_error("UploadException", str(e), {"image_path": image_path, "url": UPLOAD_URL})
        return None, str(e)

def upload_image(image_path: str) -> str:
    """上传图片到RunningHub，失败后自动重试"""
    retry_count = 0
    while True:
        if retry_count > 0: print(f"  [第 {retry_count + 1} 次尝试上传] {image_path}")
        else: print(f"  [上传] {image_path}")
        filename, error = upload_image_once(image_path)
        if filename:
            print(f"  ✓ 上传成功: {filename}")
            return filename
        retry_count += 1
        print(f"  ✗ 上传失败: {error}")
        if retry_count >= WORKFLOW_RETRY_COUNT:
            print(f"  达到最大重试次数 ({WORKFLOW_RETRY_COUNT})，上传失败。")
            raise Exception(f"图片上传失败: {image_path}") 
        print(f"  等待 {RETRY_WAIT_TIME} 秒后重试...")
        countdown(RETRY_WAIT_TIME)

def submit_workflow(image_ids: List[Optional[str]], prompt: str) -> Tuple[Optional[str], Optional[str]]:
    """【动态】提交工作流任务。"""
    global WEBAPP_ID, API_KEY, WORKFLOW_NODE_TEMPLATE
    if not all([WEBAPP_ID, API_KEY, WORKFLOW_NODE_TEMPLATE]): return None, "工作流配置未初始化"
    
    try:
        payload = {"webappId": WEBAPP_ID, "apiKey": API_KEY, "nodeInfoList": []}
        image_idx = 0 
        for node in WORKFLOW_NODE_TEMPLATE:
            new_node = node.copy()
            
            if new_node.get("fieldName") == "image":
                if image_idx < len(image_ids) and image_ids[image_idx] is not None:
                    new_node["fieldValue"] = image_ids[image_idx]
                image_idx += 1
                
            elif new_node.get("fieldName") in ["prompt", "string", "text"] or "提示词" in new_node.get("description", ""):
                new_node["fieldValue"] = prompt
            
            payload["nodeInfoList"].append(new_node)

        headers = {'Host': 'www.runninghub.cn', 'Content-Type': 'application/json'}
        response = requests.post(WORKFLOW_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                task_id = result.get('data', {}).get('taskId')
                if task_id: return task_id, None
        
        error_msg = f"API返回异常 (Status: {response.status_code}, Response: {response.text[:100]}...)"
        log_error("WorkflowFail", error_msg, {"payload_snippet": json.dumps(payload)[:300], "response_text": response.text, "image_ids": image_ids})
        print(f"  ✗ 提交失败: {error_msg}")
        return None, error_msg
        
    except Exception as e:
        error_msg = str(e)
        log_error("WorkflowException", error_msg, {"url": WORKFLOW_URL, "image_ids": image_ids})
        print(f"  ✗ 错误: {error_msg}")
        return None, error_msg

def countdown(seconds: int):
    """倒计时显示"""
    for i in range(seconds, 0, -5):
        mins = i // 60
        secs = i % 60
        print(f"  等待中... {mins:02d}:{secs:02d}", end='\r')
        time.sleep(5)
    print(" " * 30, end='\r')

# ==================== 主程序 ====================

def main():
    global WEBAPP_ID, API_KEY, WORKFLOW_NODE_TEMPLATE, BATCH_SIZE, IMAGE_STRIDE
    
    print("=" * 60)
    print("RunningHub 动态批量处理工具")
    print("=" * 60)
    
    # 1. 配置解析
    try:
        parsed_payload = parse_curl_command(CURL_COMMAND_TEMPLATE)
        WEBAPP_ID = parsed_payload.get("webappId")
        API_KEY = parsed_payload.get("apiKey")
        WORKFLOW_NODE_TEMPLATE = parsed_payload.get("nodeInfoList")
        if not all([WEBAPP_ID, API_KEY, WORKFLOW_NODE_TEMPLATE]):
            raise ValueError("解析后的配置缺少 webappId, apiKey 或 nodeInfoList。")
        print(f"✓ 配置解析成功！Webapp ID: {WEBAPP_ID}")
    except Exception as e:
        error_msg = f"配置解析失败，程序终止: {e}"
        log_error("ConfigParseFatal", error_msg, {"CURL_TEMPLATE_START": CURL_COMMAND_TEMPLATE[:200]})
        print(f"\n❌ {error_msg}")
        return
    
    # 2. 确定处理逻辑和获取文件
    BATCH_SIZE, IMAGE_STRIDE = determine_processing_logic(WORKFLOW_NODE_TEMPLATE)
    print("-" * 60)
    
    all_files: List[str] = []
    current_mode = 1 # 默认模式一
    tasks = []
    
    # 核心判断逻辑: T2I 批次模式 还是 Image 驱动模式
    all_files, seq_files, fixed_files_map, conflict_msg = get_image_files_categorized()
    has_images = bool(all_files)
    
    # 获取所有 TXT 文件内容 (用于 T2I 批次解析 或 Image 模式的通用 Prompt)
    combined_content = get_combined_txt_content()
    
    # --- 场景 A: T2I 批次模式 ---
    if not has_images and BATCH_SIZE == 0:
        print("\n**进入 T2I 批次模式**：未发现图片文件，且 API 为纯文本输入。")
        prompt_batches = parse_prompt_batches(combined_content)
        
        if not prompt_batches:
            print("\n❌ 未找到图片文件，且在 TXT 文件中未找到符合 '=== 组合提示词 - NO. X ===' 格式的提示词组合。程序终止。")
            return
            
        print(f"已识别到 {len(prompt_batches)} 个提示词组合任务。")
        
        for i, prompt in enumerate(prompt_batches):
             tasks.append({
                'image_files': [],
                'image_ids': [],
                'task_id': None,
                'status': 'pending',
                'error': None,
                'prompt': prompt, # 存储独立的 Prompt
                'task_name': f"Prompt Batch {i+1}"
             })
        
        current_mode = 3 # 标记为 T2I 批次模式
        
    # --- 场景 B: Image 驱动模式 (Mode 1/2) 或 Image API 无图片 ---
    else:
        if BATCH_SIZE > 0 and not has_images:
            print("\n❌ API 需要图片输入 (Batch Size > 0)，但未找到图片文件。程序终止。")
            return
        
        if len(all_files) < BATCH_SIZE:
            print(f"\n❌ 图片数量不足！工作流需要 {BATCH_SIZE} 张图片，但只找到 {len(all_files)} 张。程序终止。")
            return
            
        # 3. 模式选择 (仅在有图片且 BATCH_SIZE > 0 时)
        if conflict_msg:
            print(f"⚠ 文件命名冲突: {conflict_msg}")
            is_mode2_eligible = False
        else:
            num_fixed = len(fixed_files_map)
            is_mode2_eligible = num_fixed > 0 and num_fixed < BATCH_SIZE
        
        if has_images and BATCH_SIZE > 0 and is_mode2_eligible:
            current_mode = handle_mode_selection(is_mode2_eligible)
        elif BATCH_SIZE > 0 and num_fixed > 0:
            print(f"固定图片数 ({num_fixed}) 不满足 BATCH_SIZE ({BATCH_SIZE}) - 1 的要求，自动运行模式一。")
            current_mode = 1
        elif BATCH_SIZE > 0:
            print("自动运行模式一。")
            current_mode = 1

        # 4. 构造任务列表 (Mode 1/2)
        if current_mode == 1:
            i = 0
            while i + BATCH_SIZE <= len(all_files):
                current_batch_files = all_files[i : i + BATCH_SIZE]
                tasks.append({
                    'image_files': current_batch_files, 'image_ids': [None] * BATCH_SIZE, 
                    'task_id': None, 'status': 'pending', 'error': None, 'prompt': combined_content,
                    'task_name': ', '.join(current_batch_files)
                })
                i += IMAGE_STRIDE
            print(f"模式一：序列/重叠模式。将生成 {len(tasks)} 个任务。")
        
        elif current_mode == 2:
            fixed_slots = sorted(fixed_files_map.keys())
            first_available_slot = 0
            for i in range(1, BATCH_SIZE + 1):
                if i not in fixed_slots:
                    first_available_slot = i; break

            for seq_file in seq_files:
                task_batch: List[Optional[str]] = [None] * BATCH_SIZE
                for pos, f_name in fixed_files_map.items():
                    if pos <= BATCH_SIZE: task_batch[pos - 1] = f_name
                if first_available_slot > 0: task_batch[first_available_slot - 1] = seq_file
                
                tasks.append({
                    'image_files': task_batch, 'image_ids': [None] * BATCH_SIZE, 
                    'task_id': None, 'status': 'pending', 'error': None, 'prompt': combined_content,
                    'task_name': f"Fixed + {seq_file}"
                })
            print(f"模式二：固定图片模式。固定文件: {fixed_files_map}。将生成 {len(tasks)} 个任务。")
            
    # 5. 提示词总结
    print("-" * 60)
    if current_mode == 3:
        print(f"[模式：T2I 批次] 将使用 {len(prompt_batches)} 个独立提示词组合。")
    else:
        print(f"[提示词] 提取到的通用 Prompt ({len(combined_content)} 字符): {combined_content[:100]}...")
    print("-" * 60)
            
    # 6. 逐个处理任务
    print(f"每个任务间隔: {WAIT_TIME} 秒")
    print("=" * 60)
    
    uploaded_image_ids = {}
    
    for idx, task in enumerate(tasks, 1):
        file_list = task['image_files']
        current_image_ids: List[Optional[str]] = [None] * BATCH_SIZE
        task_prompt = task['prompt']

        print(f"\n[{idx}/{len(tasks)}] 任务: {task.get('task_name', 'N/A')}")
        print("-" * 60)
        
        # 上传图片 (T2I 模式跳过)
        if BATCH_SIZE > 0:
            try:
                for file_idx, file_name in enumerate(file_list):
                    if file_name:
                        if file_name not in uploaded_image_ids:
                            image_id = upload_image(file_name)
                            uploaded_image_ids[file_name] = image_id
                        else:
                            image_id = uploaded_image_ids[file_name]
                            print(f"  [跳过上传] 图片 {file_name} 已上传, ID: {image_id[:10]}...")
                        current_image_ids[file_idx] = image_id
            except Exception as e:
                task['status'] = 'upload_failed'; task['error'] = str(e)
                print(f"  ❌ 任务跳过: 图片上传发生致命失败。")
                continue 
            task['image_ids'] = current_image_ids
        
        # 提交工作流
        if task['status'] != 'upload_failed':
            workflow_retry_count = 0
            while workflow_retry_count < WORKFLOW_RETRY_COUNT:
                if workflow_retry_count > 0: print(f"  [第 {workflow_retry_count + 1} 次尝试提交工作流]")
                
                task_id, error_detail = submit_workflow(current_image_ids, task_prompt)
                
                if task_id: break
                workflow_retry_count += 1
                if workflow_retry_count < WORKFLOW_RETRY_COUNT: countdown(RETRY_WAIT_TIME)
                else: task['error'] = error_detail or '工作流提交失败'

            if task_id:
                task['task_id'] = task_id; task['status'] = 'success'
            else:
                task['status'] = 'workflow_failed'
        
        if idx < len(tasks):
            print(f"\n  等待 {WAIT_TIME} 秒后处理下一个任务...")
            countdown(WAIT_TIME)
    
    # 7. 输出结果
    print("\n" + "=" * 60)
    print("处理完成！")
    print("=" * 60)
    
    success = [r for r in tasks if r['status'] == 'success']
    workflow_failed = [r for r in tasks if r['status'] == 'workflow_failed']
    upload_failed = [r for r in tasks if r['status'] == 'upload_failed']
    
    print(f"成功: {len(success)}/{len(tasks)}")
    print(f"工作流提交失败: {len(workflow_failed)}/{len(tasks)}")
    print(f"图片上传失败: {len(upload_failed)}/{len(tasks)}")

    results_to_save = [
        {
            'mode': current_mode,
            'task_name': r['task_name'],
            'image_files': [f or 'N/A' for f in r['image_files']] if r['image_files'] else '纯文本任务',
            'status': r['status'],
            'task_id': r.get('task_id'), 
            'error': r['error']
        } for r in tasks
    ]
    with open('results_dynamic_robust.json', 'w', encoding='utf-8') as f:
        json.dump(results_to_save, f, ensure_ascii=False, indent=2)
    
    print(f"\n结果已保存到: results_dynamic_robust.json")
    print(f"详细错误日志已保存到: {ERROR_LOG_FILE}")
    print(f"请访问 https://www.runninghub.cn/ 下载结果")
    

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已取消")
    except Exception as e:
        import traceback
        log_error("UncaughtFatal", str(e), {"traceback": traceback.format_exc()})
        print(f"\n❌ 发生未捕获的致命错误，请检查 {ERROR_LOG_FILE}")
