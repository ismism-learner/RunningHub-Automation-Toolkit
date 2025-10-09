// ==UserScript==
// @name         RunningHub 批量下载助手 (v6.0 - 最终正确版)
// @namespace    http://tampermonkey.net/
// @version      6.0
// @description  批量下载RunningHub中的所有文件。能够正确识别所有下载按钮，并智能处理有无时间戳的情况。
// @author       Gemini & Jules
// @match        https://www.runninghub.cn/ai-detail/*
// @grant        GM_addStyle
// @grant        unsafeWindow
// @run-at       document-start
// ==/UserScript==

(function() {
    'use strict';

    // --- 配置 ---
    const MIN_DOWNLOAD_DELAY_MS = 3000;
    const MAX_DOWNLOAD_DELAY_MS = 4000;
    const MENU_TRIGGER_WAIT_MS = 500;
    // ---------------------------------

    let initialized = false;
    let currentAllFiles = []; // 存储文件数据

    // 1. 样式注入 (保持不变)
    GM_addStyle(`
        #batch-download-control-panel { position: fixed; top: 60px; right: 20px; z-index: 10000; background-color: #364d79; color: white; padding: 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif; width: 330px; pointer-events: auto; }
        #batch-download-control-panel.minimized { width: 50px; height: 50px; padding: 0; overflow: hidden; border-radius: 50%; }
        #panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; cursor: pointer; }
        #panel-header h4 { margin: 0; font-size: 16px; white-space: nowrap; }
        #collapse-button { background: none; border: 1px solid white; color: white; font-size: 16px; width: 25px; height: 25px; line-height: 22px; text-align: center; border-radius: 50%; cursor: pointer; }
        #collapse-button:hover { background-color: rgba(255, 255, 255, 0.1); }
        #batch-download-control-panel.minimized #panel-content { display: none; }
        #batch-download-control-panel.minimized #panel-header { padding: 12px; }
        #batch-download-control-panel.minimized #panel-header h4 { display: none; }
        #time-display { margin-bottom: 15px; padding: 5px; border: 1px dashed rgba(255, 255, 255, 0.5); border-radius: 4px; font-size: 12px; line-height: 1.5; }
        #file-selection-input { display: flex; justify-content: space-between; margin-bottom: 10px; gap: 10px; }
        #file-selection-input > div { flex: 1; display: flex; flex-direction: column; }
        #file-selection-input label { font-size: 12px; margin-bottom: 5px; font-weight: bold; }
        #file-selection-input input[type="number"] { width: 100%; padding: 5px; border: none; border-radius: 4px; color: #333; background-color: white; text-align: center; font-size: 16px; }
        #batch-download-button, #refresh-count-button { width: 100%; margin-top: 5px; }
        #refresh-count-button { background-color: #5bc0de; }
        #refresh-count-button:hover { background-color: #31b0d5; }
    `);

    // 2. 核心工具函数 (已重构)
    function findOriginalTimeStr(triggerElement) {
        const timeRegex = /(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})/;
        const historyItem = triggerElement.closest('.history-item');
        if (historyItem) {
            const timeElement = historyItem.querySelector('.history-create-time');
            if (timeElement) {
                const match = timeElement.textContent.match(timeRegex);
                if (match) return match[1];
            }
        }
        return null;
    }

    function simulateMouseAction(element, eventType) {
        const event = new MouseEvent(eventType, { view: unsafeWindow, bubbles: true, cancelable: true, composed: true });
        element.dispatchEvent(event);
    }
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    function getRandomDelay() {
        return Math.floor(Math.random() * (MAX_DOWNLOAD_DELAY_MS - MIN_DOWNLOAD_DELAY_MS + 1)) + MIN_DOWNLOAD_DELAY_MS;
    }

    // 3. 下载文件核心逻辑 (稳定)
    async function downloadFiles(indicesToProcess, isRetry) {
        let successfulCount = 0;
        let failedList = [];
        const isRetryText = isRetry ? '[重试]' : '[首次]';

        for (const index of indicesToProcess) {
            const fileData = currentAllFiles[index];
            const element = fileData.element;
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
            }
            const delay = getRandomDelay();
            await sleep(delay);
            if (!downloadClicked) {
                 failedList.push(index);
            }
        }
        return { successfulCount, failedList };
    }

    // 4. 批量下载主逻辑 (稳定)
    async function startBatchDownload(startIndex, endIndex) {
        const downloadButton = document.getElementById('batch-download-button');
        downloadButton.disabled = true;
        downloadButton.textContent = '下载中... 请勿关闭页面';

        const indicesToProcess = Array.from({ length: endIndex - startIndex + 1 }, (_, i) => startIndex + i);
        let { successfulCount, failedList } = await downloadFiles(indicesToProcess, false);

        if (failedList.length > 0) {
            console.warn(`[重试] 首次下载有 ${failedList.length} 个文件失败，等待 5 秒后开始重试...`);
            alert(`首次下载有 ${failedList.length} 个文件失败，等待 5 秒后开始重试...`);
            await sleep(5000);
            const retryResult = await downloadFiles(failedList, true);
            successfulCount += retryResult.successfulCount;
            failedList = retryResult.failedList;
        }

        const totalSelected = endIndex - startIndex + 1;
        const finalFailedCount = failedList.length;
        let failedFilesReport = '';
        if (finalFailedCount > 0) {
            const failedTimes = failedList.map(index => ` - [序号 ${index + 1}] ${currentAllFiles[index].timeStr}`);
            failedFilesReport = `\n\n最终失败文件 (序号 / 生成时间):\n${failedTimes.join('\n')}`;
        }
        alert(`批量下载完成！\n总共尝试 ${totalSelected} 个文件 (含一次重试)。\n最终成功触发下载: ${successfulCount} 个\n最终处理失败/跳过: ${finalFailedCount} 个${failedFilesReport}`);
        downloadButton.textContent = '一键批量下载';
        downloadButton.disabled = false;
    }

    // 5. UI 状态更新 (已重构：最终正确逻辑 v6.0)
    function updateUIState() {
        let allFilesData = [];
        const allEllipsisIcons = document.querySelectorAll('span.anticon-ellipsis');

        allEllipsisIcons.forEach(icon => {
            const triggerElement = icon.closest('.ant-dropdown-trigger');
            if (triggerElement) {
                allFilesData.push({
                    element: triggerElement,
                    originalTimeStr: findOriginalTimeStr(triggerElement)
                });
            }
        });

        let lastSeenTimeStr = '--';
        allFilesData.forEach(file => {
            if (file.originalTimeStr) {
                lastSeenTimeStr = file.originalTimeStr;
            }
            file.timeStr = lastSeenTimeStr;
            file.time = file.timeStr !== '--' ? new Date(file.timeStr.replace(/-/g, "/")) : null;
        });

        allFilesData.sort((a, b) => {
            if (a.time === b.time) return 0;
            if (a.time === null) return 1;
            if (b.time === null) return -1;
            return a.time - b.time;
        });

        currentAllFiles = allFilesData;
        const totalFiles = currentAllFiles.length;

        const totalCountP = document.getElementById('total-file-count');
        const startInput = document.getElementById('start-file-index');
        const endInput = document.getElementById('end-file-index');

        if (totalCountP) totalCountP.innerHTML = `共找到 **${totalFiles}** 个文件`;
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

    function findLastAvailableTimeStr(index) {
        if (index < 0 || index >= currentAllFiles.length) return '--';
        for (let i = index; i >= 0; i--) {
            if (currentAllFiles[i].originalTimeStr) {
                return currentAllFiles[i].originalTimeStr;
            }
        }
        return '--';
    }

    // 6. UI 初始化 (已重构)
    function initializeUI() {
        if (initialized) return;
        initialized = true;

        const initialTotalFiles = updateUIState();
        const panel = document.createElement('div');
        panel.id = 'batch-download-control-panel';
        panel.innerHTML = `
            <div id="panel-header"><h4>批量下载助手 (v6.0)</h4><button id="collapse-button" title="收缩/展开">-</button></div>
            <div id="panel-content">
                <p id="total-file-count">共找到 ${initialTotalFiles} 个文件</p>
                <button id="refresh-count-button">刷新文件数量</button>
                <hr style="border-top: 1px solid rgba(255,255,255,0.2); margin: 10px 0;">
                <div id="time-display">开始时间: <span id="start-file-time">--</span><br>结束时间: <span id="end-file-time">--</span></div>
                <div id="file-selection-input">
                    <div><label for="start-file-index">开始序号</label><input type="number" id="start-file-index" min="1" max="${initialTotalFiles}" value="1"></div>
                    <div><label for="end-file-index">结束序号</label><input type="number" id="end-file-index" min="1" max="${initialTotalFiles}" value="${initialTotalFiles}"></div>
                </div>
                <button id="batch-download-button">一键批量下载 (${initialTotalFiles} 个文件)</button>
            </div>`;
        document.body.appendChild(panel);

        const panelEl = document.getElementById('batch-download-control-panel');
        const collapseButton = document.getElementById('collapse-button');
        const startInput = document.getElementById('start-file-index');
        const endInput = document.getElementById('end-file-index');
        const startTimeSpan = document.getElementById('start-file-time');
        const endTimeSpan = document.getElementById('end-file-time');
        const downloadButton = document.getElementById('batch-download-button');
        const refreshButton = document.getElementById('refresh-count-button');

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

        const updateRangeDisplay = () => {
             const totalFiles = currentAllFiles.length;
             let startIdx = parseInt(startInput.value) || 1;
             let endIdx = parseInt(endInput.value) || totalFiles;
             startIdx = Math.max(1, Math.min(startIdx, totalFiles || 1));
             endIdx = Math.max(1, Math.min(endIdx, totalFiles || 1));
             if (startIdx > endIdx) {
                 if (startInput === document.activeElement) endIdx = startIdx;
                 else if (endInput === document.activeElement) startIdx = endIdx;
                 else endIdx = startIdx;
             }
             startInput.value = startIdx;
             endInput.value = endIdx;
             startTimeSpan.textContent = findLastAvailableTimeStr(startIdx - 1);
             endTimeSpan.textContent = findLastAvailableTimeStr(endIdx - 1);
             const count = (totalFiles > 0) ? (endIdx - startIdx + 1) : 0;
             downloadButton.textContent = `一键批量下载 (${count} 个文件)`;
        };

        const handleWheel = (e, inputElement) => {
            e.preventDefault();
            let currentValue = parseInt(inputElement.value);
            let newValue = currentValue + (e.deltaY < 0 ? 1 : -1);
            newValue = Math.max(1, Math.min(currentAllFiles.length || 1, newValue));
            if (newValue !== currentValue) {
                inputElement.value = newValue;
                inputElement.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        startInput.addEventListener('input', updateRangeDisplay);
        endInput.addEventListener('input', updateRangeDisplay);
        startInput.addEventListener('wheel', (e) => handleWheel(e, startInput));
        endInput.addEventListener('wheel', (e) => handleWheel(e, endInput));
        updateRangeDisplay();

        downloadButton.addEventListener('click', () => {
            updateRangeDisplay();
            const startIdx = parseInt(startInput.value);
            const endIdx = parseInt(endInput.value);
            if (startIdx > endIdx || startIdx < 1 || endIdx > currentAllFiles.length || currentAllFiles.length === 0) {
                 alert('文件序号选择无效，请检查！');
                 return;
            }
            startBatchDownload(startIdx - 1, endIdx - 1);
        });
    }

    // 7. 持续检查元素是否加载完毕 (已重构)
    function checkAndInitialize() {
        if (initialized) {
             clearInterval(intervalId);
             return;
        }
        if (document.querySelector('span.anticon-ellipsis')) {
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