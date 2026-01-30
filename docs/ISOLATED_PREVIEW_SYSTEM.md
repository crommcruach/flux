# Isolated Preview System

## Overview
The isolated preview system allows viewing and previewing non-active playlists without interfering with the active playlist's output (Art-Net DMX). This professional approach ensures that live output continues uninterrupted while exploring different playlists.

## Architecture

### Active vs Viewed Playlists
- **Active Playlist**: The playlist currently loaded into the physical players, controlling Art-Net/DMX output and video canvas
- **Viewed Playlist**: The playlist currently displayed in the GUI, which may or may not be the active one

### Preview Modes

#### 1. Active Playlist Mode
When viewing the active playlist:
- Clips load directly into the player
- Changes immediately affect output
- Live MJPEG streams show real-time rendering

#### 2. Isolated Preview Mode
When viewing a non-active playlist:
- Clicks on clips show static thumbnails
- Active playlist continues running in background
- Art-Net/DMX output remains unaffected
- Preview displays "Preview (Active playlist continues outputting)" tooltip

## Implementation Details

### Backend (`api_playlists.py`)

```python
# For non-active playlists: preview-clip endpoint returns mode='preview_isolated'
if playlist_id != playlist_system.active_playlist_id:
    return jsonify({
        "success": True,
        "mode": "preview_isolated",
        "clip": {
            "path": clip_path,
            "id": clip_id,
            "type": "video" or "generator"
        },
        "note": "Preview mode: Shows clip info only, active playlist continues outputting"
    })
```

### Frontend (`player.js`)

When receiving `mode: "preview_isolated"`:
1. Extract clip path from response
2. Generate thumbnail URL:
   - Video clips: `/api/thumbnails/{filename}`
   - Generators: SVG placeholder with generator name
3. Update preview image with static thumbnail
4. Set tooltip to indicate isolated mode

### Key Functions

#### `loadFunc` (Video/Art-Net)
```javascript
if (!isActive) {
    // Isolated preview mode
    const result = await fetch('/api/playlists/{id}/preview-clip', {...});
    if (result.mode === 'preview_isolated') {
        // Show static thumbnail
        previewImg.src = getThumbnailUrl(result.clip.path);
        showToast('Preview: {clip} (Active playlist continues)', 'info');
    }
}
```

## User Experience

### Viewing Active Playlist
1. Double-click clip → loads into player
2. Video canvas updates with live stream
3. Art-Net output changes immediately
4. Autoplay/loop settings apply

### Viewing Non-Active Playlist
1. Double-click clip → shows static thumbnail
2. Toast notification: "Preview: {clip} (Active playlist continues)"
3. Tooltip: "Preview (Active playlist continues outputting)"
4. Active playlist keeps running in background
5. Art-Net output unchanged

## Benefits

### Isolation
- Active playlist output never interrupted
- Safe to explore other playlists during live shows
- No accidental output changes

### Professional Workflow
- Preview playlist behavior before activation
- Test autoplay settings without affecting output
- Browse multiple playlists safely

### Performance
- No unnecessary player reloads
- Thumbnails cached by browser
- Active playlist maintains smooth playback

## Technical Flow

```
User clicks clip in non-active playlist
         ↓
Frontend checks: isActive = (viewedPlaylistId === activePlaylistId)
         ↓ (false)
POST /api/playlists/{id}/preview-clip
         ↓
Backend checks: playlist_id != active_playlist_id
         ↓ (true)
Return {mode: "preview_isolated", clip: {...}}
         ↓
Frontend extracts clip.path
         ↓
Generate thumbnail URL
         ↓
Update preview image (static)
         ↓
Active playlist continues unaffected
```

## Related Files

- **Backend**: `src/modules/api_playlists.py` (lines 547-651)
- **Frontend**: `frontend/js/player.js` (lines 160-200, 1950-2080, 3275-3330)
- **Playlist System**: `src/modules/playlist_manager.py` (MultiPlaylistSystem)

## Future Enhancements

1. **Live Preview Player**: Separate preview player instance for true live preview without affecting output
2. **Preview Canvas**: Dedicated preview canvas that doesn't use main player resources
3. **Thumbnail Cache**: Pre-generate thumbnails for faster preview loading
4. **Generator Previews**: Render generator output to static images for preview

## Troubleshooting

### Preview Shows "Active playlist continues outputting"
- **Expected behavior**: You're viewing a non-active playlist
- Activate the playlist to control output

### No Thumbnail Shown
- Check that `/api/thumbnails/{filename}` endpoint exists
- Verify video file has a thumbnail generated
- Check browser console for thumbnail loading errors

### Active Playlist Affected by Preview
- **Bug**: Preview should never affect active playlist
- Check that `playlist_id != active_playlist_id` check in backend
- Verify frontend checks `result.mode === 'preview_isolated'`
