# 🧠 RunningHub 动态批处理脚本

一个用于 **RunningHub 平台** 的自动化批处理工具。
该脚本通过解析用户提供的 `curl` 命令模板，自动执行图片上传、任务生成与提交流程，适用于 **图生图 (Image to Image)** 与 **文生图 (Text to Image)** 等多种工作流。

---

## 🚀 功能概述

* **自动化任务生成**
  从指定的 `curl` 命令中解析出 `webappId`、`apiKey` 与节点配置，实现批量执行。

* **多模式支持**

  * **模式一：序列模式** — 自动按批次循环处理所有图片。
  * **模式二：固定图片模式** — 支持通过文件前缀 `#`、`##`、`###` 固定特定位置图片。
  * **模式三：纯文本 (T2I) 模式** — 自动识别并批量提交多组提示词任务。

* **提示词批处理**
  支持从 `.txt` 文件中读取并解析多组提示词，识别格式：

  ```
  === 组合提示词 - NO. 1 ===
  your prompt here...
  === 组合提示词 - NO. 2 ===
  another prompt...
  ```

* **自动上传与重试机制**
  对每张图片自动上传至 RunningHub，失败时进行多次重试并记录错误日志。

* **错误日志与结果记录**

  * 错误日志保存在 `error_log.txt`
  * 成功与失败的任务记录输出至 `results_dynamic_robust.json`

---

## ⚙️ 环境依赖

* Python 3.8 或更高版本
* 依赖库：

  ```bash
  pip install requests
  ```

---

## 📦 使用步骤

### 1️⃣ 修改配置

打开脚本，找到下方配置区域：

```python
# 用户只需在此处粘贴自己的 curl 命令
CURL_COMMAND_TEMPLATE = """
curl --location --request POST 'https://www.runninghub.cn/task/openapi/ai-app/run' \
--header 'Content-Type: application/json' \
--data-raw '{ ... }'
"""
```

将你在 RunningHub 平台复制的 **curl 命令** 原样粘贴进去。

---

### 2️⃣ 准备输入文件

#### 模式一 / 模式二（图片驱动）

在脚本同目录下放置图片：

* 普通图片：按顺序命名，如 `1.jpg`, `2.jpg`, `3.jpg`
* 固定图片：在文件名前添加 `#`、`##`、`###`
  示例：

  ```
  #main.png      → 固定在第1位置
  ##mask.png     → 固定在第2位置
  photo1.jpg
  photo2.jpg
  ```

#### 模式三（文本驱动）

在同目录下放置 `.txt` 文件，格式参考：

```
=== 组合提示词 - NO. 1 ===
beautiful scenery, river, mountain
=== 组合提示词 - NO. 2 ===
cyberpunk city at night, neon lights
```

---

### 3️⃣ 运行脚本

```bash
python 批处理脚本.py
```

脚本会自动检测模式、上传图片、生成任务并提交。
支持交互式选择运行模式（1 或 2）。

---

### 4️⃣ 查看结果

* ✅ 成功任务与任务 ID 会保存在：

  ```
  results_dynamic_robust.json
  ```
* ⚠️ 错误信息会记录在：

  ```
  error_log.txt
  ```
* 所有任务完成后，可前往 [https://www.runninghub.cn/](https://www.runninghub.cn/) 下载结果。

---

## 🧩 目录结构

```
.
├── 批处理脚本.py                # 主程序
├── error_log.txt               # 错误日志（自动生成）
├── results_dynamic_robust.json # 结果记录（自动生成）
├── prompts.txt                 # 提示词输入（可选）
└── images/                     # 图片输入目录（可选）
```

---

## 📜 License

MIT License © 2025

---

## 💡 适用场景

* RunningHub 平台多批次任务自动化执行
* 图生图 / 文生图 批量生成
* 批量提示词测试与模型验证
* 提示词或输入文件批量上传与任务追踪

