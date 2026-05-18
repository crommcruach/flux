// Menu-Bar Loader - Dynamically loads the menu bar into all pages
(function() {
    // Create a placeholder for the menu bar
    const menuBarPlaceholder = document.createElement('div');
    menuBarPlaceholder.id = 'menu-bar-placeholder';
    
    // Insert the placeholder at the beginning of the body
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
            
            // Execute the theme toggle script after the menu bar has been inserted
            initThemeToggle();
            
            // If the page already had a theme toggle, remove duplicates
            const existingToggles = document.querySelectorAll('#themeToggle');
            if (existingToggles.length > 1) {
                // Keep only the first one (from the menu bar)
                for (let i = 1; i < existingToggles.length; i++) {
                    const parent = existingToggles[i].closest('.form-check');
                    if (parent) parent.remove();
                }
            }
        })
        .catch(error => {
            console.error('Error loading menu bar:', error);
        });
    
    // Theme toggle functionality
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
