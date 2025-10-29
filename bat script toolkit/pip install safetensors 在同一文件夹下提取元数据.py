import os
import json
from safetensors import safe_open
from typing import Dict, List

def extract_safetensors_metadata(file_path: str) -> Dict or None:
    """
    安全地从 .safetensors 文件中提取元数据。
    """
    try:
        # 使用 safe_open 安全地打开 safetensors 文件
        # 我们只读取元数据，不需要加载张量本身
        with safe_open(file_path, framework="numpy") as f:
            metadata = f.metadata()
            return metadata
    except Exception as e:
        # 捕获任何读取错误，例如文件损坏或格式不正确
        print(f"  [❌ 错误] 读取文件时发生错误 {os.path.basename(file_path)}: {e}")
        return None

def write_metadata_to_file(metadata: Dict or None, output_path: str, lora_file_name: str):
    """
    将元数据写入指定的文本文件。
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"--- LoRA 文件名：{lora_file_name} ---\n\n")
            
            if metadata is None:
                f.write("未找到或无法提取嵌入元数据。\n")
                return

            f.write("### 原始元数据 (Raw Metadata):\n")
            # 使用 JSON 格式打印完整的原始元数据，确保清晰可读
            f.write(json.dumps(metadata, indent=4, ensure_ascii=False))
            
            # --- 关键信息分析 ---
            f.write("\n\n" + "="*50 + "\n")
            f.write("### 关键信息猜测:\n")
            
            # 常见激活词/触发词的键名列表
            trigger_keys = ['_i2i.trigger_words', 'ss_tag_frequency', 'ss_additional_metadata', 'activation_text', 'trigger_words', 'ss_word']
            
            trigger_found = False
            for key in trigger_keys:
                if key in metadata:
                    value = metadata[key]
                    f.write(f"**潜在激活词键 [{key}]**: {value}\n")
                    trigger_found = True
            
            if not trigger_found:
                f.write("未在常见键中找到明确的激活词。\n请仔细检查 '原始元数据' 部分。\n")
            
        print(f"  [✅ 成功] 元数据已保存到: {os.path.basename(output_path)}")

    except Exception as e:
        print(f"  [❌ 错误] 写入文件时发生错误: {e}")

def main():
    # 获取脚本所在的目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 查找所有 .safetensors 文件
    lora_files: List[str] = [
        f for f in os.listdir(script_dir) 
        if f.lower().endswith(".safetensors")
    ]

    if not lora_files:
        print(f"警告：在当前文件夹 ({script_dir}) 中未找到任何 .safetensors 文件。")
        print("请将此脚本与您的 LoRA 文件放在同一目录下运行。")
        return

    print(f"找到 {len(lora_files)} 个 .safetensors 文件，开始提取元数据...\n")
    
    for lora_file in lora_files:
        print(f"处理文件: {lora_file}")
        lora_path = os.path.join(script_dir, lora_file)
        base_name = os.path.splitext(lora_file)[0]
        output_file = os.path.join(script_dir, f"{base_name}_metadata.txt")
        
        # 提取并写入
        metadata_dict = extract_safetensors_metadata(lora_path)
        write_metadata_to_file(metadata_dict, output_file, lora_file)
        print("-" * 30)

    print("\n所有文件处理完毕。")

if __name__ == "__main__":
    main()