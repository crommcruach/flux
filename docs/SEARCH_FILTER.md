# Search Filter Component

## Overview

The Search Filter component provides a reusable, universal search/filter functionality that can be applied to any list of items in the application.

## Architecture

### Component Structure

```
src/static/
├── components/
│   └── search-filter.html        # Template + styles + script
├── js/
│   └── search-filter-loader.js   # Async loader
```

### Key Features

- **Reusable**: Single component definition, multiple instances
- **Flexible**: Works with any item selector and search text extraction
- **Performant**: Debounced input (200ms default)
- **Visual Feedback**: Shows result count and clear button
- **Accessible**: Keyboard-friendly with clear placeholder text

## API Reference

### `window.SearchFilter.create(options)`

Creates a new search filter instance.

#### Parameters

```javascript
{
    container: HTMLElement,           // Required: Container to insert the search filter
    itemsSelector: string,            // Required: CSS selector for items to filter
    getSearchText: Function,          // Required: Function to extract searchable text from item
    placeholder: string,              // Optional: Placeholder text (default: "Search...")
    onFilter: Function,               // Optional: Callback after filtering
    caseSensitive: boolean,           // Optional: Case sensitive search (default: false)
    debounce: number                  // Optional: Debounce delay in ms (default: 200)
}
```

#### Returns

```javascript
{
    container: HTMLElement,           // The search filter container element
    input: HTMLInputElement,          // The search input element
    clear: Function,                  // Clear the search
    refresh: Function,                // Refresh the filter with current query
    getQuery: Function,               // Get current search query
    setQuery: Function                // Set search query programmatically
}
```

## Usage Examples

### Basic Usage

```javascript
// Wait for SearchFilter API to be available
await new Promise(resolve => {
    const check = setInterval(() => {
        if (window.SearchFilter) {
            clearInterval(check);
            resolve();
        }
    }, 100);
});

// Create filter
const myFilter = window.SearchFilter.create({
    container: document.getElementById('searchContainer'),
    itemsSelector: '.my-item-class',
    getSearchText: (item) => item.textContent,
    placeholder: 'Search items...'
});
```

### Advanced Usage with Callbacks

```javascript
const filter = window.SearchFilter.create({
    container: document.getElementById('effectsSearchContainer'),
    itemsSelector: '#availableEffects .effect-card',
    getSearchText: (item) => {
        const title = item.querySelector('.effect-card-title')?.textContent || '';
        const description = item.querySelector('.effect-card-description')?.textContent || '';
        return `${title} ${description}`;
    },
    placeholder: 'Search effects...',
    onFilter: (result) => {
        console.log(`Found ${result.visible} of ${result.total} items`);
        // Update UI based on results
        if (result.visible === 0) {
            showNoResultsMessage();
        }
    },
    caseSensitive: false,
    debounce: 300
});
```

### Programmatic Control

```javascript
// Set query programmatically
filter.setQuery('fade');

// Get current query
const currentQuery = filter.getQuery();

// Clear search
filter.clear();

// Refresh filter (e.g., after items change)
filter.refresh();
```

## Integration in Player.html

### HTML Structure

Add a container div for each search filter in the corresponding tab:

```html
<!-- Effects Tab -->
<div class="tab-pane active" id="tab-effects">
    <h6>Available Effects</h6>
    <div id="effectsSearchContainer"></div>
    <div id="availableEffects">
        <!-- Effect cards rendered here -->
    </div>
</div>
```

### JavaScript Integration

1. **Load the component**:
```html
<script src="js/search-filter-loader.js"></script>
```

2. **Initialize filters**:
```javascript
async function initializeSearchFilters() {
    // Wait for SearchFilter API
    while (!window.SearchFilter) {
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    // Create filter instances
    effectsSearchFilter = window.SearchFilter.create({
        container: document.getElementById('effectsSearchContainer'),
        itemsSelector: '#availableEffects .effect-card',
        getSearchText: (item) => {
            const title = item.querySelector('.effect-card-title')?.textContent || '';
            const description = item.querySelector('.effect-card-description')?.textContent || '';
            return `${title} ${description}`;
        },
        placeholder: 'Search effects...'
    });
}
```

3. **Refresh after data changes**:
```javascript
function renderAvailableEffects() {
    // ... render items ...
    
    // Refresh search filter
    if (effectsSearchFilter) {
        effectsSearchFilter.refresh();
    }
}
```

## Current Implementations

### Player Interface

The search filter is currently implemented for three tabs:

1. **Effects Tab** (`effectsSearchFilter`)
   - Searches: Effect name and description
   - Items: `.effect-card` elements
   - Placeholder: "Search effects..."

2. **Sources Tab** (`sourcesSearchFilter`)
   - Searches: Generator name and description
   - Items: `.generator-card` elements
   - Placeholder: "Search sources..."

3. **Files Tab** (`filesSearchFilter`)
   - Searches: File item text content
   - Items: `.file-item` elements (placeholder for future implementation)
   - Placeholder: "Search files..."

## Styling

The component includes built-in CSS with CSS variables for theming:

```css
.search-filter-input {
    background: var(--bg-secondary);
    border-color: var(--border-color);
    color: var(--text-primary);
}

.search-filter-input:focus {
    border-color: var(--accent-color);
    background: var(--bg-tertiary);
}
```

### Customization

To customize the appearance, override the CSS variables or add specific styles:

```css
/* Custom styles for a specific instance */
#effectsSearchContainer .search-filter-input {
    border-radius: 8px;
    font-size: 1rem;
}
```

## Best Practices

1. **Always refresh after rendering**: Call `filter.refresh()` after updating the item list
2. **Use debounce**: Keep the default 200ms debounce for responsive UX
3. **Extract meaningful text**: Include all searchable content in `getSearchText`
4. **Handle empty states**: Use `onFilter` callback to show "No results" messages
5. **Wait for API**: Always check `window.SearchFilter` exists before creating instances

## Performance Considerations

- **Debouncing**: Default 200ms prevents excessive DOM queries
- **Simple selectors**: Use efficient CSS selectors for `itemsSelector`
- **Text extraction**: Keep `getSearchText` lightweight
- **Refresh wisely**: Only call `refresh()` when items actually change

## Future Enhancements

- [ ] Support for multiple search terms (AND/OR logic)
- [ ] Regular expression search mode
- [ ] Save/restore search state
- [ ] Keyboard shortcuts (Ctrl+F to focus)
- [ ] Search history dropdown
- [ ] Highlighting matched text in results
- [ ] Advanced filters (e.g., by category, version)

## Troubleshooting

### Search filter not appearing
- Check that `search-filter-loader.js` is loaded
- Verify container element exists in DOM
- Check browser console for errors

### Items not filtering
- Verify `itemsSelector` matches your items
- Check that `getSearchText` returns valid text
- Ensure items are rendered before creating filter

### Search not working after data update
- Call `filter.refresh()` after rendering new items
- Check that item DOM structure hasn't changed

## Examples in Codebase

See `src/static/js/player.js` for complete implementation examples:
- `initializeSearchFilters()` - Initialization
- `renderAvailableEffects()` - Refresh after data changes
- `renderAvailableGenerators()` - Refresh after data changes
