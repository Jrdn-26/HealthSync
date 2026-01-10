#!/usr/bin/env python3
"""
Script de réinitialisation COMPLÈTE du système Nick Cloud
"""

import os
import shutil
import mysql.connector

print("=" * 60)
print("🧹 RÉINITIALISATION COMPLÈTE - NICK CLOUD SYSTEM")
print("=" * 60)

# Configuration
BASE_STORAGE = "vm_storage"
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'nick_cloud_db'
}

def reset_system():
    """Réinitialise complètement le système"""
    
    print("\n1. 🗑️  Suppression du dossier de stockage...")
    if os.path.exists(BASE_STORAGE):
        shutil.rmtree(BASE_STORAGE)
        print(f"   ✅ {BASE_STORAGE} supprimé")
    
    # Recréer vide
    os.makedirs(BASE_STORAGE, exist_ok=True)
    print(f"   ✅ {BASE_STORAGE} recréé (vide)")
    
    print("\n2. 🗄️  Réinitialisation de la base de données...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Supprimer toutes les tables
        cursor.execute("DROP TABLE IF EXISTS vm_files")
        cursor.execute("DROP TABLE IF EXISTS virtual_machines")
        cursor.execute("DROP TABLE IF EXISTS confirmation_codes")
        
        # Recréer les tables
        cursor.execute("""
            CREATE TABLE confirmation_codes (
                email VARCHAR(100) PRIMARY KEY,
                code VARCHAR(6) NOT NULL,
                data_json TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE virtual_machines (
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
        
        cursor.execute("""
            CREATE TABLE vm_files (
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
        conn.close()
        print("   ✅ Base de données réinitialisée")
        
    except Exception as e:
        print(f"   ⚠️  Erreur DB: {e}")
    
    print("\n3. 📁 Vérification des dossiers...")
    
    # Vérifier/créer static
    if not os.path.exists('static'):
        os.makedirs('static', exist_ok=True)
        print("   ✅ Dossier 'static' créé")
    
    print("\n✅ RÉINITIALISATION TERMINÉE!")
    print("\nPour démarrer le système:")
    print("   python serveur.py")
    print("\nAccédez à: http://localhost:5000")

def main():
    print("\n⚠️  Cette action va:")
    print("   • Supprimer TOUTES les VMs")
    print("   • Supprimer TOUS les fichiers")
    print("   • Réinitialiser la base de données")
    print("   • Tout recommencer à zéro")
    
    confirm = input("\nÊtes-vous sûr? (tapez 'RESET' pour confirmer): ")
    
    if confirm == "RESET":
        reset_system()
    else:
        print("\n❌ Opération annulée")

if __name__ == "__main__":
    main()