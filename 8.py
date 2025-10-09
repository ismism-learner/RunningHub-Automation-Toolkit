import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import json
import os
import logging
from datetime import datetime
import re 
import time 

# --- 日志与错误报告功能 ---

LOG_FILENAME = 'api_runner_log.txt'
logging.basicConfig(filename=LOG_FILENAME, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_error_report(message, api_data=None):
    """记录错误并生成详细的错误报告文件."""
    error_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_filename = f'ERROR_REPORT_{error_time}.txt'
    
    logging.error(message)
    
    with open(report_filename, 'w', encoding='utf-8') as f:
        f.write(f"--- API Runner 错误报告 ---\n")
        f.write(f"时间戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"错误信息: {message}\n")
        f.write(f"--- 当前 API 配置 ---\n")
        if api_data:
            f.write(f"URL: {api_data.get('url', 'N/A')}\n")
            f.write(f"Webapp ID: {api_data.get('webappId', 'N/A')}\n")
            f.write(f"API Key: {api_data.get('apiKey', 'N/A')[:4]}...\n")
        f.write(f"------------------------------\n")

    return f"操作失败。已生成错误报告文件：{report_filename}"

# --- Tkinter GUI 应用类 ---

class APIRunnerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("API Runner - 未加载配置")

        self.current_directory = os.getcwd()
        self.scanned_assets = {'image': [], 'video': [], 'json_config': []}
        self.request_payloads = []
        
        self.config_filepath_history = {} 
        self.last_loaded_config_path = None
        self.prompts = [] 

        self.API_DATA = {}
        self.INTERFACE_INFO = []
        self.BASE_HEADERS = {"Content-Type": "application/json"}
        
        self.value_vars = {} 
        self.file_vars = {} 
        self.api_info_labels = {} 
        
        # 重试/超时设置变量
        self.upload_timeout = tk.IntVar(value=60)
        self.retry_interval = tk.IntVar(value=60)
        self.max_retries = tk.IntVar(value=6)
        
        # 新增：批次模式变量 (包含所有可能性)
        self.BATCH_MODE_OPTIONS = [
            "M0: 默认单请求模式",
            "M1: 多图单提示词/视频",
            "M2: 多视频单提示词/图片",
            "M3: 纯多提示词批量",
            "M4: 多图多提示词 1:1 顺序匹配",
            "M6: 单图多提示词",
            "M7a: 多图滑窗 (2图/1步, [001,002],[002,003]...)",
            "M7b: 多图滑窗 (3图/2步, [001,002,003],[003,004,005]...)",
            "M5: (危险) 笛卡尔积/全组合"
        ]
        self.batch_mode_var = tk.StringVar(value=self.BATCH_MODE_OPTIONS[0])

        self.create_widgets()
        
        self.update_log_display("请点击 '导入新配置' 或从下拉菜单选择文件来启动应用。", level='WARNING')

    def create_widgets(self):
        main_frame = ttk.Frame(self.master)
        main_frame.pack(pady=10, padx=10, expand=True, fill="both")

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(expand=True, fill="both") 

        self.config_frame = ttk.Frame(self.notebook); self.notebook.add(self.config_frame, text="配置与扫描")
        self.editor_frame = ttk.Frame(self.notebook); self.notebook.add(self.editor_frame, text="接口值编辑")
        
        self._build_config_tab()
        self._build_editor_tab() 

        # 运行按钮和设置区域
        run_control_frame = ttk.Frame(main_frame)
        run_control_frame.pack(fill='x', pady=10)
        
        self.run_btn = ttk.Button(run_control_frame, text="🚀 运行 API 请求", command=self.run_api_requests, state='disabled')
        self.run_btn.pack(side='left', padx=(0, 10))
        
        settings_frame = ttk.LabelFrame(run_control_frame, text="运行/重试设置")
        settings_frame.pack(side='left', fill='x', expand=True)
        self.build_settings_widgets(settings_frame)

        # 日志区域放置在最下方
        self.log_frame = ttk.LabelFrame(main_frame, text="运行日志 (Run Log)")
        self.log_frame.pack(fill="x", pady=(0, 5)) 
        self._build_log_display()
        
    def build_settings_widgets(self, parent_frame):
        """构建重试/超时设置控件."""
        ttk.Label(parent_frame, text="上传超时(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.upload_timeout, width=5).pack(side='left', padx=(0, 5))
        
        ttk.Label(parent_frame, text="重试频率(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.retry_interval, width=5).pack(side='left', padx=(0, 5))
        
        ttk.Label(parent_frame, text="最大重试次数:").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.max_retries, width=5).pack(side='left', padx=(0, 5))


    def _build_config_tab(self):
        load_frame = ttk.LabelFrame(self.config_frame, text="API 配置加载")
        load_frame.pack(fill="x", padx=5, pady=5)
        
        self.config_combobox = ttk.Combobox(load_frame, values=list(self.config_filepath_history.keys()), state='readonly', width=30)
        self.config_combobox.pack(side='left', padx=5, pady=5)
        self.config_combobox.bind("<<ComboboxSelected>>", self.load_config_from_combobox)
        
        ttk.Button(load_frame, text="📂 导入新配置", command=self.select_and_load_config).pack(side='left', padx=5, pady=5)
        self.config_file_label = ttk.Label(load_frame, text="当前文件: 无")
        self.config_file_label.pack(side='left', padx=10)

        info_frame = ttk.LabelFrame(self.config_frame, text="当前 API 信息")
        info_frame.pack(fill="x", padx=5, pady=5)
        self.api_info_labels['url'] = ttk.Label(info_frame, text="URL: N/A"); self.api_info_labels['url'].pack(anchor="w", padx=5)
        self.api_info_labels['webappId'] = ttk.Label(info_frame, text="Webapp ID: N/A"); self.api_info_labels['webappId'].pack(anchor="w", padx=5)
        self.api_info_labels['apiKey'] = ttk.Label(info_frame, text="API Key: N/A"); self.api_info_labels['apiKey'].pack(anchor="w", padx=5)

        scan_frame = ttk.LabelFrame(self.config_frame, text="本地文件管理")
        scan_frame.pack(fill="x", padx=5, pady=10)
        
        self.dir_label_var = tk.StringVar(value=self.current_directory)
        ttk.Label(scan_frame, text="当前目录:").pack(anchor="w", padx=5, pady=2)
        ttk.Label(scan_frame, textvariable=self.dir_label_var, foreground="blue").pack(anchor="w", padx=5)
        
        btn_frame = ttk.Frame(scan_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="更改目录", command=self.change_directory).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="重新扫描文件", command=self.scan_files_and_update_status).pack(side="left", padx=5)
        
        self.scan_status_label = ttk.Label(scan_frame, text="文件扫描状态: 未运行")
        self.scan_status_label.pack(anchor="w", padx=5, pady=5)
        
        self.match_status_label = ttk.Label(scan_frame, text="匹配模式: 未生成请求")
        self.match_status_label.pack(anchor="w", padx=5, pady=5)

        ttk.Button(self.config_frame, text="📝 生成请求负载 (查看匹配模式)", command=self.generate_payloads).pack(pady=10)


    def _build_editor_tab(self):
        """动态构建或更新接口值编辑面板，新增文件选择区域."""
        for widget in self.editor_frame.winfo_children():
            widget.destroy()
            
        if not self.API_DATA:
            ttk.Label(self.editor_frame, text="请先加载 API 配置。").pack(padx=20, pady=20)
            return

        # 顶部：单个请求参数配置
        top_frame = ttk.LabelFrame(self.editor_frame, text="单个请求参数配置 (作为批处理的默认值)")
        top_frame.pack(fill="x", padx=5, pady=5) 
        
        canvas = tk.Canvas(top_frame, height=150) 
        scrollbar = ttk.Scrollbar(top_frame, orient="vertical", command=canvas.yview)
        self.interface_list_frame = ttk.Frame(canvas)

        canvas.create_window((0, 0), window=self.interface_list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="x", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.interface_list_frame.bind("<Configure>", 
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        self.value_vars = {} 
        self.file_vars = {}
        for info in self.INTERFACE_INFO:
            row_frame = ttk.Frame(self.interface_list_frame)
            row_frame.pack(fill="x", pady=3, padx=5)
            
            ttk.Label(row_frame, text=f"[{info['code']}] {info['name']}:", width=15, anchor="w").pack(side="left", padx=5)
            ttk.Label(row_frame, text=f"({info['type']})", width=8).pack(side="left")
            
            if info['type'] in ("value", "text"):
                var = tk.StringVar(value=info['default_value'])
                self.value_vars[info['code']] = var
                editor = ttk.Entry(row_frame, textvariable=var, width=50)
                editor.pack(side="right", expand=True, fill="x", padx=5)
                
            elif info['type'] in ("image", "video"):
                var = tk.StringVar(value=info['default_value'])
                self.file_vars[info['code']] = var
                ttk.Entry(row_frame, textvariable=var, state='readonly', width=45).pack(side="right", expand=True, fill="x", padx=5)
                ttk.Label(row_frame, text="（下方选择文件）").pack(side="right", padx=5) 
        
        
        # 底部：批量文件选择区域
        batch_frame = ttk.LabelFrame(self.editor_frame, text="批量文件与模式选择（Ctrl/Shift 多选）")
        batch_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 批次模式选择
        mode_config_frame = ttk.LabelFrame(batch_frame, text="批量模式选择")
        mode_config_frame.pack(fill='x', padx=5, pady=5)
        
        ttk.Label(mode_config_frame, text="批量模式:").pack(side='left', padx=5)
        self.mode_combobox = ttk.Combobox(mode_config_frame, textvariable=self.batch_mode_var, values=self.BATCH_MODE_OPTIONS, state='readonly', width=70)
        self.mode_combobox.pack(side='left', padx=5, fill='x', expand=True)
        
        # 文件列表
        listbox_container = ttk.Frame(batch_frame)
        listbox_container.pack(fill="both", expand=True)
        
        self.image_listbox, _ = self._create_file_listbox(listbox_container, "图片文件", self.scanned_assets['image'], 'extended')
        self.video_listbox, _ = self._create_file_listbox(listbox_container, "视频文件", self.scanned_assets['video'], 'extended')
        self.json_listbox, _ = self._create_file_listbox(listbox_container, "JSON 提示词/配置", self.scanned_assets['json_config'], 'extended')

    def _create_file_listbox(self, parent, title, file_list, selectmode):
        """创建带有滚动条的文件列表框."""
        frame = ttk.LabelFrame(parent, text=f"{title} ({len(file_list)}个)")
        frame.pack(side='left', padx=5, pady=5, fill='both', expand=True)
        
        listbox_frame = ttk.Frame(frame)
        listbox_frame.pack(fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        listbox = tk.Listbox(listbox_frame, selectmode=selectmode, height=8, yscrollcommand=scrollbar.set, exportselection=False)
        scrollbar.config(command=listbox.yview)
        
        scrollbar.pack(side='right', fill='y')
        listbox.pack(side='left', fill='both', expand=True)

        for filename in file_list:
            listbox.insert(tk.END, filename)
            
        return listbox, None 

    def _build_log_display(self):
        """构建日志输出区域 (现在放在主面板下方)"""
        self.log_text = tk.Text(self.log_frame, height=8, state='disabled', wrap='word', font=("Consolas", 10))
        self.log_text.pack(expand=True, fill="both", padx=5, pady=5)
        
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')

    def load_config_from_combobox(self, event):
        """从下拉菜单选择文件时触发加载."""
        selected_file = self.config_combobox.get()
        if selected_file and selected_file in self.config_filepath_history:
            filepath = self.config_filepath_history[selected_file]
            self.load_config_from_file(filepath, add_to_history=False) 

    def select_and_load_config(self):
        filepath = filedialog.askopenfilename(
            defaultextension=".txt",
            filetypes=[("API Config Files", "*.txt *.json"), ("All Files", "*.*")]
        )
        if filepath:
            self.load_config_from_file(filepath, add_to_history=True)
            
    def update_config_history_gui(self):
        """更新下拉菜单的内容和当前显示值."""
        self.config_combobox['values'] = list(self.config_filepath_history.keys())
        if self.last_loaded_config_path:
            filename = os.path.basename(self.last_loaded_config_path)
            self.config_combobox.set(filename)

    def load_config_from_file(self, filepath, add_to_history=True):
        """加载 API 配置，支持 curl 文件解析，并更新历史记录。 (逻辑不变)"""
        filename = os.path.basename(filepath)
        self.update_log_display(f"尝试从文件加载配置: {filename}", level='INFO')

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            config = None
            try:
                config = json.loads(file_content)
            except json.JSONDecodeError:
                url_match = re.search(r'(?:POST|GET|PUT)\s+[\'"](https?:\/\/[^\'"]+)[\'"]', file_content)
                api_url = url_match.group(1) if url_match else None
                json_body_match = re.search(r'(?:--data-raw|--data)\s+[\'"]\s*(\{.*\})\s*[\'"]', file_content, re.DOTALL)
                if not api_url or not json_body_match:
                    raise ValueError("未在文件中找到有效的 API URL 和/或 JSON 请求主体。")
                json_string = json_body_match.group(1)
                body_data = json.loads(json_string)

                config = {
                    "url": api_url, "webappId": body_data.get('webappId'), "apiKey": body_data.get('apiKey'), "nodeInfoList": body_data.get('nodeInfoList')
                }
            
            required_keys = ['url', 'webappId', 'apiKey', 'nodeInfoList']
            if not all(key in config and config[key] for key in required_keys):
                raise ValueError("解析后的配置信息中缺少必要的字段。")

            self.API_DATA = config
            self.INTERFACE_INFO = [
                {
                    "code": node['nodeId'],
                    "name": node['description'],
                    "type": node['fieldName'],
                    "default_value": node.get('fieldValue', '')
                }
                for node in config['nodeInfoList']
            ]
            
            if add_to_history:
                self.config_filepath_history[filename] = filepath
            self.last_loaded_config_path = filepath
            self.update_config_history_gui()

            self.master.title(f"API Runner - {filename}")
            self.config_file_label.config(text=f"当前文件: {filename}")
            self.api_info_labels['url'].config(text=f"URL: {self.API_DATA['url']}")
            self.api_info_labels['webappId'].config(text=f"Webapp ID: {self.API_DATA['webappId']}")
            key_display = f"{self.API_DATA['apiKey'][:4]}...{self.API_DATA['apiKey'][-4:]}" if self.API_DATA.get('apiKey') else 'N/A'
            self.api_info_labels['apiKey'].config(text=f"API Key: {key_display}")
            
            self._build_editor_tab()
            self.run_btn.config(state='normal') 
            
            self.update_log_display(f"成功加载并解析配置：{filename}", level='SUCCESS')
            self.scan_files_and_update_status()

        except Exception as e:
            msg = f"加载文件时发生错误: {e}"
            messagebox.showerror("加载错误", msg)
            self.update_log_display(msg, level='ERROR')

    def scan_files_and_update_status(self):
        """扫描当前目录下的文件并更新状态，重建 Listbox. (逻辑不变)"""
        self.update_log_display("开始扫描当前目录下的文件...")
        
        try:
            files = os.listdir(self.current_directory)
        except FileNotFoundError:
            self.update_log_display("错误: 当前目录不存在。", level='ERROR')
            return
            
        self.scanned_assets['image'] = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        self.scanned_assets['video'] = [f for f in files if f.lower().endswith(('.mp4', '.mov', '.avi', '.webm'))] 
        self.scanned_assets['json_config'] = [f for f in files if f.lower().endswith('.json')]
        
        if hasattr(self, 'editor_frame'):
            self._build_editor_tab()

        status_msg = (f"图片: {len(self.scanned_assets['image'])}, "
                      f"视频: {len(self.scanned_assets['video'])}, "
                      f"JSON配置: {len(self.scanned_assets['json_config'])}")
        self.scan_status_label.config(text=f"文件扫描状态: {status_msg}")
        self.update_log_display("文件扫描完成。", level='INFO')

    def extract_prompts_from_json(self, json_filenames):
        """从选定的 JSON 文件中提取提示词列表，支持多种格式. (逻辑不变)"""
        self.prompts = []
        text_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'text'), None)
        if not text_id: return

        for filename in json_filenames:
            filepath = os.path.join(self.current_directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 1. [{"prompt": "..."}] 格式
                if isinstance(data, list) and all(isinstance(item, dict) and 'prompt' in item for item in data):
                    self.prompts.extend([item['prompt'] for item in data if item.get('prompt')])
                    continue
                
                # 2. nodeInfoList 格式 (如 API 配置)
                if isinstance(data, dict):
                    data = [data] 
                
                if isinstance(data, list):
                    for payload in data:
                        for node in payload.get('nodeInfoList', []):
                            if node.get('nodeId') == text_id and node.get('fieldValue'):
                                self.prompts.append(node['fieldValue'])
                
                # 3. 纯字符串列表格式
                if isinstance(data, list) and all(isinstance(item, str) for item in data):
                     self.prompts.extend(data)
                     
            except Exception as e:
                self.update_log_display(f"错误: 解析 JSON 文件 {filename} 失败: {e}", level='ERROR')
        
        self.prompts = list(filter(None, self.prompts))

    def _get_base_payload_nodes(self, image_id, video_id, text_id):
        """获取所有字段的默认值，排除将被批量替换的字段。 (逻辑不变)"""
        base_nodes = []
        for info in self.INTERFACE_INFO:
            node_id = info['code']
            field_value = self.value_vars.get(node_id).get() if self.value_vars.get(node_id) and self.value_vars.get(node_id).get() != '' else info['default_value']
            
            if node_id not in [image_id, video_id, text_id] and field_value is not None:
                 base_nodes.append({
                    "nodeId": node_id,
                    "fieldName": info['type'],
                    "fieldValue": field_value,
                    "description": info['name']
                })
        return base_nodes
    
    def _create_payload(self, base_nodes, text_id=None, text_val=None, image_id=None, image_val=None, video_id=None, video_val=None):
        """创建一个单独的请求负载. (逻辑不变)"""
        final_nodes = list(base_nodes)
        
        default_text_val = self.value_vars.get(text_id).get() if text_id and self.value_vars.get(text_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == text_id), None)
        default_image_val = self.file_vars.get(image_id).get() if image_id and self.file_vars.get(image_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == image_id), None)
        default_video_val = self.file_vars.get(video_id).get() if video_id and self.file_vars.get(video_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == video_id), None)
        
        def append_node(node_id, node_type, description, value, default_value):
            if node_id:
                 final_nodes.append({
                    "nodeId": node_id,
                    "fieldName": node_type,
                    "fieldValue": value if value is not None else default_value,
                    "description": description
                })

        text_info = next((info for info in self.INTERFACE_INFO if info['code'] == text_id), None)
        if text_info: append_node(text_id, text_info['type'], text_info['name'], text_val, default_text_val)
            
        image_info = next((info for info in self.INTERFACE_INFO if info['code'] == image_id), None)
        if image_info: append_node(image_id, image_info['type'], image_info['name'], image_val, default_image_val)
            
        video_info = next((info for info in self.INTERFACE_INFO if info['code'] == video_id), None)
        if video_info: append_node(video_id, video_info['type'], video_info['name'], video_val, default_video_val)
            
        return {
            "webappId": self.API_DATA['webappId'],
            "apiKey": self.API_DATA['apiKey'],
            "nodeInfoList": final_nodes
        }
    
    def _create_single_payload(self):
        """创建单个请求负载，使用顶部面板的用户输入。 (逻辑不变)"""
        node_info_list = []
        for info in self.INTERFACE_INFO:
            node_id = info['code']
            field_value = self.value_vars.get(node_id).get() if self.value_vars.get(node_id) else info['default_value']
            
            node_info_list.append({
                "nodeId": node_id,
                "fieldName": info['type'],
                "fieldValue": field_value,
                "description": info['name']
            })
            
        return {
            "webappId": self.API_DATA['webappId'],
            "apiKey": self.API_DATA['apiKey'],
            "nodeInfoList": node_info_list
        }


    def generate_payloads(self):
        """根据用户在 Editor Tab 中的选择和当前模式，生成请求负载列表."""
        if not self.API_DATA:
            messagebox.showerror("错误", "请先加载 API 配置。")
            return
            
        # 1. 获取选中的文件 (已排序)
        selected_images = sorted([self.image_listbox.get(i) for i in self.image_listbox.curselection()])
        selected_videos = sorted([self.video_listbox.get(i) for i in self.video_listbox.curselection()])
        selected_jsons = [self.json_listbox.get(i) for i in self.json_listbox.curselection()]
        
        # 2. 提取提示词
        self.extract_prompts_from_json(selected_jsons)
        prompts = self.prompts
        
        N_img, N_vid, N_prompt = len(selected_images), len(selected_videos), len(prompts)
        
        # 3. 确定输入字段的 Node ID
        text_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'text'), None)
        image_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'image'), None)
        video_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'video'), None)
        
        # 4. 自动推荐最合理的模式 (仅在生成时更新 Combobox，让用户覆盖)
        current_mode = self.batch_mode_var.get()
        
        if N_img > 1 and N_prompt > 1 and N_img == N_prompt:
             self.batch_mode_var.set("M4: 多图多提示词 1:1 顺序匹配")
        elif N_img == 1 and N_prompt > 1:
             self.batch_mode_var.set("M6: 单图多提示词")
        elif N_img > 1 and N_prompt <= 1 and N_vid <= 1:
             # 如果用户之前选择滑窗，则保留滑窗模式
             if "滑窗" not in current_mode:
                self.batch_mode_var.set("M1: 多图单提示词/视频")
        elif N_vid > 1 and N_prompt <= 1 and N_img <= 1:
             self.batch_mode_var.set("M2: 多视频单提示词/图片")
        elif N_prompt > 1 and N_img <= 1 and N_vid <= 1:
             self.batch_mode_var.set("M3: 纯多提示词批量")
        else:
             self.batch_mode_var.set("M0: 默认单请求模式")
        
        final_mode = self.batch_mode_var.get()
        self.update_log_display(f"已根据输入自动推荐模式，当前执行模式: {final_mode}", level='INFO')

        # 5. 根据最终模式执行请求生成
        self.request_payloads = []
        base_payload_nodes = self._get_base_payload_nodes(image_id, video_id, text_id)
        
        # 获取用于批处理的文本/图片/视频默认值 (如果未被批处理文件覆盖)
        prompt_default = prompts[0] if N_prompt == 1 else (self.value_vars.get(text_id).get() if text_id and self.value_vars.get(text_id) else None)
        image_default = selected_images[0] if N_img == 1 else (self.file_vars.get(image_id).get() if image_id and self.file_vars.get(image_id) else None)
        video_default = selected_videos[0] if N_vid == 1 else (self.file_vars.get(video_id).get() if video_id and self.file_vars.get(video_id) else None)
        
        # M0/M3/M6 纯文本或单图+多文本
        if final_mode.startswith("M0") or final_mode.startswith("M3") or final_mode.startswith("M6"):
            items = prompts if N_prompt > 1 else [prompt_default]
            
            for prompt in items:
                 self.request_payloads.append(self._create_payload(
                    base_payload_nodes, text_id, prompt, image_id, image_default, video_id, video_default
                ))
            if final_mode.startswith("M0"): # M0 模式只取第一个
                 self.request_payloads = self.request_payloads[:1]

        # M1/M4/M7 多图模式 (需要处理滑窗)
        elif final_mode.startswith("M1") or final_mode.startswith("M4") or final_mode.startswith("M7"):
            
            # M4: 多图多提示词 1:1
            if final_mode.startswith("M4"):
                 for img, prompt in zip(selected_images, prompts):
                    self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt, image_id, img, video_id, video_default))
            
            # M7a/M7b: 滑窗
            elif final_mode.startswith("M7a") or final_mode.startswith("M7b"):
                window_size, step_size = (2, 1) if "M7a" in final_mode else (3, 2)
                
                i = 0
                while i + window_size <= N_img:
                    window_files = selected_images[i : i + window_size]
                    image_value = ",".join(window_files)
                    
                    self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, image_value, video_id, video_default))
                    i += step_size
            
            # M1: 多图单提示词
            elif final_mode.startswith("M1"):
                for img in selected_images:
                    self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, img, video_id, video_default))

        # M2 多视频模式
        elif final_mode.startswith("M2"):
             for vid in selected_videos:
                 self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, image_default, video_id, vid))

        # M5 笛卡尔积
        elif final_mode.startswith("M5"):
            if N_img == 0 or N_prompt == 0:
                 messagebox.showwarning("警告", "笛卡尔积模式要求同时选中多个图片和多个提示词。已回退到单请求模式。")
                 self.request_payloads = [self._create_single_payload()]
            else:
                 for img in selected_images:
                     for prompt in prompts:
                         self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt, image_id, img, video_id, video_default))
        
        # 兜底或错误处理
        if not self.request_payloads:
             self.request_payloads = [self._create_single_payload()]
             final_mode = "M0: 默认单请求模式 (兜底)"
            
        num_payloads = len(self.request_payloads)
        self.match_status_label.config(text=f"匹配模式: **{final_mode}** ({num_payloads} 个负载)")
        self.update_log_display(f"成功生成 {num_payloads} 个 API 请求负载。模式: {final_mode}", level='SUCCESS')


    # --- API 运行与重试逻辑 (保持不变) ---

    def run_api_requests(self):
        """执行 API 调用，实现重试机制."""
        if not self.request_payloads or not self.API_DATA:
            messagebox.showerror("错误", "请先加载配置并生成请求负载。")
            return

        try:
            max_retries = int(self.max_retries.get())
            retry_interval = int(self.retry_interval.get())
            timeout = int(self.upload_timeout.get())
        except ValueError:
            messagebox.showerror("错误", "重试/超时设置必须是整数。")
            return
        
        self.update_log_display(f"--- 开始执行 {len(self.request_payloads)} 个 API 请求 ---", level='INFO')
        self.update_log_display(f"设置: 超时={timeout}s, 频率={retry_interval}s, 最大重试={max_retries}次", level='INFO')
        self.run_btn.config(state='disabled') 
        
        api_url = self.API_DATA['url']
        
        for i, payload in enumerate(self.request_payloads):
            batch_id = i + 1
            
            for attempt in range(max_retries + 1):
                try:
                    self.update_log_display(f"批次 {batch_id}/{len(self.request_payloads)}: 尝试第 {attempt + 1}/{max_retries + 1} 次...", level='INFO')
                    
                    response = requests.post(api_url, headers=self.BASE_HEADERS, json=payload, timeout=timeout)
                    response.raise_for_status() 
                    
                    response_json = response.json()
                    
                    if response_json.get('success', True) or response.status_code == 200:
                        task_id = response_json.get('taskId', 'N/A')
                        self.update_log_display(f"批次 {batch_id} 成功！Task ID: {task_id}", level='SUCCESS')
                        break 
                    else:
                        error_msg = response_json.get('message', '未知业务错误')
                        raise Exception(f"API 返回业务错误: {error_msg}")

                except requests.exceptions.Timeout:
                    if attempt < max_retries:
                        self.update_log_display(f"批次 {batch_id} 超时，将在 {retry_interval} 秒后重试。", level='WARNING')
                        time.sleep(retry_interval)
                    else:
                        raise
                except requests.exceptions.RequestException as err:
                    if attempt < max_retries:
                        self.update_log_display(f"批次 {batch_id} 连接错误 ({err})，将在 {retry_interval} 秒后重试。", level='WARNING')
                        time.sleep(retry_interval)
                    else:
                        raise
                except Exception as e:
                    if attempt < max_retries:
                         self.update_log_display(f"批次 {batch_id} 错误 ({e})，将在 {retry_interval} 秒后重试。", level='WARNING')
                         time.sleep(retry_interval)
                    else:
                         raise
            else:
                msg = log_error_report(f"执行批次 {batch_id} 失败，已达到最大重试次数 ({max_retries} 次)", self.API_DATA)
                self.update_log_display(msg, level='ERROR')


        self.update_log_display("--- 所有请求执行完毕 ---", level='INFO')
        self.run_btn.config(state='normal') 

    def update_log_display(self, message, level='INFO'):
        """更新 GUI 日志文本框和主日志文件."""
        log_method = getattr(logging, level.lower(), logging.info)
        log_method(message)
        
        self.log_text.config(state='normal')
        self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} [{level}]: {message}\n", level)
        self.log_text.config(state='disabled')
        self.log_text.see(tk.END)
        
    def change_directory(self):
        new_dir = filedialog.askdirectory(initialdir=self.current_directory)
        if new_dir:
            self.current_directory = new_dir
            self.dir_label_var.set(self.current_directory)
            self.update_log_display(f"工作目录已更改为: {new_dir}")
            self.scan_files_and_update_status()

# --- 应用程序启动 ---

if __name__ == "__main__":
    root = tk.Tk()
    app = APIRunnerApp(root)
    root.mainloop()