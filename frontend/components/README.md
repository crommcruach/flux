# Reusable UI Components

This directory contains reusable UI components that can be used across multiple pages.

## Toast Notifications

### Usage

**Automatic loading (recommended):**
```html
<!-- In the HTML head or before the closing </body> tag -->
<script src="js/toast-loader.js"></script>
```

**Manual include:**
```html
<!-- Alternative: Direct include (if supported) -->
<div id="toast-container-wrapper"></div>
<script>
    fetch('/static/components/toast.html')
        .then(r => r.text())
        .then(html => {
            document.getElementById('toast-container-wrapper').innerHTML = html;
        });
</script>
```

### JavaScript API

The toast functionality is provided via `common.js`:

```javascript
import { showToast } from './common.js';

// Success (green)
showToast('Operation successful!', 'success', 3000);

// Error (red)
showToast('An error occurred', 'error', 5000);

// Info (blue)
showToast('Informative message', 'info', 3000);

// Warning (yellow)
showToast('Caution!', 'warning', 4000);
```

### Customizing styles

All toast styles are located in `components/toast.html`. Changes there are automatically applied to all pages.

**CSS variables for theme customization:**
- `--bg-secondary`: Background color
- `--border-color`: Border color
- `--text-primary`: Text color
- `--text-secondary`: Secondary text color

### Benefits of the centralized component

✅ **Single Source of Truth**: All changes in one place  
✅ **Consistent design**: Same toast appearance across all pages  
✅ **Maintainability**: No code duplication  
✅ **Easy updates**: Only one file to change instead of 5+  

## Additional Components

More reusable components can be added here following the same pattern:

- Modals
- Loading Spinner
- Alert Boxes
- Navigation Bars
