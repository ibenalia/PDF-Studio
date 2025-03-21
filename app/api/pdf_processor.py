"""
Interface pour l'outil de traitement PDF C++
"""
import os
import subprocess
import uuid
import shutil
from flask import current_app, session
from werkzeug.utils import secure_filename
import logging
import time
import re
import magic

logger = logging.getLogger(__name__)

def ensure_dir(directory):
    """Crée un répertoire s'il n'existe pas déjà"""
    if not os.path.exists(directory):
        os.makedirs(directory)

def get_session_id():
    """
    Obtient l'ID de session ou en crée un nouveau
    """
    if 'pdf_session_id' not in session:
        session['pdf_session_id'] = str(uuid.uuid4())
    return session['pdf_session_id']

def get_session_dir():
    """
    Crée et retourne un répertoire spécifique à la session
    """
    session_id = get_session_id()
    session_dir = os.path.join(current_app.config['DATA_DIR'], 'sessions', session_id)
    ensure_dir(session_dir)
    return session_dir

def get_temp_dir():
    """
    Crée et retourne un répertoire temporaire unique pour cette session
    
    Returns:
        str: Chemin vers le répertoire temporaire
    """
    session_id = str(uuid.uuid4())
    temp_dir = os.path.join(current_app.config['DATA_DIR'], 'temp', session_id)
    ensure_dir(temp_dir)
    return temp_dir

def get_processed_dir():
    """
    Retourne le répertoire pour les fichiers traités
    
    Returns:
        str: Chemin vers le répertoire des fichiers traités
    """
    processed_dir = os.path.join(current_app.config['DATA_DIR'], 'processed')
    ensure_dir(processed_dir)
    return processed_dir

def is_valid_pdf(file_stream):
    """
    Vérifie si un fichier est un PDF valide en inspectant son contenu

    Args:
        file_stream: Flux du fichier à vérifier

    Returns:
        bool: True si le fichier est un PDF valide, False sinon
    """
    try:
        # Sauvegarder la position actuelle dans le flux
        current_position = file_stream.tell()
        
        # Lire les premiers octets pour déterminer le type MIME
        file_stream.seek(0)
        mime = magic.from_buffer(file_stream.read(4096), mime=True)
        
        # Restaurer la position dans le flux
        file_stream.seek(current_position)
        
        # Vérifier si c'est un PDF
        return mime == 'application/pdf'
    except Exception as e:
        logger.error(f"Erreur lors de la validation du PDF: {str(e)}")
        return False

def sanitize_command_arg(arg):
    """
    Sanitize un argument de commande pour éviter les injections

    Args:
        arg: L'argument à sanitizer

    Returns:
        str: L'argument sanitizé

    Raises:
        ValueError: Si l'argument contient des caractères dangereux
    """
    if not isinstance(arg, str):
        raise ValueError(f"L'argument n'est pas une chaîne de caractères: {arg}")
    
    # Vérifier les caractères dangereux
    dangerous_chars = ['|', '&', ';', '$', '`', '>', '<', '*', '?', '(', ')', '[', ']', '{', '}', '\\', '\'', '"', '\n', '\r']
    if any(c in arg for c in dangerous_chars):
        raise ValueError(f"L'argument contient des caractères interdits: {arg}")
    
    # Limite la longueur des arguments
    if len(arg) > 1024:
        raise ValueError(f"L'argument est trop long: {len(arg)} caractères")
    
    return arg

def get_pdfeditor_path():
    """Retourne le chemin vers l'exécutable pdfeditor"""
    pdfeditor_path = os.path.join(current_app.config.get('BASE_DIR', os.getcwd()), 'bin', 'pdfeditor')
    
    # Pour Windows, ajouter .exe si nécessaire
    if os.name == 'nt' and not pdfeditor_path.endswith('.exe'):
        pdfeditor_path += '.exe'
        
    return pdfeditor_path

def run_pdfeditor(cmd_args):
    """
    Exécute l'outil pdfeditor avec les arguments spécifiés
    
    Args:
        cmd_args: Liste d'arguments pour l'outil
        
    Returns:
        Tuple (return_code, stdout, stderr)
    """
    # Sanitize tous les arguments
    sanitized_args = []
    try:
        for arg in cmd_args:
            sanitized_args.append(sanitize_command_arg(arg))
    except ValueError as e:
        logger.error(f"Argument invalide pour pdfeditor: {str(e)}")
        return -1, "", f"Argument invalide détecté: {str(e)}"
    
    cmd = [get_pdfeditor_path()] + sanitized_args
    
    logger.info(f"Exécution de la commande: {' '.join(cmd)}")
    
    try:
        # Vérifier que l'exécutable existe
        pdfeditor_path = get_pdfeditor_path()
        if not os.path.isfile(pdfeditor_path):
            logger.error(f"L'exécutable pdfeditor n'existe pas: {pdfeditor_path}")
            return -1, "", f"L'exécutable pdfeditor n'existe pas: {pdfeditor_path}"
            
        # Vérifier que l'exécutable est exécutable
        if not os.access(pdfeditor_path, os.X_OK) and os.name != 'nt':  # Skip on Windows
            logger.error(f"L'exécutable pdfeditor n'est pas exécutable: {pdfeditor_path}")
            return -1, "", f"L'exécutable pdfeditor n'est pas exécutable: {pdfeditor_path}"
        
        # Définir un timeout pour éviter les processus bloqués
        timeout = 60  # 1 minute au lieu de 5
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            universal_newlines=True,
            shell=False  # Éviter l'injection de commandes
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logger.error(f"Timeout lors de l'exécution de pdfeditor (après {timeout}s)")
            return -1, stdout, f"Timeout lors de l'exécution de pdfeditor (après {timeout}s)"
        
        if process.returncode != 0:
            logger.error(f"Erreur lors de l'exécution de pdfeditor (code {process.returncode}): {stderr}")
            
        return process.returncode, stdout, stderr
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        error_msg = f"Exception lors de l'exécution de pdfeditor: {str(e)}\n{stack_trace}"
        logger.exception(error_msg)
        return -1, "", error_msg

def merge_pdfs(files):
    """
    Fusionne plusieurs fichiers PDF en un seul
    
    Args:
        files: Liste d'objets fichiers à fusionner
        
    Returns:
        Dictionnaire avec les informations sur le fichier fusionné
    """
    if not files or len(files) == 0:
        raise Exception("Aucun fichier fourni pour la fusion")
        
    temp_dir = get_temp_dir()
    
    try:
        # Sauvegarder les fichiers d'entrée
        input_files = []
        total_input_size = 0
        file_count = 0
        
        # Assurer un nom de fichier unique et sécurisé
        for file in files:
            if not file.filename.lower().endswith('.pdf'):
                continue  # Ignorer les fichiers non-PDF
                
            # Vérifier si le contenu est un PDF valide 
            if not is_valid_pdf(file):
                logger.warning(f"Fichier non PDF ignoré: {file.filename}")
                continue
                
            safe_filename = secure_filename(file.filename)
            input_path = os.path.join(temp_dir, f"{file_count}_{safe_filename}")
            file.save(input_path)
            
            # Vérifier si le fichier est valide
            if os.path.getsize(input_path) == 0:
                logger.warning(f"Fichier vide ignoré: {safe_filename}")
                os.remove(input_path)
                continue
                
            input_files.append(input_path)
            total_input_size += os.path.getsize(input_path)
            file_count += 1
        
        if not input_files:
            raise Exception("Aucun fichier PDF valide trouvé pour la fusion")
            
        # Générer un nom de fichier de sortie
        output_filename = f"merged_{uuid.uuid4()}.pdf"
        output_path = os.path.join(temp_dir, output_filename)
        
        # Préparer les arguments pour l'outil C++
        cmd_args = ["merge", output_path] + input_files
        
        # Exécuter l'outil
        logger.info(f"Fusion de {len(input_files)} fichiers PDF")
        returncode, stdout, stderr = run_pdfeditor(cmd_args)
        
        if returncode != 0:
            # Nettoyer
            raise Exception(f"Erreur lors de la fusion des PDFs: {stderr}")
            
        # Déplacer vers le répertoire des fichiers traités
        processed_dir = get_processed_dir()
        final_path = os.path.join(processed_dir, output_filename)
        shutil.move(output_path, final_path)
        
        return {
            'filename': output_filename,
            'path': final_path,
            'url': f"/download/{output_filename}",
            'size': os.path.getsize(final_path),
            'page_count': None  # Pourrait être amélioré pour compter les pages
        }
    finally:
        # Nettoyer les fichiers temporaires dans tous les cas
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def clean_old_sessions(max_age_hours=6):
    """
    Nettoie les fichiers temporaires et traités qui sont plus anciens que max_age_hours
    
    Args:
        max_age_hours: Durée maximale de conservation des fichiers en heures
    """
    try:
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        
        # Nettoyer les répertoires de données
        for dir_name in ['temp', 'uploads', 'processed']:
            dir_path = os.path.join(current_app.config['DATA_DIR'], dir_name)
            
            if not os.path.exists(dir_path):
                continue
                
            for filename in os.listdir(dir_path):
                file_path = os.path.join(dir_path, filename)
                
                # Si c'est un répertoire dans temp, supprimer tout le répertoire
                if os.path.isdir(file_path) and dir_name == 'temp':
                    try:
                        dir_age = now - os.path.getmtime(file_path)
                        if dir_age > max_age_seconds:
                            shutil.rmtree(file_path)
                            logger.info(f"Répertoire temporaire nettoyé: {file_path}")
                    except Exception as e:
                        logger.error(f"Erreur lors du nettoyage du répertoire {file_path}: {str(e)}")
                
                # Si c'est un fichier, vérifier son âge
                elif os.path.isfile(file_path):
                    try:
                        file_age = now - os.path.getmtime(file_path)
                        if file_age > max_age_seconds:
                            os.remove(file_path)
                            logger.info(f"Fichier nettoyé: {file_path}")
                    except Exception as e:
                        logger.error(f"Erreur lors du nettoyage du fichier {file_path}: {str(e)}")
                        
        return True
    except Exception as e:
        logger.error(f"Erreur lors du nettoyage des sessions: {str(e)}")
        return False

def clean_session_files(session_id=None):
    """
    Fonction conservée pour compatibilité
    """
    # Cette fonction ne fait rien car nous ne gérons plus les fichiers par session
    pass

def split_pdf(file, page_range=None, **options):
    """
    Divise un fichier PDF en fichiers individuels, un par page
    
    Args:
        file: Objet fichier à diviser
        page_range: Plage de pages à extraire, format: "1,3,5-10"
        **options: Options avancées
        
    Returns:
        Liste de dictionnaires avec les informations sur les fichiers générés
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Générer un préfixe pour les fichiers de sortie
    original_basename = os.path.splitext(safe_filename)[0]
    output_prefix = os.path.join(temp_dir, original_basename)
    
    # Vérification préalable du PDF pour détecter les problèmes potentiels
    try:
        # Vérifier la validité du PDF avec l'outil info
        info_cmd_args = ["info", input_path]
        info_returncode, info_stdout, info_stderr = run_pdfeditor(info_cmd_args)
        
        page_count = 0
        if info_returncode == 0:
            import json
            info = json.loads(info_stdout)
            if info and 'pageCount' in info:
                page_count = info['pageCount']
                
                # Si aucune plage spécifiée, créer une plage pour toutes les pages
                if not page_range or page_range == 'all':
                    # Si le PDF a beaucoup de pages, utiliser plutôt la méthode par lots
                    if page_count > 200:
                        logger.info(f"PDF volumineux détecté avec {page_count} pages - utilisation du traitement par lots")
                        return split_pdf_in_batches(input_path, temp_dir, page_count, **options)
                    else:
                        # Pour un nombre raisonnable de pages, créer une plage
                        page_range = ','.join(str(i+1) for i in range(page_count))
                        logger.info(f"Extraction de pages individuelles: {page_range}")
        
        if info_returncode != 0:
            logger.warning(f"PDF problématique détecté avec info: {info_stderr}")
            # Le PDF est problématique, nous utiliserons une approche alternative
            return split_pdf_fallback(input_path, temp_dir, "all", options)
    except Exception as e:
        logger.warning(f"Erreur lors de la vérification préalable du PDF: {str(e)}")
        # En cas d'erreur, continuons avec l'approche standard
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["split", input_path, output_prefix]
    
    # Si page_range a été défini, l'utiliser
    if page_range:
        cmd_args.append(page_range)
    
    # Vérifier si l'argument n'est pas trop long
    arg_length = sum(len(arg) for arg in cmd_args)
    if arg_length > 2000 and page_count > 0:
        logger.warning(f"Argument trop long pour pdfeditor ({arg_length} caractères) - utilisation du traitement par lots")
        return split_pdf_in_batches(input_path, temp_dir, page_count, **options)
    
    # Exécuter l'outil
    logger.info(f"Exécution de split_pdf avec les arguments: {cmd_args}")
    returncode, stdout, stderr = run_pdfeditor(cmd_args)

    if returncode != 0:
        logger.error(f"Erreur lors de l'exécution de pdfeditor (code {returncode}): {stderr}")
        
        # Si l'outil échoue, essayer l'approche alternative
        logger.info("Tentative avec l'approche alternative pour les PDF problématiques")
        return split_pdf_fallback(input_path, temp_dir, "all", options)
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    
    try:
        # Récupérer la liste des fichiers générés
        import json
        files_info = json.loads(stdout)
        
        if 'files' not in files_info:
            raise ValueError("La structure de la réponse est invalide, 'files' manquant")
            
        result_files = []
        
        # Traiter chaque fichier généré
        for file_info in files_info['files']:
            source_path = file_info.get('path')
            filename = file_info.get('name', os.path.basename(source_path))
            
            if not os.path.isfile(source_path):
                logger.warning(f"Fichier généré introuvable: {source_path}")
                continue
                
            # Générer un nom unique pour éviter les conflits
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            dest_path = os.path.join(processed_dir, unique_name)
            
            # Déplacer le fichier
            shutil.copy2(source_path, dest_path)
            
            # URL relative pour le téléchargement
            download_url = f"/download/{unique_name}"
            
            # Déterminer le numéro de page si disponible
            page_number = file_info.get('page_number', None)
            
            result_files.append({
                'filename': filename,  # Utiliser 'filename' pour la cohérence
                'name': filename,      # Conserver 'name' pour la rétrocompatibilité
                'path': dest_path,
                'url': download_url,
                'size': os.path.getsize(dest_path),
                'page_number': page_number
            })
            
        # Trier les fichiers par numéro de page
        if all(f.get('page_number') for f in result_files):
            result_files.sort(key=lambda f: int(f.get('page_number', 0)))
        
        return result_files
    
    except Exception as e:
        logger.error(f"Erreur lors du traitement des fichiers générés: {e}")
        # Essayer l'approche alternative
        return split_pdf_fallback(input_path, temp_dir, "all", options)

def split_pdf_in_batches(input_path, temp_dir, total_pages, **options):
    """
    Divise un PDF en fichiers individuels en traitant les pages par lots
    pour éviter les arguments de ligne de commande trop longs.
    
    Args:
        input_path: Chemin vers le fichier PDF d'entrée
        temp_dir: Répertoire temporaire pour les opérations
        total_pages: Nombre total de pages dans le PDF
        **options: Options avancées
        
    Returns:
        Liste de dictionnaires avec les informations sur les fichiers générés
    """
    logger.info(f"Division du PDF en lots pour {total_pages} pages")
    
    # Import PyPDF2 pour travailler avec des pages spécifiques
    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        logger.error("PyPDF2 n'est pas installé. Cette bibliothèque est requise pour le traitement par lots.")
        # Utiliser la méthode de secours complète
        return split_pdf_fallback(input_path, temp_dir, "all", options)
    
    # Taille du lot - nombre de pages à traiter à la fois
    batch_size = 50  # Nombre de pages par lot
    
    # Créer des lots de pages à traiter
    batches = []
    for i in range(0, total_pages, batch_size):
        start_page = i + 1  # Pages commencent à 1
        end_page = min(i + batch_size, total_pages)
        batches.append((start_page, end_page))
    
    logger.info(f"Traitement du PDF en {len(batches)} lots")
    
    result_files = []
    processed_dir = get_processed_dir()
    
    # Traiter chaque lot
    for batch_index, (start_page, end_page) in enumerate(batches):
        logger.info(f"Traitement du lot {batch_index+1}/{len(batches)}: pages {start_page}-{end_page}")
        
        # Créer un PDF temporaire pour ce lot
        batch_pdf_path = os.path.join(temp_dir, f"batch_{batch_index}.pdf")
        
        # Extraire les pages pour ce lot
        with open(input_path, 'rb') as input_file:
            reader = PdfReader(input_file)
            writer = PdfWriter()
            
            # Ajouter les pages pour ce lot
            for page_num in range(start_page - 1, end_page):
                writer.add_page(reader.pages[page_num])
            
            # Écrire le PDF temporaire
            with open(batch_pdf_path, 'wb') as output_file:
                writer.write(output_file)
        
        # Générer un préfixe pour les fichiers de sortie
        base_name = os.path.basename(input_path)
        original_name = os.path.splitext(base_name)[0]
        output_prefix = os.path.join(temp_dir, f"{original_name}_batch_{batch_index}")
        
        # Préparer les arguments pour l'outil C++
        cmd_args = ["split", batch_pdf_path, output_prefix]
        
        # Exécuter l'outil pour ce lot
        returncode, stdout, stderr = run_pdfeditor(cmd_args)
        
        if returncode != 0:
            logger.error(f"Erreur lors du traitement du lot {batch_index+1}: {stderr}")
            # Nettoyer le fichier temporaire
            if os.path.exists(batch_pdf_path):
                os.remove(batch_pdf_path)
            continue
        
        try:
            # Récupérer la liste des fichiers générés pour ce lot
            import json
            files_info = json.loads(stdout)
            
            if 'files' not in files_info:
                logger.warning(f"Structure de réponse invalide pour le lot {batch_index+1}")
                continue
            
            # Calculer le décalage de page pour ce lot
            page_offset = start_page - 1
            
            # Traiter chaque fichier généré
            for file_info in files_info['files']:
                source_path = file_info.get('path')
                filename = file_info.get('name', os.path.basename(source_path))
                
                if not os.path.isfile(source_path):
                    logger.warning(f"Fichier généré introuvable: {source_path}")
                    continue
                
                # Ajuster le numéro de page pour tenir compte du lot
                original_page = file_info.get('page_number', 0)
                adjusted_page = original_page + page_offset
                
                # Générer un nom unique avec le numéro de page correct
                original_name_base = os.path.splitext(original_name)[0]
                new_filename = f"{original_name_base}_page_{adjusted_page}.pdf"
                
                # Générer un nom unique pour éviter les conflits
                unique_name = f"{uuid.uuid4().hex}_{new_filename}"
                dest_path = os.path.join(processed_dir, unique_name)
                
                # Déplacer le fichier
                shutil.copy2(source_path, dest_path)
                
                # URL relative pour le téléchargement
                download_url = f"/download/{unique_name}"
                
                result_files.append({
                    'filename': new_filename,  # Utiliser 'filename' pour la cohérence
                    'name': new_filename,      # Conserver 'name' pour la rétrocompatibilité
                    'path': dest_path,
                    'url': download_url,
                    'size': os.path.getsize(dest_path),
                    'page_number': adjusted_page
                })
        
        except Exception as e:
            logger.error(f"Erreur lors du traitement du lot {batch_index+1}: {str(e)}")
        
        finally:
            # Nettoyer le fichier temporaire
            if os.path.exists(batch_pdf_path):
                os.remove(batch_pdf_path)
    
    # Trier les fichiers par numéro de page
    result_files.sort(key=lambda f: int(f.get('page_number', 0)))
    
    if not result_files:
        logger.warning("Aucun fichier généré par le traitement par lots, utilisation de la méthode de secours")
        return split_pdf_fallback(input_path, temp_dir, "all", options)
    
    return result_files

def split_pdf_by_count(file, pages_per_file, **options):
    """
    Divise un PDF en fichiers contenant un nombre spécifique de pages chacun
    
    Args:
        file: Objet fichier à diviser
        pages_per_file: Nombre de pages par fichier de sortie
        **options: Options avancées
        
    Returns:
        Liste de dictionnaires avec les informations sur les fichiers générés
    """
    if pages_per_file < 1:
        raise ValueError("Le nombre de pages par fichier doit être supérieur à 0")
    
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Obtenir des informations sur le PDF (nombre total de pages)
    total_pages = 0
    try:
        info_cmd_args = ["info", input_path]
        info_returncode, info_stdout, info_stderr = run_pdfeditor(info_cmd_args)
        
        if info_returncode == 0:
            import json
            info = json.loads(info_stdout)
            if info and 'pageCount' in info:
                total_pages = info['pageCount']
                logger.info(f"Nombre total de pages dans le PDF: {total_pages}")
        
        if total_pages == 0:
            # Utiliser PyPDF2 comme solution de secours
            import PyPDF2
            with open(input_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                total_pages = len(pdf.pages)
                logger.info(f"Nombre total de pages détecté avec PyPDF2: {total_pages}")
    except Exception as e:
        logger.error(f"Erreur lors de la détermination du nombre de pages: {e}")
        raise Exception("Impossible de déterminer le nombre de pages dans le PDF")
    
    # Calculer les plages de pages basées sur le nombre de pages par fichier
    page_ranges = []
    for i in range(0, total_pages, pages_per_file):
        start_page = i + 1  # Pages commencent à 1
        end_page = min(i + pages_per_file, total_pages)
        if start_page == end_page:
            page_ranges.append(f"{start_page}")
        else:
            page_ranges.append(f"{start_page}-{end_page}")
    
    # Convertir les plages en une seule chaîne pour l'appel standard
    page_range = ','.join(page_ranges)
    logger.info(f"Plages de pages générées: {page_range}")
    
    # Utiliser la fonction standard avec la plage calculée
    return split_pdf(file, page_range, **options)

def split_pdf_fallback(input_path, temp_dir, page_range=None, options=None):
    """
    Méthode alternative pour diviser un PDF en fichiers individuels, un par page
    
    Cette méthode est utilisée comme secours lorsque l'outil C++ échoue.
    Elle utilise PyPDF2 pour extraire chaque page du PDF.
    
    Args:
        input_path: Chemin vers le fichier PDF d'entrée
        temp_dir: Répertoire temporaire pour les opérations
        page_range: Plage de pages à extraire (non utilisé, toutes les pages sont extraites)
        options: Options supplémentaires (non utilisées actuellement)
        
    Returns:
        Liste de dictionnaires avec les informations sur les fichiers générés
    """
    logger.info("Utilisation de la méthode de secours pour diviser le PDF")
    
    # Vérifier que le fichier existe
    if not os.path.isfile(input_path):
        raise FileNotFoundError(f"Le fichier d'entrée n'existe pas: {input_path}")
        
    try:
        # Import PyPDF2 ici pour éviter la dépendance si non nécessaire
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        logger.error("PyPDF2 n'est pas installé. Cette bibliothèque est requise pour la méthode de secours.")
        raise ImportError("PyPDF2 est requis pour la méthode de secours. Installez-le avec pip install PyPDF2")
    
    try:
        # Ouvrir le fichier d'entrée
        with open(input_path, 'rb') as f:
            reader = PdfReader(f)
            
            # Obtenir le nombre total de pages
            page_count = len(reader.pages)
            logger.info(f"Le PDF contient {page_count} pages")
            
            if page_count == 0:
                raise ValueError("Le PDF est vide, aucune page à extraire")
                
            # Extraire chaque page individuellement
            result_files = []
            
            base_name = os.path.basename(input_path)
            original_name = os.path.splitext(base_name)[0]
            
            # Extraire toutes les pages individuellement
            pages_to_extract = list(range(1, page_count + 1))
            
            processed_dir = get_processed_dir()
            
            # Créer un fichier par page
            for page_num in pages_to_extract:
                # Créer un nouveau PdfWriter
                writer = PdfWriter()
                
                # Ajouter une seule page
                writer.add_page(reader.pages[page_num - 1])
                
                # Générer un nom de fichier unique
                output_filename = f"{original_name}_page_{page_num}.pdf"
                unique_id = uuid.uuid4().hex
                unique_output_filename = f"{unique_id}_{output_filename}"
                
                output_path_temp = os.path.join(temp_dir, output_filename)
                output_path = os.path.join(processed_dir, unique_output_filename)
                
                # Écrire le fichier
                with open(output_path_temp, 'wb') as out_file:
                    writer.write(out_file)
                
                # Déplacer vers le répertoire de traitement
                shutil.move(output_path_temp, output_path)
                
                result_files.append({
                    'filename': output_filename,  # Utiliser 'filename' pour la cohérence
                    'name': output_filename,      # Conserver 'name' pour la rétrocompatibilité
                    'path': output_path,
                    'url': f"/download/{unique_output_filename}",
                    'size': os.path.getsize(output_path),
                    'page_number': page_num
                })
            
            # Trier les fichiers par numéro de page
            result_files.sort(key=lambda f: f['page_number'])
            return result_files
    except Exception as e:
        logger.exception(f"Erreur lors de la division du PDF avec la méthode de secours: {str(e)}")
        raise Exception(f"Impossible de diviser le PDF: {str(e)}")

def compress_pdf(file, quality="medium"):
    """
    Compresse un fichier PDF
    
    Args:
        file: Objet fichier à compresser
        quality: Niveau de compression (low, medium, high)
        
    Returns:
        Dictionnaire avec les informations sur le fichier compressé
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Générer un nom de fichier de sortie
    output_filename = f"compressed_{uuid.uuid4()}.pdf"
    output_path = os.path.join(temp_dir, output_filename)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["compress", input_path, output_path, quality]
    
    # Exécuter l'outil
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        raise Exception(f"Erreur lors de la compression du PDF: {stderr}")
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    final_path = os.path.join(processed_dir, output_filename)
    shutil.move(output_path, final_path)
    
    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)
    
    return {
        'filename': output_filename,
        'path': final_path,
        'url': f"/download/{output_filename}"
    }

def rotate_pdf(file, degrees):
    """
    Fait pivoter un fichier PDF
    
    Args:
        file: Objet fichier à faire pivoter
        degrees: Angle de rotation (90, 180, 270)
        
    Returns:
        Dictionnaire avec les informations sur le fichier pivoté
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Générer un nom de fichier de sortie
    output_filename = f"rotated_{uuid.uuid4()}.pdf"
    output_path = os.path.join(temp_dir, output_filename)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["rotate", input_path, output_path, str(degrees)]
    
    # Exécuter l'outil
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        raise Exception(f"Erreur lors de la rotation du PDF: {stderr}")
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    final_path = os.path.join(processed_dir, output_filename)
    shutil.move(output_path, final_path)
    
    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)
    
    return {
        'filename': output_filename,
        'path': final_path,
        'url': f"/download/{output_filename}"
    }

def watermark_pdf(file, text, opacity=0.5):
    """
    Ajoute un filigrane à un fichier PDF
    
    Args:
        file: Objet fichier à traiter
        text: Texte du filigrane
        opacity: Opacité du filigrane (entre 0 et 1)
        
    Returns:
        Dictionnaire avec les informations sur le fichier traité
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Valider l'opacité
    try:
        opacity_value = float(opacity)
        if opacity_value < 0 or opacity_value > 1:
            opacity_value = 0.5
    except (ValueError, TypeError):
        opacity_value = 0.5
    
    # Générer un nom de fichier de sortie
    output_filename = f"watermarked_{uuid.uuid4()}.pdf"
    output_path = os.path.join(temp_dir, output_filename)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["watermark", input_path, output_path, text, str(opacity_value)]
    
    # Exécuter l'outil
    logger.info(f"Exécution de watermark_pdf avec les arguments: {cmd_args}")
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        logger.error(f"Erreur lors de l'ajout du filigrane: {stderr}")
        raise Exception(f"Erreur lors de l'ajout du filigrane: {stderr}")
    
    # Vérifier que le fichier de sortie existe
    if not os.path.exists(output_path):
        shutil.rmtree(temp_dir)
        logger.error(f"Le fichier de sortie n'a pas été créé: {output_path}")
        raise Exception("Le fichier de sortie n'a pas été créé")
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    final_path = os.path.join(processed_dir, output_filename)
    shutil.move(output_path, final_path)
    
    # Collecter des informations sur le traitement
    file_info = {
        'filename': output_filename,
        'path': final_path,
        'url': f"/download/{output_filename}",
        'watermark_text': text,
        'watermark_opacity': opacity_value,
        'original_size': os.path.getsize(input_path) if os.path.exists(input_path) else 0,
        'processed_size': os.path.getsize(final_path)
    }
    
    # Ajouter des informations formatées pour l'UI
    file_info['original_size_formatted'] = format_file_size(file_info['original_size'])
    file_info['processed_size_formatted'] = format_file_size(file_info['processed_size'])
    
    # Sortie de débogage
    logger.info(f"Filigrane ajouté avec succès: {output_filename}")
    
    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)
    
    return file_info

def protect_pdf(file, password):
    """
    Protège un fichier PDF avec un mot de passe
    
    Args:
        file: Objet fichier à protéger
        password: Mot de passe pour protéger le fichier
        
    Returns:
        Dictionnaire avec les informations sur le fichier protégé
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Générer un nom de fichier de sortie
    output_filename = f"protected_{uuid.uuid4()}.pdf"
    output_path = os.path.join(temp_dir, output_filename)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["protect", input_path, output_path, password]
    
    # Exécuter l'outil
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        raise Exception(f"Erreur lors de la protection du PDF: {stderr}")
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    final_path = os.path.join(processed_dir, output_filename)
    shutil.move(output_path, final_path)
    
    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)
    
    return {
        'filename': output_filename,
        'path': final_path,
        'url': f"/download/{output_filename}"
    }

def unlock_pdf(file, password):
    """
    Déverrouille un fichier PDF protégé par mot de passe
    
    Args:
        file: Objet fichier à déverrouiller
        password: Mot de passe pour déverrouiller le fichier
        
    Returns:
        Dictionnaire avec les informations sur le fichier déverrouillé
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Générer un nom de fichier de sortie
    output_filename = f"unlocked_{uuid.uuid4()}.pdf"
    output_path = os.path.join(temp_dir, output_filename)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["unlock", input_path, output_path, password]
    
    # Exécuter l'outil
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        raise Exception(f"Erreur lors du déverrouillage du PDF: {stderr}")
    
    # Déplacer vers le répertoire des fichiers traités
    processed_dir = get_processed_dir()
    final_path = os.path.join(processed_dir, output_filename)
    shutil.move(output_path, final_path)
    
    # Nettoyer les fichiers temporaires
    shutil.rmtree(temp_dir)
    
    return {
        'filename': output_filename,
        'path': final_path,
        'url': f"/download/{output_filename}"
    }

def get_pdf_info(file):
    """
    Obtient des informations sur un fichier PDF
    
    Args:
        file: Objet fichier à analyser
        
    Returns:
        Dictionnaire avec les informations sur le fichier PDF
    """
    temp_dir = get_temp_dir()
    
    # Sauvegarder le fichier d'entrée
    safe_filename = secure_filename(file.filename)
    input_path = os.path.join(temp_dir, safe_filename)
    file.save(input_path)
    
    # Préparer les arguments pour l'outil C++
    cmd_args = ["info", input_path]
    
    # Exécuter l'outil
    returncode, stdout, stderr = run_pdfeditor(cmd_args)
    
    if returncode != 0:
        # Nettoyer
        shutil.rmtree(temp_dir)
        raise Exception(f"Erreur lors de l'obtention des informations du PDF: {stderr}")
    
    # Analyser la sortie JSON
    try:
        import json
        pdf_info = json.loads(stdout)
        
        # Ajouter des informations supplémentaires
        if os.path.exists(input_path):
            pdf_info['size'] = os.path.getsize(input_path)
            pdf_info['size_formatted'] = format_file_size(pdf_info['size'])
        
        # Nettoyer les fichiers temporaires
        shutil.rmtree(temp_dir)
        
        return pdf_info
    except json.JSONDecodeError as e:
        logger.error(f"Erreur lors de l'analyse de la sortie JSON: {e}")
        logger.error(f"Sortie brute: {stdout}")
        
        # Format de secours si le format JSON n'est pas disponible
        # Analyser la sortie texte brute
        result = {
            'fileName': safe_filename,
            'filePath': input_path,
            'size': os.path.getsize(input_path),
            'size_formatted': format_file_size(os.path.getsize(input_path))
        }
        
        # Extraire les informations basiques du stdout si possible
        # (Cette partie peut être personnalisée selon le format de sortie de l'outil)
        page_count = 0
        for line in stdout.splitlines():
            if "Number of Pages:" in line:
                try:
                    page_count = int(line.split(":")[1].strip())
                except:
                    pass
                
        result['pageCount'] = page_count
        
        # Nettoyer les fichiers temporaires
        shutil.rmtree(temp_dir)
        
        return result

def format_file_size(size_bytes):
    """Formate la taille du fichier en format lisible"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB" 