/**
 * Modal Component Loader
 * Loads the universal modal component HTML and injects it into the page
 */

(async function() {
    try {
        // Fetch the component HTML
        const response = await fetch('/static/components/modal.html');
        const html = await response.text();
        
        // Create a temporary container
        const temp = document.createElement('div');
        temp.innerHTML = html;
        
        // Extract template and script
        const template = temp.querySelector('template');
        const script = temp.querySelector('script');
        
        // Inject template into document
        if (template) {
            document.body.insertBefore(template, document.body.firstChild);
        }
        
        // Execute the script
        if (script) {
            const scriptElement = document.createElement('script');
            scriptElement.textContent = script.textContent;
            document.head.appendChild(scriptElement);
        }
        
        console.log('✅ Modal component loaded');
    } catch (error) {
        console.error('❌ Failed to load modal component:', error);
    }
})();
