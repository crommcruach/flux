# Waveform Analyzer

A modular audio waveform analysis tool built with WaveSurfer.js v7.

## Features

- **Audio Loading**: Drag & drop or browse for audio files (MP3, WAV, etc.)
- **Waveform Visualization**: Interactive waveform display with timeline
- **Split Management**: Click on waveform to create splits, right-click regions to remove
- **Slot System**: Automatic slot creation based on splits
- **Playback Controls**: Play, pause, stop with real-time progress tracking
- **Slot Looping**: Click any slot to loop playback within that segment
- **Minify View**: Toggle compact view for waveform and slots
- **Manual Split Adjustment**: Fine-tune split times with numeric inputs

## File Structure

```
waveform-analyzer/
├── index.html      # Main HTML structure
├── style.css       # Styles and layout
├── app.js          # Core JavaScript logic
└── README.md       # This file
```

## Usage

1. Open `index.html` in a modern web browser
2. Drag and drop an audio file or click the preview area to browse
3. Click on the waveform to add split points
4. Right-click on regions to remove splits
5. Click on any slot to loop that segment
6. Use the minify button (⬇️) to toggle compact view

## Technologies

- **WaveSurfer.js v7**: Waveform rendering and audio playback
- **RegionsPlugin**: Interactive region management
- **TimelinePlugin**: Time markers display
- **ES6 Modules**: Modular JavaScript architecture

## Browser Support

Requires a modern browser with ES6 module support and Web Audio API.
