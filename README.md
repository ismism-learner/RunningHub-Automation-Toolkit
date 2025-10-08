# ⚙️ RunningHub 自动化工具合集 (RunningHub Automation Toolkit)

这是一个专为 [**RunningHub.cn**](https://www.runninghub.cn/) 平台设计的高效辅助工具合集，旨在帮助创作者实现 **批量生成、批量上传与批量下载**，大幅提升工作流效率。

本项目包含三个核心模块：
1️⃣ **批量提示词生成器**
2️⃣ **批量上传任务执行脚本**
3️⃣ **批量结果文件下载脚本**

---

## 🚀 项目简介

**RunningHub.cn** 是一个集成式的 AI 任务运行平台，支持文本、图像、多模态模型的执行。
然而，对于高频用户来说，手动上传、执行和下载往往效率较低。

本仓库提供的脚本与网页工具可以自动化一些流程，实现“一键批量化”操作，帮助你更快完成 AI 内容生成与管理。

---

## 🧩 模块功能概览

### 🧠 1. 批量提示词生成器（Prompt-word-random-combiner）

**文件名：** `Prompt-word-random-combiner.html`

一个基于网页端的提示词组合工具。

* 支持多分类提示词管理（服装、发型、姿势、镜头等）
* 可随机组合生成 AI 绘图提示词
* 支持收藏、导入/导出、自动保存至浏览器
* 适用于对人的文生图任务（Text-to-Image）

> 💡 用于快速生成高质量的 AI 提示词组合，以便导入 RunningHub 使用。

---

### 🖼️ 2. 批量上传与任务执行脚本（Runninghub Batch Uploader）

**文件名：** `runninghub batch uploader.py`

一个Python 脚本，支持自动解析 RunningHub 的API并批量执行任务。

* 自动识别并上传图片至 RunningHub
* 批量提交任务（支持图生图 / 文生图 / 多模态任务）
* 自动重试、日志记录、结果保存
* 支持固定图片模式与多批次文本输入模式

> 💡 适用于需要大量自动生成任务的用户，例如模型测试、图像批处理、提示词批量实验等。

---

### 📥 3. 批量结果下载脚本（RunningHub File Downloader）

**文件名：** `runninghub file downloader.js`

一个基于 **Tampermonkey（油猴）** 的浏览器脚本，用于在 RunningHub 网站上自动化下载任务结果文件。

* 自动识别任务结果并批量下载
* 支持自定义命名与下载进度显示
* 一键下载所有任务结果（图片、视频或压缩包）

> 💡 安装后可直接在 RunningHub 网页端批量下载生成内容，免去手动点击的繁琐操作。

---

## 🧠 工作流推荐

一个典型的 RunningHub 自动化使用流程如下：

1️⃣ 使用 **提示词生成器** 创建多组 AI 提示词组合
2️⃣ 将这些提示词导入 **批量上传脚本**，自动提交任务
3️⃣ 待任务完成后，使用 **油猴下载脚本** 一键下载所有结果文件

🎯 整个流程完全围绕 RunningHub 平台实现，真正做到从“批量生成”到“批量下载”的全自动化！

---

## ⚙️ 环境要求

### Python 环境（批量上传脚本）

```bash
Python >= 3.8
pip install requests
```

### 浏览器插件（批量下载脚本）

* Tampermonkey / Violentmonkey / Greasemonkey（任选其一）

---

## 📜 License

MIT License © 2025

---

## ❤️ 致谢

特别感谢 [**RunningHub.cn**](https://www.runninghub.cn/) 提供开放接口与创作平台，
使自动化内容创作与批量化工作流成为可能。

---

## 🐔

你也能够成为电商设计大师哦
下面是我的注册邀请码，虽然这些工具都是给有高频需要的人用的，不过如果你是新手用户，还随手点了一下链接的话，我真感激不尽了。
打开链接：https://www.runninghub.cn/?inviteCode=msiu6dkh 注册领500RH币可以免费生成好多图片视频哦！

---
