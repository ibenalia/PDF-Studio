import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, send_from_directory, session
from werkzeug.utils import secure_filename
import json
import time
import zipfile
from io import BytesIO
from app.api import pdf_processor
import logging
import datetime

# Configurer le logging
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

# Helper functions
def allowed_file(filename, extensions=None):
    if extensions is None:
        extensions = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in extensions

def generate_unique_filename(filename):
    """Generate a unique filename while preserving the original extension."""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

# Ensure upload directory exists
def ensure_dir(directory):
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
    logger.info("Entrée dans upload_file")
    if 'file' not in request.files:
        logger.error("Pas de fichier dans request.files")
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('file')
    logger.info(f"Fichiers reçus: {len(files)}")
    
    if not files or files[0].filename == '':
        logger.error("Pas de fichier sélectionné")
        return jsonify({'error': 'No file selected'}), 400
    
    uploaded_files = []
    for file in files:
        if file and allowed_file(file.filename):
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
    return send_from_directory(current_app.config['PROCESSED_FOLDER'], filename, as_attachment=True)

@main.route('/api/pdf-info', methods=['POST'])
def pdf_info():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        return jsonify({'error': 'Please upload a valid PDF file'}), 400
    
    try:
        # Déléguer le traitement au composant C++
        info = pdf_processor.get_pdf_info(file)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/merge-pdf', methods=['POST'])
def api_merge_pdf():
    logger.info("API merge-pdf endpoint called")
    logger.info(f"Request files keys: {list(request.files.keys())}")
    
    if 'files[]' not in request.files and 'files' not in request.files:
        logger.error("No files provided in request")
        return jsonify({'error': 'No files provided'}), 400
    
    # Récupérer les fichiers selon le format de la requête
    if 'files[]' in request.files:
        files = request.files.getlist('files[]')
    else:
        files = request.files.getlist('files')
    
    logger.info(f"Number of files received: {len(files)}")
    
    if not files or len(files) < 2:
        logger.error(f"Not enough files: {len(files)}")
        return jsonify({'error': 'At least two PDF files are required'}), 400
    
    for file in files:
        if not file or not allowed_file(file.filename, {'pdf'}):
            return jsonify({'error': 'All files must be valid PDFs'}), 400
    
    try:
        # Déléguer le traitement au composant C++
        result = pdf_processor.merge_pdfs(files)
        return jsonify({
            'success': True,
            'message': 'PDFs merged successfully',
            'download_url': result['url'],
            'filename': result.get('filename', ''),
            'is_zip': False
        })
    except Exception as e:
        logger.error(f"Error in merge_pdf: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/split-pdf', methods=['POST'])
def api_split_pdf():
    logger.info("API split-pdf endpoint called")
    logger.info(f"Request files keys: {list(request.files.keys())}")
    
    if 'file' not in request.files and 'file[]' not in request.files:
        logger.error("No file provided in request")
        return jsonify({'error': 'No file provided'}), 400
    
    # Récupérer le fichier selon le format de la requête
    if 'file' in request.files:
        file = request.files['file']
    else:
        # Prendre le premier élément car split n'a besoin que d'un seul fichier
        file = request.files.getlist('file[]')[0]
    
    logger.info(f"Received file: {file.filename if file else 'None'}")
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        logger.error(f"Invalid file: {file.filename if file else 'None'}")
        return jsonify({'error': 'Please upload a valid PDF file'}), 400
    
    try:
        # Déléguer le traitement au composant C++ pour un split par page
        results = pdf_processor.split_pdf(file, "all")
        
        # Créer un fichier ZIP pour tous les fichiers PDF (une page par fichier)
        zip_filename = f"split_{uuid.uuid4().hex}.zip"
        zip_path = os.path.join(current_app.config['PROCESSED_FOLDER'], zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for result in results:
                zipf.write(result['path'], os.path.basename(result['path']))
        
        return jsonify({
            'success': True,
            'message': 'PDF split successfully',
            'download_url': f"/download/{zip_filename}",
            'is_zip': True,
            'files_count': len(results)
        })
    except Exception as e:
        logger.error(f"Error in split_pdf: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/compress-pdf', methods=['POST'])
def api_compress_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        return jsonify({'error': 'Please upload a valid PDF file'}), 400
    
    quality = request.form.get('quality', 'medium')
    
    try:
        # Déléguer le traitement au composant C++
        result = pdf_processor.compress_pdf(file, quality)
        return jsonify({
            'success': True,
            'message': 'PDF compressed successfully',
            'download_url': result['url']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main.route('/api/rotate-pdf', methods=['POST'])
def api_rotate_pdf():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not file or not allowed_file(file.filename, {'pdf'}):
        return jsonify({'error': 'Please upload a valid PDF file'}), 400
    
    degrees = request.form.get('degrees', '90')
    
    try:
        degrees = int(degrees)
        # Déléguer le traitement au composant C++
        result = pdf_processor.rotate_pdf(file, degrees)
        return jsonify({
            'success': True,
            'message': 'PDF rotated successfully',
            'download_url': result['url']
        })
    except ValueError:
        return jsonify({'error': 'Rotation degrees must be a valid number'}), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def format_file_size(size_bytes):
    """Format the file size as a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

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
    
    # Liste pour stocker les informations des fichiers
    files = []
    
    # Liste temporaire pour tous les fichiers avant filtrage
    all_files = []
    
    # Vérifier si le répertoire existe
    if os.path.exists(processed_dir):
        # Parcourir tous les fichiers du répertoire
        for filename in os.listdir(processed_dir):
            if filename.endswith('.pdf') or filename.endswith('.zip'):
                file_path = os.path.join(processed_dir, filename)
                file_stats = os.stat(file_path)
                
                # Calculer le temps écoulé depuis la création du fichier
                creation_time = datetime.datetime.fromtimestamp(file_stats.st_mtime)
                time_since_creation = datetime.datetime.now() - creation_time
                
                # Formater le temps écoulé
                if time_since_creation.days > 0:
                    time_elapsed = f"{time_since_creation.days} jour{'s' if time_since_creation.days > 1 else ''}"
                elif time_since_creation.seconds // 3600 > 0:
                    hours = time_since_creation.seconds // 3600
                    time_elapsed = f"{hours} heure{'s' if hours > 1 else ''}"
                elif time_since_creation.seconds // 60 > 0:
                    minutes = time_since_creation.seconds // 60
                    time_elapsed = f"{minutes} minute{'s' if minutes > 1 else ''}"
                else:
                    time_elapsed = "quelques secondes"
                
                # Créer une structure avec les informations du fichier
                file_info = {
                    'filename': filename,
                    'display_name': filename.split('_', 1)[1] if '_' in filename else filename,
                    'size': file_stats.st_size,
                    'size_formatted': pdf_processor.format_file_size(file_stats.st_size),
                    'creation_time': creation_time.strftime('%d/%m/%Y à %H:%M'),
                    'time_elapsed': time_elapsed,
                    'download_url': f"/api/download/{filename}",
                    'is_zip': filename.endswith('.zip'),
                    'is_split_page': '_page_' in filename and filename.endswith('.pdf')
                }
                
                all_files.append(file_info)
        
        # Identifier les ZIP de fractionnement
        split_zips = [f for f in all_files if f['is_zip'] and f['filename'].startswith('split_')]
        
        # Identifier les pages individuelles de fractionnement
        split_pages = [f for f in all_files if f['is_split_page']]
        
        # Filtrer les fichiers pour exclure les pages individuelles
        # si un fichier ZIP de fractionnement existe dans la même période
        filtered_files = []
        for file in all_files:
            # Toujours garder les ZIP et les fichiers qui ne sont pas des pages individuelles
            if file['is_zip'] or not file['is_split_page']:
                filtered_files.append(file)
            # Pour les pages individuelles, ne les garder que si elles n'ont pas de ZIP correspondant créé à peu près au même moment
            elif file['is_split_page']:
                # On ne garde pas les pages individuelles
                continue
        
        files = filtered_files
        
        # Trier les fichiers par date de création (les plus récents d'abord)
        files.sort(key=lambda x: x['creation_time'], reverse=True)
    
    return render_template('my_files.html', files=files) 