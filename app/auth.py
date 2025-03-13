"""
Module d'authentification pour l'application PDF Editor
"""
import os
import functools
from flask import request, Response, session, current_app, redirect, url_for, flash
import secrets
import hashlib
import time

def check_auth(username, password):
    """
    Vérifie les identifiants d'authentification

    Si les variables d'environnement ADMIN_USER et ADMIN_PASSWORD sont définies,
    vérifie par rapport à ces valeurs. Sinon, utilise des identifiants par défaut 
    pour le développement.
    """
    env_user = os.environ.get('ADMIN_USER')
    env_password = os.environ.get('ADMIN_PASSWORD')
    
    # En production, utiliser les variables d'environnement
    if env_user and env_password:
        return username == env_user and password == env_password
    
    # En développement uniquement, utiliser des identifiants par défaut
    # Cela devrait être changé en production
    return username == 'admin' and password == 'pdfeditor-secure-password'

def authenticate():
    """Envoie une réponse d'authentification HTTP Basic"""
    return Response(
        'Accès limité. Veuillez vous authentifier.\n',
        401,
        {'WWW-Authenticate': 'Basic realm="PDF Editor Admin"'}
    )

def requires_auth(f):
    """Décorateur pour protéger les routes sensibles avec une authentification Basic"""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def generate_csrf_token():
    """
    Génère un jeton CSRF sécurisé pour les formulaires
    
    Retourne:
        str: Jeton CSRF
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def validate_csrf_token(token):
    """
    Valide un jeton CSRF
    
    Args:
        token: Jeton CSRF à valider
        
    Retourne:
        bool: True si le jeton est valide, False sinon
    """
    if not token or 'csrf_token' not in session:
        return False
    return token == session['csrf_token']

def rate_limit(key, limit=10, period=60):
    """
    Limite le nombre de requêtes par IP
    
    Args:
        key: Clé de limitation (généralement l'IP)
        limit: Nombre de requêtes autorisées par période
        period: Période en secondes
        
    Retourne:
        bool: True si la limite est dépassée, False sinon
    """
    cache_key = f"rate_limit:{key}"
    now = time.time()
    
    # Créer un enregistrement si non existant
    if not hasattr(current_app, 'rate_limit_cache'):
        current_app.rate_limit_cache = {}
    
    # Récupérer le cache existant ou créer un nouveau
    if cache_key not in current_app.rate_limit_cache:
        current_app.rate_limit_cache[cache_key] = {'count': 0, 'reset_at': now + period}
    
    cache = current_app.rate_limit_cache[cache_key]
    
    # Réinitialiser le compteur si la période est écoulée
    if now > cache['reset_at']:
        cache['count'] = 0
        cache['reset_at'] = now + period
    
    # Incrémenter le compteur
    cache['count'] += 1
    
    # Vérifier si la limite est dépassée
    return cache['count'] > limit

def get_client_ip():
    """
    Récupère l'adresse IP du client de manière sécurisée
    
    Retourne:
        str: Adresse IP du client
    """
    # Priorité aux en-têtes standard
    if request.environ.get('REMOTE_ADDR'):
        return request.environ.get('REMOTE_ADDR')
    
    # Utiliser X-Forwarded-For en dernier recours (moins fiable)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Prendre la première IP (client d'origine)
        return forwarded_for.split(',')[0].strip()
    
    return 'unknown'

def sanitize_redirect_url(url):
    """
    Sanitise une URL de redirection pour éviter les redirections ouvertes
    
    Args:
        url: URL à sanitiser
        
    Retourne:
        str: URL sanitisée
    """
    if not url or not url.startswith('/'):
        return '/'
    return url 