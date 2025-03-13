import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory, session, abort
from werkzeug.utils import secure_filename
import json
import time
import zipfile
from io import BytesIO
from app.api import pdf_processor
import logging
import datetime
from app.auth import requires_auth, get_client_ip, rate_limit, validate_csrf_token, sanitize_redirect_url

# Configurer le logging
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

# Helper functions
def allowed_file(filename, extensions=None):
    if extensions is None:
        extensions = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def generate_unique_filename(filename):
    """Génère un nom de fichier unique basé sur UUID"""
    name, ext = os.path.splitext(filename)
    return f"{uuid.uuid4().hex}{ext}"

def ensure_dir(directory):
    """Crée un répertoire s'il n'existe pas déjà"""
    if not os.path.exists(directory):
        os.makedirs(directory)

# Ensure all data directories exist
def ensure_data_dirs():
    for dir_name in ['uploads', 'temp', 'processed']:
        dir_path = os.path.join(current_app.config['DATA_DIR'], dir_name)
        ensure_dir(dir_path)

@main.before_app_first_request
def setup_directories():
    """Setup all required directories before first request"""
    ensure_data_dirs()

@main.route('/')
def index():
    """Page d'accueil"""
    return render_template('index.html')

@main.route('/upload', methods=['POST'])
def upload_file():
    # Vérifier si l'IP est limitée
    client_ip = get_client_ip()
    if rate_limit(f"upload:{client_ip}", limit=30, period=60):
        logger.warning(f"Rate limit dépassé pour l'upload depuis {client_ip}")
        return jsonify({'error': 'Trop de requêtes, veuillez réessayer plus tard.'}), 429
    
    logger.info("Entrée dans upload_file")
    if 'file' not in request.files:
        logger.error("Pas de fichier dans request.files")
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')
    logger.info(f"Fichiers reçus: {len(files)}")
    
    if not files or files[0].filename == '':
        logger.error("Pas de fichier sélectionné")
        return jsonify({'error': 'No file selected'}), 400
    
    # Vérifier le token CSRF pour les requêtes POST
    csrf_token = request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        logger.warning(f"Tentative d'upload avec un token CSRF invalide depuis {client_ip}")
        return jsonify({'error': 'Invalid CSRF token'}), 403
    
    uploaded_files = []
    for file in files:
        if file and allowed_file(file.filename):
            # Validation supplémentaire du type de fichier
            if file.filename.lower().endswith('.pdf') and not pdf_processor.is_valid_pdf(file):
                logger.warning(f"Fichier PDF invalide rejeté: {file.filename}")
                continue
                
            filename = secure_filename(file.filename)
            unique_filename = generate_unique_filename(filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
            file.save(file_path)
            logger.info(f"Fichier sauvegardé: {file_path}")
            
            # Get file information
            file_size = os.path.getsize(file_path)
            uploaded_files.append({
                'name': filename,
                'unique_name': unique_filename,
                'size': file_size,
                'formatted_size': pdf_processor.format_file_size(file_size),
                'path': file_path
            })
    
    logger.info(f"Fichiers uploadés: {len(uploaded_files)}")
    return jsonify({'files': uploaded_files})

@main.route('/merge-pdf', methods=['GET', 'POST'])
def merge_pdf():
    if request.method == 'GET':
        return render_template('merge_pdf.html')
    
    # Log pour le débogage
    logger.info("Entrée dans merge_pdf - méthode POST")
    logger.info(f"Formulaire reçu: {request.form}")
    logger.info(f"Fichiers reçus: {request.files}")
    logger.info(f"Clés des fichiers: {list(request.files.keys())}")
    
    # Vérification des fichiers soumis
    if 'files[]' not in request.files:
        logger.error("'files[]' n'est pas dans request.files")
        # Essayons de récupérer les fichiers avec un autre nom
        alternative_keys = [key for key in request.files.keys() if 'files' in key or 'file' in key]
        logger.info(f"Clés alternatives trouvées: {alternative_keys}")
        
        if alternative_keys:
            files = []
            for key in alternative_keys:
                files.extend(request.files.getlist(key))
            logger.info(f"Utilisation de clés alternatives, fichiers trouvés: {len(files)}")
        else:
            flash('No files provided', 'error')
            return render_template('merge_pdf.html', error='No files provided')
    else:
        files = request.files.getlist('files[]')
        logger.info(f"Nombre de fichiers dans 'files[]': {len(files)}")
    
    if not files or len(files) < 2:
        logger.error(f"Pas assez de fichiers: {len(files) if files else 0}")
        flash('At least two PDF files are required', 'error')
        return render_template('merge_pdf.html', error='At least two PDF files are required')
    
    # Vérification que tous les fichiers sont des PDFs
    for file in files:
        logger.info(f"Vérification du fichier: {file.filename}")
        if not file or not allowed_file(file.filename, {'pdf'}):
            logger.error(f"Fichier non valide: {file.filename if file else 'None'}")
            flash('All files must be valid PDFs', 'error')
            return render_template('merge_pdf.html', error='All files must be valid PDFs')
    
    try:
        # Déléguer le traitement au composant C++
        logger.info("Début du traitement des fichiers...")
        result = pdf_processor.merge_pdfs(files)
        logger.info(f"Résultat du traitement: {result}")
        flash('PDFs merged successfully!', 'success')
        return render_template('merge_pdf.html', success=True, download_url=result['url'])
    except Exception as e:
        logger.error(f"Erreur lors de la fusion: {str(e)}")
        flash(f'Error merging PDFs: {str(e)}', 'error')
        return render_template('merge_pdf.html', error=f'Error merging PDFs: {str(e)}')

@main.route('/split-pdf', methods=['GET', 'POST'])
def split_pdf():
    if request.method == 'GET':
        return render_template('split_pdf.html')
    
    # Vérification du fichier soumis
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return render_template('split_pdf.html', error='No file provided')
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        flash('Please upload a valid PDF file', 'error')
        return render_template('split_pdf.html', error='Please upload a valid PDF file')
    
    try:
        # Traitement avec un fichier PDF par page
        results = pdf_processor.split_pdf(file, "all")
        
        # Créer un fichier ZIP contenant tous les fichiers PDF (une page par fichier)
        zip_filename = f"split_{uuid.uuid4().hex}.zip"
        zip_path = os.path.join(current_app.config['PROCESSED_FOLDER'], zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for result in results:
                zipf.write(result['path'], os.path.basename(result['path']))
        
        flash('PDF split successfully!', 'success')
        return render_template('split_pdf.html', success=True, download_url=f"/download/{zip_filename}")
    except Exception as e:
        flash(f'Error splitting PDF: {str(e)}', 'error')
        return render_template('split_pdf.html', error=f'Error splitting PDF: {str(e)}')

@main.route('/compress-pdf', methods=['GET', 'POST'])
def compress_pdf():
    if request.method == 'GET':
        return render_template('compress_pdf.html')
    
    # Vérification du fichier soumis
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return render_template('compress_pdf.html', error='No file provided')
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        flash('Please upload a valid PDF file', 'error')
        return render_template('compress_pdf.html', error='Please upload a valid PDF file')
    
    # Récupérer le niveau de compression
    quality = request.form.get('quality', 'medium')
    
    try:
        # Déléguer le traitement au composant C++
        result = pdf_processor.compress_pdf(file, quality)
        flash('PDF compressed successfully!', 'success')
        return render_template('compress_pdf.html', success=True, download_url=result['url'])
    except Exception as e:
        flash(f'Error compressing PDF: {str(e)}', 'error')
        return render_template('compress_pdf.html', error=f'Error compressing PDF: {str(e)}')

@main.route('/rotate-pdf', methods=['GET', 'POST'])
def rotate_pdf():
    if request.method == 'GET':
        return render_template('rotate_pdf.html')
    
    # Vérification du fichier soumis
    if 'file' not in request.files:
        flash('No file provided', 'error')
        return render_template('rotate_pdf.html', error='No file provided')
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        flash('Please upload a valid PDF file', 'error')
        return render_template('rotate_pdf.html', error='Please upload a valid PDF file')
    
    # Récupérer l'angle de rotation
    degrees = request.form.get('degrees', '90')
    
    try:
        degrees = int(degrees)
        # Déléguer le traitement au composant C++
        result = pdf_processor.rotate_pdf(file, degrees)
        flash('PDF rotated successfully!', 'success')
        return render_template('rotate_pdf.html', success=True, download_url=result['url'])
    except ValueError:
        flash('Rotation degrees must be a valid number', 'error')
        return render_template('rotate_pdf.html', error='Rotation degrees must be a valid number')
    except Exception as e:
        flash(f'Error rotating PDF: {str(e)}', 'error')
        return render_template('rotate_pdf.html', error=f'Error rotating PDF: {str(e)}')

@main.route('/download/<filename>')
def download_file(filename):
    # Vérifier si le nom de fichier est sécurisé
    if not secure_filename(filename) == filename:
        logger.warning(f"Tentative d'accès à un fichier non sécurisé: {filename}")
        abort(404)
         
    return send_from_directory(current_app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@main.route('/download-all')
def download_all_files():
    """Route principale qui redirige vers l'API pour le téléchargement de plusieurs fichiers"""
    # Récupérer les paramètres pour les transmettre à l'API
    files_param = request.args.get('files', '')
    clean_param = request.args.get('clean', 'false')
    return redirect(url_for('api.download_all_files', files=files_param, clean=clean_param))

@main.route('/download-session')
def download_session_files():
    """Route principale qui redirige vers l'API pour le téléchargement de session"""
    # Récupérer les paramètres pour les transmettre à l'API
    session_id = request.args.get('session_id', '')
    clean_param = request.args.get('clean', 'false')
    return redirect(url_for('api.download_session_files', session_id=session_id, clean=clean_param))

@main.route('/split-pdf')
def split_pdf_page():
    """Page pour diviser un PDF"""
    return render_template('split_pdf.html')

@main.route('/merge-pdf')
def merge_pdf_page():
    """Page pour fusionner des PDFs"""
    return render_template('merge_pdf.html')

@main.route('/my-files')
def my_files():
    """Page pour afficher les fichiers PDF générés par l'utilisateur"""
    # Obtenir l'ID de session de l'utilisateur
    session_id = pdf_processor.get_session_id()
    
    # Obtenir le chemin du répertoire de traitement
    processed_dir = pdf_processor.get_processed_dir()
    
    print(f"MY FILES: Checking for files in directory: {processed_dir}")
    
    # Liste pour stocker les informations des fichiers
    files = []
    
    # Liste temporaire pour tous les fichiers avant filtrage
    all_files = []
    
    # Vérifier si le répertoire existe
    if os.path.exists(processed_dir):
        # Parcourir tous les fichiers du répertoire
        for filename in os.listdir(processed_dir):
            if filename.endswith('.pdf') or filename.endswith('.zip'):
                print(f"MY FILES: Found file: {filename}")
                file_path = os.path.join(processed_dir, filename)
                file_stats = os.stat(file_path)
                
                # Calculer le temps écoulé depuis la création du fichier
                creation_time = datetime.datetime.fromtimestamp(file_stats.st_mtime)
                time_since_creation = datetime.datetime.now() - creation_time
                
                # Formater le temps écoulé
                if time_since_creation.days > 0:
                    time_elapsed = f"{time_since_creation.days} day{'s' if time_since_creation.days > 1 else ''}"
                elif time_since_creation.seconds // 3600 > 0:
                    hours = time_since_creation.seconds // 3600
                    time_elapsed = f"{hours} hour{'s' if hours > 1 else ''}"
                elif time_since_creation.seconds // 60 > 0:
                    minutes = time_since_creation.seconds // 60
                    time_elapsed = f"{minutes} minute{'s' if minutes > 1 else ''}"
                else:
                    time_elapsed = "a few seconds"
                
                # Créer une structure avec les informations du fichier
                file_info = {
                    'filename': filename,
                    'display_name': filename.split('_', 1)[1] if '_' in filename else filename,
                    'size': file_stats.st_size,
                    'size_formatted': pdf_processor.format_file_size(file_stats.st_size),
                    'creation_time': creation_time.strftime('%m/%d/%Y at %H:%M'),
                    'time_elapsed': time_elapsed,
                    'download_url': f"/download/{filename}",
                    'is_zip': filename.endswith('.zip'),
                    'is_split_page': '_page_' in filename and filename.endswith('.pdf')
                }
                
                all_files.append(file_info)
        
        # Identifier les ZIP de fractionnement
        split_zips = [f for f in all_files if f['is_zip'] and f['filename'].startswith('split_')]
        print(f"MY FILES: Found {len(split_zips)} split ZIP files: {[z['filename'] for z in split_zips]}")
        
        # Identifier les pages individuelles de fractionnement
        split_pages = [f for f in all_files if f['is_split_page']]
        print(f"MY FILES: Found {len(split_pages)} split pages")
        
        # Filtrer les fichiers pour exclure les pages individuelles
        # si un fichier ZIP de fractionnement existe dans la même période
        filtered_files = []
        for file in all_files:
            # Toujours inclure les fichiers ZIP et les fichiers qui ne sont pas des pages individuelles
            if file['is_zip'] or not file['is_split_page']:
                filtered_files.append(file)
                print(f"MY FILES: Including file in filtered list: {file['filename']}")
            # Pour les pages individuelles, ne les garder que si elles n'ont pas de ZIP correspondant créé à peu près au même moment
            elif file['is_split_page']:
                # On ne garde pas les pages individuelles (comportement existant)
                print(f"MY FILES: Excluding split page from filtered list: {file['filename']}")
                continue
        
        files = filtered_files
        
        # Trier les fichiers par date de création (les plus récents d'abord)
        files.sort(key=lambda x: x['creation_time'], reverse=True)
    
    return render_template('my_files.html', files=files)

@main.route('/admin')
@requires_auth
def admin_dashboard():
    """Page d'administration sécurisée"""
    # Récupérer les statistiques du système
    stats = {
        'upload_count': 0,
        'processed_count': 0,
        'disk_usage': 0,
        'disk_usage_formatted': '0 MB'
    }
    
    # Compter les fichiers
    try:
        upload_dir = current_app.config['UPLOAD_FOLDER']
        processed_dir = current_app.config['PROCESSED_FOLDER']
        
        if os.path.exists(upload_dir):
            stats['upload_count'] = len([f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))])
            
        if os.path.exists(processed_dir):
            stats['processed_count'] = len([f for f in os.listdir(processed_dir) if os.path.isfile(os.path.join(processed_dir, f))])
            
        # Calculer l'utilisation du disque
        stats['disk_usage'] = sum(os.path.getsize(os.path.join(upload_dir, f)) for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f)))
        stats['disk_usage'] += sum(os.path.getsize(os.path.join(processed_dir, f)) for f in os.listdir(processed_dir) if os.path.isfile(os.path.join(processed_dir, f)))
        stats['disk_usage_formatted'] = pdf_processor.format_file_size(stats['disk_usage'])
    except Exception as e:
        logger.error(f"Erreur lors du calcul des statistiques: {str(e)}")
    
    return render_template('admin/dashboard.html', stats=stats)

@main.route('/admin/clean-files', methods=['POST'])
@requires_auth
def admin_clean_files():
    """Nettoyer les fichiers anciens (action d'administration)"""
    # Vérifier le token CSRF
    csrf_token = request.form.get('csrf_token')
    if not validate_csrf_token(csrf_token):
        return redirect(url_for('main.admin_dashboard'))
    
    try:
        # Nettoyer les fichiers
        pdf_processor.clean_old_sessions(max_age_hours=1)  # Nettoyer les fichiers de plus d'une heure
        flash('Les fichiers ont été nettoyés avec succès.', 'success')
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des fichiers: {str(e)}")
        flash(f'Erreur lors du nettoyage des fichiers: {str(e)}', 'error')
    
    return redirect(url_for('main.admin_dashboard'))

@main.route('/analytics/web-vitals')
def web_vitals_analytics():
    """View web-vitals analytics dashboard"""
    return render_template('analytics.html')

@main.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error="Page non trouvée"), 404

@main.errorhandler(500)
def server_error(e):
    return render_template('error.html', error="Erreur interne du serveur"), 500

@main.errorhandler(403)
def forbidden(e):
    return render_template('error.html', error="Accès interdit"), 403 