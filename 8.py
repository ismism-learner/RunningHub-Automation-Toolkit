import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import requests
import json
import os
import logging
from datetime import datetime
import re
import time
import threading

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

        self.upload_timeout = tk.IntVar(value=60)
        self.retry_interval = tk.IntVar(value=60)
        self.max_retries = tk.IntVar(value=6)
        self.upload_delay_on_success = tk.IntVar(value=0)

        # New settings for task polling
        self.task_polling_interval = tk.IntVar(value=5)
        self.task_timeout = tk.IntVar(value=300)

        self.BATCH_MODE_OPTIONS = [
            "M0: 默认单请求模式",
            "M1: 多图单提示词/视频",
            "M2: 多视频单提示词/图片",
            "M3: 纯多提示词批量",
            "M4: 多图多提示词 1:1 顺序匹配",
            "M6: 单图多提示词",
            "M7a: 多图滑窗 (2图/1步, [001,002],[002,003]...)",
            "M7b: 多图滑窗 (3图/2步, [001,002,003],[003,004,005]...)",
            "M8: 纯多图批量",
            "M9: 纯多视频批量",
            "M10: 固定单图+多图组合",
            "M11: 固定双图+多图组合",
            "M5: (危险) 笛卡尔积/全组合"
        ]
        self.batch_mode_var = tk.StringVar(value=self.BATCH_MODE_OPTIONS[0])

        self.create_widgets()
        self.update_log_display("请点击 '导入新配置' 或从下拉菜单选择文件来启动应用。", level='WARNING')

    def create_widgets(self):
        main_frame = ttk.Frame(self.master)
        main_frame.pack(pady=10, padx=10, expand=True, fill="both")

        control_area = ttk.Frame(main_frame)
        control_area.pack(side='bottom', fill='x', pady=(10, 0))

        self.log_frame = ttk.LabelFrame(main_frame, text="运行日志 (Run Log)")
        self.log_frame.pack(side='bottom', fill="x", expand=True, pady=(5, 0), ipady=5)
        self._build_log_display()

        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        self.scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_unified_ui(self.scrollable_frame)

        self.run_btn = ttk.Button(control_area, text="🚀 运行 API 请求", command=self.start_run_api_requests_thread, state='disabled')
        self.run_btn.pack(side='left', padx=(0, 10))

        settings_frame = ttk.LabelFrame(control_area, text="运行/重试设置")
        settings_frame.pack(side='left', fill='x', expand=True)
        self.build_settings_widgets(settings_frame)

    def build_settings_widgets(self, parent_frame):
        ttk.Label(parent_frame, text="连接超时(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.upload_timeout, width=5).pack(side='left', padx=(0, 10))

        ttk.Label(parent_frame, text="失败重试间隔(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.retry_interval, width=5).pack(side='left', padx=(0, 10))

        ttk.Label(parent_frame, text="最大重试次数:").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.max_retries, width=5).pack(side='left', padx=(0, 10))

        ttk.Label(parent_frame, text="成功上传间隔(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.upload_delay_on_success, width=5).pack(side='left', padx=(0, 10))

        ttk.Label(parent_frame, text="任务轮询间隔(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.task_polling_interval, width=5).pack(side='left', padx=(0, 10))

        ttk.Label(parent_frame, text="任务超时(s):").pack(side='left', padx=(5, 2))
        ttk.Entry(parent_frame, textvariable=self.task_timeout, width=5).pack(side='left', padx=(0, 5))

    def _build_unified_ui(self, parent_frame):
        load_frame = ttk.LabelFrame(parent_frame, text="API 配置加载")
        load_frame.pack(fill="x", padx=5, pady=5)

        self.config_combobox = ttk.Combobox(load_frame, values=list(self.config_filepath_history.keys()), state='readonly', width=30)
        self.config_combobox.pack(side='left', padx=5, pady=5)
        self.config_combobox.bind("<<ComboboxSelected>>", self.load_config_from_combobox)

        ttk.Button(load_frame, text="📂 导入新配置", command=self.select_and_load_config).pack(side='left', padx=5, pady=5)
        self.config_file_label = ttk.Label(load_frame, text="当前文件: 无")
        self.config_file_label.pack(side='left', padx=10)

        info_frame = ttk.LabelFrame(parent_frame, text="当前 API 信息")
        info_frame.pack(fill="x", padx=5, pady=5)
        self.api_info_labels['url'] = ttk.Label(info_frame, text="URL: N/A"); self.api_info_labels['url'].pack(anchor="w", padx=5)
        self.api_info_labels['webappId'] = ttk.Label(info_frame, text="Webapp ID: N/A"); self.api_info_labels['webappId'].pack(anchor="w", padx=5)
        self.api_info_labels['apiKey'] = ttk.Label(info_frame, text="API Key: N/A"); self.api_info_labels['apiKey'].pack(anchor="w", padx=5)

        scan_frame = ttk.LabelFrame(parent_frame, text="本地文件管理")
        scan_frame.pack(fill="x", padx=5, pady=10)

        self.dir_label_var = tk.StringVar(value=self.current_directory)
        ttk.Label(scan_frame, text="当前目录:").pack(anchor="w", padx=5, pady=2)
        ttk.Label(scan_frame, textvariable=self.dir_label_var, foreground="blue").pack(anchor="w", padx=5)

        btn_frame = ttk.Frame(scan_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="更改目录", command=self.change_directory).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="重新扫描文件", command=self.scan_files_and_update_status).pack(side="left", padx=5)
        self.generate_btn = ttk.Button(btn_frame, text="📝 生成请求负载", command=self.start_generate_payloads_thread)
        self.generate_btn.pack(side='left', padx=(20, 5))

        self.scan_status_label = ttk.Label(scan_frame, text="文件扫描状态: 未运行")
        self.scan_status_label.pack(anchor="w", padx=5, pady=5)

        self.match_status_label = ttk.Label(scan_frame, text="匹配模式: 未生成请求")
        self.match_status_label.pack(anchor="w", padx=5, pady=5)

        self.editor_container_frame = ttk.Frame(parent_frame)
        self.editor_container_frame.pack(fill="x", expand=True, pady=(10,0))
        self._build_editor_ui()

    def _build_editor_ui(self):
        for widget in self.editor_container_frame.winfo_children():
            widget.destroy()

        if not self.API_DATA:
            ttk.Label(self.editor_container_frame, text="请先加载 API 配置以编辑接口值。").pack(padx=20, pady=20)
            return

        top_frame = ttk.LabelFrame(self.editor_container_frame, text="单个请求参数配置 (作为批处理的默认值)")
        top_frame.pack(fill="x", padx=5, pady=5)

        editor_canvas = tk.Canvas(top_frame, height=150)
        editor_scrollbar = ttk.Scrollbar(top_frame, orient="vertical", command=editor_canvas.yview)
        self.interface_list_frame = ttk.Frame(editor_canvas)

        editor_canvas.create_window((0, 0), window=self.interface_list_frame, anchor="nw")
        editor_canvas.configure(yscrollcommand=editor_scrollbar.set)

        editor_canvas.pack(side="left", fill="x", expand=True)
        editor_scrollbar.pack(side="right", fill="y")

        self.interface_list_frame.bind("<Configure>",
            lambda e: editor_canvas.configure(scrollregion=editor_canvas.bbox("all")))

        self.value_vars = {}
        self.file_vars = {}
        for info in self.INTERFACE_INFO:
            row_frame = ttk.Frame(self.interface_list_frame)
            row_frame.pack(fill="x", pady=3, padx=5)

            ttk.Label(row_frame, text=f"[{info['code']}] {info['name']}:", width=15, anchor="w").pack(side="left", padx=5)
            ttk.Label(row_frame, text=f"({info['type']})", width=8).pack(side="left")

            if info['type'] in ("value", "text", "select"):
                var = tk.StringVar(value=info['default_value'])
                self.value_vars[info['code']] = var
                editor = ttk.Entry(row_frame, textvariable=var, width=50)
                editor.pack(side="right", expand=True, fill="x", padx=5)

            elif info['type'] in ("image", "video"):
                var = tk.StringVar(value=info['default_value'])
                self.file_vars[info['code']] = var
                entry = ttk.Entry(row_frame, textvariable=var, state='readonly', width=40)
                entry.pack(side="right", expand=True, fill="x", padx=(0, 5))
                browse_btn = ttk.Button(row_frame, text="浏览...", command=lambda v=var, t=info['type']: self._browse_file_for_var(v, t))
                browse_btn.pack(side="right")

        batch_frame = ttk.LabelFrame(self.editor_container_frame, text="批量文件与模式选择（Ctrl/Shift 多选）")
        batch_frame.pack(fill="both", expand=True, padx=5, pady=5)

        mode_config_frame = ttk.LabelFrame(batch_frame, text="批量模式选择")
        mode_config_frame.pack(fill='x', padx=5, pady=5)

        ttk.Label(mode_config_frame, text="批量模式:").pack(side='left', padx=5)
        self.mode_combobox = ttk.Combobox(mode_config_frame, textvariable=self.batch_mode_var, values=self.BATCH_MODE_OPTIONS, state='readonly', width=70)
        self.mode_combobox.pack(side='left', padx=5, fill='x', expand=True)

        listbox_container = ttk.Frame(batch_frame)
        listbox_container.pack(fill="both", expand=True)

        self.image_listbox, _ = self._create_file_listbox(listbox_container, "图片文件", self.scanned_assets['image'], 'extended')
        self.video_listbox, _ = self._create_file_listbox(listbox_container, "视频文件", self.scanned_assets['video'], 'extended')
        self.json_listbox, _ = self._create_file_listbox(listbox_container, "JSON 提示词/配置", self.scanned_assets['json_config'], 'extended')

    def _create_file_listbox(self, parent, title, file_list, selectmode):
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

        if file_list:
            listbox.select_set(0, tk.END)

        return listbox, None

    def _build_log_display(self):
        """Builds the log display area with both vertical and horizontal scrollbars."""
        log_container = ttk.Frame(self.log_frame)
        log_container.pack(expand=True, fill='both', padx=5, pady=5)
        log_container.grid_rowconfigure(0, weight=1)
        log_container.grid_columnconfigure(0, weight=1)

        v_scrollbar = ttk.Scrollbar(log_container, orient=tk.VERTICAL)
        h_scrollbar = ttk.Scrollbar(log_container, orient=tk.HORIZONTAL)

        self.log_text = tk.Text(log_container, height=8, state='disabled', wrap='none',
                                font=("Consolas", 10),
                                yscrollcommand=v_scrollbar.set,
                                xscrollcommand=h_scrollbar.set)

        v_scrollbar.config(command=self.log_text.yview)
        h_scrollbar.config(command=self.log_text.xview)

        self.log_text.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')

    def load_config_from_combobox(self, event):
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
        self.config_combobox['values'] = list(self.config_filepath_history.keys())
        if self.last_loaded_config_path:
            filename = os.path.basename(self.last_loaded_config_path)
            self.config_combobox.set(filename)

    def load_config_from_file(self, filepath, add_to_history=True):
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

            self._build_editor_ui()
            self.run_btn.config(state='normal')

            self.update_log_display(f"成功加载并解析配置：{filename}", level='SUCCESS')
            self.scan_files_and_update_status()

        except Exception as e:
            msg = f"加载文件时发生错误: {e}"
            messagebox.showerror("加载错误", msg)
            self.update_log_display(msg, level='ERROR')

    def scan_files_and_update_status(self):
        self.update_log_display("开始扫描当前目录下的文件...")

        try:
            files = os.listdir(self.current_directory)
        except FileNotFoundError:
            self.update_log_display("错误: 当前目录不存在。", level='ERROR')
            return

        self.scanned_assets['image'] = sorted([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
        self.scanned_assets['video'] = sorted([f for f in files if f.lower().endswith(('.mp4', '.mov', '.avi', '.webm'))])
        self.scanned_assets['json_config'] = sorted([f for f in files if f.lower().endswith('.json')])

        if hasattr(self, 'editor_container_frame'):
            self._build_editor_ui()

        status_msg = (f"图片: {len(self.scanned_assets['image'])}, "
                      f"视频: {len(self.scanned_assets['video'])}, "
                      f"JSON配置: {len(self.scanned_assets['json_config'])}")
        self.scan_status_label.config(text=f"文件扫描状态: {status_msg}")
        self.update_log_display("文件扫描完成。", level='INFO')

    def extract_prompts_from_json(self, json_filenames):
        self.prompts = []
        text_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'text'), None)
        if not text_id: return

        for filename in json_filenames:
            filepath = os.path.join(self.current_directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if isinstance(data, list) and all(isinstance(item, dict) and 'prompt' in item for item in data):
                    self.prompts.extend([item['prompt'] for item in data if item.get('prompt')])
                    continue

                if isinstance(data, dict): data = [data]

                if isinstance(data, list):
                    for payload in data:
                        for node in payload.get('nodeInfoList', []):
                            if node.get('nodeId') == text_id and node.get('fieldValue'):
                                self.prompts.append(node['fieldValue'])

                if isinstance(data, list) and all(isinstance(item, str) for item in data):
                     self.prompts.extend(data)

            except Exception as e:
                self.update_log_display(f"错误: 解析 JSON 文件 {filename} 失败: {e}", level='ERROR')

        self.prompts = list(filter(None, self.prompts))
        if json_filenames:
            self.update_log_display(f"从JSON文件中成功提取了 {len(self.prompts)} 个提示词。", level='INFO')

    def _get_base_payload_nodes(self, image_id, video_id, text_id):
        base_nodes = []
        for info in self.INTERFACE_INFO:
            node_id = info['code']
            field_value = self.value_vars.get(node_id).get() if self.value_vars.get(node_id) and self.value_vars.get(node_id).get() != '' else info['default_value']

            if node_id not in [image_id, video_id, text_id] and field_value is not None:
                 base_nodes.append({
                    "nodeId": node_id, "fieldName": info['type'], "fieldValue": field_value, "description": info['name']
                })
        return base_nodes

    def _create_payload(self, base_nodes, text_id=None, text_val=None, image_id=None, image_val=None, video_id=None, video_val=None):
        final_nodes = list(base_nodes)

        default_text_val = self.value_vars.get(text_id).get() if text_id and self.value_vars.get(text_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == text_id), None)
        default_image_val = self.file_vars.get(image_id).get() if image_id and self.file_vars.get(image_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == image_id), None)
        default_video_val = self.file_vars.get(video_id).get() if video_id and self.file_vars.get(video_id) else next((info['default_value'] for info in self.INTERFACE_INFO if info['code'] == video_id), None)

        def append_node(node_id, node_type, description, value, default_value):
            if node_id:
                 final_nodes.append({
                    "nodeId": node_id, "fieldName": node_type, "fieldValue": value if value is not None else default_value, "description": description
                })

        text_info = next((info for info in self.INTERFACE_INFO if info['code'] == text_id), None)
        if text_info: append_node(text_id, text_info['type'], text_info['name'], text_val, default_text_val)

        image_info = next((info for info in self.INTERFACE_INFO if info['code'] == image_id), None)
        if image_info: append_node(image_id, image_info['type'], image_info['name'], image_val, default_image_val)

        video_info = next((info for info in self.INTERFACE_INFO if info['code'] == video_id), None)
        if video_info: append_node(video_id, video_info['type'], video_info['name'], video_val, default_video_val)

        return {
            "webappId": self.API_DATA['webappId'], "apiKey": self.API_DATA['apiKey'], "nodeInfoList": final_nodes
        }

    def _create_single_payload(self):
        node_info_list = []
        for info in self.INTERFACE_INFO:
            node_id = info['code']
            field_value = self.value_vars.get(node_id).get() if self.value_vars.get(node_id) else info['default_value']
            node_info_list.append({
                "nodeId": node_id, "fieldName": info['type'], "fieldValue": field_value, "description": info['name']
            })
        return {
            "webappId": self.API_DATA['webappId'], "apiKey": self.API_DATA['apiKey'], "nodeInfoList": node_info_list
        }

    def _browse_file_for_var(self, target_var, file_type='image'):
        """Opens a file dialog to select a single file and updates the target StringVar."""
        if file_type == 'image':
            filetypes = [("Image Files", "*.png *.jpg *.jpeg"), ("All Files", "*.*")]
        elif file_type == 'video':
            filetypes = [("Video Files", "*.mp4 *.mov *.avi *.webm"), ("All Files", "*.*")]
        else:
            filetypes = [("All Files", "*.*")]

        filepath = filedialog.askopenfilename(
            initialdir=self.current_directory,
            filetypes=filetypes
        )
        if filepath:
            filename = os.path.basename(filepath)
            target_var.set(filename)
            self.update_log_display(f"已为单个参数选择文件: {filename}", level='INFO')

    def start_generate_payloads_thread(self):
        """Starts the payload generation process in a separate thread to keep the UI responsive."""
        thread = threading.Thread(target=self.generate_payloads, daemon=True)
        thread.start()

    def generate_payloads(self):
        if not self.API_DATA:
            messagebox.showerror("错误", "请先加载 API 配置。")
            return

        self.generate_btn.config(state='disabled')
        self.run_btn.config(state='disabled')

        try:
            self.update_log_display("--- 开始生成请求负载 ---", level='INFO')

            # 1. Get selected local filenames
            selected_images_local = sorted([self.image_listbox.get(i) for i in self.image_listbox.curselection()])
            selected_videos_local = sorted([self.video_listbox.get(i) for i in self.video_listbox.curselection()])
            selected_jsons = [self.json_listbox.get(i) for i in self.json_listbox.curselection()]

            # 2. Upload all required files first
            self.update_log_display("开始上传所有必需的文件...", level='INFO')

            uploaded_images = [self._upload_file_and_get_url(f) for f in selected_images_local]
            uploaded_images = [url for url in uploaded_images if url]

            uploaded_videos = [self._upload_file_and_get_url(f) for f in selected_videos_local]
            uploaded_videos = [url for url in uploaded_videos if url]

            if len(uploaded_images) != len(selected_images_local) or len(uploaded_videos) != len(selected_videos_local):
                self.update_log_display("一个或多个批量文件上传失败。仅使用上传成功的文件生成任务。", level='WARNING')

            image_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'image'), None)
            video_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'video'), None)

            fixed_image_local = self.file_vars.get(image_id).get() if image_id and self.file_vars.get(image_id) else None
            fixed_video_local = self.file_vars.get(video_id).get() if video_id and self.file_vars.get(video_id) else None

            uploaded_fixed_image = None
            if fixed_image_local and ',' in fixed_image_local:
                fixed_images_parts = [img.strip() for img in fixed_image_local.split(',')]
                uploaded_fixed_parts = [self._upload_file_and_get_url(p) for p in fixed_images_parts]
                uploaded_fixed_parts = [url for url in uploaded_fixed_parts if url]
                if len(uploaded_fixed_parts) == len(fixed_images_parts):
                     uploaded_fixed_image = ",".join(uploaded_fixed_parts)
                else:
                     self.update_log_display("一个或多个固定图片上传失败。", level='ERROR')
            else:
                uploaded_fixed_image = self._upload_file_and_get_url(fixed_image_local)

            uploaded_fixed_video = self._upload_file_and_get_url(fixed_video_local)
            self.update_log_display("文件上传阶段完成。", level='INFO')

            # 3. Extract prompts
            self.extract_prompts_from_json(selected_jsons)
            prompts = self.prompts

            N_img, N_vid, N_prompt = len(uploaded_images), len(uploaded_videos), len(prompts)

            # 4. Auto-recommend mode
            text_id = next((info['code'] for info in self.INTERFACE_INFO if info['type'] == 'text'), None)
            current_mode = self.batch_mode_var.get()

            if N_img > 1 and N_prompt > 1 and N_img == N_prompt: self.batch_mode_var.set("M4: 多图多提示词 1:1 顺序匹配")
            elif N_img == 1 and N_prompt > 1: self.batch_mode_var.set("M6: 单图多提示词")
            elif N_img > 1 and N_prompt == 0 and N_vid == 0: self.batch_mode_var.set("M8: 纯多图批量")
            elif N_vid > 1 and N_prompt == 0 and N_img == 0: self.batch_mode_var.set("M9: 纯多视频批量")
            elif N_img > 1 and N_prompt <= 1:
                 if "滑窗" not in current_mode and "组合" not in current_mode: self.batch_mode_var.set("M1: 多图单提示词/视频")
            elif N_vid > 1 and N_prompt <= 1: self.batch_mode_var.set("M2: 多视频单提示词/图片")
            elif N_prompt > 1 and N_img < 2 and N_vid < 2: self.batch_mode_var.set("M3: 纯多提示词批量")
            elif "组合" not in current_mode: self.batch_mode_var.set("M0: 默认单请求模式")

            final_mode = self.batch_mode_var.get()
            self.update_log_display(f"已根据输入自动推荐模式，当前执行模式: {final_mode}", level='INFO')

            # 5. Generate payloads using UPLOADED URLs
            self.request_payloads = []
            base_payload_nodes = self._get_base_payload_nodes(image_id, video_id, text_id)

            prompt_default = prompts[0] if N_prompt == 1 else (self.value_vars.get(text_id).get() if text_id and self.value_vars.get(text_id) else None)
            image_default = uploaded_fixed_image
            video_default = uploaded_fixed_video

            if final_mode.startswith(("M0", "M3", "M6")):
                items = prompts if N_prompt > 1 else [prompt_default]
                img_val = uploaded_images[0] if N_img == 1 else image_default
                for prompt in items:
                     self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt, image_id, img_val, video_id, video_default))
                if final_mode.startswith("M0"): self.request_payloads = self.request_payloads[:1]

            elif final_mode.startswith(("M1", "M4", "M7", "M8", "M10", "M11")):
                if final_mode.startswith("M4"):
                     for img, prompt in zip(uploaded_images, prompts):
                        self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt, image_id, img, video_id, video_default))
                elif "M7" in final_mode:
                    window_size, step_size = (2, 1) if "M7a" in final_mode else (3, 2)
                    i = 0
                    while i + window_size <= N_img:
                        image_value = ",".join(uploaded_images[i : i + window_size])
                        self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, image_value, video_id, video_default))
                        i += step_size
                elif final_mode.startswith("M8"):
                    for img in uploaded_images:
                        self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, None, image_id, img, video_id, None))
                elif final_mode.startswith("M10"):
                    if not image_default:
                        messagebox.showwarning("模式错误", "M10 模式要求在'单个请求参数'中选择一个固定的图片 (且上传成功)。")
                    else:
                        for img in uploaded_images:
                            combined_images = f"{image_default},{img}"
                            self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, combined_images, video_id, video_default))
                elif final_mode.startswith("M11"):
                    if not image_default or len(image_default.split(',')) != 2:
                         messagebox.showwarning("模式错误", "M11 模式要求在'单个请求参数'的图片栏中选择两个固定的图片 (且上传成功)。")
                    else:
                        for img in uploaded_images:
                            combined_images = f"{image_default},{img}"
                            self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, combined_images, video_id, video_default))
                else: # M1
                    for img in uploaded_images:
                        self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, img, video_id, video_default))

            elif final_mode.startswith(("M2", "M9")):
                 if final_mode.startswith("M9"):
                     for vid in uploaded_videos:
                         self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, None, image_id, None, video_id, vid))
                 else:
                    for vid in uploaded_videos:
                        self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt_default, image_id, image_default, video_id, vid))
            elif final_mode.startswith("M5"):
                if N_img == 0 or N_prompt == 0:
                     messagebox.showwarning("警告", "笛卡尔积模式要求同时选中多个图片和多个提示词。")
                     self.request_payloads = [self._create_single_payload()]
                else:
                     for img in uploaded_images:
                         for prompt in prompts:
                             self.request_payloads.append(self._create_payload(base_payload_nodes, text_id, prompt, image_id, img, video_id, video_default))

            if not self.request_payloads:
                 self.request_payloads = [self._create_single_payload()]
                 final_mode = "M0: 默认单请求模式 (兜底)"

            num_payloads = len(self.request_payloads)
            self.match_status_label.config(text=f"匹配模式: **{final_mode}** ({num_payloads} 个负载)")
            self.update_log_display(f"成功生成 {num_payloads} 个 API 请求负载。模式: {final_mode}", level='SUCCESS')

            if self.request_payloads:
                self.update_log_display("--- 生成的请求负载 (JSON) ---", level='INFO')
                for i, payload in enumerate(self.request_payloads):
                    payload_str = json.dumps(payload, indent=2, ensure_ascii=False)
                    self.update_log_display(f"--- 负载 #{i+1} ---\n{payload_str}", level='INFO')
                self.update_log_display("--- 请求负载日志结束 ---", level='INFO')

        finally:
            self.generate_btn.config(state='normal')
            if self.request_payloads:
                self.run_btn.config(state='normal')

    def _upload_file_and_get_url(self, local_filename):
        """Uploads a single file and returns the server-side filename/URL."""
        if not local_filename:
            return None

        filepath = os.path.join(self.current_directory, local_filename)
        if not os.path.exists(filepath):
            self.update_log_display(f"Upload Error: File not found at {filepath}", level='ERROR')
            return None

        file_type = 'video' if local_filename.lower().endswith(('.mp4', '.mov', '.avi', '.webm')) else 'image'
        upload_url = "https://www.runninghub.cn/task/openapi/upload"

        files = {'file': (local_filename, open(filepath, 'rb'))}
        payload = {
            'apiKey': self.API_DATA['apiKey'],
            'fileType': file_type
        }

        self.update_log_display(f"Uploading {file_type}: {local_filename}...", level='INFO')

        try:
            response = requests.post(upload_url, data=payload, files=files)
            response.raise_for_status()
            response_data = response.json()

            if response_data.get('code') == 0 and response_data.get('data', {}).get('fileName'):
                server_filename = response_data['data']['fileName']
                self.update_log_display(f"Upload successful: {local_filename} -> {server_filename}", level='SUCCESS')
                return server_filename
            else:
                error_msg = response_data.get('msg', 'Unknown upload error')
                self.update_log_display(f"Upload failed for {local_filename}: {error_msg}", level='ERROR')
                return None
        except requests.exceptions.RequestException as e:
            self.update_log_display(f"Upload failed for {local_filename} with network error: {e}", level='ERROR')
            return None
        except Exception as e:
            self.update_log_display(f"An unexpected error occurred during upload of {local_filename}: {e}", level='ERROR')
            return None

    def _handle_single_task(self, payload, batch_id):
        """
        Handles the complete lifecycle of a single task: create, poll for status, and get results.
        Returns True if successful, False otherwise.
        """
        api_url = self.API_DATA['url']
        api_key = self.API_DATA['apiKey']

        connect_timeout = int(self.upload_timeout.get())
        polling_interval = int(self.task_polling_interval.get())
        task_timeout = int(self.task_timeout.get())

        try:
            # 1. Create the task
            self.update_log_display(f"批次 {batch_id}: 正在创建任务...", level='INFO')
            create_response = requests.post(api_url, headers=self.BASE_HEADERS, json=payload, timeout=connect_timeout)
            create_response.raise_for_status()
            create_data = create_response.json()

            if create_data.get('code') != 0 or 'data' not in create_data or 'taskId' not in create_data['data']:
                error_msg = create_data.get('msg', '创建任务时返回了未知错误')
                self.update_log_display(f"批次 {batch_id}: 创建任务失败: {error_msg}", level='ERROR')
                return False

            task_id = create_data['data']['taskId']
            self.update_log_display(f"批次 {batch_id}: 任务创建成功, Task ID: {task_id}", level='INFO')

            # 2. Poll for task completion by checking the outputs endpoint
            start_time = time.time()
            outputs_url = "https://www.runninghub.cn/task/openapi/outputs"

            while True:
                if time.time() - start_time > task_timeout:
                    self.update_log_display(f"批次 {batch_id}: 任务超时 ({task_timeout}s)", level='ERROR')
                    return False

                time.sleep(polling_interval)

                self.update_log_display(f"批次 {batch_id}: 正在查询任务结果 (Task ID: {task_id})...", level='INFO')
                outputs_payload = {"apiKey": api_key, "taskId": task_id}

                try:
                    outputs_response = requests.post(outputs_url, headers=self.BASE_HEADERS, json=outputs_payload, timeout=connect_timeout)
                    outputs_response.raise_for_status()
                    outputs_data = outputs_response.json()
                except requests.exceptions.RequestException as poll_e:
                    self.update_log_display(f"批次 {batch_id}: 查询结果时网络错误: {poll_e}, 将在稍后重试查询。", level='WARNING')
                    continue

                if outputs_data.get('code') == 0:
                    if isinstance(outputs_data.get('data'), list) and outputs_data['data']:
                        self.update_log_display(f"批次 {batch_id}: 任务成功完成!", level='SUCCESS')
                        for i, result in enumerate(outputs_data['data']):
                            file_url = result.get('fileUrl', 'N/A')
                            self.update_log_display(f"  结果 {i+1}: {file_url}", level='SUCCESS')
                        return True
                    else:
                        error_msg = outputs_data.get('msg', '任务完成但未返回任何结果或已失败。')
                        self.update_log_display(f"批次 {batch_id}: {error_msg}", level='ERROR')
                        return False
                else:
                    status_msg = outputs_data.get('msg', '任务仍在处理中...')
                    self.update_log_display(f"批次 {batch_id}: {status_msg}", level='INFO')

        except requests.exceptions.RequestException as e:
            self.update_log_display(f"批次 {batch_id}: 初始网络请求失败: {e}", level='ERROR')
            return False
        except Exception as e:
            log_error_report(f"未知错误在 _handle_single_task: {e}", self.API_DATA)
            self.update_log_display(f"批次 {batch_id}: 处理时发生未知错误: {e}", level='ERROR')
            return False

    def start_run_api_requests_thread(self):
        """Starts the API request process in a separate thread to keep the UI responsive."""
        thread = threading.Thread(target=self.run_api_requests, daemon=True)
        thread.start()

    def run_api_requests(self):
        if not self.request_payloads or not self.API_DATA:
            messagebox.showerror("错误", "请先加载配置并生成请求负载。")
            return
        try:
            max_retries = int(self.max_retries.get())
            retry_interval = int(self.retry_interval.get())
            success_delay = int(self.upload_delay_on_success.get())
            task_polling_interval = int(self.task_polling_interval.get())
            task_timeout = int(self.task_timeout.get())
            connect_timeout = int(self.upload_timeout.get())
        except ValueError:
            messagebox.showerror("错误", "运行设置必须是有效的整数。")
            return

        self.update_log_display(f"--- 开始执行 {len(self.request_payloads)} 个 API 请求 ---", level='INFO')
        settings_log = (f"设置: 连接超时={connect_timeout}s, 失败重试间隔={retry_interval}s, "
                        f"最大重试={max_retries}次, 成功间隔={success_delay}s, "
                        f"任务轮询={task_polling_interval}s, 任务超时={task_timeout}s")
        self.update_log_display(settings_log, level='INFO')
        self.run_btn.config(state='disabled')

        for i, payload in enumerate(self.request_payloads):
            batch_id = i + 1

            for attempt in range(max_retries + 1):
                self.update_log_display(f"批次 {batch_id}/{len(self.request_payloads)}: 开始第 {attempt + 1}/{max_retries + 1} 次尝试...", level='INFO')

                task_successful = self._handle_single_task(payload, batch_id)

                if task_successful:
                    is_last_request = (i == len(self.request_payloads) - 1)
                    if success_delay > 0 and not is_last_request:
                        self.update_log_display(f"等待 {success_delay} 秒后继续下一个批次...", level='INFO')
                        time.sleep(success_delay)
                    break
                else:
                    if attempt < max_retries:
                        self.update_log_display(f"批次 {batch_id} 任务失败，将在 {retry_interval} 秒后重试。", level='WARNING')
                        time.sleep(retry_interval)
            else:
                msg = log_error_report(f"执行批次 {batch_id} 失败，已达到最大重试次数 ({max_retries} 次)。", self.API_DATA)
                self.update_log_display(msg, level='ERROR')

        self.update_log_display("--- 所有请求执行完毕 ---", level='INFO')
        self.run_btn.config(state='normal')

    def update_log_display(self, message, level='INFO'):
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