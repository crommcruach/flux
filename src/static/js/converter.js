/**
 * Video Converter Module
 */

import { FilesTab } from '/js/components/files-tab.js';

// State
let selectedFormat = 'hap';
let availableFormats = [];
let canvasSize = {width: 60, height: 300};
let filesTab = null;
let selectedFiles = new Set(); // Track selected files
let usePatternMode = false; // Toggle between browser and pattern mode

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    // Load menu bar
    const menuResponse = await fetch('menu-bar.html');
    document.getElementById('menu-bar-container').innerHTML = await menuResponse.text();

    // Check converter status first
    await checkConverterStatus();
    
    // Load formats
    await loadFormats();
    
    // Load canvas size
    await loadCanvasSize();
    
    // Initialize file browser
    await initializeFileBrowser();
    
    // Setup drop zone
    setupDropZone();
    
    // Event listeners
    document.getElementById('start-conversion-btn').addEventListener('click', startConversion);
    document.getElementById('use-canvas-size-btn').addEventListener('click', useCanvasSize);
    document.getElementById('clear-selection-btn').addEventListener('click', clearSelection);
    document.getElementById('use-pattern-btn').addEventListener('click', togglePatternMode);
    document.getElementById('use-browser-btn')?.addEventListener('click', togglePatternMode);
    document.getElementById('browse-files-btn').addEventListener('click', () => {
        document.getElementById('file-upload-input').click();
    });
    document.getElementById('file-upload-input').addEventListener('change', handleLocalFileSelect);
});

// Initialize file browser with FilesTab component
async function initializeFileBrowser() {
    try {
        // Enable multiselect mode for converter
        filesTab = new FilesTab('converter-files-container', 'converter-search-container', 'button', true);
        await filesTab.init();
        
        // Listen for selection events from FilesTab
        const container = document.getElementById('converter-files-container');
        container.addEventListener('filesSelected', (e) => {
            console.log('Files selected in browser:', e.detail.selectedFiles);
        });
    } catch (error) {
        console.error('Error initializing file browser:', error);
        document.getElementById('converter-files-container').innerHTML = `
            <div class="alert alert-danger">
                Failed to load file browser: ${error.message}
            </div>
        `;
    }
}

// Setup drop zone for drag & drop
function setupDropZone() {
    const dropZone = document.getElementById('drop-zone');
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop zone when dragging over it
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });
    
    // Handle dropped files
    dropZone.addEventListener('drop', handleDrop, false);
    
    // Make drop zone clickable
    dropZone.addEventListener('click', (e) => {
        // Only trigger if clicking the drop zone itself, not the file list
        if (e.target === dropZone || e.target.classList.contains('drop-zone-icon') || 
            e.target.classList.contains('drop-zone-text') || e.target.classList.contains('drop-zone-hint')) {
            document.getElementById('file-upload-input').click();
        }
    });
    
    // Add cursor pointer style
    dropZone.style.cursor = 'pointer';
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDrop(e) {
    const dt = e.dataTransfer;
    
    // Check if actual files were dropped (from file system)
    if (dt.files && dt.files.length > 0) {
        handleLocalFiles(dt.files);
        return;
    }
    
    // Check if multiple files were dropped from file browser
    const filePathsJson = dt.getData('file-paths');
    if (filePathsJson) {
        try {
            const filePaths = JSON.parse(filePathsJson);
            console.log('Drop received - Multiple files:', filePaths);
            filePaths.forEach(path => addFileToSelection(path));
            
            // Clear selection in file browser after drag
            if (filesTab && filesTab.enableMultiselect) {
                filesTab.clearSelection();
            }
            return;
        } catch (error) {
            console.error('Error parsing file paths:', error);
        }
    }
    
    // Check if it's a single file path from the file browser
    const filePath = dt.getData('file-path') || dt.getData('text/plain');
    const fileType = dt.getData('file-type');
    
    console.log('Drop received - filePath:', filePath, 'fileType:', fileType);
    
    if (filePath && (fileType === 'video' || fileType === 'image')) {
        addFileToSelection(filePath);
    }
}

function handleLocalFileSelect(e) {
    const files = e.target.files;
    if (files && files.length > 0) {
        handleLocalFiles(files);
    }
}

async function handleLocalFiles(files) {
    const fileArray = Array.from(files);
    showToast(`Uploading ${fileArray.length} file(s)...`, 'info');
    
    for (const file of fileArray) {
        try {
            // Upload file to server
            const uploadedPath = await uploadFile(file);
            addFileToSelection(uploadedPath);
        } catch (error) {
            console.error('Error uploading file:', error);
            showToast(`Failed to upload ${file.name}: ${error.message}`, 'danger');
        }
    }
    
    showToast(`Successfully uploaded ${fileArray.length} file(s)`, 'success');
}

async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch('/api/converter/upload', {
        method: 'POST',
        body: formData
    });
    
    if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || 'Upload failed');
    }
    
    const data = await response.json();
    return data.path;
}

function addFileToSelection(filePath) {
    if (selectedFiles.has(filePath)) {
        return; // Already added
    }
    
    console.log('Adding file to selection:', filePath);
    selectedFiles.add(filePath);
    updateSelectedFilesList();
}

function removeFileFromSelection(filePath) {
    selectedFiles.delete(filePath);
    updateSelectedFilesList();
}

function updateSelectedFilesList() {
    const listContainer = document.getElementById('selected-files-list');
    
    if (selectedFiles.size === 0) {
        listContainer.innerHTML = '';
        return;
    }
    
    listContainer.innerHTML = '';
    selectedFiles.forEach(filePath => {
        const fileName = filePath.split('/').pop();
        
        const fileItem = document.createElement('div');
        fileItem.className = 'selected-file-item';
        fileItem.innerHTML = `
            <span class="file-icon">🎬</span>
            <span class="file-name" title="${filePath}">${fileName}</span>
            <span class="remove-btn" data-path="${filePath}">
                <i class="bi bi-x-circle"></i>
            </span>
        `;
        
        fileItem.querySelector('.remove-btn').addEventListener('click', () => {
            removeFileFromSelection(filePath);
        });
        
        listContainer.appendChild(fileItem);
    });
}

function clearSelection() {
    selectedFiles.clear();
    updateSelectedFilesList();
    
    // Also clear file browser selection
    if (filesTab && filesTab.enableMultiselect) {
        filesTab.clearSelection();
    }
}

function togglePatternMode() {
    usePatternMode = !usePatternMode;
    
    const browserSection = document.querySelector('.file-selection-area');
    const patternSection = document.getElementById('pattern-input-section');
    
    if (usePatternMode) {
        browserSection.classList.add('d-none');
        patternSection.classList.remove('d-none');
    } else {
        browserSection.classList.remove('d-none');
        patternSection.classList.add('d-none');
    }
}

window.addFileToSelection = addFileToSelection;
window.removeFileFromSelection = removeFileFromSelection;
window.clearSelection = clearSelection;
window.togglePatternMode = togglePatternMode;

async function checkConverterStatus() {
    try {
        const response = await fetch('/api/converter/status');
        const data = await response.json();
        
        if (!data.success || !data.ffmpeg_available) {
            // Show installation instructions
            showFFmpegInstallationGuide();
            document.getElementById('start-conversion-btn').disabled = true;
        }
    } catch (error) {
        console.error('Error checking converter status:', error);
        showToast('Error checking converter status: ' + error.message, 'warning');
    }
}

function showFFmpegInstallationGuide() {
    const guide = document.createElement('div');
    guide.className = 'alert alert-warning alert-dismissible fade show';
    guide.innerHTML = `
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        <h5><i class="bi bi-exclamation-triangle"></i> FFmpeg Not Found</h5>
        <p class="mb-2">FFmpeg is required for video conversion. Please install it:</p>
        <div class="bg-dark p-3 rounded mb-3">
            <code style="color: #0f0;">winget install Gyan.FFmpeg</code>
        </div>
        <p class="mb-2"><strong>Steps:</strong></p>
        <ol class="mb-2">
            <li>Open PowerShell as Administrator</li>
            <li>Run the command above</li>
            <li>Close and reopen PowerShell to refresh PATH</li>
            <li>Verify with: <code>ffmpeg -version</code></li>
            <li>Restart the Flux server</li>
        </ol>
        <p class="mb-0 small">
            <strong>Alternative:</strong> Download manually from 
            <a href="https://ffmpeg.org/download.html" target="_blank">ffmpeg.org/download.html</a>
        </p>
    `;
    
    // Insert at top of card body
    const cardBody = document.querySelector('.card-body');
    cardBody.insertBefore(guide, cardBody.firstChild);
}

async function loadFormats() {
    try {
        const response = await fetch('/api/converter/formats');
        const data = await response.json();
        availableFormats = data.formats;
        
        const container = document.getElementById('format-cards');
        container.innerHTML = '';
        
        data.formats.forEach(format => {
            const card = document.createElement('div');
            card.className = 'col-md-3 mb-3';
            card.innerHTML = `
                <div class="card format-card ${format.id === selectedFormat ? 'selected' : ''}" 
                     data-format="${format.id}">
                    <div class="card-body text-center">
                        <h5>${format.name}</h5>
                        <p class="small mb-0">${format.description}</p>
                    </div>
                </div>
            `;
            container.appendChild(card);
            
            card.querySelector('.format-card').addEventListener('click', () => {
                document.querySelectorAll('.format-card').forEach(c => c.classList.remove('selected'));
                card.querySelector('.format-card').classList.add('selected');
                selectedFormat = format.id;
            });
        });
    } catch (error) {
        console.error('Error loading formats:', error);
        showToast('Error loading formats: ' + error.message, 'danger');
    }
}

async function loadCanvasSize() {
    try {
        const response = await fetch('/api/converter/canvas-size');
        const data = await response.json();
        if (data.success) {
            canvasSize = data.canvas;
        }
    } catch (error) {
        console.error('Error loading canvas size:', error);
    }
}

function useCanvasSize() {
    document.getElementById('target-width').value = canvasSize.width;
    document.getElementById('target-height').value = canvasSize.height;
    document.getElementById('resize-mode').value = 'fit';
}

async function startConversion() {
    const outputDir = document.getElementById('output-dir').value.trim();
    const resizeMode = document.getElementById('resize-mode').value;
    const optimizeLoop = document.getElementById('optimize-loop').checked;
    
    // Determine input: use selected files or pattern
    let inputPattern;
    let filesToConvert = [];
    
    if (usePatternMode) {
        // Use pattern mode
        inputPattern = document.getElementById('input-pattern').value.trim();
        
        // If input doesn't contain wildcards and doesn't start with a path, add video/ prefix
        if (!inputPattern.includes('*') && !inputPattern.includes('\\') && !inputPattern.includes('/')) {
            // Single filename without path - check common video directories
            inputPattern = `video/**/${inputPattern}`;
            showToast('Searching in video folders for: ' + inputPattern, 'info');
        }
    } else {
        // Use selected files from browser
        if (selectedFiles.size === 0) {
            showToast('Please select files to convert or switch to pattern mode', 'warning');
            return;
        }
        
        filesToConvert = Array.from(selectedFiles);
        
        // For browser mode, always use convertMultipleFiles which handles direct paths
        await convertMultipleFiles(filesToConvert, outputDir, resizeMode, optimizeLoop);
        return;
    }
    
    const width = document.getElementById('target-width').value;
    const height = document.getElementById('target-height').value;
    const targetSize = (width && height) ? [parseInt(width), parseInt(height)] : null;
    
    // Show progress section
    document.getElementById('progress-section').classList.add('active');
    document.getElementById('results-summary').classList.add('d-none');
    document.getElementById('start-conversion-btn').classList.add('d-none');
    document.getElementById('stop-conversion-btn').classList.remove('d-none');
    
    // Reset progress
    updateProgress(0, 'Starting conversion...');
    document.getElementById('conversion-queue').innerHTML = '';
    
    try {
        const requestBody = {
            input_pattern: inputPattern,
            output_dir: outputDir,
            format: selectedFormat,
            target_size: targetSize,
            resize_mode: resizeMode,
            optimize_loop: optimizeLoop
        };
        
        console.log('Sending conversion request:', requestBody);
        
        const response = await fetch('/api/converter/batch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestBody)
        });
        
        const data = await response.json();
        console.log('Conversion response:', data);
        
        if (response.ok && data.success) {
            // Show results
            showResults(data);
        } else {
            const errorMsg = data.error || 'Unknown error';
            
            // Show helpful message for "no files found" error
            if (errorMsg.includes('No files found')) {
                showToast(
                    `${errorMsg}\n\nTip: Check if the file exists and the path is correct.\n` +
                    `Examples:\n` +
                    `- video/**/*.mp4 (all MP4 in video folders)\n` +
                    `- video/kanal_1/*.mp4 (specific folder)\n` +
                    `- C:/path/to/video.mp4 (absolute path)`,
                    'warning'
                );
            } else {
                const errorDetails = data.details ? '\n\n' + data.details : '';
                showToast('Conversion failed: ' + errorMsg + errorDetails, 'danger');
            }
            updateProgress(0, 'Conversion failed: ' + errorMsg);
        }
    } catch (error) {
        console.error('Conversion error:', error);
        showToast('Conversion error: ' + error.message, 'danger');
        updateProgress(0, 'Error: ' + error.message);
    } finally {
        document.getElementById('start-conversion-btn').classList.remove('d-none');
        document.getElementById('stop-conversion-btn').classList.add('d-none');
    }
}

async function convertMultipleFiles(files, outputDir, resizeMode, optimizeLoop) {
    const width = document.getElementById('target-width').value;
    const height = document.getElementById('target-height').value;
    const targetSize = (width && height) ? [parseInt(width), parseInt(height)] : null;
    
    // Show progress section
    document.getElementById('progress-section').classList.add('active');
    document.getElementById('results-summary').classList.add('d-none');
    document.getElementById('start-conversion-btn').classList.add('d-none');
    document.getElementById('stop-conversion-btn').classList.remove('d-none');
    
    // Reset progress
    updateProgress(0, 'Starting batch conversion...');
    document.getElementById('conversion-queue').innerHTML = '';
    
    const results = [];
    let successful = 0;
    let failed = 0;
    let totalInputSize = 0;
    let totalOutputSize = 0;
    
    try {
        for (let i = 0; i < files.length; i++) {
            const filePath = files[i];
            // Handle both forward and backslashes
            const fileName = filePath.split(/[/\\]/).pop();
            const progress = ((i) / files.length) * 100;
            
            updateProgress(progress, `Converting ${i + 1}/${files.length}: ${fileName}...`);
            
            try {
                // Generate output path with correct extension based on format
                const fileNameNoExt = fileName.substring(0, fileName.lastIndexOf('.'));
                let outputExt = '.mov'; // Default for HAP formats
                
                if (selectedFormat === 'h264' || selectedFormat === 'h264_nvenc') {
                    outputExt = '.mp4';
                }
                
                const outputPath = `${outputDir}/${fileNameNoExt}_converted${outputExt}`;
                
                console.log('Converting file:', filePath, '-> Output:', outputPath);
                
                const requestBody = {
                    input_path: filePath,
                    output_path: outputPath,
                    format: selectedFormat,
                    target_size: targetSize,
                    resize_mode: resizeMode,
                    optimize_loop: optimizeLoop
                };
                
                const response = await fetch('/api/converter/convert', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(requestBody)
                });
                
                const data = await response.json();
                
                if (response.ok && data.success) {
                    const result = data.result;
                    results.push(result);
                    successful++;
                    totalInputSize += result.input_size_mb || 0;
                    totalOutputSize += result.output_size_mb || 0;
                    addQueueItem(fileName, true, `${result.output_size_mb.toFixed(2)} MB (${(result.compression_ratio * 100).toFixed(1)}% of original)`);
                } else {
                    failed++;
                    const errorMsg = data.error || 'Unknown error';
                    results.push({ success: false, input_path: filePath, error: errorMsg });
                    addQueueItem(fileName, false, errorMsg);
                }
            } catch (error) {
                failed++;
                console.error(`Error converting ${fileName}:`, error);
                results.push({ success: false, input_path: filePath, error: error.message });
                addQueueItem(fileName, false, error.message);
            }
        }
        
        updateProgress(100, 'Batch conversion complete!');
        
        // Show summary
        document.getElementById('success-count').textContent = successful;
        document.getElementById('failed-count').textContent = failed;
        document.getElementById('total-input-size').textContent = totalInputSize.toFixed(2);
        document.getElementById('total-output-size').textContent = totalOutputSize.toFixed(2);
        const compressionRatio = totalInputSize > 0 ? (totalOutputSize / totalInputSize * 100) : 0;
        document.getElementById('compression-ratio').textContent = compressionRatio.toFixed(1);
        document.getElementById('results-summary').classList.remove('d-none');
        
        showToast(`Conversion complete: ${successful} successful, ${failed} failed`, successful > 0 ? 'success' : 'warning');
    } catch (error) {
        console.error('Batch conversion error:', error);
        showToast('Batch conversion error: ' + error.message, 'danger');
    } finally {
        document.getElementById('start-conversion-btn').classList.remove('d-none');
        document.getElementById('stop-conversion-btn').classList.add('d-none');
    }
}

function addQueueItem(fileName, success, message) {
    const queue = document.getElementById('conversion-queue');
    const item = document.createElement('div');
    item.className = `conversion-queue-item ${success ? 'success' : 'error'}`;
    
    const status = success ? `✓ ${message}` : `✗ ${message}`;
    
    item.innerHTML = `
        <div class="d-flex justify-content-between">
            <span><strong>${fileName}</strong></span>
            <span>${status}</span>
        </div>
    `;
    queue.appendChild(item);
}

function updateProgress(percent, text) {
    document.getElementById('progress-bar').style.width = percent + '%';
    document.getElementById('progress-percent').textContent = Math.round(percent) + '%';
    document.getElementById('progress-text').textContent = text;
}

function showResults(data) {
    updateProgress(100, 'Conversion complete!');
    
    // Show queue
    const queue = document.getElementById('conversion-queue');
    queue.innerHTML = '';
    
    let totalInputSize = 0;
    let totalOutputSize = 0;
    
    data.results.forEach(result => {
        const item = document.createElement('div');
        item.className = `conversion-queue-item ${result.success ? 'success' : 'error'}`;
        
        const filename = result.input_path.split(/[/\\]/).pop();
        const status = result.success ? 
            `✓ ${result.output_size_mb.toFixed(2)} MB (${(result.compression_ratio * 100).toFixed(1)}% of original)` :
            `✗ ${result.error}`;
        
        item.innerHTML = `
            <div class="d-flex justify-content-between">
                <span><strong>${filename}</strong></span>
                <span>${status}</span>
            </div>
        `;
        queue.appendChild(item);
        
        if (result.success) {
            totalInputSize += result.input_size_mb;
            totalOutputSize += result.output_size_mb;
        }
    });
    
    // Show summary
    document.getElementById('success-count').textContent = data.successful;
    document.getElementById('failed-count').textContent = data.failed;
    document.getElementById('total-input-size').textContent = totalInputSize.toFixed(2);
    document.getElementById('total-output-size').textContent = totalOutputSize.toFixed(2);
    const compressionRatio = totalInputSize > 0 ? (totalOutputSize / totalInputSize * 100) : 0;
    document.getElementById('compression-ratio').textContent = compressionRatio.toFixed(1);
    document.getElementById('results-summary').classList.remove('d-none');
}

function showToast(message, type = 'info') {
    // Simple toast notification
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} position-fixed top-0 end-0 m-3`;
    toast.style.zIndex = '9999';
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => toast.remove(), 5000);
}
