"""
Cache Command Helper Functions
"""
import os
import json


def execute_cache_command(args, cache_dir, config_path=None):
    """Führt erweiterte Cache-Befehle aus."""
    
    if args == "clear":
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            file_count = 0
            errors = []
            for f in files:
                try:
                    os.remove(os.path.join(cache_dir, f))
                    file_count += 1
                except Exception as e:
                    errors.append(f"{f}: {e}")
            result = f"✓ Cache geleert ({file_count} Dateien gelöscht)"
            if errors:
                result += "\n⚠ Fehler bei: " + ", ".join(errors[:3])
            return result
        return "Cache-Ordner existiert nicht"
        
    elif args == "info":
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            status = "Unbekannt"
            if config_path and os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    cfg = json.load(f)
                status = 'Aktiviert' if cfg.get('cache', {}).get('enabled', True) else 'Deaktiviert'
            return f"Cache-Informationen:\n  Dateien: {len(files)}\n  Größe: {total_size / (1024*1024):.2f} MB\n  Pfad: {cache_dir}\n  Status: {status}"
        return "Cache-Ordner existiert nicht"
        
    elif args and args.startswith("delete"):
        parts = args.split(maxsplit=1)
        if len(parts) > 1:
            video_name = parts[1]
            if os.path.exists(cache_dir):
                try:
                    import msgpack
                except ImportError:
                    return "msgpack nicht installiert"
                    
                for cache_file in os.listdir(cache_dir):
                    if cache_file.endswith('.msgpack'):
                        cache_path = os.path.join(cache_dir, cache_file)
                        try:
                            with open(cache_path, 'rb') as f:
                                cache_data = msgpack.unpackb(f.read(), raw=False)
                            if video_name.lower() in cache_data.get('video', '').lower():
                                file_size_mb = os.path.getsize(cache_path) / (1024*1024)
                                os.remove(cache_path)
                                return f"✓ Cache gelöscht für: {cache_data.get('video')} ({file_size_mb:.2f} MB)"
                        except:
                            pass
            return f"Keine Cache-Datei gefunden für: {video_name}"
        return "Verwendung: cache delete <videoname>"
        
    elif args == "enable":
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            cfg['cache']['enabled'] = True
            with open(config_path, 'w') as f:
                json.dump(cfg, f, indent=2)
            return "✓ RGB-Caching aktiviert"
        return "config.json nicht gefunden"
        
    elif args == "disable":
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = json.load(f)
            cfg['cache']['enabled'] = False
            with open(config_path, 'w') as f:
                json.dump(cfg, f, indent=2)
            return "✓ RGB-Caching deaktiviert"
        return "config.json nicht gefunden"
        
    elif args == "size":
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            result = f"Cache-Größe: {total_size / (1024*1024):.2f} MB ({len(files)} Dateien)"
            if files:
                result += "\n\nTop 5 größte Dateien:"
                file_sizes = [(f, os.path.getsize(os.path.join(cache_dir, f))) for f in files]
                for fname, fsize in sorted(file_sizes, key=lambda x: x[1], reverse=True)[:5]:
                    result += f"\n  {fname}: {fsize / (1024*1024):.2f} MB"
            return result
        return "Cache-Ordner existiert nicht"
        
    return "Verwendung: cache clear | info | delete <name> | enable | disable | size"
