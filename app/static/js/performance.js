/**
 * PDF Studio - Performance Monitoring Module
 * Implements web-vitals to track and report Core Web Vitals and other performance metrics
 */

// Use standard module loading
// Note: We'll load the web-vitals from a reliable CDN in the base template

// Function to get CSRF token (duplicate of the one in main.js to avoid dependency)
function getCsrfToken() {
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  return metaTag ? metaTag.getAttribute('content') : '';
}

// Function to send metrics to the server
function sendToAnalytics(metric) {
  // Console log for development
  console.log('Web Vital:', metric.name, metric.value.toFixed(2), metric.rating || 'unknown');
  
  try {
    // Create a simplified payload with only the necessary data
    const payload = {
      name: metric.name,
      value: parseFloat(metric.value.toFixed(2)),
      rating: metric.rating || 'unknown',
      page: window.location.pathname
    };
    
    const csrfToken = getCsrfToken();
    
    // Use fetch API with proper error handling
    fetch('/api/analytics/web-vitals', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken
      },
      body: JSON.stringify(payload),
      keepalive: true
    })
    .then(response => {
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}`);
      }
      return response.json();
    })
    .then(data => {
      console.log('Web vitals data sent successfully');
    })
    .catch(error => {
      console.error('Error sending web vitals data:', error);
    });
  } catch (err) {
    console.error('Error preparing web vitals data:', err);
  }
}

// Initialize performance monitoring - will be called after web-vitals is loaded
function initWebVitals() {
  if (typeof webVitals === 'undefined') {
    console.error('Web Vitals library not found');
    return;
  }

  console.log('Performance monitoring initialized');
  
  try {
    // Core Web Vitals
    webVitals.onCLS(sendToAnalytics);   // Cumulative Layout Shift
    webVitals.onLCP(sendToAnalytics);   // Largest Contentful Paint
    webVitals.onFID(sendToAnalytics);   // First Input Delay
    
    // Other important metrics
    webVitals.onTTFB(sendToAnalytics);  // Time to First Byte
    webVitals.onFCP(sendToAnalytics);   // First Contentful Paint
    webVitals.onINP(sendToAnalytics);   // Interaction to Next Paint
    
    console.log('All web vitals metrics registered');
  } catch (err) {
    console.error('Error setting up web vitals:', err);
  }
}

// Wait for DOM content to be loaded before initializing
document.addEventListener('DOMContentLoaded', function() {
  // Check if web-vitals is loaded
  if (typeof webVitals !== 'undefined') {
    initWebVitals();
  } else {
    console.log('Web Vitals not immediately available, waiting...');
    // Give time for the script to load
    setTimeout(function() {
      if (typeof webVitals !== 'undefined') {
        initWebVitals();
      } else {
        console.error('Web Vitals library failed to load');
      }
    }, 1000);
  }
}); 