from flask import Flask, render_template
import os
from flask_wtf.csrf import CSRFProtect
import logging

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
        level=logging.DEBUG,
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
        SECRET_KEY='dev',
        DATA_DIR='/app/data',
        BASE_DIR=os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
        UPLOAD_FOLDER='/app/data/uploads',
        PROCESSED_FOLDER='/app/data/processed',
        ALLOWED_EXTENSIONS={'pdf', 'jpg', 'jpeg', 'png'},
        WTF_CSRF_ENABLED=False,  # Disable CSRF completely for simplicity
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

    # Initialize CSRF protection but with exemptions
    csrf = CSRFProtect()
    csrf.init_app(app)
    
    # Register blueprints
    from app.routes import main
    app.register_blueprint(main)
    
    # Register API routes
    from app.api.routes import api
    app.register_blueprint(api)
    
    # Exempt API routes from CSRF protection
    csrf.exempt(api)

    # Add an error handler
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html'), 404

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