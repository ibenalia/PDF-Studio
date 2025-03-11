"""
API Routes for PDF processing
"""
from flask import Blueprint, request, jsonify, current_app, send_file, after_this_request
from werkzeug.utils import secure_filename
import os
import zipfile
import traceback
from io import BytesIO
from . import pdf_processor
import uuid
import io

api = Blueprint('api', __name__, url_prefix='/api')

@api.route('/pdf-info', methods=['POST'])
def pdf_info():
    """Get PDF information"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
            
        # Get PDF information
        info = pdf_processor.get_pdf_info(file)
            
        return jsonify({
            'status': 'success',
            'data': info
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in pdf_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/merge-pdf', methods=['POST'])
def merge_pdf():
    """Merge multiple PDFs"""
    try:
        print("API: merge-pdf endpoint called")
        
        if 'files' not in request.files:
            print("API: No files provided in request")
            return jsonify({'error': 'No file provided'}), 400
            
        files = request.files.getlist('files')
        
        if len(files) == 0:
            print("API: Files list is empty")
            return jsonify({'error': 'No file selected'}), 400
            
        if len(files) < 2:
            print(f"API: Not enough files: {len(files)}")
            return jsonify({'error': 'Please select at least two PDF files to merge'}), 400
            
        # Check that all files are PDFs
        for file in files:
            print(f"API: Processing file: {file.filename}")
            if not file.filename.lower().endswith('.pdf'):
                print(f"API: Invalid file type: {file.filename}")
                return jsonify({'error': f"The file {file.filename} is not a valid PDF"}), 400
                
        # Print current data directories
        print(f"API: DATA_DIR = {current_app.config.get('DATA_DIR')}")
        print(f"API: UPLOAD_FOLDER = {current_app.config.get('UPLOAD_FOLDER')}")
        print(f"API: Directories exist: {os.path.exists(current_app.config.get('DATA_DIR'))}, {os.path.exists(current_app.config.get('UPLOAD_FOLDER'))}")
        
        # Merge PDFs
        result = pdf_processor.merge_pdfs(files)
        
        print(f"API: Merge successful, result = {result}")
        return jsonify({
            'status': 'success',
            'data': result,
            'message': f'Successfully merged {len(files)} PDF files.',
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in merge_pdf: {str(e)}")
        print(f"API ERROR: {str(e)}")
        print(f"API ERROR Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@api.route('/split-pdf', methods=['POST'])
def split_pdf():
    """Split a PDF"""
    try:
        print("API: split-pdf endpoint called")
        
        if 'file' not in request.files:
            print("API: No file provided in request")
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            print("API: Empty filename")
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            print(f"API: Invalid file type: {file.filename}")
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Print all form data for debugging
        print(f"API: Form data: {request.form}")
            
        # Get split parameters
        split_method = request.form.get('split_method', 'range')
        page_range = request.form.get('page_range', '')
        
        print(f"API: Split method: {split_method}, Page range: {page_range}")
        
        # Vérifier la taille du fichier
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        # Si le fichier est trop grand, donnez un avertissement
        size_warning = None
        if file_size > 5 * 1024 * 1024:  # 5 MB
            print(f"API: Large file detected: {file_size / (1024 * 1024):.2f} MB")
            size_warning = "Fichier volumineux détecté. Le traitement peut prendre plus de temps."
        
        # Traitement des formats spéciaux de plage
        if page_range.startswith('count:'):
            # Format spécial pour "pages par fichier"
            try:
                pages_per_file = int(page_range.split(':')[1])
                print(f"API: Using pages per file: {pages_per_file}")
                # Convertir en format reconnu par notre backend (on envoie None pour page_range)
                request_page_range = None
            except (ValueError, IndexError):
                print(f"API: Invalid count format: {page_range}")
                return jsonify({'error': 'Format de nombre de pages invalide'}), 400
        else:
            # Vérifier si c'est un simple numéro de page (extraction d'une page)
            try:
                # Si c'est un simple nombre, c'est une demande d'extraction d'une seule page
                page_num = int(page_range.strip())
                print(f"API: Extracting single page: {page_num}")
                # On garde tel quel, notre split_pdf peut maintenant gérer ça directement
                request_page_range = page_range.strip()
            except ValueError:
                # Format standard pour page_range
                request_page_range = page_range
            
        # Récupérer les options avancées
        optimize = request.form.get('optimize', 'false').lower() == 'true'
        single_files = request.form.get('single_files', 'false').lower() == 'true'
        output_naming = request.form.get('output_naming', '[original]_p[page]')
        
        print(f"API: Advanced options - Optimize: {optimize}, Single files: {single_files}, Naming: {output_naming}")
        
        # Créer un dictionnaire d'options pour passer au processeur PDF
        options = {
            'optimize': optimize,
            'single_files': single_files,
            'output_naming': output_naming
        }
        
        # Déterminer la méthode de division appropriée à appeler
        try:
            if split_method == 'range' or split_method == 'extract':
                # Pour 'range' et 'extract', on utilise le même backend mais avec une plage de pages différente
                output_files = pdf_processor.split_pdf(file, request_page_range, **options)
            elif split_method == 'count':
                # Pour 'count', on utilise une fonction spéciale qui divise par nombre de pages
                if pages_per_file < 1:
                    return jsonify({'error': 'Le nombre de pages par fichier doit être supérieur à 0'}), 400
                output_files = pdf_processor.split_pdf_by_count(file, pages_per_file, **options)
            else:
                return jsonify({'error': 'Méthode de division non reconnue'}), 400
            
            if not output_files:
                print("API: No output files generated")
                return jsonify({'error': 'No files generated. Check the page range.'}), 400
                
            # Récupération de la session_id pour la référencer dans la réponse
            session_id = pdf_processor.get_session_id()
            
            # Optimisation pour les PDFs volumineux
            # Pour limiter la taille de la réponse, on limite les détails des fichiers si nécessaire
            max_detailed_files = 100  # Nombre maximum de fichiers à détailler dans la réponse
            total_file_count = len(output_files)
            files_to_return = output_files
            
            # Si le nombre de fichiers est très élevé, ne retourner que les informations essentielles
            if total_file_count > max_detailed_files:
                print(f"API: Limiting detailed files in response from {total_file_count} to {max_detailed_files}")
                # On garde tous les URLs pour le téléchargement groupé, mais on limite les détails pour l'affichage
                files_to_return = output_files[:max_detailed_files]
            
            # Format de réponse basé sur le nombre de fichiers générés
            if total_file_count > 1:
                # Plusieurs fichiers générés, proposer un zip
                print(f"API: Creating a ZIP download for {total_file_count} files")
                
                # Préparer une liste de tous les noms de fichiers pour l'URL de téléchargement
                filenames = ",".join([f["filename"] for f in output_files])
                
                # Si la chaîne est trop longue, utiliser plutôt l'ID de session
                if len(filenames) > 2000:
                    download_url = f"/api/download-session?session_id={session_id}&clean=true"
                    print(f"API: URL too long, using session ID instead: {session_id}")
                else:
                    download_url = f"/api/download-all?files={filenames}&clean=true"
                
                # Générer un identifiant unique pour le téléchargement
                download_id = uuid.uuid4().hex[:16]
                zip_filename = f"split_{download_id}.zip"
                
                # Format de réponse simplifié pour les téléchargements multiples
                return jsonify({
                    "success": True,
                    "message": f"PDF divisé avec succès en {total_file_count} fichiers.",
                    "files_count": total_file_count,
                    "download_url": download_url,
                    "is_zip": True,
                    "filename": zip_filename
                })
            
            else:
                # Un seul fichier généré, retourner directement son URL
                print(f"API: Returning a single file download")
                file_info = output_files[0]
                
                return jsonify({
                    "success": True,
                    "message": "PDF divisé avec succès",
                    "files_count": 1,
                    "download_url": file_info["url"],
                    "is_zip": False,
                    "filename": file_info["filename"]
                })
            
            # Version classique de la réponse (maintenue pour la rétrocompatibilité mais non utilisée)
            response = {
                'status': 'success',
                'data': {
                    'files': files_to_return,
                    'total_file_count': total_file_count,
                    'all_files': [f['filename'] for f in output_files],
                    'session_id': session_id
                },
                'message': f'PDF divisé avec succès en {total_file_count} fichiers.'
            }
            
            # Ajouter l'avertissement si nécessaire
            if size_warning:
                response['warning'] = size_warning
            
            return jsonify(response)
                
        except Exception as e:
            # Tentative de récupération d'informations plus détaillées sur l'erreur
            error_msg = str(e)
            error_details = None
            error_code = 500
            
            # Logging détaillé de l'erreur pour faciliter le débogage
            current_app.logger.error(f"Error in split_pdf: {error_msg}")
            current_app.logger.error(traceback.format_exc())
            
            # Analyser l'erreur pour donner une réponse plus précise
            if "PoDoFo::PdfError" in error_msg:
                error_msg = "Le PDF semble être corrompu ou contenir des éléments non standard."
                error_details = "Essayez de le réparer ou d'utiliser un autre PDF."
                error_code = 400
            elif "PyPDF2" in error_msg:
                error_msg = "Impossible de traiter ce PDF."
                error_details = "Le fichier pourrait être protégé ou corrompu."
                error_code = 400
            elif "pages" in error_msg.lower() and "range" in error_msg.lower():
                error_msg = "La plage de pages spécifiée est invalide."
                error_details = "Vérifiez que les numéros de page existent dans le document."
                error_code = 400
            elif "count:" in error_msg.lower():
                error_msg = "Format de découpage par nombre de pages invalide."
                error_details = "Vérifiez que vous avez spécifié un nombre entier positif de pages par fichier."
                error_code = 400
            elif "Aucune page valide" in error_msg:
                error_msg = "Aucune page valide à extraire."
                error_details = "Vérifiez votre sélection de pages et assurez-vous qu'elle correspond au document."
                error_code = 400
            
            # Formatage de la réponse d'erreur enrichie
            error_response = {
                'error': error_msg,
                'status': 'error'
            }
            
            if error_details:
                error_response['details'] = error_details
            
            # Ajouter des informations techniques en mode debug
            if current_app.debug:
                error_response['debug'] = {
                    'original_error': str(e),
                    'traceback': traceback.format_exc().split('\n')
                }
            
            return jsonify(error_response), error_code
            
    except Exception as e:
        current_app.logger.error(f"Error in split_pdf: {str(e)}")
        print(f"API ERROR: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/compress-pdf', methods=['POST'])
def compress_pdf():
    """Compress a PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Get compression quality
        quality = request.form.get('quality', 'medium')
        if quality not in ['low', 'medium', 'high']:
            quality = 'medium'
        
        # Compress the PDF
        result = pdf_processor.compress_pdf(file, quality)
        
        return jsonify({
            'status': 'success',
            'message': f'PDF successfully compressed. Compression rate: {result["compression_rate"]}',
            'originalSize': result['original_size'],
            'compressedSize': result['compressed_size'],
            'compressionRate': result['compression_rate'],
            'downloadUrl': result['url'],
            'filename': result['filename']
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in compress_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/rotate-pdf', methods=['POST'])
def rotate_pdf():
    """Rotate a PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Get rotation angle
        degrees = request.form.get('degrees', '90')
        try:
            degrees = int(degrees)
            if degrees % 90 != 0:
                return jsonify({'error': 'Rotation angle must be a multiple of 90 degrees'}), 400
        except ValueError:
            return jsonify({'error': 'Rotation angle must be a number'}), 400
        
        # Rotate the PDF
        result = pdf_processor.rotate_pdf(file, degrees)
        
        return jsonify({
            'status': 'success',
            'message': f'PDF successfully rotated by {degrees} degrees.',
            'downloadUrl': result['url'],
            'filename': result['filename']
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in rotate_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/watermark-pdf', methods=['POST'])
def watermark_pdf():
    """Add a watermark to a PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Get watermark text
        text = request.form.get('text', '')
        if not text:
            return jsonify({'error': 'Please specify text for the watermark'}), 400
        
        # Get opacity
        opacity = request.form.get('opacity', '0.5')
        try:
            opacity = float(opacity)
            if opacity < 0 or opacity > 1:
                opacity = 0.5
        except ValueError:
            opacity = 0.5
        
        # Add watermark
        result = pdf_processor.watermark_pdf(file, text, opacity)
        
        return jsonify({
            'status': 'success',
            'message': f'Watermark successfully added to PDF.',
            'downloadUrl': result['url'],
            'filename': result['filename']
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in watermark_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/protect-pdf', methods=['POST'])
def protect_pdf():
    """Protect a PDF with a password"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Get password
        password = request.form.get('password', '')
        if not password:
            return jsonify({'error': 'Please specify a password'}), 400
        
        # Protect the PDF
        result = pdf_processor.protect_pdf(file, password)
        
        return jsonify({
            'status': 'success',
            'message': f'PDF successfully protected with password.',
            'downloadUrl': result['url'],
            'filename': result['filename']
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in protect_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/unlock-pdf', methods=['POST'])
def unlock_pdf():
    """Unlock a protected PDF"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
            
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
            
        if not file.filename.lower().endswith('.pdf'):
            return jsonify({'error': 'Invalid file type. Please upload a PDF.'}), 400
        
        # Get password
        password = request.form.get('password', '')
        if not password:
            return jsonify({'error': 'Please specify the password'}), 400
        
        # Unlock the PDF
        result = pdf_processor.unlock_pdf(file, password)
        
        return jsonify({
            'status': 'success',
            'message': f'PDF successfully unlocked.',
            'downloadUrl': result['url'],
            'filename': result['filename']
        })
            
    except Exception as e:
        current_app.logger.error(f"Error in unlock_pdf: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download a processed file and clean up afterwards"""
    try:
        # Obtenir le chemin du répertoire de traitement de la session
        processed_dir = pdf_processor.get_processed_dir()
        file_path = os.path.join(processed_dir, filename)
        
        if not os.path.exists(file_path):
            current_app.logger.warning(f"Fichier introuvable: {file_path}")
            return jsonify({'error': 'File not found'}), 404
        
        # Option pour nettoyer les fichiers après téléchargement
        clean_after = request.args.get('clean', 'false').lower() == 'true'
        
        # Créer une fonction de rappel (callback) pour nettoyer après le téléchargement
        @after_this_request
        def cleanup(response):
            if clean_after:
                try:
                    # Supprimer uniquement ce fichier
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        current_app.logger.info(f"Fichier nettoyé après téléchargement: {filename}")
                except Exception as e:
                    current_app.logger.error(f"Erreur lors du nettoyage du fichier {filename}: {str(e)}")
            return response
            
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename.split('_', 1)[1] if '_' in filename else filename
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in download_file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/download-all', methods=['GET'])
def download_all_files():
    """Download multiple files as a ZIP archive"""
    try:
        files_param = request.args.get('files', '')
        
        if not files_param:
            return jsonify({'error': 'No files specified'}), 400
            
        filenames = files_param.split(',')
        
        if not filenames:
            return jsonify({'error': 'No valid files specified'}), 400
        
        # Create a temporary directory for the ZIP file
        temp_dir = pdf_processor.get_temp_dir()
        
        # Create a ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            processed_dir = pdf_processor.get_processed_dir()
            
            # Keep track of filenames to avoid duplicates in the ZIP
            used_names = set()
            files_added = False
            
            # Add each file to the ZIP
            for filename in filenames:
                filepath = os.path.join(processed_dir, filename)
                
                if os.path.exists(filepath):
                    # Get a clean name for the file in the ZIP
                    original_name = filename.split('_', 1)[1] if '_' in filename else filename
                    
                    # Handle duplicates by adding a suffix
                    zip_name = original_name
                    counter = 1
                    while zip_name in used_names:
                        name_parts = os.path.splitext(original_name)
                        zip_name = f"{name_parts[0]}_{counter}{name_parts[1]}"
                        counter += 1
                    
                    used_names.add(zip_name)
                    
                    # Add to ZIP archive
                    zip_file.write(filepath, zip_name)
                    files_added = True
        
        # Si aucun fichier n'a été ajouté
        if not files_added:
            return jsonify({'error': 'No files found to download'}), 404
            
        # Reset file pointer to the beginning
        zip_buffer.seek(0)
        
        # Create a unique ZIP filename
        zip_filename = f"pdf_files_{uuid.uuid4()}.zip"
        
        # Option pour nettoyer les fichiers après téléchargement
        clean_after = request.args.get('clean', 'false').lower() == 'true'
        
        # Créer une fonction de rappel (callback) pour nettoyer après le téléchargement
        @after_this_request
        def cleanup(response):
            if clean_after:
                try:
                    # Nettoyer les fichiers individuels
                    for filename in filenames:
                        filepath = os.path.join(processed_dir, filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    current_app.logger.info(f"Fichiers nettoyés après téléchargement ZIP: {len(filenames)} fichiers")
                except Exception as e:
                    current_app.logger.error(f"Erreur lors du nettoyage des fichiers: {str(e)}")
            return response
        
        # Return the ZIP file
        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in download_all_files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api.route('/download-session', methods=['GET'])
def download_session_files():
    """Télécharger les fichiers générés récemment"""
    try:
        # Récupérer la session ID de la requête (maintenu pour compatibilité)
        session_id = request.args.get('session_id')
        
        # Option pour nettoyer les fichiers après téléchargement
        should_clean = request.args.get('clean', 'false').lower() == 'true'
        
        # Récupérer tous les fichiers du dossier processed
        processed_dir = pdf_processor.get_processed_dir()
        if not os.path.exists(processed_dir):
            return jsonify({'error': 'No files available'}), 404
            
        # Lister tous les fichiers PDF dans le répertoire processed
        pdf_files = []
        for filename in os.listdir(processed_dir):
            if filename.lower().endswith('.pdf'):
                file_path = os.path.join(processed_dir, filename)
                # Trier par date de modification (plus récent en premier)
                pdf_files.append((filename, file_path, os.path.getmtime(file_path)))
                
        # Trier par date de modification (plus récent en premier)
        pdf_files.sort(key=lambda x: x[2], reverse=True)
        
        # Ne garder que les noms et chemins de fichiers
        session_files = [(name, path) for name, path, _ in pdf_files]
                
        if not session_files:
            return jsonify({'error': 'No files found'}), 404
            
        # Si un seul fichier, le retourner directement
        if len(session_files) == 1:
            filename, file_path = session_files[0]
            response = send_file(file_path, as_attachment=True)
            
            # Nettoyer si demandé
            if should_clean:
                try:
                    os.remove(file_path)
                    print(f"API: Cleaned up file after download: {file_path}")
                except Exception as e:
                    print(f"API: Error cleaning up file: {str(e)}")
                    
            return response
            
        # Pour plusieurs fichiers, les comprimer
        current_app.logger.info(f"API: Creating ZIP with {len(session_files)} files")
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename, file_path in session_files:
                zf.write(file_path, filename)
                
        memory_file.seek(0)
        
        # Nettoyer les fichiers si demandé
        if should_clean:
            try:
                for _, file_path in session_files:
                    os.remove(file_path)
                print(f"API: Cleaned up {len(session_files)} files after download")
            except Exception as e:
                print(f"API: Error cleaning up files: {str(e)}")
                
        download_id = uuid.uuid4().hex[:8]
        return send_file(
            memory_file,
            download_name=f'pdf_files_{download_id}.zip',
            as_attachment=True,
            mimetype='application/zip'
        )
        
    except Exception as e:
        current_app.logger.error(f"Error in download_session_files: {str(e)}")
        return jsonify({'error': str(e)}), 500 