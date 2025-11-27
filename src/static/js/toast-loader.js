/**
 * Toast Component Loader
 * Automatically loads and injects the toast component HTML
 * Usage: <script src="js/toast-loader.js"></script>
 */

(function() {
    // Check if toast container already exists
    if (document.getElementById('toastContainer')) {
        console.log('Toast container already exists, skipping injection');
        return;
    }

    // Fetch and inject toast component
    fetch('/static/components/toast.html')
        .then(response => response.text())
        .then(html => {
            // Create a container div
            const container = document.createElement('div');
            container.innerHTML = html;
            
            // Append to body
            document.body.appendChild(container);
            console.log('✅ Toast component loaded');
        })
        .catch(error => {
            console.error('❌ Failed to load toast component:', error);
            
            // Fallback: Create basic toast container
            const fallback = document.createElement('div');
            fallback.id = 'toastContainer';
            fallback.className = 'toast-container';
            fallback.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;';
            document.body.appendChild(fallback);
            console.log('⚠️ Using fallback toast container');
        });
})();
