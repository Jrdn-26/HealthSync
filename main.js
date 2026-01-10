// Configuration globale
let currentVM = {
    name: null,
    storage: '500MB',
    used: '0MB',
    files: [],
    email: null
};

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Nick Cloud System initialisé');
    showView('home');
    setupEventListeners();
});

// Fonctions de navigation
function showView(viewId) {
    console.log(`Navigation vers: ${viewId}`);
    
    document.querySelectorAll('.view-section').forEach(section => {
        section.classList.add('hidden');
    });
    
    const targetView = document.getElementById(`view-${viewId}`);
    if (targetView) {
        targetView.classList.remove('hidden');
    }
    
    updateNavigation(viewId);
    
    if (viewId === 'dashboard' && currentVM.name) {
        loadVMData();
    }
}

function updateNavigation(viewId) {
    const isDashboard = viewId === 'dashboard';
    const navPrivate = document.getElementById('nav-private');
    const navPublic = document.getElementById('nav-public');
    
    if (navPrivate) navPrivate.classList.toggle('hidden', !isDashboard);
    if (navPublic) navPublic.classList.toggle('hidden', isDashboard);
}

// Gestionnaire d'inscription
async function handleRegister() {
    const vmName = document.getElementById('reg-vm-name').value.trim();
    const vmEmail = document.getElementById('reg-vm-email').value.trim();
    const vmPassword = document.getElementById('reg-vm-password').value;
    const vmStorage = document.getElementById('reg-vm-storage').value;
    const regMessage = document.getElementById('reg-message');
    
    showMessage(regMessage, '', 'clear');
    
    if (!vmName || !vmEmail || !vmPassword) {
        showMessage(regMessage, 'Veuillez remplir tous les champs', 'error');
        return;
    }
    
    if (vmPassword.length < 8) {
        showMessage(regMessage, 'Le mot de passe doit avoir au moins 8 caractères', 'error');
        return;
    }
    
    showMessage(regMessage, 'Génération du code de confirmation...', 'loading');
    
    try {
        const response = await fetch('/send_code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                vmName: vmName,
                vmEmail: vmEmail,
                vmPassword: vmPassword,
                vmStorage: vmStorage + 'MB'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Stocker temporairement
            sessionStorage.setItem('pendingRegistration', JSON.stringify({
                vmName: vmName,
                vmEmail: vmEmail,
                vmPassword: vmPassword,
                vmStorage: vmStorage + 'MB'
            }));
            
            // Afficher confirmation
            document.getElementById('confirm-email-display').textContent = vmEmail;
            if (data.test_code) {
                document.getElementById('confirm-code-input').value = data.test_code;
            }
            showView('confirm');
            
        } else {
            showMessage(regMessage, data.message, 'error');
        }
        
    } catch (error) {
        showMessage(regMessage, 'Erreur de connexion au serveur', 'error');
    }
}

// Gestionnaire de confirmation
async function handleConfirm() {
    const enteredCode = document.getElementById('confirm-code-input').value.trim();
    const confirmMessage = document.getElementById('confirm-message');
    
    showMessage(confirmMessage, '', 'clear');
    
    if (!enteredCode) {
        showMessage(confirmMessage, 'Veuillez entrer le code', 'error');
        return;
    }
    
    // Récupérer les données temporaires
    const pendingData = JSON.parse(sessionStorage.getItem('pendingRegistration') || '{}');
    
    if (!pendingData.vmName) {
        showMessage(confirmMessage, 'Données d\'inscription perdues', 'error');
        return;
    }
    
    showMessage(confirmMessage, 'Création de votre VM...', 'loading');
    
    try {
        const response = await fetch('/register_vm', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                ...pendingData,
                enteredCode: enteredCode
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showMessage(confirmMessage, '✅ VM créée avec succès !', 'success');
            
            // Nettoyer
            sessionStorage.removeItem('pendingRegistration');
            
            // Redirection
            setTimeout(() => {
                document.getElementById('login-vm-name').value = data.vm_name || pendingData.vmName;
                showView('login');
            }, 1500);
            
        } else {
            showMessage(confirmMessage, data.message, 'error');
        }
        
    } catch (error) {
        showMessage(confirmMessage, 'Erreur de connexion au serveur', 'error');
    }
}

// Gestionnaire de connexion
async function handleLogin() {
    const vmName = document.getElementById('login-vm-name').value.trim();
    const password = document.getElementById('login-vm-password').value;
    const loginMessage = document.getElementById('login-message');
    
    showMessage(loginMessage, '', 'clear');
    
    if (!vmName || !password) {
        showMessage(loginMessage, 'Veuillez remplir tous les champs', 'error');
        return;
    }
    
    showMessage(loginMessage, 'Connexion en cours...', 'loading');
    
    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                vmName: vmName,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentVM.name = data.vm_name;
            currentVM.storage = data.storage;
            currentVM.email = data.email;
            
            // Mettre à jour l'affichage
            document.getElementById('current-vm-display').textContent = `VM: ${data.vm_name}`;
            document.getElementById('dashboard-vm-name').textContent = data.vm_name;
            
            // Afficher le dashboard
            showView('dashboard');
            
            // Charger les données immédiatement
            await loadVMData();
            
        } else {
            showMessage(loginMessage, data.message, 'error');
        }
        
    } catch (error) {
        showMessage(loginMessage, 'Erreur de connexion au serveur', 'error');
    }
}

// Charger les données de la VM
async function loadVMData() {
    if (!currentVM.name) return;
    
    try {
        // Charger le stockage
        const storageResponse = await fetch(`/api/vm/${currentVM.name}/storage`);
        const storageData = await storageResponse.json();
        
        if (storageData.success) {
            currentVM.used = `${Math.round(storageData.storage.used_mb)}MB`;
            updateStorageDisplay(storageData.storage);
        }
        
        // Charger les fichiers
        await loadVMFiles();
        
    } catch (error) {
        console.error('Erreur chargement données:', error);
        showNotification('Erreur lors du chargement des données', 'error');
    }
}

// Charger les fichiers de la VM
async function loadVMFiles() {
    if (!currentVM.name) return;
    
    try {
        const response = await fetch(`/api/vm/${currentVM.name}/files`);
        const data = await response.json();
        
        if (data.success) {
            // CORRECTION: Filtrer uniquement les fichiers valides
            currentVM.files = data.files.filter(file => 
                file && file.name && file.size_display && file.name.trim() !== ''
            );
            updateFileList();
        } else {
            // Réinitialiser si erreur
            currentVM.files = [];
            updateFileList();
        }
    } catch (error) {
        console.error('Erreur chargement fichiers:', error);
        currentVM.files = [];
        updateFileList();
    }
}

// Mettre à jour l'affichage du stockage
function updateStorageDisplay(storageInfo) {
    const storageInfoEl = document.getElementById('dashboard-storage-info');
    const progressBar = document.getElementById('storage-progress-bar');
    const percentageEl = document.getElementById('storage-percentage');
    const totalDisplay = document.getElementById('storage-total-display');
    
    if (!storageInfo) {
        if (storageInfoEl) storageInfoEl.innerHTML = '<i class="fas fa-hdd mr-1"></i> Non connecté';
        if (progressBar) progressBar.style.width = '0%';
        if (percentageEl) percentageEl.textContent = '0%';
        if (totalDisplay) totalDisplay.textContent = '0 MB';
        return;
    }
    
    const usedMB = storageInfo.used_mb;
    const limitMB = storageInfo.limit_mb;
    const percentage = Math.min(100, Math.round((usedMB / limitMB) * 100));
    
    if (storageInfoEl) {
        storageInfoEl.innerHTML = `<i class="fas fa-hdd mr-1"></i> Utilisé: ${usedMB.toFixed(1)}MB / Total: ${limitMB.toFixed(0)}MB`;
    }
    
    if (progressBar) {
        progressBar.style.width = `${percentage}%`;
        // Changer la couleur en fonction de l'utilisation
        if (percentage > 90) {
            progressBar.className = 'bg-red-500 h-2.5 rounded-full';
        } else if (percentage > 70) {
            progressBar.className = 'bg-yellow-500 h-2.5 rounded-full';
        } else {
            progressBar.className = 'bg-nick-primary h-2.5 rounded-full';
        }
    }
    
    if (percentageEl) {
        percentageEl.textContent = `${percentage}%`;
        if (percentage > 90) {
            percentageEl.className = 'text-sm font-semibold text-red-600';
        } else if (percentage > 70) {
            percentageEl.className = 'text-sm font-semibold text-yellow-600';
        } else {
            percentageEl.className = 'text-sm font-semibold text-nick-dark';
        }
    }
    
    if (totalDisplay) {
        totalDisplay.textContent = `${limitMB.toFixed(0)} MB`;
    }
}

// Mettre à jour la liste des fichiers
function updateFileList() {
    const fileListEl = document.getElementById('dashboard-file-list');
    const fileCountEl = document.getElementById('file-count');
    
    if (!fileListEl) return;
    
    // CORRECTION: Vérification stricte
    if (!currentVM.files || currentVM.files.length === 0) {
        fileListEl.innerHTML = `
            <div class="text-center py-10">
                <i class="fas fa-cloud text-4xl text-gray-300 mb-3"></i>
                <p class="text-gray-500">Aucun fichier dans votre cloud</p>
                <p class="text-sm text-gray-400 mt-1">Commencez par uploader un fichier</p>
            </div>
        `;
        
        if (fileCountEl) {
            fileCountEl.textContent = '0 fichiers';
        }
        return;
    }
    
    // Afficher la liste des fichiers
    let html = '<div class="space-y-3">';
    
    currentVM.files.forEach((file) => {
        const fileIcon = getFileIcon(file.name);
        const safeName = file.name.replace(/'/g, "\\'").replace(/"/g, '\\"');
        
        html += `
            <div class="flex items-center justify-between p-3 bg-white rounded-lg border border-gray-200 hover:bg-gray-50 transition">
                <div class="flex items-center space-x-3">
                    <i class="fas ${fileIcon} text-xl text-blue-500"></i>
                    <div>
                        <div class="font-medium text-gray-800">${file.name}</div>
                        <div class="text-sm text-gray-500">
                            ${file.size_display} • ${file.modified_display || 'Date inconnue'}
                        </div>
                    </div>
                </div>
                <div class="flex space-x-2">
                    <button onclick="downloadVMFile('${safeName}')" class="p-2 text-green-600 hover:bg-green-50 rounded" title="Télécharger">
                        <i class="fas fa-download"></i>
                    </button>
                    <button onclick="deleteVMFile('${safeName}')" class="p-2 text-red-600 hover:bg-red-50 rounded" title="Supprimer">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    fileListEl.innerHTML = html;
    
    // Mettre à jour le compteur
    if (fileCountEl) {
        fileCountEl.textContent = `${currentVM.files.length} fichier${currentVM.files.length > 1 ? 's' : ''}`;
    }
}

function getFileIcon(filename) {
    const ext = filename.split('.').pop().toLowerCase();
    const icons = {
        'pdf': 'fa-file-pdf',
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'png': 'fa-file-image',
        'gif': 'fa-file-image',
        'mp4': 'fa-file-video',
        'avi': 'fa-file-video',
        'mov': 'fa-file-video',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
        'zip': 'fa-file-archive',
        'rar': 'fa-file-archive',
        'txt': 'fa-file-alt',
        'mp3': 'fa-file-audio'
    };
    return icons[ext] || 'fa-file';
}

// Télécharger un fichier
async function downloadVMFile(filename) {
    if (!currentVM.name) return;
    
    try {
        const response = await fetch(`/api/vm/${currentVM.name}/download/${encodeURIComponent(filename)}`);
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification(`Téléchargement de "${filename}" démarré`, 'success');
        } else {
            const error = await response.json();
            showNotification(`Erreur: ${error.message}`, 'error');
        }
    } catch (error) {
        showNotification('Erreur de téléchargement', 'error');
    }
}

// Supprimer un fichier
async function deleteVMFile(filename) {
    if (!currentVM.name) return;
    
    if (!confirm(`Êtes-vous sûr de vouloir supprimer "${filename}" ?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/vm/${currentVM.name}/delete/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`"${filename}" supprimé avec succès`, 'success');
            await loadVMData();
        } else {
            showNotification(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showNotification('Erreur de suppression', 'error');
    }
}

// Uploader un fichier - CORRECTION DÉFINITIVE
async function handleUpload() {
    const fileInput = document.getElementById('upload-file-input');
    const uploadMessage = document.getElementById('upload-message');
    const selectedOption = document.querySelector('input[name="upload-option"]:checked');
    
    if (!fileInput.files.length) {
        showMessage(uploadMessage, '❌ Veuillez sélectionner un fichier', 'error');
        return;
    }
    
    const file = fileInput.files[0];
    const option = selectedOption ? selectedOption.value : 'store_only';
    
    // Vérifier la taille du fichier
    if (file.size > 100 * 1024 * 1024) {
        showMessage(uploadMessage, '❌ Fichier trop volumineux (max 100MB)', 'error');
        return;
    }
    
    showMessage(uploadMessage, `Vérification de l'espace disponible...`, 'loading');
    
    try {
        // Vérification STRICTE avant upload
        const storageResponse = await fetch(`/api/vm/${currentVM.name}/storage`);
        const storageData = await storageResponse.json();
        
        if (storageData.success) {
            const availableMB = storageData.storage.available_mb;
            const fileMB = file.size / (1024 * 1024);
            const limitMB = storageData.storage.limit_mb;
            const usedMB = storageData.storage.used_mb;
            
            console.log(`📊 Vérification: Fichier=${fileMB.toFixed(2)}MB, Disponible=${availableMB.toFixed(2)}MB, Limite=${limitMB.toFixed(2)}MB`);
            
            // VÉRIFICATION 1: Fichier dépasse l'espace disponible
            if (fileMB > availableMB) {
                showMessage(uploadMessage, 
                    `❌ ESPACE INSUFFISANT! 
                    Disponible: ${availableMB.toFixed(2)}MB
                    Fichier: ${fileMB.toFixed(2)}MB
                    Déficit: ${(fileMB - availableMB).toFixed(2)}MB`, 
                    'error');
                return;
            }
            
            // VÉRIFICATION 2: Nouveau total dépasse la limite
            const newTotal = usedMB + fileMB;
            if (newTotal > limitMB) {
                showMessage(uploadMessage,
                    `❌ DÉPASSEMENT DE QUOTA! 
                    Limite: ${limitMB.toFixed(2)}MB
                    Nouveau total: ${newTotal.toFixed(2)}MB`,
                    'error');
                return;
            }
            
        } else {
            showMessage(uploadMessage, '❌ Impossible de vérifier l\'espace disponible', 'error');
            return;
        }
        
        // Upload le fichier
        showMessage(uploadMessage, `Upload en cours (${(file.size/(1024*1024)).toFixed(2)}MB)...`, 'loading');
        
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`/api/vm/${currentVM.name}/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            const optionName = getOptionName(option);
            showMessage(uploadMessage, `✅ Fichier "${file.name}" uploadé (${optionName})`, 'success');
            
            // Réinitialiser
            fileInput.value = '';
            document.getElementById('selected-file-name').textContent = 'Aucun fichier sélectionné';
            document.getElementById('selected-file-name').className = 'text-sm text-gray-500 italic';
            
            // Recharger les données
            setTimeout(async () => {
                await loadVMData();
                showNotification(`✅ Fichier "${file.name}" uploadé avec succès`, 'success');
            }, 1000);
            
        } else {
            showMessage(uploadMessage, data.message || 'Erreur lors de l\'upload', 'error');
        }
        
    } catch (error) {
        console.error('Erreur upload:', error);
        showMessage(uploadMessage, '❌ Erreur de connexion au serveur', 'error');
    }
}

// Recherche de fichier P2P
async function handleRequest() {
    const filename = document.getElementById('request-filename').value.trim();
    const requestMessage = document.getElementById('request-message');
    
    if (!filename) {
        showMessage(requestMessage, '❌ Veuillez spécifier un nom de fichier', 'error');
        return;
    }
    
    showMessage(requestMessage, `🔍 Recherche de "${filename}" sur le réseau P2P...`, 'loading');
    
    // Simulation pour l'instant
    setTimeout(() => {
        showMessage(requestMessage, `ℹ️ Aucun fichier "${filename}" trouvé sur le réseau P2P`, 'info');
    }, 2000);
}

// Actualiser les fichiers
async function refreshFiles() {
    if (!currentVM.name) {
        showNotification('Vous devez être connecté pour actualiser', 'error');
        return;
    }
    
    const fileListEl = document.getElementById('dashboard-file-list');
    
    if (fileListEl) {
        fileListEl.innerHTML = `
            <div class="text-center py-10">
                <i class="fas fa-sync-alt fa-spin text-4xl text-nick-primary mb-3"></i>
                <p class="text-gray-500">Actualisation en cours...</p>
            </div>
        `;
    }
    
    try {
        await loadVMFiles();
        showNotification('Liste des fichiers actualisée', 'success');
        
    } catch (error) {
        console.error('Erreur actualisation:', error);
        showNotification('Erreur lors de l\'actualisation', 'error');
    }
}

// Nettoyer les fichiers fantômes
async function cleanupGhostFiles() {
    if (!currentVM.name) return;
    
    if (!confirm('Voulez-vous nettoyer les fichiers fantômes de cette VM?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/vm/${currentVM.name}/cleanup`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`✅ ${data.deleted_count} fichiers fantômes nettoyés`, 'success');
            await loadVMFiles();
        } else {
            showNotification(`Erreur: ${data.message}`, 'error');
        }
    } catch (error) {
        showNotification('Erreur de nettoyage', 'error');
    }
}

// Fonctions utilitaires
function getOptionName(option) {
    const options = {
        'store_only': 'Stocker uniquement',
        'share_only': 'Partager uniquement',
        'store_and_share': 'Stocker & Partager'
    };
    return options[option] || option;
}

function showMessage(element, message, type = 'info') {
    if (!element) return;
    
    element.innerHTML = '';
    element.className = '';
    
    const colors = {
        'success': 'text-green-700 bg-green-50 border border-green-200',
        'error': 'text-red-700 bg-red-50 border border-red-200',
        'loading': 'text-blue-700 bg-blue-50 border border-blue-200',
        'info': 'text-gray-700 bg-gray-50 border border-gray-200',
        'clear': ''
    };
    
    const icons = {
        'success': 'fa-check-circle',
        'error': 'fa-exclamation-circle',
        'loading': 'fa-spinner fa-spin',
        'info': 'fa-info-circle'
    };
    
    if (type === 'clear') return;
    
    element.className = `p-3 rounded-lg ${colors[type]}`;
    
    if (type === 'loading') {
        element.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${icons[type]} mr-2"></i>
                <span>${message}</span>
            </div>
        `;
    } else {
        element.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${icons[type] || 'fa-info-circle'} mr-2"></i>
                <span>${message}</span>
            </div>
        `;
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = 'notification-item fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg transform transition-transform duration-300 translate-x-full';
    
    const bgColor = type === 'success' ? 'bg-green-100 border-l-4 border-green-500 text-green-700' :
                    type === 'error' ? 'bg-red-100 border-l-4 border-red-500 text-red-700' :
                    'bg-blue-100 border-l-4 border-blue-500 text-blue-700';
    
    const icon = type === 'success' ? 'fa-check-circle' :
                 type === 'error' ? 'fa-exclamation-circle' :
                 'fa-info-circle';
    
    notification.innerHTML = `
        <div class="flex items-center ${bgColor} p-4 rounded">
            <i class="fas ${icon} text-xl mr-3"></i>
            <div class="flex-1 max-w-xs">${message}</div>
            <button onclick="this.parentElement.parentElement.remove()" class="ml-4 text-gray-500 hover:text-gray-700">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
        notification.classList.add('translate-x-0');
    }, 10);
    
    setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('translate-x-full');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, 5000);
}

// Configuration des événements
function setupEventListeners() {
    console.log('⚙️ Configuration des événements...');
    
    // Navigation
    document.querySelectorAll('button[onclick^="showView"]').forEach(button => {
        const originalOnClick = button.getAttribute('onclick');
        button.removeAttribute('onclick');
        button.addEventListener('click', function() {
            const viewId = originalOnClick.match(/showView\('(.+)'\)/)[1];
            showView(viewId);
        });
    });
    
    // Boutons principaux
    document.getElementById('register-btn')?.addEventListener('click', handleRegister);
    document.getElementById('confirm-code-btn')?.addEventListener('click', handleConfirm);
    document.getElementById('login-btn')?.addEventListener('click', handleLogin);
    document.getElementById('logout-btn')?.addEventListener('click', function() {
        currentVM = { name: null, storage: '500MB', used: '0MB', files: [], email: null };
        showView('home');
        showNotification('Déconnexion réussie', 'info');
    });
    
    // Boutons dashboard
    document.getElementById('upload-btn')?.addEventListener('click', handleUpload);
    document.getElementById('request-btn')?.addEventListener('click', handleRequest);
    
    // Bouton d'actualisation
    const refreshBtn = document.getElementById('refresh-files-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshFiles);
    }
    
    // Gestion du fichier sélectionné
    const fileInput = document.getElementById('upload-file-input');
    const fileNameDisplay = document.getElementById('selected-file-name');
    
    if (fileInput && fileNameDisplay) {
        fileInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                const file = this.files[0];
                const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
                fileNameDisplay.textContent = `Fichier: ${file.name} (${sizeMB} MB)`;
                fileNameDisplay.className = 'text-sm text-green-600 font-medium';
            } else {
                fileNameDisplay.textContent = 'Aucun fichier sélectionné';
                fileNameDisplay.className = 'text-sm text-gray-500 italic';
            }
        });
        
        // Drag and drop support
        const dropZone = document.querySelector('.border-dashed');
        if (dropZone) {
            dropZone.addEventListener('dragover', function(e) {
                e.preventDefault();
                this.classList.add('border-nick-primary', 'bg-nick-light');
            });
            
            dropZone.addEventListener('dragleave', function(e) {
                e.preventDefault();
                this.classList.remove('border-nick-primary', 'bg-nick-light');
            });
            
            dropZone.addEventListener('drop', function(e) {
                e.preventDefault();
                this.classList.remove('border-nick-primary', 'bg-nick-light');
                
                if (e.dataTransfer.files.length) {
                    fileInput.files = e.dataTransfer.files;
                    fileInput.dispatchEvent(new Event('change'));
                }
            });
        }
    }
    
    // Support de la touche Entrée
    document.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            const activeView = document.querySelector('.view-section:not(.hidden)');
            if (activeView) {
                const viewId = activeView.id.replace('view-', '');
                
                switch(viewId) {
                    case 'register':
                        handleRegister();
                        break;
                    case 'confirm':
                        handleConfirm();
                        break;
                    case 'login':
                        handleLogin();
                        break;
                }
            }
        }
    });
    
    // Rafraîchir automatiquement toutes les 30 secondes
    setInterval(() => {
        if (currentVM.name && document.getElementById('view-dashboard') && 
            !document.getElementById('view-dashboard').classList.contains('hidden')) {
            loadVMFiles().catch(console.error);
        }
    }, 30000);
    
    console.log('✅ Événements configurés');
}

// Export des fonctions pour l'HTML
window.showView = showView;
window.refreshFiles = refreshFiles;
window.downloadVMFile = downloadVMFile;
window.deleteVMFile = deleteVMFile;
window.cleanupGhostFiles = cleanupGhostFiles;