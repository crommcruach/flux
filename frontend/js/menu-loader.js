// Menu-Bar Loader - Lädt die Menu-Bar dynamisch in alle Seiten
(function() {
    // Erstelle einen Platzhalter für die Menu-Bar
    const menuBarPlaceholder = document.createElement('div');
    menuBarPlaceholder.id = 'menu-bar-placeholder';
    
    // Füge den Platzhalter am Anfang des Body ein
    if (document.body.firstChild) {
        document.body.insertBefore(menuBarPlaceholder, document.body.firstChild);
    } else {
        document.body.appendChild(menuBarPlaceholder);
    }
    
    // Lade die Menu-Bar
    fetch('/static/menu-bar.html')
        .then(response => response.text())
        .then(html => {
            menuBarPlaceholder.innerHTML = html;
            
            // Führe das Theme-Toggle-Script aus, nachdem die Menu-Bar eingefügt wurde
            initThemeToggle();
            
            // Falls die Seite bereits ein Theme-Toggle hatte, entferne Duplikate
            const existingToggles = document.querySelectorAll('#themeToggle');
            if (existingToggles.length > 1) {
                // Behalte nur das erste (aus der Menu-Bar)
                for (let i = 1; i < existingToggles.length; i++) {
                    const parent = existingToggles[i].closest('.form-check');
                    if (parent) parent.remove();
                }
            }
        })
        .catch(error => {
            console.error('Fehler beim Laden der Menu-Bar:', error);
        });
    
    // Theme Toggle Funktionalität
    function initThemeToggle() {
        const themeToggle = document.getElementById('themeToggle');
        const themeLabel = document.getElementById('themeLabel');
        const body = document.body;
        
        function setTheme(theme) {
            body.setAttribute('data-theme', theme);
            localStorage.setItem('theme', theme);
            if (themeLabel) themeLabel.textContent = theme === 'dark' ? 'Dunkel' : 'Hell';
            if (themeToggle) themeToggle.checked = theme === 'dark';
        }
        
        let savedTheme = localStorage.getItem('theme');
        if (!savedTheme) {
            savedTheme = 'dark';
            localStorage.setItem('theme', 'dark');
        }
        setTheme(savedTheme);
        
        if (themeToggle) {
            themeToggle.checked = savedTheme === 'dark';
            themeToggle.addEventListener('change', () => {
                setTheme(themeToggle.checked ? 'dark' : 'light');
            });
        }
    }
    
    // Global Active Mode Display Update Function
    window.updateActiveModeDisplay = function(mode) {
        const displayDiv = document.getElementById('menuActiveModeDisplay');
        const textSpan = document.getElementById('menuActiveModeText');
        
        if (!displayDiv || !textSpan) return;
        
        textSpan.textContent = mode;
        
        // Farben basierend auf Modus
        if (mode === 'Test') {
            displayDiv.style.borderColor = '#ffc107'; // Gelb
            displayDiv.style.background = 'rgba(255, 193, 7, 0.15)';
        } else if (mode === 'Replay') {
            displayDiv.style.borderColor = '#17a2b8'; // Cyan
            displayDiv.style.background = 'rgba(23, 162, 184, 0.15)';
        } else { // Video
            displayDiv.style.borderColor = '#28a745'; // Grün
            displayDiv.style.background = 'rgba(40, 167, 69, 0.15)';
        }
    };
    
    // Global Auto-Save Status Update Function
    window.updateGlobalAutoSaveStatus = function(status) {
        const statusDiv = document.getElementById('globalAutoSaveStatus');
        const badge = document.getElementById('autoSaveStatusBadge');
        
        if (!statusDiv || !badge) return;
        
        statusDiv.style.display = 'block';
        
        if (status === 'saving') {
            badge.className = 'badge bg-warning';
            badge.textContent = '⏳ Speichert...';
        } else if (status === 'saved') {
            badge.className = 'badge bg-success';
            badge.textContent = '✓ Gespeichert';
            // Auto-hide after 2 seconds
            setTimeout(() => {
                if (statusDiv) statusDiv.style.display = 'none';
            }, 2000);
        } else if (status === 'error') {
            badge.className = 'badge bg-danger';
            badge.textContent = '✗ Fehler';
        }
    };
})();
