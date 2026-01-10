import socket
import threading
import json
import logging
import os
import random
import string
import shutil
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_from_directory, send_file
import mysql.connector
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from pathlib import Path
import tempfile

# Configuration de l'application
app = Flask(__name__, static_folder='.', static_url_path='')

# --- CONFIGURATION ---
VOTRE_EMAIL = "amougoubrayan14@gmail.com"
VOTRE_MOT_DE_PASSE = "rnmeybbwtsjgoaoo"

# Configuration XAMPP MySQL
DB_CONFIG = {
    'user': 'root',
    'password': '',  # Mot de passe vide par défaut pour XAMPP
    'host': 'localhost',  # localhost pour XAMPP
    'database': 'nick_cloud_db'
}

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dossier de base pour le stockage
BASE_STORAGE_PATH = "vm_storage"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB maximum

# --- FONCTIONS UTILITAIRES ---
def get_db_connection():
    """Établit une connexion à la base de données MySQL (XAMPP)"""
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        logger.error(f"Erreur de connexion à la DB: {err}")
        return None

def init_database():
    """Initialise la base de données"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Impossible de se connecter à la base de données")
            return False
            
        cursor = conn.cursor()
        
        # Table des codes de confirmation
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS confirmation_codes (
                email VARCHAR(100) PRIMARY KEY,
                code VARCHAR(6) NOT NULL,
                data_json TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table des machines virtuelles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS virtual_machines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vm_name VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(100) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                storage_mb INT NOT NULL DEFAULT 500,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                status ENUM('active', 'suspended') DEFAULT 'active'
            )
        """)
        
        # Table pour les fichiers (optionnel - pour tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vm_files (
                id INT AUTO_INCREMENT PRIMARY KEY,
                vm_name VARCHAR(100) NOT NULL,
                filename VARCHAR(255) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                size_bytes BIGINT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_vm_name (vm_name)
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info("✅ Base de données initialisée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erreur d'initialisation DB: {e}")
        return False

def generate_confirmation_code(length=6):
    """Génère un code de confirmation numérique"""
    return ''.join(random.choices(string.digits, k=length))

def send_confirmation_email(to_email, code):
    """Envoie un email de confirmation"""
    try:
        # Configuration de l'email
        sender_email = VOTRE_EMAIL
        sender_password = VOTRE_MOT_DE_PASSE
        
        # Création du message
        message = MIMEMultipart("alternative")
        message["Subject"] = "Code de confirmation - Nick Cloud System"
        message["From"] = sender_email
        message["To"] = to_email
        
        # Version texte
        text = f"""Bonjour,
        
Votre code de confirmation pour Nick Cloud System est :
{code}

Ce code est valable pendant 10 minutes.

L'équipe Nick Cloud System"""
        
        # Version HTML
        html = f"""<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
        <h2 style="color: #4CAF50;">Nick Cloud System</h2>
        <h3>Confirmation de création de VM</h3>
        
        <p>Bonjour,</p>
        
        <p>Voici votre code de confirmation pour créer votre VM :</p>
        
        <div style="background-color: #f0f9ff; padding: 20px; text-align: center; border-radius: 5px; margin: 20px 0;">
            <h1 style="color: #1E3A8A; font-size: 32px; letter-spacing: 5px;">{code}</h1>
        </div>
        
        <p>Ce code est valable pendant <strong>10 minutes</strong>.</p>
        
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        
        <p style="color: #666; font-size: 12px;">
            Cet email a été envoyé automatiquement par le Nick Cloud System.
        </p>
    </div>
</body>
</html>"""
        
        # Convertir en MIMEText
        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)
        
        # Envoyer l'email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        
        logger.info(f"Email de confirmation envoyé à {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Erreur d'envoi d'email: {e}")
        return False

def get_vm_storage_path(vm_name):
    """Retourne le chemin du dossier de stockage d'une VM"""
    return os.path.join(BASE_STORAGE_PATH, vm_name)

def create_vm_storage(vm_name):
    """Crée le dossier de stockage pour une VM"""
    vm_path = get_vm_storage_path(vm_name)
    os.makedirs(vm_path, exist_ok=True)
    logger.info(f"Dossier de stockage créé pour {vm_name}: {vm_path}")
    return vm_path

def get_vm_storage_info(vm_name):
    """Calcule l'utilisation du stockage d'une VM - CORRIGÉ"""
    vm_path = get_vm_storage_path(vm_name)
    
    if not os.path.exists(vm_path):
        return {'used_bytes': 0, 'used_mb': 0, 'file_count': 0}
    
    total_size = 0
    file_count = 0
    
    for root, dirs, files in os.walk(vm_path):
        for file in files:
            file_path = os.path.join(root, file)
            if os.path.isfile(file_path):
                try:
                    total_size += os.path.getsize(file_path)
                    file_count += 1
                except OSError as e:
                    logger.warning(f"Impossible de lire le fichier {file_path}: {e}")
    
    return {
        'used_bytes': total_size,
        'used_mb': total_size / (1024 * 1024),
        'file_count': file_count
    }

def get_storage_limit(vm_name):
    """Retourne la limite de stockage d'une VM"""
    conn = get_db_connection()
    if not conn:
        return 500 * 1024 * 1024  # 500MB par défaut
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT storage_mb FROM virtual_machines WHERE vm_name = %s", (vm_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result['storage_mb'] * 1024 * 1024  # Convertir en bytes
    except Exception as e:
        logger.error(f"Erreur récupération limite stockage: {e}")
    
    return 500 * 1024 * 1024  # 500MB par défaut

def check_storage_space_before_upload(vm_name, file_size):
    """Vérifie l'espace disponible AVANT upload - CORRECTION CRITIQUE"""
    storage_limit = get_storage_limit(vm_name)
    storage_info = get_vm_storage_info(vm_name)
    
    available_space = storage_limit - storage_info['used_bytes']
    
    logger.info(f"🔍 Vérification espace: VM={vm_name}, Fichier={file_size}B, Disponible={available_space}B, Limite={storage_limit}B")
    
    if file_size > available_space:
        return False, {
            'available_mb': available_space / (1024 * 1024),
            'needed_mb': file_size / (1024 * 1024),
            'used_mb': storage_info['used_mb'],
            'limit_mb': storage_limit / (1024 * 1024),
            'exceeded_by': file_size - available_space
        }
    
    return True, {
        'available_mb': available_space / (1024 * 1024),
        'needed_mb': file_size / (1024 * 1024),
        'used_mb': storage_info['used_mb'],
        'limit_mb': storage_limit / (1024 * 1024)
    }

def cleanup_old_files():
    """Nettoie les anciens fichiers de la base de données qui n'existent plus"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Récupérer tous les fichiers de la DB
        cursor.execute("SELECT vm_name, filename, file_path FROM vm_files")
        db_files = cursor.fetchall()
        
        deleted_count = 0
        
        for db_file in db_files:
            vm_name = db_file['vm_name']
            filename = db_file['filename']
            file_path = db_file['file_path']
            
            # Vérifier si le fichier existe physiquement
            if not os.path.exists(file_path):
                # Supprimer de la DB
                cursor.execute("DELETE FROM vm_files WHERE vm_name = %s AND filename = %s", 
                             (vm_name, filename))
                deleted_count += 1
                logger.info(f"🗑️  Fichier fantôme supprimé de la DB: {vm_name}/{filename}")
        
        if deleted_count > 0:
            conn.commit()
            logger.info(f"✅ {deleted_count} fichiers fantômes nettoyés")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Erreur nettoyage fichiers: {e}")

# --- ROUTES API COMPLÈTES ---
@app.route('/')
def index():
    """Page d'accueil"""
    return send_from_directory('.', 'index.html')

@app.route('/api/status')
def api_status():
    """Statut de l'API"""
    return jsonify({
        'status': 'online',
        'service': 'Nick Cloud System',
        'version': '2.0.0',
        'storage_path': BASE_STORAGE_PATH
    })

@app.route('/send_code', methods=['POST'])
def send_confirmation_code():
    """Envoie un code de confirmation par email"""
    try:
        data = request.json
        logger.info(f"Demande de code pour: {data.get('vmEmail')}")
        
        # Validation
        required_fields = ['vmName', 'vmEmail', 'vmPassword', 'vmStorage']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'message': f'Champ manquant: {field}'
                }), 400
        
        vm_name = data['vmName'].strip()
        email = data['vmEmail'].strip().lower()
        password = data['vmPassword']
        storage = data['vmStorage']
        
        # Validation basique
        if len(vm_name) < 3:
            return jsonify({
                'success': False,
                'message': 'Le nom de la VM doit avoir au moins 3 caractères'
            }), 400
        
        if len(password) < 8:
            return jsonify({
                'success': False,
                'message': 'Le mot de passe doit avoir au moins 8 caractères'
            }), 400
        
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'message': 'Email invalide'
            }), 400
        
        # Vérifier si la VM existe déjà
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT vm_name FROM virtual_machines WHERE vm_name = %s", (vm_name,))
            existing_vm = cursor.fetchone()
            
            if existing_vm:
                conn.close()
                return jsonify({
                    'success': False,
                    'message': 'Ce nom de VM est déjà utilisé'
                }), 400
            conn.close()
        
        # Générer le code
        code = generate_confirmation_code()
        
        # Stocker temporairement
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                expires_at = datetime.now() + timedelta(minutes=10)
                
                cursor.execute("""
                    INSERT INTO confirmation_codes (email, code, data_json, expires_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    code = VALUES(code),
                    data_json = VALUES(data_json),
                    expires_at = VALUES(expires_at)
                """, (email, code, json.dumps(data), expires_at))
                
                conn.commit()
                conn.close()
        except Exception as db_error:
            logger.warning(f"Erreur DB: {db_error}")
        
        # Envoyer l'email
        email_sent = send_confirmation_email(email, code)
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': 'Code de confirmation envoyé par email'
            })
        else:
            logger.warning(f"Email non envoyé, code généré: {code}")
            return jsonify({
                'success': True,
                'message': 'Code généré (mode test)',
                'test_code': code
            })
            
    except Exception as e:
        logger.error(f"Erreur dans send_code: {e}")
        return jsonify({
            'success': False,
            'message': 'Erreur interne du serveur'
        }), 500

@app.route('/register_vm', methods=['POST'])
def register_virtual_machine():
    """Crée une nouvelle VM avec confirmation par email"""
    try:
        data = request.json
        logger.info(f"Inscription VM: {data.get('vmEmail')}")
        
        entered_code = data.get('enteredCode', '').strip()
        email = data.get('vmEmail', '').strip().lower()
        
        if not entered_code:
            return jsonify({
                'success': False,
                'message': 'Code de confirmation requis'
            }), 400
        
        # Récupérer les données originales
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT code, data_json FROM confirmation_codes 
                WHERE email = %s AND expires_at > NOW()
            """, (email,))
            
            code_data = cursor.fetchone()
            
            if not code_data:
                conn.close()
                return jsonify({
                    'success': False,
                    'message': 'Code expiré ou non trouvé'
                }), 400
            
            if code_data['code'] != entered_code:
                conn.close()
                return jsonify({
                    'success': False,
                    'message': 'Code de confirmation incorrect'
                }), 400
            
            original_data = json.loads(code_data['data_json'])
            conn.close()
        else:
            # Mode test sans DB
            original_data = {
                'vmName': data.get('vmName'),
                'vmEmail': email,
                'vmPassword': data.get('vmPassword'),
                'vmStorage': data.get('vmStorage', '500MB')
            }
        
        # Extraire les données
        vm_name = original_data.get('vmName', '').strip()
        password = original_data.get('vmPassword', '')
        storage_str = original_data.get('vmStorage', '500MB')
        
        # Convertir le stockage
        storage_mb = 500
        try:
            storage_mb = int(storage_str.replace('MB', '').strip())
        except:
            pass
        
        # Hasher le mot de passe
        hashed_password = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
        
        # Créer la VM dans la base de données
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute("""
                    INSERT INTO virtual_machines (vm_name, email, password_hash, storage_mb)
                    VALUES (%s, %s, %s, %s)
                """, (vm_name, email, hashed_password, storage_mb))
                
                # Nettoyer le code utilisé
                cursor.execute("DELETE FROM confirmation_codes WHERE email = %s", (email,))
                
                conn.commit()
                conn.close()
                
                # Créer le dossier de stockage (VIDE)
                create_vm_storage(vm_name)
                
                logger.info(f"✅ VM créée: {vm_name} avec {storage_mb}MB")
                
                return jsonify({
                    'success': True,
                    'message': 'VM créée avec succès',
                    'vm_name': vm_name,
                    'storage': f"{storage_mb}MB",
                    'email': email
                })
                
            except mysql.connector.Error as err:
                conn.close()
                if err.errno == 1062:  # Duplicate entry
                    return jsonify({
                        'success': False,
                        'message': 'Cette VM ou email existe déjà'
                    }), 400
                else:
                    raise err
        else:
            # Mode simulation
            create_vm_storage(vm_name)
            return jsonify({
                'success': True,
                'message': 'VM créée (mode simulation)',
                'vm_name': vm_name,
                'storage': f"{storage_mb}MB",
                'email': email
            })
        
    except Exception as e:
        logger.error(f"Erreur dans register_vm: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/login', methods=['POST'])
def login_vm():
    """Authentifie une VM"""
    try:
        data = request.json
        vm_name = data.get('vmName', '').strip()
        password = data.get('password', '')
        
        logger.info(f"Tentative de connexion: {vm_name}")
        
        if not vm_name or not password:
            return jsonify({
                'success': False,
                'message': 'Nom de VM et mot de passe requis'
            }), 400
        
        # Rechercher la VM
        conn = get_db_connection()
        if not conn:
            # Mode simulation si DB non disponible
            return jsonify({
                'success': True,
                'message': 'Connexion réussie',
                'vm_name': vm_name,
                'storage': '500MB',
                'email': f'{vm_name}@test.com'
            })
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT vm_name, email, password_hash, storage_mb
            FROM virtual_machines 
            WHERE vm_name = %s AND status = 'active'
        """, (vm_name,))
        
        vm = cursor.fetchone()
        
        if not vm:
            conn.close()
            return jsonify({
                'success': False,
                'message': 'VM non trouvée'
            }), 404
        
        # Vérifier le mot de passe
        if not bcrypt.checkpw(password.encode('utf-8'), vm['password_hash'].encode('utf-8')):
            conn.close()
            return jsonify({
                'success': False,
                'message': 'Mot de passe incorrect'
            }), 401
        
        # Mettre à jour la dernière connexion
        cursor.execute("""
            UPDATE virtual_machines 
            SET last_login = NOW() 
            WHERE vm_name = %s
        """, (vm_name,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Connexion réussie: {vm_name}")
        
        return jsonify({
            'success': True,
            'message': 'Connexion réussie',
            'vm_name': vm['vm_name'],
            'storage': f"{vm['storage_mb']}MB",
            'email': vm['email']
        })
        
    except Exception as e:
        logger.error(f"Erreur dans login: {e}")
        return jsonify({
            'success': False,
            'message': 'Erreur interne du serveur'
        }), 500

@app.route('/api/vm/<vm_name>/storage')
def get_vm_storage(vm_name):
    """Récupère les informations de stockage d'une VM"""
    try:
        storage_info = get_vm_storage_info(vm_name)
        storage_limit = get_storage_limit(vm_name)
        
        used_mb = storage_info['used_mb']
        limit_mb = storage_limit / (1024 * 1024)
        
        # CORRECTION : Garantir que used_mb ne dépasse pas limit_mb
        if used_mb > limit_mb:
            logger.warning(f"⚠️ Utilisation excessive détectée: {vm_name} - {used_mb:.2f}MB > {limit_mb:.2f}MB")
            used_mb = limit_mb
        
        available_bytes = max(0, storage_limit - storage_info['used_bytes'])
        
        return jsonify({
            'success': True,
            'storage': {
                'used_bytes': storage_info['used_bytes'],
                'used_mb': used_mb,
                'limit_bytes': storage_limit,
                'limit_mb': limit_mb,
                'available_bytes': available_bytes,
                'available_mb': available_bytes / (1024 * 1024),
                'file_count': storage_info['file_count']
            }
        })
    except Exception as e:
        logger.error(f"Erreur get_vm_storage: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/vm/<vm_name>/files')
def get_vm_files(vm_name):
    """Récupère la liste des fichiers d'une VM - CORRIGÉ"""
    try:
        vm_path = get_vm_storage_path(vm_name)
        files = []
        
        if os.path.exists(vm_path):
            for filename in os.listdir(vm_path):
                filepath = os.path.join(vm_path, filename)
                if os.path.isfile(filepath) and not filename.startswith('.'):  # Ignorer fichiers cachés
                    try:
                        size = os.path.getsize(filepath)
                        modified = os.path.getmtime(filepath)
                        
                        files.append({
                            'name': filename,
                            'size': size,
                            'size_display': format_file_size(size),
                            'modified': datetime.fromtimestamp(modified).isoformat(),
                            'modified_display': datetime.fromtimestamp(modified).strftime('%d/%m/%Y %H:%M'),
                            'path': filepath
                        })
                    except OSError as e:
                        logger.warning(f"Impossible de lire le fichier {filepath}: {e}")
        
        # Trier par date de modification (plus récent d'abord)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        logger.info(f"📁 Fichiers pour {vm_name}: {len(files)} fichiers réels")
        
        return jsonify({
            'success': True,
            'files': files
        })
    except Exception as e:
        logger.error(f"Erreur get_vm_files: {e}")
        return jsonify({
            'success': False,
            'message': str(e),
            'files': []
        }), 500

@app.route('/api/vm/<vm_name>/upload', methods=['POST'])
def upload_file(vm_name):
    """Upload un fichier pour une VM - CORRECTION CRITIQUE"""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Aucun fichier fourni'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': 'Nom de fichier vide'
            }), 400
        
        # Sécuriser le nom du fichier
        filename = secure_filename(file.filename)
        
        # CORRECTION CRITIQUE: Sauvegarder d'abord dans un fichier temporaire
        temp_file = None
        try:
            # Créer un fichier temporaire
            temp_fd, temp_path = tempfile.mkstemp()
            os.close(temp_fd)
            
            # Sauvegarder le fichier dans le temporaire
            file.save(temp_path)
            
            # Obtenir la taille EXACTE du fichier
            file_size = os.path.getsize(temp_path)
            
            logger.info(f"📄 Fichier temporaire créé: {filename} - Taille: {file_size}B ({file_size/(1024*1024):.2f}MB)")
            
        except Exception as temp_error:
            logger.error(f"Erreur création fichier temporaire: {temp_error}")
            return jsonify({
                'success': False,
                'message': 'Erreur lors de la préparation du fichier'
            }), 500
        
        # Vérifier la taille maximale
        if file_size > MAX_FILE_SIZE:
            os.remove(temp_path)
            return jsonify({
                'success': False,
                'message': f'Fichier trop volumineux (max {MAX_FILE_SIZE/(1024*1024)}MB)'
            }), 400
        
        # CORRECTION CRITIQUE: Vérifier l'espace disponible AVANT de copier
        has_space, space_info = check_storage_space_before_upload(vm_name, file_size)
        
        if not has_space:
            os.remove(temp_path)
            return jsonify({
                'success': False,
                'message': f'❌ ESPACE INSUFFISANT! Disponible: {space_info["available_mb"]:.2f}MB, Nécessaire: {space_info["needed_mb"]:.2f}MB',
                'space_info': space_info
            }), 400
        
        # Préparer le chemin de destination
        vm_path = get_vm_storage_path(vm_name)
        os.makedirs(vm_path, exist_ok=True)
        
        # Vérifier si le fichier existe déjà
        destination_path = os.path.join(vm_path, filename)
        counter = 1
        base_name, extension = os.path.splitext(filename)
        
        while os.path.exists(destination_path):
            filename = f"{base_name}_{counter}{extension}"
            destination_path = os.path.join(vm_path, filename)
            counter += 1
        
        # CORRECTION CRITIQUE: Copier le fichier temporaire vers la destination
        try:
            shutil.copy2(temp_path, destination_path)
            
            # Vérifier que la copie a réussi
            if not os.path.exists(destination_path):
                raise Exception("La copie du fichier a échoué")
            
            saved_size = os.path.getsize(destination_path)
            
            logger.info(f"✅ Fichier copié: {filename} ({saved_size}B) vers {vm_name}")
            
        except Exception as copy_error:
            logger.error(f"❌ Erreur copie fichier: {copy_error}")
            os.remove(temp_path)
            return jsonify({
                'success': False,
                'message': f'Erreur lors de la copie du fichier: {str(copy_error)}'
            }), 500
        
        # Nettoyer le fichier temporaire
        try:
            os.remove(temp_path)
        except:
            pass
        
        # Enregistrer dans la base de données
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vm_files (vm_name, filename, file_path, size_bytes)
                VALUES (%s, %s, %s, %s)
            """, (vm_name, filename, destination_path, saved_size))
            conn.commit()
            conn.close()
        
        logger.info(f"✅ Upload réussi: {filename} ({saved_size} bytes) pour {vm_name}")
        
        return jsonify({
            'success': True,
            'message': '✅ Fichier uploadé avec succès',
            'filename': filename,
            'size': saved_size,
            'size_display': format_file_size(saved_size)
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur upload_file: {e}")
        # Nettoyer le fichier temporaire si il existe
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/vm/<vm_name>/delete/<filename>', methods=['DELETE'])
def delete_file(vm_name, filename):
    """Supprime un fichier d'une VM"""
    try:
        # Sécuriser le nom du fichier
        safe_filename = secure_filename(filename)
        vm_path = get_vm_storage_path(vm_name)
        filepath = os.path.join(vm_path, safe_filename)
        
        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Fichier non trouvé'
            }), 404
        
        # Supprimer le fichier
        file_size = os.path.getsize(filepath)
        os.remove(filepath)
        
        # Supprimer de la base de données
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM vm_files WHERE vm_name = %s AND filename = %s", 
                          (vm_name, safe_filename))
            conn.commit()
            conn.close()
        
        logger.info(f"✅ Fichier supprimé: {safe_filename} de {vm_name}")
        
        return jsonify({
            'success': True,
            'message': '✅ Fichier supprimé avec succès',
            'filename': safe_filename,
            'size_freed': file_size
        })
        
    except Exception as e:
        logger.error(f"❌ Erreur delete_file: {e}")
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500

@app.route('/api/vm/<vm_name>/download/<filename>')
def download_file(vm_name, filename):
    """Télécharge un fichier d'une VM"""
    try:
        safe_filename = secure_filename(filename)
        vm_path = get_vm_storage_path(vm_name)
        filepath = os.path.join(vm_path, safe_filename)
        
        if not os.path.exists(filepath):
            return jsonify({
                'success': False,
                'message': 'Fichier non trouvé'
            }), 404
        
        return send_file(filepath, as_attachment=True, download_name=safe_filename)
        
    except Exception as e:
        logger.error(f"❌ Erreur download_file: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/vm/<vm_name>/cleanup', methods=['POST'])
def cleanup_vm_files(vm_name):
    """Nettoie les fichiers fantômes d'une VM"""
    try:
        deleted_count = 0
        conn = get_db_connection()
        
        if conn:
            cursor = conn.cursor(dictionary=True)
            
            # Récupérer tous les fichiers de la VM depuis la DB
            cursor.execute("SELECT filename, file_path FROM vm_files WHERE vm_name = %s", (vm_name,))
            db_files = cursor.fetchall()
            
            for db_file in db_files:
                file_path = db_file['file_path']
                
                # Vérifier si le fichier existe physiquement
                if not os.path.exists(file_path):
                    # Supprimer de la DB
                    cursor.execute("DELETE FROM vm_files WHERE vm_name = %s AND file_path = %s", 
                                 (vm_name, file_path))
                    deleted_count += 1
            
            if deleted_count > 0:
                conn.commit()
            
            conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ {deleted_count} fichiers fantômes nettoyés',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        logger.error(f"Erreur cleanup: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

def format_file_size(size_bytes):
    """Formate la taille d'un fichier en unités lisibles"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

# --- NETTOYAGE AU DÉMARRAGE ---
def startup_cleanup():
    """Nettoie les fichiers fantômes au démarrage"""
    logger.info("🧹 Nettoyage des fichiers fantômes au démarrage...")
    
    # Nettoyer la base de données
    cleanup_old_files()
    
    # Vérifier l'intégrité des dossiers
    if os.path.exists(BASE_STORAGE_PATH):
        vm_count = len([d for d in os.listdir(BASE_STORAGE_PATH) if os.path.isdir(os.path.join(BASE_STORAGE_PATH, d))])
        logger.info(f"📂 {vm_count} VMs trouvées dans le stockage")
    else:
        os.makedirs(BASE_STORAGE_PATH, exist_ok=True)
        logger.info(f"📂 Dossier de stockage créé: {BASE_STORAGE_PATH}")

# --- POINT D'ENTRÉE PRINCIPAL ---
def main():
    """Fonction principale"""
    logger.info("🚀 Démarrage du Nick Cloud System...")
    
    # Créer les dossiers nécessaires
    os.makedirs(BASE_STORAGE_PATH, exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    # Nettoyage au démarrage
    startup_cleanup()
    
    # Initialiser la base de données
    if not init_database():
        logger.warning("⚠️ Base de données non initialisée - mode test activé")
    
    # Démarrer le serveur Flask
    logger.info("🌐 Serveur web démarré sur http://0.0.0.0:5000")
    logger.info("📂 Dossier de stockage: vm_storage/")
    logger.info("=" * 50)
    logger.info("Accédez à l'interface: http://localhost:5000")
    logger.info("=" * 50)
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        use_reloader=False
    )

if __name__ == '__main__':
    main() 