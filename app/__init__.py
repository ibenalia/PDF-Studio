from flask import Flask, render_template, request
import os
from flask_wtf.csrf import CSRFProtect
import logging
import secrets

def create_app(test_config=None):
    """
    Create and configure the Flask application
    
    Args:
        test_config (dict, optional): Test configuration to override default settings
        
    Returns:
        Flask: Configured Flask application instance
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,  # Réduire le niveau en production
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting application")

    # Create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),  # Clé sécurisée
        DATA_DIR='/app/data',
        BASE_DIR=os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
        UPLOAD_FOLDER='/app/data/uploads',
        PROCESSED_FOLDER='/app/data/processed',
        ALLOWED_EXTENSIONS={'pdf', 'jpg', 'jpeg', 'png'},
        WTF_CSRF_ENABLED=True,  # Activer la protection CSRF
        MAX_CONTENT_LENGTH=1024 * 1024 * 1024,  # Limiter la taille des fichiers à 1 Go
    )

    # Log directory paths
    logger.info(f"DATA_DIR: {app.config['DATA_DIR']}")
    logger.info(f"UPLOAD_FOLDER: {app.config['UPLOAD_FOLDER']}")
    logger.info(f"PROCESSED_FOLDER: {app.config['PROCESSED_FOLDER']}")

    # Load custom configuration if it exists
    if test_config is None:
        # Use hardcoded configuration, no need to load from instance
        pass
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)
        
    # Ensure data directories exist
    for dir in ['uploads', 'temp', 'processed']:
        dir_path = os.path.join(app.config['DATA_DIR'], dir)
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Directory created/verified: {dir_path}")

    # Initialize CSRF protection
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Register API routes
    from app.api.routes import api
    app.register_blueprint(api)
    
    # Register Analytics routes
    from app.api.analytics import analytics_bp
    app.register_blueprint(analytics_bp)
    
    # Exempt API routes from CSRF protection
    csrf.exempt(api)
    csrf.exempt(analytics_bp)

    # Add security headers to all responses
    @app.after_request
    def set_security_headers(response):
        # Allow the web-vitals API to be accessed
        if request.path.startswith('/api/analytics/web-vitals'):
            return response
            
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' rsms.me fonts.googleapis.com; img-src 'self' data: images.unsplash.com; font-src 'self' rsms.me fonts.gstatic.com; object-src 'none'; connect-src 'self'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

    # Add an error handler
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404
        
    # Add an error handler for file size limit exceeded
    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('error.html', error="The file is too large. The maximum size is 20 MB."), 413

    # Clean old files
    clean_old_sessions(app)

    logger.info("Application successfully initialized")
    return app 

def ensure_dirs(app):
    """
    Create necessary directories for the application
    
    Args:
        app (Flask): Flask application instance
    """
    data_dir = app.config['DATA_DIR']
    for subdir in ['temp', 'uploads', 'processed']:
        dir_path = os.path.join(data_dir, subdir)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    # Also create bin directory if needed
    bin_dir = os.path.join(app.root_path, '..', 'bin')
    if not os.path.exists(bin_dir):
        os.makedirs(bin_dir)

def clean_old_sessions(app):
    """
    Clean old files at application startup
    
    Args:
        app (Flask): Flask application instance
    """
    with app.app_context():
        try:
            from .api.pdf_processor import clean_old_sessions
            app.logger.info("Cleaning old files...")
            clean_old_sessions(max_age_hours=6)
            app.logger.info("Old files cleanup completed")
        except Exception as e:
            app.logger.error(f"Error during old files cleanup: {e}") 