/**
 * PDF Splitter Module
 * Handles splitting PDF files into individual pages
 */

document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input');
    const selectFileBtn = document.getElementById('select-file-btn');
    const previewContainer = document.getElementById('preview-container');
    const fileName = document.getElementById('file-name');
    const fileInfo = document.getElementById('file-info');
    const changeFileBtn = document.getElementById('change-file');
    const splitButton = document.getElementById('split-button');
    const progressContainer = document.getElementById('progress-container');
    const resultContainer = document.getElementById('result-container');
    const splitNewFileBtn = document.getElementById('split-new-file');

    // State variables
    let selectedFile = null;
    let currentPageCount = 0;
    
    // Set up UI initial state
    if (previewContainer) previewContainer.style.display = 'none';
    if (progressContainer) progressContainer.style.display = 'none';
    if (resultContainer) resultContainer.style.display = 'none';
    
    /**
     * Formats file size in bytes to human-readable format
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
     * Gets the exact page count from the backend
     * @param {File} file - The PDF file to analyze
     * @return {Promise<number>} Promise resolving to page count
     */
    async function getExactPageCount(file) {
        return new Promise((resolve) => {
            const formData = new FormData();
            formData.append('file', file);
            
            const xhr = new XMLHttpRequest();
            xhr.open('POST', '/api/pdf-info', true);
            
            const csrfToken = getCsrfToken();
            if (csrfToken) {
                xhr.setRequestHeader('X-CSRFToken', csrfToken);
            }
            
            xhr.onload = function() {
                if (xhr.status === 200) {
                    try {
                        const response = JSON.parse(xhr.responseText);
                        const pageCount = response.page_count || response.pageCount || 0;
                        resolve(pageCount);
                    } catch (error) {
                        console.error('Error parsing page count response:', error);
                        resolve(0);
                    }
                } else {
                    console.error('HTTP error getting page count:', xhr.status);
                    resolve(0);
                }
            };
            
            xhr.onerror = function() {
                console.error('Network error getting page count');
                resolve(0);
            };
            
            xhr.send(formData);
        });
    }
    
    /**
     * Updates split button state based on page count
     * @param {number} pageCount - Number of pages in the PDF
     */
    function updateSplitButtonState(pageCount) {
        if (!splitButton) return;
        
        currentPageCount = pageCount;
        
        if (pageCount <= 1) {
            splitButton.disabled = true;
            splitButton.classList.add('opacity-50', 'cursor-not-allowed');
            splitButton.title = "This PDF doesn't have enough pages to be split (minimum 2 pages required)";
        } else {
            splitButton.disabled = false;
            splitButton.classList.remove('opacity-50', 'cursor-not-allowed');
            splitButton.title = "";
        }
    }
    
    /**
     * Handles file selection and displays preview
     * @param {File} file - The selected PDF file
     */
    function handleFileSelect(file) {
        if (!file) return;
        
        selectedFile = file;
        
        // Show file preview
        if (dropArea) dropArea.style.display = 'none';
        if (previewContainer) previewContainer.style.display = 'block';
        
        // Update file information
        if (fileName) fileName.textContent = file.name;
        
        // Show file size initially
        const fileSize = formatFileSize(file.size);
        if (fileInfo) fileInfo.textContent = fileSize;
        
        // Get exact page count from backend
        updateProgress(20, 'Analyzing PDF...');
        if (progressContainer) progressContainer.style.display = 'block';
        
        getExactPageCount(file).then(pageCount => {
            // Update file info with exact page count
            if (fileInfo) {
                fileInfo.textContent = `${fileSize} - ${pageCount} page${pageCount > 1 ? 's' : ''}`;
            }
            
            // Update split button state
            updateSplitButtonState(pageCount);
            
            // Hide progress container
            if (progressContainer) progressContainer.style.display = 'none';
        }).catch(error => {
            console.error('Error getting page count:', error);
            if (fileInfo) {
                fileInfo.textContent = `${fileSize} - Unknown page count`;
            }
            
            // Hide progress container
            if (progressContainer) progressContainer.style.display = 'none';
        });
    }
    
    /**
     * Resets UI to upload state
     */
    function resetToUpload() {
        // Reset file input
        if (fileInput) fileInput.value = '';
        selectedFile = null;
        currentPageCount = 0;
        
        // Reset split button state
        if (splitButton) {
            splitButton.disabled = false;
            splitButton.classList.remove('opacity-50', 'cursor-not-allowed');
            splitButton.title = "";
        }
        
        // Show drop area, hide preview container
        if (dropArea) dropArea.style.display = 'flex';
        if (previewContainer) previewContainer.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'none';
        if (resultContainer) resultContainer.style.display = 'none';
        
        // Remove any error containers
        const errorContainer = document.querySelector('.split-error-container');
        if (errorContainer) {
            errorContainer.style.display = 'none';
        }
    }
    
    /**
     * Resets the entire UI
     */
    function resetUI() {
        resetToUpload();
    }
    
    /**
     * Shows error message
     * @param {string} errorMessage - Error message to display
     */
    function showError(errorMessage) {
        // Hide containers
        if (previewContainer) previewContainer.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'none';
        if (resultContainer) resultContainer.style.display = 'none';
        
        // Create or update error container
        let errorContainer = document.querySelector('.split-error-container');
        
        if (!errorContainer) {
            errorContainer = document.createElement('div');
            errorContainer.className = 'split-error-container mt-4 bg-red-900 bg-opacity-30 rounded-lg border border-red-700 p-4';
            dropArea.parentNode.insertBefore(errorContainer, dropArea.nextSibling);
        }
        
        // Update error message
        errorContainer.style.display = 'block';
        errorContainer.innerHTML = `
            <h3 class="text-lg font-semibold text-red-300 mb-2">Error</h3>
            <p class="text-red-200">${errorMessage}</p>
        `;
        
        // Show drop area again
        if (dropArea) dropArea.style.display = 'flex';
    }
    
    /**
     * Updates progress bar and message
     * @param {number} progress - Progress percentage (0-100)
     * @param {string} message - Progress message to display
     */
    function updateProgress(progress, message) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        
        if (progressBar) progressBar.style.width = `${progress}%`;
        if (progressText) progressText.textContent = message;
    }
    
    /**
     * Gets CSRF token from meta tag or cookies
     * @return {string} CSRF token or empty string
     */
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
        
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrf_token') return value;
        }
        
        return '';
    }
    
    /**
     * Uploads and splits the PDF file
     */
    function uploadAndSplitPDF() {
        if (!selectedFile) {
            showError('Please select a PDF file.');
            return;
        }
        
        if (currentPageCount <= 1) {
            showError('This PDF does not have enough pages to be split (minimum 2 pages required).');
            return;
        }
        
        // Hide preview, show progress
        if (previewContainer) previewContainer.style.display = 'none';
        if (progressContainer) progressContainer.style.display = 'block';
        
        // Update initial progress
        updateProgress(0, 'Preparing PDF...');
        
        // Create FormData object
        const formData = new FormData();
        formData.append('file', selectedFile);
        
        // Get CSRF token
        const csrfToken = getCsrfToken();
        
        // Setup request
        const xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/split-pdf', true);
        
        // Set CSRF token header if available
        if (csrfToken) {
            xhr.setRequestHeader('X-CSRFToken', csrfToken);
        }
        
        // Track upload progress
        xhr.upload.onprogress = function(e) {
            if (e.lengthComputable) {
                const progress = Math.round((e.loaded / e.total) * 50); // 0-50%
                updateProgress(progress, 'Sending file...');
            }
        };
        
        // Handle completion
        xhr.onload = function() {
            if (xhr.status === 200) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    updateProgress(100, 'PDF split successfully!');
            
                    // After a short delay to show 100% progress
                    setTimeout(() => {
                        if (progressContainer) progressContainer.style.display = 'none';
                        showResult(data);
                    }, 500);
                } catch (error) {
                    showError(`Processing response error: ${error.message}`);
                }
            } else {
                showError(`HTTP error! Status: ${xhr.status}`);
            }
        };
        
        // Handle errors
        xhr.onerror = function() {
            showError('Network error during file sending.');
        };
        
        // Send the request
        xhr.send(formData);
        
        // Simulate processing while waiting for response
        let processingProgress = 50;
        const progressInterval = setInterval(() => {
            processingProgress += 2;
            if (processingProgress >= 90) {
                clearInterval(progressInterval);
                return;
            }
            
            let message = processingProgress < 70 ? 'Splitting PDF...' : 'Finalizing...';
            updateProgress(processingProgress, message);
        }, 200);
    }
    
    /**
     * Shows the result of the split operation
     * @param {Object} data - Response data from the server
     */
    function showResult(data) {
        const resultContainer = document.getElementById('result-container');
        const resultMessage = document.getElementById('result-message');
        const downloadAllLink = document.getElementById('download-all-link');
        
        if (!resultContainer || !resultMessage || !downloadAllLink) {
            return;
        }
        
        // Show result container
        resultContainer.style.display = 'block';
        
        // Update result message
        resultMessage.textContent = `Your PDF has been split into ${data.files_count} files.`;
        
        // Set download link
        downloadAllLink.href = data.download_url;
    }
    
    // Set up event listeners
    
    // Drag and drop functionality
    if (dropArea) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(event => {
            dropArea.addEventListener(event, e => {
                e.preventDefault();
                e.stopPropagation();
            });
        });
        
        // Visual feedback
        ['dragenter', 'dragover'].forEach(event => {
            dropArea.addEventListener(event, () => {
                dropArea.classList.add('border-primary-400', 'bg-surface-300');
            });
        });
        
        ['dragleave', 'drop'].forEach(event => {
            dropArea.addEventListener(event, () => {
                dropArea.classList.remove('border-primary-400', 'bg-surface-300');
            });
        });
        
        // Handle drop
        dropArea.addEventListener('drop', e => {
            const files = Array.from(e.dataTransfer.files).filter(file => 
                file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
            );
            
            if (files.length > 0) {
                handleFileSelect(files[0]);
            } else {
                showError('Please select a PDF file.');
            }
        });
        
        // Normal click on drop area (not on button)
        dropArea.addEventListener('click', e => {
            if (!e.target.closest('#select-file-btn')) {
                fileInput.click();
            }
        });
    }
    
    // Button event listeners
    if (selectFileBtn) {
        selectFileBtn.addEventListener('click', e => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', () => {
            if (fileInput.files && fileInput.files.length > 0) {
                handleFileSelect(fileInput.files[0]);
            }
        });
    }
    
    if (changeFileBtn) {
        changeFileBtn.addEventListener('click', resetToUpload);
    }
    
    if (splitButton) {
        splitButton.addEventListener('click', uploadAndSplitPDF);
    }
    
    if (splitNewFileBtn) {
        splitNewFileBtn.addEventListener('click', resetUI);
    }
}); 