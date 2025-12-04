/**
 * Search Filter Component Loader
 * Asynchronously loads the universal search filter component
 */

(async function() {
    try {
        const response = await fetch('/static/components/search-filter.html');
        if (!response.ok) {
            throw new Error(`Failed to load search filter: ${response.status}`);
        }
        
        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        
        // Inject template
        const template = doc.getElementById('search-filter-template');
        if (template) {
            document.body.appendChild(template);
        }
        
        // Inject styles
        const style = doc.querySelector('style');
        if (style) {
            document.head.appendChild(style);
        }
        
        // Inject script
        const script = doc.querySelector('script');
        if (script) {
            const newScript = document.createElement('script');
            newScript.textContent = script.textContent;
            document.body.appendChild(newScript);
        }
        
        console.log('✅ Search filter component loaded');
    } catch (error) {
        console.error('❌ Failed to load search filter component:', error);
    }
})();
