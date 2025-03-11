/**
 * PDF Studio - Main JavaScript Module
 * Contains utility functions used across the application
 */

console.log("PDF Studio main.js loaded");

/**
 * Get CSRF token from meta tag
 * @return {string} CSRF token or empty string if not found
 */
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    return metaTag ? metaTag.getAttribute('content') : '';
}

/**
 * Format file size in bytes to human-readable format
 * @param {number} bytes - File size in bytes
 * @return {string} Formatted file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Show notification to the user
 * @param {string} message - Message to display
 * @param {string} type - Type of notification (success, error, warning, info)
 */
function showNotification(message, type = 'success') {
    // Implementation for showing notifications
    // In a real app, this would show a toast or notification
    
    // For development purposes only
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        console.log(`[${type}] ${message}`);
    }
}

// Debug logging
document.addEventListener('DOMContentLoaded', function() {
    console.log('PDF Studio initialized');
}); 