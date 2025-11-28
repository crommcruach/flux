# Universal Modal Component

## Overview
A reusable modal component system that replaces duplicate Bootstrap modal definitions across all HTML files with a dynamic, JavaScript-controlled solution.

## Files
- **Component**: `src/static/components/modal.html` - Template and ModalManager
- **Loader**: `src/static/js/modal-loader.js` - Automatic component injection
- **Usage**: All HTML files load via `<script src="js/modal-loader.js"></script>`

## Architecture

### Component Structure
```html
<template id="modal-template">
  <!-- Bootstrap 5 modal structure -->
</template>

<script>
  window.ModalManager = {
    create(options),
    get(id),
    confirm(options),
    alert(options)
  }
</script>
```

### ModalManager API

#### `ModalManager.create(options)`
Creates a new modal instance.

**Options:**
```javascript
{
  id: 'uniqueModalId',              // Required: Unique identifier
  title: '📂 Modal Title',           // Modal header title (supports emoji)
  content: '<p>Content</p>',        // HTML string or HTMLElement
  size: 'lg' | 'xl' | 'sm' | null,  // Bootstrap modal size
  centered: true,                    // Vertically center modal
  closeButton: true,                 // Show close button in header
  buttons: [                         // Footer buttons
    {
      label: 'OK',
      class: 'btn btn-primary',
      callback: (modal) => {},       // Called on click
      dismiss: true                  // Auto-dismiss on click (default: true)
    }
  ],
  onShow: () => {},                  // Called when modal shows
  onHide: () => {}                   // Called when modal hides
}
```

**Returns:** Modal controller object
```javascript
{
  id,
  element,        // DOM element
  bsModal,        // Bootstrap Modal instance
  show(),         // Show modal
  hide(),         // Hide modal
  toggle(),       // Toggle visibility
  setTitle(text), // Update title
  setContent(html), // Update content
  showLoading(msg), // Show loading spinner
  destroy()       // Remove modal from DOM
}
```

#### `ModalManager.get(id)`
Retrieves existing modal by ID.

#### `ModalManager.confirm(options)`
Quick confirmation dialog.

```javascript
ModalManager.confirm({
  title: '⚠️ Confirm Action',
  message: 'Are you sure?',
  confirmLabel: 'Yes',
  cancelLabel: 'No',
  onConfirm: () => console.log('Confirmed'),
  onCancel: () => console.log('Cancelled')
});
```

#### `ModalManager.alert(options)`
Quick alert dialog.

```javascript
ModalManager.alert({
  title: 'ℹ️ Information',
  message: 'Operation completed!',
  buttonLabel: 'OK'
});
```

## Migration Examples

### Before (controls.html)
```html
<!-- Duplicate modal definition -->
<div class="modal fade" id="playlistModal" ...>
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">📂 Load Playlists</h5>
        <button class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body" id="playlistModalBody">
        <!-- Content -->
      </div>
    </div>
  </div>
</div>

<script>
  const modal = new bootstrap.Modal(document.getElementById('playlistModal'));
  modal.show();
  document.getElementById('playlistModalBody').innerHTML = content;
</script>
```

### After (controls.js)
```javascript
// Initialize once
let playlistModal = ModalManager.create({
  id: 'playlistModal',
  title: '📂 Load Playlists',
  content: '<div class="spinner-border"></div>',
  centered: true
});

// Use anywhere
playlistModal.show();
playlistModal.setContent('<p>New content</p>');
playlistModal.hide();
```

## Replaced Modals

### controls.html
- **playlistModal** - Load saved playlists
- **snapshotModal** - Restore session snapshots

### editor.html
- **projectManagerModal** - Project management (load/delete/download)

### index.html
- **projectManagerModal** - Same as editor.html (shares editor.js)

## Benefits

1. **DRY Principle**: Single modal template, reused everywhere
2. **Consistency**: Uniform styling and behavior
3. **Maintainability**: Update once, affects all modals
4. **Dynamic Creation**: Create modals on-demand
5. **Type Safety**: Structured API vs. manual DOM manipulation
6. **Smaller HTML**: Removed ~150 lines of duplicate code

## Implementation Checklist

- [x] Create modal component template
- [x] Create modal loader script
- [x] Update controls.html (remove 2 modals)
- [x] Update editor.html (remove 1 modal)
- [x] Update index.html (remove 1 modal)
- [x] Update controls.js (playlist + snapshot modals)
- [x] Update editor.js (project manager modal)
- [x] Add modal-loader.js to all HTML files
- [x] Test modal initialization timing
- [x] Verify backward compatibility

## Testing

### Manual Tests
1. **Controls Page**
   - Click "Load Playlists" → Modal opens with list
   - Click "Restore" → Modal opens with snapshots
   - Close modals → No errors

2. **Editor Page**
   - Click project manager icon → Modal opens
   - Load/delete projects → Modal updates correctly
   - Close modal → No errors

3. **Index Page**
   - Same as Editor (shares code)

### Console Checks
```javascript
// Verify ModalManager loaded
console.log(window.ModalManager); // Should exist

// Check modals initialized
console.log(playlistModal);       // In controls.js scope
console.log(projectManagerModal); // In editor.js scope
```

## Future Enhancements

- [ ] Add animation options (fade, slide, scale)
- [ ] Support for custom backdrop colors
- [ ] Modal stacking (multiple modals at once)
- [ ] Draggable modals
- [ ] Resizable modals
- [ ] Form validation helpers
- [ ] Modal templates (confirm, prompt, form, list)
- [ ] Accessibility improvements (focus trap, ARIA)

## Notes

- Requires Bootstrap 5.3.0+
- Modals auto-create on first use (lazy loading)
- Safe to call before ModalManager loads (queues initialization)
- All modals use `backdrop: 'static'` to prevent accidental closes
- Loading states use Bootstrap spinner component
