import socket
import os
import json
import hashlib
import threading
import time
from datetime import datetime
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VirtualMachine:
    """Classe représentant une Machine Virtuelle dans le réseau P2P"""
    
    def __init__(self, name, storage_limit_mb=500):
        self.name = name
        self.storage_limit = storage_limit_mb * 1024 * 1024  # Convertir en octets
        self.folder = f"vm_{name}"
        self.connected = False
        self.server_socket = None
        self.shared_files = []
        
        # Créer le dossier de la VM
        os.makedirs(self.folder, exist_ok=True)
        
        # Initialiser le stockage
        self.update_storage_info()
        
        logger.info(f"✅ VM '{name}' initialisée avec {storage_limit_mb}MB de stockage")
    
    def update_storage_info(self):
        """Met à jour les informations de stockage"""
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.folder):
            for file in files:
                filepath = os.path.join(root, file)
                total_size += os.path.getsize(filepath)
                file_count += 1
        
        self.storage_used = total_size
        self.file_count = file_count
        
        return {
            'used_kb': total_size / 1024,
            'used_mb': total_size / (1024 * 1024),
            'limit_mb': self.storage_limit / (1024 * 1024),
            'percentage': (total_size / self.storage_limit) * 100,
            'file_count': file_count
        }
    
    def check_quota(self, additional_size_bytes):
        """Vérifie si l'ajout du fichier dépasse le quota"""
        if self.storage_used + additional_size_bytes > self.storage_limit:
            free_kb = (self.storage_limit - self.storage_used) / 1024
            needed_kb = additional_size_bytes / 1024
            logger.warning(f"❌ Espace insuffisant! Libre: {free_kb:.1f}KB, Nécessaire: {needed_kb:.1f}KB")
            return False
        return True
    
    def connect_to_server(self, host='localhost', port=7000):
        """Se connecte au serveur Cloud P2P"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.connect((host, port))
            
            # Envoyer la commande d'initialisation
            init_message = f"VM_INIT:{self.name}"
            self.server_socket.sendall(init_message.encode('utf-8'))
            
            # Attendre la confirmation
            response = self.server_socket.recv(1024).decode('utf-8')
            
            if response.startswith("AUTH_OK"):
                self.connected = True
                logger.info(f"✅ Connecté au serveur Cloud P2P")
                
                # Démarrer un thread pour écouter les messages
                listener_thread = threading.Thread(
                    target=self.listen_for_messages,
                    daemon=True
                )
                listener_thread.start()
                
                # Annoncer les fichiers partagés
                self.announce_shared_files()
                
                return True
            else:
                logger.error(f"❌ Erreur de connexion: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erreur de connexion au serveur: {e}")
            return False
    
    def listen_for_messages(self):
        """Écoute les messages du serveur"""
        try:
            while self.connected:
                data = self.server_socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                self.process_server_message(data)
                
        except Exception as e:
            logger.error(f"❌ Erreur d'écoute: {e}")
        finally:
            self.connected = False
            logger.info("⚠️ Déconnecté du serveur")
    
    def process_server_message(self, message):
        """Traite un message du serveur"""
        try:
            if message == "PONG":
                logger.debug("Pong reçu du serveur")
            
            elif message.startswith("{"):
                # Message JSON
                data = json.loads(message)
                
                if data.get('type') == 'SEARCH_RESULTS':
                    filename = data.get('filename')
                    results = data.get('results', [])
                    
                    logger.info(f"🔍 Résultats pour '{filename}': {len(results)} trouvaille(s)")
                    
                    if results:
                        print(f"\n📁 Fichier trouvé: {filename}")
                        for i, result in enumerate(results, 1):
                            print(f"  {i}. Sur VM: {result['vm']} - Taille: {result['size']}")
                        
                        # Demander si l'utilisateur veut télécharger
                        choice = input("\n📥 Télécharger depuis quelle VM? (numéro ou 0 pour annuler): ")
                        
                        try:
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(results):
                                self.download_from_vm(filename, results[choice_idx])
                        except ValueError:
                            pass
        
        except json.JSONDecodeError:
            logger.warning(f"Message non-JSON reçu: {message[:50]}...")
    
    def announce_shared_files(self):
        """Annonce les fichiers partagés au serveur"""
        shared_files = self.get_shared_files()
        
        for file_info in shared_files:
            message = f"FILE_REGISTER:{file_info['name']}:{file_info['size']}:{file_info['checksum']}"
            self.server_socket.sendall(message.encode('utf-8'))
            time.sleep(0.1)  # Petit délai pour éviter la surcharge
    
    def get_shared_files(self):
        """Retourne la liste des fichiers partagés"""
        shared_files = []
        
        for root, dirs, files in os.walk(self.folder):
            for file in files:
                filepath = os.path.join(root, file)
                
                # Pour cette démo, tous les fichiers sont considérés comme partagés
                file_size = os.path.getsize(filepath)
                checksum = self.calculate_checksum(filepath)
                
                shared_files.append({
                    'name': file,
                    'size': f"{file_size}B",
                    'checksum': checksum,
                    'path': filepath
                })
        
        return shared_files
    
    def calculate_checksum(self, filepath):
        """Calcule le checksum MD5 d'un fichier"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def create_file(self):
        """Crée un nouveau fichier"""
        print(f"\n{'='*50}")
        print("📄 CRÉATION DE FICHIER")
        print("="*50)
        
        name = input("Nom du fichier: ").strip()
        if not name:
            print("❌ Nom de fichier invalide")
            return
        
        content = input("Contenu du fichier (appuyez sur Entrée deux fois pour finir):\n")
        
        if not content:
            content = f"Fichier créé par {self.name} le {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        content_bytes = content.encode('utf-8')
        
        if self.check_quota(len(content_bytes)):
            filepath = os.path.join(self.folder, name)
            
            with open(filepath, "wb") as f:
                f.write(content_bytes)
            
            self.update_storage_info()
            
            # Annoncer le fichier si connecté
            if self.connected:
                checksum = self.calculate_checksum(filepath)
                message = f"FILE_REGISTER:{name}:{len(content_bytes)}B:{checksum}"
                self.server_socket.sendall(message.encode('utf-8'))
            
            print(f"✅ Fichier '{name}' créé avec succès ({len(content_bytes)} octets)")
        else:
            print("❌ Espace insuffisant!")
    
    def delete_file(self):
        """Supprime un fichier"""
        files = os.listdir(self.folder)
        
        if not files:
            print("📭 Le cloud est vide.")
            return
        
        print(f"\n{'='*50}")
        print("🗑️  SUPPRESSION DE FICHIER")
        print("="*50)
        
        print("\nFichiers disponibles:")
        for i, file in enumerate(files, 1):
            filepath = os.path.join(self.folder, file)
            size = os.path.getsize(filepath)
            print(f"  {i}. {file} ({size} octets)")
        
        try:
            choice = input("\nNuméro du fichier à supprimer (0 pour annuler): ")
            if choice == '0':
                return
            
            idx = int(choice) - 1
            if 0 <= idx < len(files):
                file_to_delete = files[idx]
                filepath = os.path.join(self.folder, file_to_delete)
                
                confirmation = input(f"Êtes-vous sûr de vouloir supprimer '{file_to_delete}'? (o/N): ")
                if confirmation.lower() == 'o':
                    os.remove(filepath)
                    self.update_storage_info()
                    print(f"✅ Fichier '{file_to_delete}' supprimé.")
                else:
                    print("❌ Suppression annulée.")
            else:
                print("❌ Choix invalide.")
        except ValueError:
            print("❌ Entrée invalide.")
    
    def search_file(self, filename=None):
        """Recherche un fichier sur le réseau P2P"""
        if not self.connected:
            print("❌ Non connecté au réseau P2P")
            return
        
        if not filename:
            filename = input("Nom du fichier à rechercher: ").strip()
        
        if filename:
            message = f"FILE_SEARCH:{filename}"
            self.server_socket.sendall(message.encode('utf-8'))
            print(f"🔍 Recherche de '{filename}' en cours...")
        else:
            print("❌ Nom de fichier invalide")
    
    def download_from_vm(self, filename, source_info):
        """Télécharge un fichier depuis une autre VM"""
        print(f"\n📥 Tentative de téléchargement de '{filename}' depuis {source_info['vm']}...")
        
        # Simulation de téléchargement
        # Dans une vraie implémentation, cela impliquerait une connexion directe P2P
        time.sleep(2)  # Simuler le temps de téléchargement
        
        # Créer un fichier simulé
        filepath = os.path.join(self.folder, f"downloaded_{filename}")
        content = f"Fichier téléchargé depuis {source_info['vm']} le {datetime.now()}\n"
        content += f"Taille originale: {source_info['size']}\n"
        content += f"Checksum: {source_info.get('checksum', 'N/A')}\n"
        
        with open(filepath, "w") as f:
            f.write(content)
        
        self.update_storage_info()
        print(f"✅ Fichier téléchargé et sauvegardé comme '{filepath}'")
    
    def display_status(self):
        """Affiche le statut de la VM"""
        storage_info = self.update_storage_info()
        
        print(f"\n{'='*60}")
        print(f"🤖 VM: {self.name}")
        print("="*60)
        print(f"📊 Stockage: {storage_info['used_mb']:.1f}MB / {storage_info['limit_mb']:.1f}MB "
              f"({storage_info['percentage']:.1f}%)")
        print(f"📁 Fichiers: {storage_info['file_count']}")
        print(f"🌐 Connecté au P2P: {'✅ Oui' if self.connected else '❌ Non'}")
        print("="*60)
    
    def main_menu(self):
        """Menu principal de la VM"""
        while True:
            self.display_status()
            
            print("\n📋 MENU PRINCIPAL:")
            print("  1. 📄 Créer un fichier")
            print("  2. 🗑️  Supprimer un fichier")
            print("  3. 🔍 Rechercher un fichier (P2P)")
            print("  4. 📊 Voir fichiers locaux")
            print("  5. 🔄 Rafraîchir la connexion")
            print("  6. ❌ Quitter")
            
            choice = input("\n👉 Votre choix: ").strip()
            
            if choice == "1":
                self.create_file()
            elif choice == "2":
                self.delete_file()
            elif choice == "3":
                self.search_file()
            elif choice == "4":
                self.list_local_files()
            elif choice == "5":
                self.reconnect()
            elif choice == "6":
                print("👋 Déconnexion...")
                if self.connected:
                    self.server_socket.close()
                break
            else:
                print("❌ Choix invalide")
            
            input("\nAppuyez sur Entrée pour continuer...")
    
    def list_local_files(self):
        """Liste les fichiers locaux"""
        files = os.listdir(self.folder)
        
        if not files:
            print("📭 Aucun fichier local")
            return
        
        print(f"\n{'='*50}")
        print("📁 FICHIERS LOCAUX")
        print("="*50)
        
        for i, file in enumerate(files, 1):
            filepath = os.path.join(self.folder, file)
            size = os.path.getsize(filepath)
            modified = datetime.fromtimestamp(os.path.getmtime(filepath))
            
            print(f"  {i}. {file}")
            print(f"     Taille: {size} octets")
            print(f"     Modifié: {modified.strftime('%d/%m/%Y %H:%M')}")
            print()
    
    def reconnect(self):
        """Tente de se reconnecter au serveur"""
        if self.connected:
            print("✅ Déjà connecté")
            return
        
        print("🔗 Tentative de reconnexion...")
        if self.connect_to_server():
            print("✅ Reconnecté avec succès")
        else:
            print("❌ Échec de la reconnexion")

def main():
    """Fonction principale"""
    print("="*60)
    print("🚀 NICK CLOUD SYSTEM - CLIENT VM")
    print("="*60)
    
    # Demander le nom de la VM
    vm_name = input("Nom de votre VM: ").strip()
    if not vm_name:
        vm_name = "vm_default"
    
    # Demander la capacité de stockage
    try:
        storage_mb = int(input("Capacité de stockage (MB) [500]: ") or "500")
    except ValueError:
        storage_mb = 500
    
    # Créer l'instance de la VM
    vm = VirtualMachine(vm_name, storage_mb)
    
    # Tenter de se connecter au serveur
    print(f"\n🔗 Connexion au serveur Cloud P2P...")
    if vm.connect_to_server():
        print("✅ Connecté au réseau P2P")
    else:
        print("⚠️  Mode hors ligne - Fonctionnalités P2P limitées")
    
    # Lancer le menu principal
    vm.main_menu()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du client VM")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")