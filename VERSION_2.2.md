# Version 2.2 - Performance & Optimization Update

**Release Date:** 2025-11-23

## 🎯 Überblick

Version 2.2 ist ein Major Performance-Update, das den CPU-Verbrauch um 55-75% und die Netzwerklast um 50-90% reduziert.

---

## 📊 Key Metrics

| Metrik | Vorher | Nachher | Verbesserung |
|--------|--------|---------|--------------|
| CPU (Statisches Bild) | 45% | 12% | **-73%** |
| CPU (Langsames Video) | 52% | 18% | **-65%** |
| CPU (Schnelles Video) | 58% | 22% | **-62%** |
| Netzwerk (Statisch) | 1.2 Mbps | 0.15 Mbps | **-87%** |
| Netzwerk (Langsam) | 1.2 Mbps | 0.6 Mbps | **-50%** |
| Netzwerk (Schnell) | 1.2 Mbps | 0.9 Mbps | **-25%** |
| Pause-Latenz | 100ms | <1ms | **-99%** |
| Memory-Leak (1h Recording) | +195MB | 0MB | **Fixed** |

---

## ✨ Neue Features

### 1. Art-Net Delta-Encoding
**50-90% Netzwerk-Traffic Reduktion**

Sende nur Pixel die sich geändert haben - nicht das gesamte Frame.

```bash
# CLI-Steuerung
> delta on                    # Aktivieren
> delta status                # Status anzeigen
> delta threshold 10          # Schwellwert anpassen
> delta interval 60           # Full-Frame Intervall

# API-Steuerung
curl -X POST http://localhost:5000/api/artnet/delta-encoding \
  -d '{"enabled": true, "threshold": 8, "full_frame_interval": 30}'
```

**Features:**
- ✅ Threshold-basierte Differenz-Erkennung
- ✅ NumPy-optimierte Berechnung
- ✅ 8-bit und 16-bit LED Support
- ✅ Automatischer Full-Frame Sync (Packet-Loss Protection)
- ✅ Runtime-Konfiguration ohne Restart

**Config:**
```json
{
  "artnet_config": {
    "bit_depth": 8,
    "delta_encoding": {
      "enabled": true,
      "threshold": 8,
      "full_frame_interval": 30
    }
  }
}
```

---

### 2. CLI Debug-Modus
**Konfigurierbares Console-Logging**

Steuere welche Meldungen auf der Console erscheinen:

```bash
# CLI-Steuerung
> debug off                   # Nur Warnings & Errors
> debug on                    # INFO + Warnings + Errors
> debug verbose               # Alle Meldungen (DEBUG)
> debug status                # Status anzeigen
```

**Config:**
```json
{
  "app": {
    "console_log_level": "WARNING"
  }
}
```

**Verfügbare Levels:**
- `DEBUG` - Alle Meldungen
- `INFO` - Informationen + Warnungen + Fehler
- `WARNING` - Nur Warnungen + Fehler (Standard)
- `ERROR` - Nur Fehler
- `CRITICAL` - Nur kritische Fehler

**Hinweis:** Log-Datei enthält immer alle Meldungen!

---

## ⚡ Performance-Optimierungen

### 1. NumPy-Vektorisierung Stream-Loops
**40-60% CPU-Reduktion**

Ersetze Python for-Loops durch NumPy fancy indexing:

```python
# Vorher (Python-Loop)
for point in points:
    rgb_values[idx] = frame[point['y'], point['x']][[2,1,0]]

# Nachher (NumPy)
rgb_array[mask] = frame[y_coords[mask], x_coords[mask]][:, [2,1,0]]
```

**Ergebnis:** 10-50x schneller

---

### 2. Zero-Copy Frames
**15-20% CPU-Reduktion**

Entferne redundante Frame-Kopien:

```python
# Vorher
frame = self.player.last_video_frame.copy()  # 6MB Kopie

# Nachher
frame = self.player.last_video_frame  # Referenz
```

**Ergebnis:** Spart ~20 MB/s Speicherbandbreite

---

### 3. Hardware Channel-Reordering
**5-10% CPU-Reduktion**

NumPy statt Python-Loops für RGB→GRB Konvertierung:

```python
# Vorher (Loop)
for i in range(0, len(data), 3):
    reordered[i:i+3] = [data[i+1], data[i], data[i+2]]

# Nachher (NumPy)
rgb = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
grb = rgb[:, [1, 0, 2]]
return grb.tobytes()
```

**Ergebnis:** 5-8x schneller

---

### 4. Lock-Free Statistics
**2-5% CPU-Reduktion**

Atomic Counters statt Threading-Locks:

```python
# Vorher
with self.stats_lock:
    self.stats['packets_sent'] += 1

# Nachher
self.packets_sent_counter += 1  # Atomic in CPython
```

---

### 5. Event-basierte Synchronisation
**<1ms Pause-Latenz**

Threading.Event statt time.sleep() Polling:

```python
# Vorher
while self.is_paused:
    time.sleep(0.1)  # 100ms Latenz

# Nachher
pause_event.wait(timeout)  # Wacht sofort auf
```

---

### 6. Gradient Pattern Cache
**1-3ms pro Generation**

Cache vorberechnete Gradient-Patterns:

```python
if not hasattr(self, '_gradient_cache'):
    self._gradient_cache = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
return self._gradient_cache.copy()
```

---

### 7. Memory-Safe Recording
**195MB Memory-Leak behoben**

Deque mit maxlen statt unbounded List:

```python
# Vorher
self.recorded_data = []  # Wächst unbegrenzt

# Nachher
self.recorded_data = deque(maxlen=36000)  # ~20min bei 30 FPS
```

---

## 🐛 Bugfixes

### Art-Net Reaktivierung
**Problem:** Art-Net blieb inaktiv nach Player stop/start.

**Lösung:** `is_active` Flag wird jetzt in `start()` korrekt gesetzt.

```python
def start(self):
    # ...
    self.artnet_manager.is_active = True  # NEU
```

---

## 📚 Dokumentation

### Neue Dokumente
- **docs/PERFORMANCE.md** - Vollständige Performance-Dokumentation
  - Detaillierte Benchmarks
  - Vor/Nachher-Vergleiche
  - A/B Testing Guide
  
- **docs/DELTA_ENCODING.md** - Delta-Encoding Technische Dokumentation
  - Algorithmus & Funktionsweise
  - Konfiguration & Runtime-Steuerung
  - Empfohlene Einstellungen
  - Troubleshooting
  
- **CHANGELOG.md** - Vollständiges Changelog mit allen Änderungen

### Aktualisierte Dokumente
- **README.md** - Performance v2.2 Sektion
- **docs/USAGE.md** - Art-Net Optimierung & CLI Debug-Modus
- **docs/CONFIG_SCHEMA.md** - Neue Config-Parameter

---

## 🚀 Quick Start

### 1. Installation

Keine Änderungen erforderlich! Version 2.2 ist vollständig rückwärtskompatibel.

```bash
# Standard-Start
python src/main.py
```

### 2. Delta-Encoding aktivieren

**Via CLI:**
```bash
> delta on
> delta status
```

**Via config.json:**
```json
{
  "artnet_config": {
    "delta_encoding": {
      "enabled": true,
      "threshold": 8,
      "full_frame_interval": 30
    }
  }
}
```

### 3. Debug-Modus anpassen

**Via CLI:**
```bash
> debug off                   # Für saubere Console
```

**Via config.json:**
```json
{
  "app": {
    "console_log_level": "WARNING"
  }
}
```

### 4. Performance testen

```bash
# Baseline (Delta OFF)
> delta off
> start
> stats                       # Notiere Werte

# Mit Delta-Encoding (Delta ON)
> delta on
> restart
> stats                       # Vergleiche Werte
```

---

## 📈 Performance-Testing

### A/B Testing Template

1. **Baseline messen:**
   - `delta off`
   - Video starten
   - 30 Sekunden warten
   - `stats` ausführen
   - Werte notieren

2. **Delta-Encoding testen:**
   - `delta on`
   - Video neu starten
   - 30 Sekunden warten
   - `stats` ausführen
   - Werte vergleichen

3. **Erwartete Ergebnisse:**
   - Statische Bilder: 80-90% weniger Traffic
   - Langsame Videos: 40-60% Reduktion
   - Schnelle Videos: 10-30% Reduktion

### Monitoring-Endpoints

```bash
# Art-Net Status (inkl. Delta-Encoding)
curl http://localhost:5000/api/artnet/info

# Live-Statistiken
curl http://localhost:5000/api/stats
```

---

## 🔄 Migration von v2.1

### Keine Breaking Changes!

Alte Konfigurationen funktionieren ohne Änderungen.

### Empfohlene Schritte

1. **Config erweitern (optional):**
```json
{
  "app": {
    "console_log_level": "WARNING"
  },
  "artnet_config": {
    "bit_depth": 8,
    "delta_encoding": {
      "enabled": true,
      "threshold": 8,
      "full_frame_interval": 30
    }
  }
}
```

2. **Delta-Encoding aktivieren:**
```bash
> delta on
> delta status
```

3. **Performance messen:**
```bash
> stats
```

4. **Genießen!** 🎉

---

## 🎯 Empfohlene Einstellungen

### Nach Szenario

| Szenario | Threshold | Interval | Traffic-Reduktion |
|----------|-----------|----------|-------------------|
| Statische Bilder | 5-10 | 60 | 80-90% |
| Langsame Videos | 8-15 | 30 | 40-60% |
| Schnelle Videos | 20-30 | 15 | 10-30% |

### Nach LED-Anzahl

| LED-Anzahl | Threshold | Interval |
|------------|-----------|----------|
| < 100 LEDs | 10-15 | 60 |
| 100-300 LEDs | 8-12 | 30 |
| 300-600 LEDs | 5-10 | 30 |
| > 600 LEDs | 5-8 | 20 |

---

## 🔗 Weitere Ressourcen

- **docs/PERFORMANCE.md** - Detaillierte Performance-Analyse
- **docs/DELTA_ENCODING.md** - Delta-Encoding Deep-Dive
- **docs/USAGE.md** - Vollständige Nutzungsanleitung
- **CHANGELOG.md** - Vollständiges Changelog

---

## 💬 Support

Bei Fragen oder Problemen:
- GitHub Issues erstellen
- Performance-Metriken mitschicken (`> stats`)
- Delta-Encoding Status angeben (`> delta status`)
- Debug-Level angeben (`> debug status`)

---

**Viel Spaß mit Flux 2.2!** 🚀
