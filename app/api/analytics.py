"""
Analytics API handlers for PDF Studio
Handles collecting and storing web-vitals metrics
"""
from flask import Blueprint, request, jsonify, current_app
import json
import logging
import os
from datetime import datetime

# Setup logger
logger = logging.getLogger(__name__)

# Create blueprint
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/analytics')

@analytics_bp.route('/web-vitals', methods=['POST'])
def collect_web_vitals():
    """
    Endpoint to collect web-vitals performance metrics
    """
    try:
        # Check if we have a valid request
        if not request.is_json:
            logger.error(f"Invalid content type. Expected application/json, got {request.content_type}")
            return jsonify({"success": False, "error": "Invalid content type"}), 400
        
        # Get data from request
        data = request.json
        if not data:
            logger.error("Empty request body")
            return jsonify({"success": False, "error": "Empty request body"}), 400
        
        # Log received data for debugging
        logger.debug(f"Received web-vitals data: {data}")
        
        # Check required fields
        required_fields = ['name', 'value']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            logger.error(f"Missing required fields: {missing_fields}")
            return jsonify({"success": False, "error": f"Missing required fields: {missing_fields}"}), 400
        
        # Add timestamp
        data['timestamp'] = datetime.utcnow().isoformat()
        
        # Add user agent
        data['userAgent'] = request.headers.get('User-Agent', 'Unknown')
        
        # Add IP (anonymized for privacy)
        ip = request.remote_addr
        if ip:
            # Only store first two octets for privacy
            ip_parts = ip.split('.')
            if len(ip_parts) == 4:  # IPv4
                anonymized_ip = f"{ip_parts[0]}.{ip_parts[1]}.0.0"
                data['anonymizedIP'] = anonymized_ip
        
        # Log performance data
        metric_type = data.get('name', 'unknown')
        metric_value = data.get('value', 'unknown')
        metric_rating = data.get('rating', 'unknown')
        page = data.get('page', 'unknown')
        
        log_message = f"Web Vital: {metric_type}={metric_value} ({metric_rating}) on {page}"
        logger.info(log_message)
        
        # Always log to a persistent data directory
        try:
            # Use DATA_DIR from config which should be mounted as a volume
            data_dir = current_app.config.get('DATA_DIR', '/app/data')
            analytics_dir = os.path.join(data_dir, 'analytics')
            
            # Ensure analytics directory exists
            os.makedirs(analytics_dir, exist_ok=True)
            
            # Create a log file with today's date
            today = datetime.utcnow().strftime('%Y-%m-%d')
            log_file = os.path.join(analytics_dir, f'web_vitals_{today}.jsonl')
            
            with open(log_file, 'a') as f:
                f.write(json.dumps(data) + '\n')
            
            # Debug - show where the file was saved
            logger.info(f"Web vitals data saved to {log_file}")
            
        except Exception as e:
            logger.error(f"Failed to write metrics to persistent storage: {e}", exc_info=True)
        
        return jsonify({
            "success": True,
            "message": log_message,
            "storage_location": os.path.join(data_dir, 'analytics') if 'data_dir' in locals() else "unknown"
        })
    
    except Exception as e:
        logger.error(f"Error collecting web-vitals: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@analytics_bp.route('/reports', methods=['GET'])
def get_reports():
    """
    View available analytics reports
    """
    try:
        # Use DATA_DIR from config
        data_dir = current_app.config.get('DATA_DIR', '/app/data')
        analytics_dir = os.path.join(data_dir, 'analytics')
        
        # Ensure analytics directory exists
        os.makedirs(analytics_dir, exist_ok=True)
        
        # List all files in the analytics directory
        files = os.listdir(analytics_dir)
        report_files = [f for f in files if f.startswith('web_vitals_') and f.endswith('.jsonl')]
        
        reports = []
        for file in report_files:
            file_path = os.path.join(analytics_dir, file)
            file_size = os.path.getsize(file_path)
            file_date = file.replace('web_vitals_', '').replace('.jsonl', '')
            
            # Count entries in the file
            count = 0
            with open(file_path, 'r') as f:
                for line in f:
                    count += 1
            
            reports.append({
                'date': file_date,
                'file': file,
                'size': file_size,
                'metrics_count': count
            })
        
        return jsonify({
            "success": True,
            "reports": reports,
            "analytics_dir": analytics_dir
        })
        
    except Exception as e:
        logger.error(f"Error listing analytics reports: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@analytics_bp.route('/reports/<date>', methods=['GET'])
def get_report_data(date):
    """
    View analytics report data for a specific date
    """
    try:
        # Use DATA_DIR from config
        data_dir = current_app.config.get('DATA_DIR', '/app/data')
        analytics_dir = os.path.join(data_dir, 'analytics')
        
        # Check if the file exists
        file_path = os.path.join(analytics_dir, f'web_vitals_{date}.jsonl')
        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": f"Report for date {date} not found"}), 404
        
        # Read the file
        metrics = []
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    metrics.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        # Group metrics by type
        metrics_by_type = {}
        for metric in metrics:
            metric_type = metric.get('name')
            if metric_type not in metrics_by_type:
                metrics_by_type[metric_type] = []
            metrics_by_type[metric_type].append(metric)
        
        return jsonify({
            "success": True,
            "date": date,
            "metrics_count": len(metrics),
            "metrics_by_type": metrics_by_type
        })
        
    except Exception as e:
        logger.error(f"Error getting report data: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500 