"""
DMX Controller - Empfängt DMX-Befehle über Art-Net
"""
import socket
import struct
import threading
import os
from .constants import VIDEO_EXTENSIONS_LIST
from .logger import get_logger

logger = get_logger(__name__)


class DMXController:
    """Empfängt DMX-Befehle über Art-Net zur Steuerung der Anwendung."""
    
    def __init__(self, player, listen_ip='0.0.0.0', listen_port=6454, control_universe=100, video_base_dir=None):
        self.player = player
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.control_universe = control_universe
        self.video_base_dir = video_base_dir
        
        self.is_running = False
        self.thread = None
        self.sock = None
        
        # Letzte DMX-Werte für Trigger-Erkennung
        self.last_values = [0] * 512
        
        # Video-Slot Cache (Kanal -> Video-Pfad Mapping)
        self.video_cache = {}
        if video_base_dir:
            self._build_video_cache()
        
    def start(self):
        """Startet DMX-Listener."""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        print(f"DMX-Steuerung aktiv auf {self.listen_ip}:{self.listen_port}, Universum {self.control_universe}")
        print("DMX-Kanal-Mapping:")
        print("  Ch 1: Play/Stop (0-127=Stop, 128-255=Play)")
        print("  Ch 2: Brightness (0-255)")
        print("  Ch 3: Speed (0-255, 128=1x)")
        print("  Ch 4: Pause/Resume (0-127=Resume, 128-255=Pause)")
        print("  Ch 5: Blackout (0-127=Normal, 128-255=Blackout)")
        print("  Ch 6-9: Video-Slot (4 Kanäle für bis zu 1020 Videos)")
        print("         Ch6=Kanal (1-4), Ch7-9=Slot (0-255 pro Kanal)")
        if self.video_cache:
            print(f"  Video-Cache: {len(self.video_cache)} Videos geladen")
    
    def stop(self):
        """Stoppt DMX-Listener."""
        self.is_running = False
        if self.sock:
            self.sock.close()
        if self.thread:
            self.thread.join(timeout=1.0)
    
    def _listen_loop(self):
        """Hauptschleife zum Empfang von Art-Net Paketen."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.listen_ip, self.listen_port))
            self.sock.settimeout(1.0)
            
            while self.is_running:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    self._process_artnet_packet(data)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.is_running:
                        print(f"Fehler beim Empfang: {e}")
        
        except Exception as e:
            print(f"DMX-Listener Fehler: {e}")
        finally:
            if self.sock:
                self.sock.close()
    
    def _process_artnet_packet(self, data):
        """Verarbeitet empfangenes Art-Net Paket."""
        if len(data) < 18:
            return
        
        # Art-Net Header prüfen
        if data[0:8] != b'Art-Net\x00':
            return
        
        opcode = struct.unpack('<H', data[8:10])[0]
        if opcode != 0x5000:  # ArtDMX
            return
        
        # Universum extrahieren
        universe = struct.unpack('<H', data[14:16])[0]
        
        if universe != self.control_universe:
            return
        
        # DMX-Daten extrahieren
        length = struct.unpack('>H', data[16:18])[0]
        dmx_data = list(data[18:18+length])
        
        if len(dmx_data) < 9:
            return
        
        # Ausgabe wenn sich relevante Werte ändern
        print(f"[DMX] Empfangen - Ch1:{dmx_data[0]} Ch2:{dmx_data[1]} Ch3:{dmx_data[2]} Ch4:{dmx_data[3]} Ch5:{dmx_data[4]} Ch6:{dmx_data[5]} Ch7:{dmx_data[6]} Ch8:{dmx_data[7]} Ch9:{dmx_data[8]}")
        
        self._process_dmx_values(dmx_data)
    
    def _process_dmx_values(self, dmx):
        """Verarbeitet DMX-Werte und steuert Player."""
        # Kanal 1: Play/Stop
        if dmx[0] != self.last_values[0]:
            if self.last_values[0] < 128 and dmx[0] >= 128:
                if not self.player.is_playing:
                    print("[DMX] Start triggered")
                    self.player.start()
            elif self.last_values[0] >= 128 and dmx[0] < 128:
                if self.player.is_playing:
                    print("[DMX] Stop triggered")
                    self.player.stop()
        
        # Kanal 2: Brightness
        if abs(dmx[1] - self.last_values[1]) > 2:  # Hysterese
            brightness = (dmx[1] / 255.0) * 100
            print(f"[DMX] Brightness → {brightness:.0f}%")
            self.player.set_brightness(brightness)
        
        # Kanal 3: Speed
        if abs(dmx[2] - self.last_values[2]) > 2:
            # 0=0.25x, 128=1x, 255=4x
            if dmx[2] < 128:
                speed = 0.25 + (dmx[2] / 128.0) * 0.75  # 0.25 - 1.0
            else:
                speed = 1.0 + ((dmx[2] - 128) / 127.0) * 3.0  # 1.0 - 4.0
            print(f"[DMX] Speed → {speed:.2f}x")
            self.player.set_speed(speed)
        
        # Kanal 4: Pause/Resume
        if dmx[3] != self.last_values[3]:
            if self.last_values[3] < 128 and dmx[3] >= 128:
                if self.player.is_playing and not self.player.is_paused:
                    print("[DMX] Pause triggered")
                    self.player.pause()
            elif self.last_values[3] >= 128 and dmx[3] < 128:
                if self.player.is_playing and self.player.is_paused:
                    print("[DMX] Resume triggered")
                    self.player.resume()
        
        # Kanal 5: Blackout
        if dmx[4] != self.last_values[4]:
            if self.last_values[4] < 128 and dmx[4] >= 128:
                print("[DMX] Blackout triggered")
                self.player.blackout()
        
        # Kanal 6-9: Video-Slot Auswahl (4 Kanäle für bis zu 1020 Videos)
        # Ch6: Kanal-Auswahl (1-4), Ch7-9: Slot innerhalb Kanal (0-255)
        if (dmx[5] != self.last_values[5] or dmx[6] != self.last_values[6] or 
            dmx[7] != self.last_values[7] or dmx[8] != self.last_values[8]):
            
            kanal = max(1, min(4, (dmx[5] // 64) + 1))  # 0-63=K1, 64-127=K2, 128-191=K3, 192-255=K4
            slot_ch1 = dmx[6]  # Slot Kanal 1 (0-255)
            slot_ch2 = dmx[7]  # Slot Kanal 2 (0-255)
            slot_ch3 = dmx[8]  # Slot Kanal 3 (0-255)
            
            # Berechne Video-Index: Kanal wählt welcher der 3 Slot-Kanäle aktiv ist
            if kanal == 1:
                video_slot = slot_ch1
            elif kanal == 2:
                video_slot = 255 + slot_ch2
            elif kanal == 3:
                video_slot = 510 + slot_ch3
            else:  # kanal == 4
                video_slot = 765 + slot_ch1  # Kanal 4 nutzt Ch7 nochmal
            
            # Suche Video in Cache
            if self.video_cache and video_slot in self.video_cache:
                video_path = self.video_cache[video_slot]
                print(f"[DMX] Video-Slot → Kanal {kanal}, Slot {video_slot}, Video: {os.path.basename(video_path)}")
                was_playing = self.player.is_playing
                if was_playing:
                    self.player.stop()
                if self.player.load_video(video_path):
                    if was_playing:
                        self.player.start()
            elif video_slot > 0:
                print(f"[DMX] Video-Slot {video_slot} nicht gefunden (Kanal {kanal})")
        
        # Speichere aktuelle Werte
        self.last_values = dmx.copy()
    
    def _build_video_cache(self):
        """Erstellt Video-Cache aus Kanal-Ordnern."""
        if not self.video_base_dir or not os.path.exists(self.video_base_dir):
            return
        
        video_extensions = VIDEO_EXTENSIONS_LIST
        slot_index = 0
        
        # Erstelle und scanne Kanal-Ordner
        for kanal in range(1, 5):
            kanal_dir = os.path.join(self.video_base_dir, f"kanal_{kanal}")
            
            # Erstelle Ordner wenn nicht vorhanden
            if not os.path.exists(kanal_dir):
                os.makedirs(kanal_dir)
                print(f"Kanal-Ordner erstellt: {kanal_dir} (Max 255 Videos)")
                continue
            
            # Scanne Videos im Kanal-Ordner
            videos = sorted([f for f in os.listdir(kanal_dir) 
                           if os.path.isfile(os.path.join(kanal_dir, f)) 
                           and any(f.lower().endswith(ext) for ext in video_extensions)])
            
            if len(videos) > 255:
                print(f"⚠️  WARNUNG: Kanal {kanal} hat {len(videos)} Videos (Max 255)! Nur erste 255 werden verwendet.")
                videos = videos[:255]
            
            # Füge Videos zum Cache hinzu
            for i, video in enumerate(videos):
                video_path = os.path.join(kanal_dir, video)
                self.video_cache[slot_index + i] = video_path
            
            if videos:
                print(f"Kanal {kanal}: {len(videos)} Videos geladen (Slots {slot_index}-{slot_index + len(videos) - 1})")
            
            slot_index += 255  # Nächster Kanal startet bei +255
        
        print(f"Video-Cache: {len(self.video_cache)} Videos in {len([d for d in os.listdir(self.video_base_dir) if d.startswith('kanal_')])} Kanälen")
