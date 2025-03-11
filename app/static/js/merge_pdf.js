/**
 * PDF Merger Module
 * Handles merging multiple PDF files into a single document
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('[MERGE] DOM loaded, initializing PDF merger');
    
    // DOM Elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const selectedFilesList = document.getElementById('selected-files-list');
    const fileCount = document.getElementById('file-count');
    const totalSize = document.getElementById('total-size');
    const changeFilesBtn = document.getElementById('change-files');
    const clearAllBtn = document.getElementById('clear-all');
    const mergeButton = document.getElementById('merge-button');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const resultContainer = document.getElementById('result-container');
    const resultMessage = document.getElementById('result-message');
    const downloadLink = document.getElementById('download-link');
    const mergeNewFilesBtn = document.getElementById('merge-new-files');
    const selectFilesBtn = document.getElementById('select-files-btn');
    const filesSelectedIndicator = document.getElementById('files-selected-indicator');
    const filesCountIndicator = document.getElementById('files-count-indicator');
    
    // Sort method radio buttons
    const sortByNameRadio = document.getElementById('sort-by-name');
    const sortBySelectionRadio = document.getElementById('sort-by-selection');
    
    // State
    let selectedFiles = [];
    let totalBytes = 0;
    
    /**
     * Initialize event listeners
     */
    function initEventListeners() {
        // Event Listeners for Drop Area
        if (dropArea) {
            dropArea.addEventListener('dragover', handleDragOver);
            dropArea.addEventListener('dragleave', handleDragLeave);
            dropArea.addEventListener('drop', handleDrop);
            dropArea.addEventListener('click', handleDropAreaClick);
        }
        
        // Handle click on select files button
        if (selectFilesBtn) {
            selectFilesBtn.addEventListener('click', handleSelectButtonClick);
        }
        
        // Handle file selection from input
        if (fileInput) {
            fileInput.addEventListener('change', handleFileInputChange);
        }
        
        // Handle changing files
        if (changeFilesBtn) {
            changeFilesBtn.addEventListener('click', resetToUpload);
        }
        
        // Handle clearing all files
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', clearAllFiles);
        }
        
        // Handle merging
        if (mergeButton) {
            mergeButton.addEventListener('click', uploadAndMergePDFs);
        }
        
        // Handle starting over after merge
        if (mergeNewFilesBtn) {
            mergeNewFilesBtn.addEventListener('click', resetUI);
        }
    }
    
    /**
     * Handle dragover event
     * @param {Event} e - The dragover event
     */
    function handleDragOver(e) {
        e.preventDefault();
        e.stopPropagation();
        dropArea.classList.add('border-primary-400');
        dropArea.classList.add('bg-surface-300');
    }
    
    /**
     * Handle dragleave event
     * @param {Event} e - The dragleave event
     */
    function handleDragLeave(e) {
        e.preventDefault();
        e.stopPropagation();
        dropArea.classList.remove('border-primary-400');
        dropArea.classList.remove('bg-surface-300');
    }
    
    /**
     * Handle drop event
     * @param {Event} e - The drop event
     */
    function handleDrop(e) {
        e.preventDefault();
        e.stopPropagation();
        dropArea.classList.remove('border-primary-400');
        dropArea.classList.remove('bg-surface-300');
        
        const files = Array.from(e.dataTransfer.files).filter(file => 
            file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
        );
        
        if (files.length > 0) {
            handleFilesSelect(files);
        }
    }
    
    /**
     * Handle click on drop area
     * @param {Event} e - The click event
     */
    function handleDropAreaClick(e) {
        // Prevent click if clicking on the select button
        if (e.target.closest('#select-files-btn')) {
            return;
        }
        fileInput.click();
    }
    
    /**
     * Handle click on select files button
     * @param {Event} e - The click event
     */
    function handleSelectButtonClick(e) {
        e.stopPropagation(); // Prevent the click event from reaching the dropArea
        fileInput.click();
    }
    
    /**
     * Handle file input change
     */
    function handleFileInputChange() {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFilesSelect(Array.from(fileInput.files));
        }
    }
    
    /**
     * Handle files selection
     * @param {File[]} files - Array of selected files
     */
    function handleFilesSelect(files) {
        if (!files || files.length === 0) return;
        
        // Add to selected files
        selectedFiles = selectedFiles.concat(files);
        
        // Update UI to show file details
        updateFilesPreview();
        
        // Show preview container and enable merge button
        previewContainer.classList.remove('hidden');
        mergeButton.disabled = false;
        
        // Reset the file input value
        if (fileInput) {
            fileInput.value = '';
        }
    }
    
    /**
     * Update files preview in the UI
     */
    function updateFilesPreview() {
        // Clear the list
        selectedFilesList.innerHTML = '';
        
        // Reset counters
        totalBytes = 0;
        
        // Add each file to the list
        selectedFiles.forEach((file, index) => {
            totalBytes += file.size;
            
            const fileItem = document.createElement('div');
            fileItem.className = 'flex items-center justify-between bg-surface-400 rounded p-2';
            
            const fileInfo = document.createElement('div');
            fileInfo.className = 'flex items-center flex-1 min-w-0';
            
            const iconSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            iconSvg.setAttribute('class', 'h-5 w-5 text-primary-400 flex-shrink-0');
            iconSvg.setAttribute('viewBox', '0 0 20 20');
            iconSvg.setAttribute('fill', 'currentColor');
            iconSvg.innerHTML = '<path fill-rule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clip-rule="evenodd" />';
            
            const fileNameSpan = document.createElement('span');
            fileNameSpan.className = 'ml-2 truncate text-white';
            fileNameSpan.textContent = file.name;
            
            const fileSizeSpan = document.createElement('span');
            fileSizeSpan.className = 'ml-2 text-xs text-gray-400 flex-shrink-0';
            fileSizeSpan.textContent = formatFileSize(file.size);
            
            fileInfo.appendChild(iconSvg);
            fileInfo.appendChild(fileNameSpan);
            fileInfo.appendChild(fileSizeSpan);
            
            const actionButtons = document.createElement('div');
            actionButtons.className = 'flex space-x-2 ml-2';
            
            // Move up button
            if (index > 0) {
                const moveUpBtn = document.createElement('button');
                moveUpBtn.type = 'button';
                moveUpBtn.className = 'text-gray-400 hover:text-primary-400';
                moveUpBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clip-rule="evenodd" /></svg>';
                moveUpBtn.addEventListener('click', () => moveFile(index, index - 1));
                actionButtons.appendChild(moveUpBtn);
            }
            
            // Move down button
            if (index < selectedFiles.length - 1) {
                const moveDownBtn = document.createElement('button');
                moveDownBtn.type = 'button';
                moveDownBtn.className = 'text-gray-400 hover:text-primary-400';
                moveDownBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>';
                moveDownBtn.addEventListener('click', () => moveFile(index, index + 1));
                actionButtons.appendChild(moveDownBtn);
            }
            
            // Remove button
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'text-gray-400 hover:text-red-400';
            removeBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>';
            removeBtn.addEventListener('click', () => removeFile(index));
            actionButtons.appendChild(removeBtn);
            
            fileItem.appendChild(fileInfo);
            fileItem.appendChild(actionButtons);
            
            selectedFilesList.appendChild(fileItem);
        });
        
        // Update the count and size
        fileCount.textContent = selectedFiles.length;
        totalSize.textContent = formatFileSize(totalBytes);
        
        // Update the indicator for already selected files
        if (selectedFiles.length > 0) {
            filesSelectedIndicator.classList.remove('hidden');
            filesCountIndicator.textContent = selectedFiles.length;
        } else {
            filesSelectedIndicator.classList.add('hidden');
        }
    }
    
    /**
     * Move a file from one position to another
     * @param {number} fromIndex - Source index
     * @param {number} toIndex - Destination index
     */
    function moveFile(fromIndex, toIndex) {
        // Reorder the files array
        const file = selectedFiles.splice(fromIndex, 1)[0];
        selectedFiles.splice(toIndex, 0, file);
        
        // Update the UI
        updateFilesPreview();
    }
    
    /**
     * Remove a file from the selection
     * @param {number} index - Index of the file to remove
     */
    function removeFile(index) {
        // Remove the file from the array
        selectedFiles.splice(index, 1);
        
        // Update the UI
        updateFilesPreview();
        
        // If no files left, reset to upload view
        if (selectedFiles.length === 0) {
            resetToUpload();
            mergeButton.disabled = true;
        }
    }
    
    /**
     * Clear all selected files
     */
    function clearAllFiles() {
        selectedFiles = [];
        resetToUpload();
        mergeButton.disabled = true;
    }
    
    /**
     * Reset UI to upload state
     */
    function resetToUpload() {
        previewContainer.classList.add('hidden');
        progressContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
    }
    
    /**
     * Format file size in bytes to human-readable format
     * @param {number} bytes - File size in bytes
     * @return {string} Formatted file size
     */
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    /**
     * Upload and merge PDF files
     */
    function uploadAndMergePDFs() {
        if (selectedFiles.length < 2) {
            alert('Please select at least 2 PDF files to merge.');
            return;
        }
        
        console.log('Starting PDF merge process...');
        
        // Show progress UI
        previewContainer.classList.add('hidden');
        progressContainer.classList.remove('hidden');
        
        // Create FormData to send to server
        const formData = new FormData();
        
        // Add each file
        selectedFiles.forEach((file, index) => {
            formData.append('files[]', file);
        });
        
        // Add sort method
        const sortMethod = sortByNameRadio?.checked ? 'name' : 'selection';
        formData.append('sortMethod', sortMethod);
        
        // Add include bookmarks option
        const includeBookmarks = document.getElementById('include-bookmarks')?.checked || false;
        formData.append('includeBookmarks', includeBookmarks);
        
        // Add CSRF token
        const csrfToken = getCsrfToken();
        if (csrfToken) {
            formData.append('csrf_token', csrfToken);
        }
        
        // Setup for progress tracking
        const xhr = new XMLHttpRequest();
        
        // Listen for progress events if supported
        if (xhr.upload) {
            xhr.upload.addEventListener('progress', function(event) {
                if (event.lengthComputable) {
                    // Calculate upload progress (0-50%)
                    const uploadPercentage = (event.loaded / event.total) * 50;
                    updateProgress(uploadPercentage, 'Uploading files... ');
                }
            });
        }
        
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        // Complete the progress bar when we get the response
                        updateProgress(100, 'Processing complete! ');
                        
                        // Short delay to show the completed progress before showing results
                        setTimeout(() => {
                            showResult(data);
                        }, 500);
                    } catch (error) {
                        console.error('Error parsing response:', error);
                        updateProgress(100, 'Error during processing ');
                        progressText.classList.add('text-red-500');
                    }
                } else {
                    console.error('Request failed:', xhr.status);
                    updateProgress(100, 'Error: ' + xhr.status + ' ');
                    progressText.classList.add('text-red-500');
                }
            } else if (xhr.readyState > 1) {
                // Processing - Update progress based on state (50-90%)
                const stateProgress = 50 + ((xhr.readyState - 1) / 3) * 40;
                updateProgress(stateProgress, 'Merging in progress... ');
            }
        };
        
        // Open and send the request
        xhr.open('POST', '/api/merge-pdf', true);
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
        xhr.send(formData);
        
        // Initialize progress
        updateProgress(0, 'Preparing files... ');
    }
    
    /**
     * Update progress bar and text
     * @param {number} progress - Progress percentage (0-100)
     * @param {string} message - Progress message to display
     */
    function updateProgress(progress, message) {
        // Ensure progress is between 0 and 100
        progress = Math.min(Math.max(progress, 0), 100);
        
        // Update progress bar width
        progressBar.style.width = progress + '%';
        
        // Update progress text with percentage
        progressText.textContent = message + Math.round(progress) + '%';
    }
    
    /**
     * Show result of merge operation
     * @param {Object} data - Response data from the server
     */
    function showResult(data) {
        progressContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
        
        // If there's an error or success is false
        if (data.error || data.success === false) {
            const errorMessage = data.error || "An error occurred while processing your files.";
            resultMessage.textContent = errorMessage;
            resultMessage.classList.add('text-red-500');
            return;
        }
        
        resultMessage.classList.remove('text-red-500');
        resultMessage.textContent = data.message || 'Your PDFs have been successfully merged.';
        
        // Configure the download link
        downloadLink.href = data.download_url || '#';
        
        // If it's a ZIP file, adjust the button text
        if (data.is_zip) {
            downloadLink.querySelector('span').textContent = 'Download ZIP archive';
        } else {
            downloadLink.querySelector('span').textContent = 'Download merged PDF';
        }
    }
    
    /**
     * Reset UI to initial state
     */
    function resetUI() {
        selectedFiles = [];
        totalBytes = 0;
        fileCount.textContent = '0';
        totalSize.textContent = '0 B';
        selectedFilesList.innerHTML = '';
        
        previewContainer.classList.add('hidden');
        progressContainer.classList.add('hidden');
        resultContainer.classList.add('hidden');
        
        // Hide the selected files indicator
        filesSelectedIndicator.classList.add('hidden');
        
        mergeButton.disabled = true;
    }
    
    /**
     * Get CSRF token from meta tag
     * @return {string|null} CSRF token or null if not found
     */
    function getCsrfToken() {
        // Try to get CSRF token from meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        return null;
    }
    
    // Initialize event listeners
    initEventListeners();
}); 