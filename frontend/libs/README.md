# Frontend Libraries - Offline Dependencies

This directory contains all external JavaScript and CSS libraries used by the Py_artnet frontend, downloaded locally for better performance and offline availability.

## 📦 Installed Libraries

| Library | Version | Size | Purpose |
|---------|---------|------|---------|
| **Bootstrap** | 5.3.0 | 313 KB | UI framework (CSS + JS) |
| **Ion RangeSlider** | 2.3.1 | 52 KB | Range slider component |
| **Chart.js** | latest | 208 KB | Data visualization |
| **Bootstrap Icons** | 1.11.1 | 98 KB | Icon font |
| **WaveSurfer.js** | 7.x | 61 KB | Audio waveform visualization + plugins |

**Total Size:** ~731 KB

## 🔄 Updating Libraries

To update all libraries to their latest versions, run:

```powershell
cd frontend\libs
.\update-libs.ps1
```

The script will:
- Download the latest versions from CDNs
- Replace existing files
- Show a summary of successful/failed downloads

## 📝 Version History

### December 23, 2025
- **Initial Setup**: Downloaded all libraries offline
- Migrated from CDN links to local files
- Created update script for maintenance

## 🎯 Benefits

✅ **Faster Load Times** - No external requests, instant loading  
✅ **Offline Support** - Works without internet connection  
✅ **Version Control** - Track exact versions in use  
✅ **Reliability** - No CDN downtime or blocking issues  
✅ **Performance** - Reduced latency, better caching  

## 📂 Directory Structure

```
libs/
├── bootstrap/
│   ├── css/
│   │   └── bootstrap.min.css
│   └── js/
│       └── bootstrap.bundle.min.js
├── ion-rangeslider/
│   ├── css/
│   │   └── ion.rangeSlider.min.css
│   └── js/
│       └── ion.rangeSlider.min.js
├── chartjs/
│   └── chart.min.js
├── bootstrap-icons/
│   └── bootstrap-icons.css
├── wavesurfer/
│   └── dist/
│       ├── wavesurfer.esm.js
│       └── plugins/
│           ├── regions.esm.js
│           └── timeline.esm.js
├── update-libs.ps1
└── README.md
```

- [WaveSurfer.js](https://wavesurfer-js.org/)
## 🔗 Official Documentation

- [Bootstrap](https://getbootstrap.com/docs/5.3/)
- [Ion RangeSlider](http://ionden.com/a/plugins/ion.rangeSlider/)
- [Chart.js](https://www.chartjs.org/)
- [Bootstrap Icons](https://icons.getbootstrap.com/)

## ⚠️ Important Notes

- **jQuery**: Ion RangeSlider requires jQuery (not included, consider removing if not needed elsewhere)
- **Font Files**: Bootstrap Icons may need font files for some icons (currently using CSS only)
- **Updates**: Run the update script monthly or when new features are released
- **Backups**: Consider backing up working versions before updating

## 🛠️ Maintenance Tasks

- [ ] Check for library updates monthly
- [ ] Test all pages after updating
- [ ] Remove unused libraries to reduce size
- [ ] Consider minifying custom CSS/JS files

## 📊 Performance Impact

**Before (CDN):**
- 4-6 external requests
- ~500ms average load time (network dependent)
- Requires internet connection

**After (Local):**
- 0 external requests
- <50ms average load time
- Works completely offline

---

*Last updated: December 23, 2025*
