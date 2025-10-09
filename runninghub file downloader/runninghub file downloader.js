// ==UserScript==
// @name         RunningHub 视频批量下载助手 (v4.3 最终精简版)
// @namespace    http://tampermonkey.net/
// @version      4.4
// @description  批量下载RunningHub视频和zip文件，无动画过渡，无确认弹窗，支持滚轮调整和详细失败报告。
// @author       Gemini & Jules
// @match        https://www.runninghub.cn/ai-detail/*
// @grant        GM_addStyle
// @grant        unsafeWindow
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // --- 配置 ---
    const MIN_DOWNLOAD_DELAY_MS = 3000; // 最小延迟 3秒
    const MAX_DOWNLOAD_DELAY_MS = 4000; // 最大延迟 4秒
    const MENU_TRIGGER_WAIT_MS = 500;
    // ---------------------------------

    let initialized = false;
    let currentAllFiles = []; // 存储文件数据，内部使用 0-based 索引

    // 1. 样式注入 (保持不变)
    GM_addStyle(`
        #batch-download-control-panel {
            position: fixed;
            top: 60px;
            right: 20px;
            z-index: 10000;
            background-color: #364d79;
            color: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            width: 330px;
            pointer-events: auto;
        }
        #batch-download-control-panel.minimized {
            width: 50px;
            height: 50px;
            padding: 0;
            overflow: hidden;
            border-radius: 50%;
        }
        #panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            cursor: pointer;
        }
        #panel-header h4 {
            margin: 0;
            font-size: 16px;
            white-space: nowrap;
        }
        #collapse-button {
            background: none;
            border: 1px solid white;
            color: white;
            font-size: 16px;
            width: 25px;
            height: 25px;
            line-height: 22px;
            text-align: center;
            border-radius: 50%;
            cursor: pointer;
        }
        #collapse-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
        }
        #batch-download-control-panel.minimized #panel-content { display: none; }
        #batch-download-control-panel.minimized #panel-header { padding: 12px; }
        #batch-download-control-panel.minimized #panel-header h4 { display: none; }

        #time-display {
            margin-bottom: 15px;
            padding: 5px;
            border: 1px dashed rgba(255, 255, 255, 0.5);
            border-radius: 4px;
            font-size: 12px;
            line-height: 1.5;
        }

        #file-selection-input {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            gap: 10px;
        }
        #file-selection-input > div {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        #file-selection-input label {
            font-size: 12px;
            margin-bottom: 5px;
            font-weight: bold;
        }
        #file-selection-input input[type="number"] {
            width: 100%;
            padding: 5px;
            border: none;
            border-radius: 4px;
            color: #333;
            background-color: white;
            text-align: center;
            font-size: 16px;
        }

        #batch-download-button, #refresh-count-button {
            width: 100%;
            margin-top: 5px;
        }
        #refresh-count-button { background-color: #5bc0de; }
        #refresh-count-button:hover { background-color: #31b0d5; }
    `);

    // 2. 核心工具函数 (保持不变)
    function simulateMouseAction(element, eventType) {
        const event = new MouseEvent(eventType, {
            view: unsafeWindow,
            bubbles: true,
            cancelable: true,
            composed: true
        });
        element.dispatchEvent(event);
    }
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    function getRandomDelay() {
        return Math.floor(Math.random() * (MAX_DOWNLOAD_DELAY_MS - MIN_DOWNLOAD_DELAY_MS + 1)) + MIN_DOWNLOAD_DELAY_MS;
    }

    // 3. 下载文件核心逻辑 (已修改：使用 element 属性)
    async function downloadFiles(indicesToProcess, isRetry) {
        let successfulCount = 0;
        let failedList = [];
        const isRetryText = isRetry ? '[重试]' : '[首次]';

        for (const index of indicesToProcess) {
            const fileData = currentAllFiles[index];
            const element = fileData.element; // MODIFIED
            let downloadClicked = false;

            if (!element) {
                console.error(`${isRetryText} 索引 ${index+1} 对应的文件元素未找到。`);
                failedList.push(index);
                continue;
            }

            console.log(`${isRetryText} [${index+1} / ${currentAllFiles.length}] 正在处理文件，时间: ${fileData.timeStr}...`);

            simulateMouseAction(element, 'mouseenter');
            await sleep(MENU_TRIGGER_WAIT_MS);

            try {
                const menuItems = document.querySelectorAll('.ant-dropdown-menu-title-content');
                const downloadMenuItem = Array.from(menuItems).find(el => el.textContent.trim() === '下载');

                if (downloadMenuItem) {
                    const downloadLink = downloadMenuItem.closest('a') || downloadMenuItem.querySelector('a');
                    if (downloadLink) {
                        downloadLink.click();
                        console.log(`✅ ${isRetryText} 文件 ${index+1}：下载操作已触发。`);
                        successfulCount++;
                        downloadClicked = true;
                    }
                }
            } catch (error) {
                console.error(`❌ ${isRetryText} 文件 ${index+1}：查找或点击下载链接时出错:`, error);
            }

            const activeDropdown = document.querySelector('.ant-dropdown');
            if (activeDropdown) {
                activeDropdown.remove();
                console.log(`[CleanUp] 已强制移除激活的下载菜单。`);
            }

            const delay = getRandomDelay();
            console.log(`等待随机延迟: ${delay}ms...`);
            await sleep(delay);

            if (!downloadClicked) {
                 failedList.push(index);
            }
        }
        return { successfulCount, failedList };
    }


    // 4. 批量下载主逻辑 (保持不变)
    async function startBatchDownload(startIndex, endIndex) {
        const downloadButton = document.getElementById('batch-download-button');
        downloadButton.disabled = true;
        downloadButton.textContent = '下载中... 请勿关闭页面';

        const indicesToProcess = Array.from({ length: endIndex - startIndex + 1 }, (_, i) => startIndex + i);

        // --- 第一轮下载 ---
        let firstResult = await downloadFiles(indicesToProcess, false);
        let successfulDownloads = firstResult.successfulCount;
        let failedList = firstResult.failedList;

        // --- 第二轮重试 ---
        if (failedList.length > 0) {
            console.warn(`[重试] 首次下载有 ${failedList.length} 个文件失败，等待 5 秒后开始重试...`);
            alert(`首次下载有 ${failedList.length} 个文件失败，等待 5 秒后开始重试...`);
            await sleep(5000);

            const retryResult = await downloadFiles(failedList, true);
            successfulDownloads += retryResult.successfulCount;
            failedList = retryResult.failedList; // 最终失败列表
        }

        // --- 最终结果统计和报告 ---
        const totalSelected = endIndex - startIndex + 1;
        const finalFailedCount = failedList.length;

        let failedFilesReport = '';
        if (finalFailedCount > 0) {
            const failedTimes = failedList.map(index => {
                const fileData = currentAllFiles[index];
                const fileNumber = index + 1; // 1-based index for user
                return ` - [序号 ${fileNumber}] ${fileData.timeStr}`;
            });
            failedFilesReport = `\n\n最终失败文件 (序号 / 生成时间):\n${failedTimes.join('\n')}`;
        }

        alert(`批量下载完成！\n总共尝试 ${totalSelected} 个文件 (含一次重试)。\n最终成功触发下载: ${successfulDownloads} 个\n最终处理失败/跳过: ${finalFailedCount} 个${failedFilesReport}`);

        downloadButton.textContent = '一键批量下载';
        downloadButton.disabled = false;
    }


    // 5. UI 状态更新 (已重构：基于 .history-item 结构)
    function updateUIState() {
        const allFilesData = [];
        const timeRegex = /(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})/;

        const historyItems = document.querySelectorAll('.history-item');

        historyItems.forEach(item => {
            const ellipsisButton = item.querySelector('span.anticon-ellipsis');
            const timeElement = item.querySelector('.history-create-time');

            if (ellipsisButton && timeElement) {
                const timeMatch = timeElement.textContent.match(timeRegex);
                if (timeMatch) {
                    const timeStr = timeMatch[0];
                    allFilesData.push({
                        element: ellipsisButton,
                        timeStr: timeStr,
                        time: new Date(timeStr.replace(/-/g, "/"))
                    });
                }
            }
        });

        // 按时间从早到晚统一排序
        allFilesData.sort((a, b) => a.time - b.time);

        // 更新全局变量和UI
        currentAllFiles = allFilesData;
        const totalFiles = currentAllFiles.length;

        const totalCountP = document.getElementById('total-file-count');
        const startInput = document.getElementById('start-file-index');
        const endInput = document.getElementById('end-file-index');

        if (totalCountP) {
            totalCountP.innerHTML = `共找到 **${totalFiles}** 个文件`;
        }

        if (startInput) {
            startInput.max = totalFiles;
            const currentStart = parseInt(startInput.value) || 1;
            startInput.value = Math.max(1, Math.min(currentStart, totalFiles || 1));
        }

        if (endInput) {
            endInput.max = totalFiles;
            endInput.value = totalFiles || 1;
        }

        if (startInput) startInput.dispatchEvent(new Event('input'));

        return totalFiles;
    }


    // 6. UI 初始化 (已修改：不再接收参数)
    function initializeUI() {
        if (initialized) return;
        initialized = true;

        const initialTotalFiles = updateUIState();

        const panel = document.createElement('div');
        panel.id = 'batch-download-control-panel';
        panel.innerHTML = `
            <div id="panel-header">
                <h4>批量下载助手 (v4.4)</h4>
                <button id="collapse-button" title="收缩/展开">-</button>
            </div>

            <div id="panel-content">
                <p id="total-file-count">共找到 ${initialTotalFiles} 个文件</p>
                <button id="refresh-count-button">刷新文件数量</button>
                <hr style="border-top: 1px solid rgba(255,255,255,0.2); margin: 10px 0;">

                <div id="time-display">
                    开始时间: <span id="start-file-time">--</span><br>
                    结束时间: <span id="end-file-time">--</span>
                </div>

                <div id="file-selection-input">
                    <div>
                        <label for="start-file-index">开始序号 (1-based)</label>
                        <input type="number" id="start-file-index" min="1" max="${initialTotalFiles}" value="1">
                    </div>
                    <div>
                        <label for="end-file-index">结束序号 (1-based)</label>
                        <input type="number" id="end-file-index" min="1" max="${initialTotalFiles}" value="${initialTotalFiles}">
                    </div>
                </div>

                <button id="batch-download-button">一键批量下载 (${initialTotalFiles} 个文件)</button>
            </div>
        `;
        document.body.appendChild(panel);

        // 获取元素
        const panelEl = document.getElementById('batch-download-control-panel');
        const collapseButton = document.getElementById('collapse-button');
        const startInput = document.getElementById('start-file-index');
        const endInput = document.getElementById('end-file-index');
        const startTimeSpan = document.getElementById('start-file-time');
        const endTimeSpan = document.getElementById('end-file-time');
        const downloadButton = document.getElementById('batch-download-button');
        const refreshButton = document.getElementById('refresh-count-button');

        // 通用事件：收缩和刷新
        collapseButton.addEventListener('click', () => {
            const isMinimized = panelEl.classList.toggle('minimized');
            collapseButton.textContent = isMinimized ? '+' : '-';
        });

        refreshButton.addEventListener('click', () => {
            refreshButton.textContent = '正在刷新...';
            refreshButton.disabled = true;
            updateUIState();
            refreshButton.textContent = '刷新文件数量';
            refreshButton.disabled = false;
        });

        // 核心功能：数字输入更新逻辑 (约束、时间、计数)
        const updateRangeDisplay = () => {
             const totalFiles = currentAllFiles.length;
             let startIdx = parseInt(startInput.value) || 1;
             let endIdx = parseInt(endInput.value) || totalFiles;

             // 1. 约束：确保 start >= 1, end <= totalFiles
             startIdx = Math.max(1, startIdx);
             endIdx = Math.min(totalFiles, endIdx);

             // 2. 约束：确保 start <= end (推拉逻辑)
             if (startIdx > endIdx) {
                 if (startInput === document.activeElement) {
                     endIdx = startIdx;
                 } else if (endInput === document.activeElement) {
                     startIdx = endIdx;
                 } else {
                     endIdx = startIdx;
                 }
             }

             // 3. 更新输入框显示 (应用约束后的值)
             startInput.value = startIdx;
             endInput.value = endIdx;

             // 4. 映射到时间 (注意：这里使用 0-based 索引)
             const startIndex0 = startIdx - 1;
             const endIndex0 = endIdx - 1;

             const startTimeStr = (currentAllFiles[startIndex0] && startIndex0 < totalFiles) ? currentAllFiles[startIndex0].timeStr : '--';
             const endTimeStr = (currentAllFiles[endIndex0] && endIndex0 < totalFiles) ? currentAllFiles[endIndex0].timeStr : '--';


             startTimeSpan.textContent = startTimeStr;
             endTimeSpan.textContent = endTimeStr;

             const count = (totalFiles > 0) ? (endIdx - startIdx + 1) : 0;
             downloadButton.textContent = `一键批量下载 (${count} 个文件)`;
        };

        // 鼠标滚轮处理逻辑
        const handleWheel = (e, inputElement) => {
            e.preventDefault();

            let currentValue = parseInt(inputElement.value);
            const direction = e.deltaY < 0 ? 1 : -1;

            let newValue = currentValue + direction;

            newValue = Math.max(1, newValue);
            newValue = Math.min(currentAllFiles.length || 1, newValue);

            if (newValue !== currentValue) {
                inputElement.value = newValue;
                inputElement.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        // 绑定事件
        startInput.addEventListener('input', updateRangeDisplay);
        endInput.addEventListener('input', updateRangeDisplay);

        startInput.addEventListener('wheel', (e) => handleWheel(e, startInput));
        endInput.addEventListener('wheel', (e) => handleWheel(e, endInput));

        updateRangeDisplay(); // 初始调用

        // 去除确认弹窗，直接启动下载
        downloadButton.addEventListener('click', () => {
            updateRangeDisplay(); // 确保使用最新的约束值
            const startIdx = parseInt(startInput.value);
            const endIdx = parseInt(endInput.value);

            if (startIdx > endIdx || startIdx < 1 || endIdx > currentAllFiles.length || currentAllFiles.length === 0) {
                 alert('文件序号选择无效，请检查！ (1-based, 且开始序号 <= 结束序号)');
                 return;
            }

            // 转换为 0-based 索引
            const startIndex0 = startIdx - 1;
            const endIndex0 = endIdx - 1;

            const confirmMsg = `下载任务已启动：序号 ${startIdx} 到 ${endIdx}，共 ${endIdx - startIdx + 1} 个文件 (含一次重试)。`;
            console.log(`[下载启动] ${confirmMsg}`);

            // 直接启动下载
            startBatchDownload(startIndex0, endIndex0);
        });
    }

    // 7. 持续检查元素是否加载完毕 (已重构：检查 .history-item)
    function checkAndInitialize() {
        if (initialized) {
             clearInterval(intervalId);
             return;
        }
        // 检查 .history-item 元素是否存在
        const historyItemsExist = document.querySelector('.history-item') !== null;

        if (historyItemsExist) {
            initializeUI();
        }
    }

    const intervalId = setInterval(checkAndInitialize, 500);

    setTimeout(() => {
        if (!initialized) {
            clearInterval(intervalId);
            console.warn("RunningHub 批量下载助手：超时，未找到下载项目。");
        }
    }, 20000);
})();