"""
Motion Key Effect Plugin - Automatisches Freistellen durch Bewegungserkennung
Nutzt OpenCV BackgroundSubtraction (MOG2/KNN) um den statischen Hintergrund
automatisch zu lernen und nur den bewegten Vordergrund anzuzeigen.
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class MotionKeyEffect(PluginBase):
    """
    Motion Key (Bewegungsbasiertes Freistellen).

    Der Effekt lernt den Hintergrund aus den ersten Frames automatisch und
    zeigt nur Pixel, die sich bewegen (Vordergrund = "interessanter Teil").
    Ideal für Performer, Objekte oder Installationen vor statischem Hintergrund.

    Algorithmen:
      - MOG2: Robuster Gauss-Mixture-Modell Algorithmus (empfohlen)
      - KNN:  K-Nearest-Neighbor, besser bei starken Beleuchtungswechseln

    Workflow:
      1. Plugin startet → lernt automatisch den Hintergrund (learning_frames)
      2. Nach dem Einlernen wird der statische Hintergrund ausgeblendet
      3. "Reset" erzwingt ein Neu-Einlernen (z.B. nach Kamerabewegung)
    """

    METADATA = {
        'id': 'motion_key',
        'name': 'Motion Key',
        'description': 'Freistellen durch Bewegungserkennung – lernt Hintergrund automatisch',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }

    PARAMETERS = [
        {
            'name': 'algorithm',
            'label': 'Algorithmus',
            'type': ParameterType.SELECT,
            'default': 'MOG2',
            'options': ['MOG2', 'KNN'],
            'description': 'Hintergrundsubtraktions-Algorithmus (MOG2 = robuster, KNN = bei Lichtwechseln)'
        },
        {
            'name': 'sensitivity',
            'label': 'Empfindlichkeit',
            'type': ParameterType.INT,
            'default': 30,
            'min': 5,
            'max': 150,
            'step': 5,
            'description': 'Bewegungs-Schwellwert – kleiner = empfindlicher, größer = weniger Rauschen'
        },
        {
            'name': 'learning_rate',
            'label': 'Lernrate',
            'type': ParameterType.FLOAT,
            'default': 0.005,
            'min': 0.0,
            'max': 0.1,
            'step': 0.001,
            'description': 'Wie schnell der Hintergrund neu gelernt wird (0 = eingefroren, 0.1 = schnell)'
        },
        {
            'name': 'learning_frames',
            'label': 'Einlern-Frames',
            'type': ParameterType.INT,
            'default': 60,
            'min': 10,
            'max': 300,
            'step': 10,
            'description': 'Anzahl Frames zum initialen Hintergrund-Einlernen'
        },
        {
            'name': 'morph_size',
            'label': 'Morph. Bereinigung',
            'type': ParameterType.INT,
            'default': 5,
            'min': 0,
            'max': 30,
            'step': 1,
            'description': 'Morphologische Bereinigung der Maske (entfernt Löcher & Rauschen)'
        },
        {
            'name': 'edge_blur',
            'label': 'Kantensanftheit',
            'type': ParameterType.INT,
            'default': 7,
            'min': 0,
            'max': 51,
            'step': 2,
            'description': 'Weichzeichnung der Maskenkanten für natürlichere Übergänge'
        },
        {
            'name': 'shadow_removal',
            'label': 'Schatten entfernen',
            'type': ParameterType.SELECT,
            'default': 'yes',
            'options': ['yes', 'no'],
            'description': 'Bewegungsschatten aus der Maske entfernen (MOG2-Funktion)'
        },
        {
            'name': 'bg_color',
            'label': 'Hintergrundfarbe',
            'type': ParameterType.COLOR,
            'default': '#000000',
            'description': 'Farbe für den entfernten Hintergrund'
        },
        {
            'name': 'reset',
            'label': 'Hintergrund Reset',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['no', 'yes'],
            'description': 'Auf "yes" setzen um Hintergrundmodell neu einzulernen'
        }
    ]

    @staticmethod
    def _unwrap(value):
        """Extrahiert den echten Wert aus einem WebSocket-Dict {'_value': x, '_uid': ...} oder gibt value direkt zurück."""
        if isinstance(value, dict) and '_value' in value:
            return value['_value']
        return value

    def initialize(self, config):
        """Initialisiert das Plugin und erstellt den Background Subtractor."""
        self.algorithm = str(self._unwrap(config.get('algorithm', 'MOG2')))
        self.sensitivity = int(self._unwrap(config.get('sensitivity', 30)))
        self.learning_rate = float(self._unwrap(config.get('learning_rate', 0.005)))
        self.learning_frames = int(self._unwrap(config.get('learning_frames', 60)))
        self.morph_size = int(self._unwrap(config.get('morph_size', 5)))
        self.edge_blur = int(self._unwrap(config.get('edge_blur', 7)))
        self.shadow_removal = str(self._unwrap(config.get('shadow_removal', 'yes')))
        bg_hex = str(self._unwrap(config.get('bg_color', '#000000')))
        self.bg_color = self._hex_to_bgr(bg_hex)
        self.reset_flag = str(self._unwrap(config.get('reset', 'no')))

        self._frame_count = 0
        self._subtractor = None
        self._build_subtractor()

    def _build_subtractor(self):
        """Erstellt einen neuen Background Subtractor."""
        self._frame_count = 0
        if self.algorithm == 'KNN':
            self._subtractor = cv2.createBackgroundSubtractorKNN(
                history=self.learning_frames,
                dist2Threshold=self.sensitivity * self.sensitivity,
                detectShadows=(self.shadow_removal == 'yes')
            )
        else:  # MOG2 (default)
            self._subtractor = cv2.createBackgroundSubtractorMOG2(
                history=self.learning_frames,
                varThreshold=self.sensitivity,
                detectShadows=(self.shadow_removal == 'yes')
            )

    def _hex_to_bgr(self, hex_color):
        """Konvertiert Hex-Farbe (#rrggbb) zu BGR-Tupel."""
        hex_color = str(hex_color).lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (b, g, r)
        return (0, 0, 0)

    def process_frame(self, frame, **kwargs):
        """
        Wendet Motion Key auf ein Frame an.

        In den ersten `learning_frames` Frames wird der Hintergrund
        mit hoher Lernrate eintrainiert. Danach läuft die Subtraktion
        mit der konfigurierten (niedrigen) Lernrate.

        Args:
            frame: Input-Frame als NumPy Array (BGR, uint8)
            **kwargs: fps, time, frame_number (optional)

        Returns:
            numpy.ndarray: Frame mit entferntem Hintergrund (BGR, uint8)
        """
        if self._subtractor is None:
            self._build_subtractor()

        # Reset auf Wunsch
        if self.reset_flag == 'yes':
            self._build_subtractor()
            self.reset_flag = 'no'

        self._frame_count += 1

        # Während des Einlernens hohe Lernrate für schnelle Konvergenz
        if self._frame_count <= self.learning_frames:
            lr = 1.0 / max(1, self.learning_frames - self._frame_count + 1)
        else:
            lr = self.learning_rate

        # Hintergrundsubtraktion → Rohmaske (255 = Vordergrund, 127 = Schatten, 0 = Hintergrund)
        raw_mask = self._subtractor.apply(frame, learningRate=lr)

        # Schatten (Graubereich 127) als Hintergrund behandeln
        if self.shadow_removal == 'yes':
            # Nur echte Vordergrundbereiche (255) behalten
            _, fg_mask = cv2.threshold(raw_mask, 200, 255, cv2.THRESH_BINARY)
        else:
            fg_mask = raw_mask

        # Morphologische Bereinigung: Löcher schließen, Rauschen entfernen
        if self.morph_size > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (self.morph_size, self.morph_size)
            )
            # Close: Löcher im Vordergrund schließen
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
            # Open: kleines Rauschen entfernen
            fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        # Kantensanftheit für natürliche Übergänge
        if self.edge_blur > 0:
            blur_size = self.edge_blur | 1  # Muss ungerade sein
            fg_mask = cv2.GaussianBlur(fg_mask, (blur_size, blur_size), 0)

        # Während des Einlernens das Original-Frame anzeigen (kein Flackern)
        if self._frame_count <= self.learning_frames:
            return frame

        # Alpha Blending: Vordergrund + Hintergrundfarbe
        alpha = fg_mask.astype(np.float32) / 255.0
        background = np.full_like(frame, self.bg_color, dtype=np.uint8)

        alpha_3ch = alpha[:, :, np.newaxis]  # (H, W, 1) für Broadcasting
        result = (frame.astype(np.float32) * alpha_3ch +
                  background.astype(np.float32) * (1.0 - alpha_3ch))

        return result.astype(np.uint8)

    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit. value kann plain oder dict {'_value':...,'_uid':...} sein."""
        value = self._unwrap(value)
        if name == 'algorithm':
            new_algo = str(value)
            if new_algo != self.algorithm:
                self.algorithm = new_algo
                self._build_subtractor()  # Neu aufbauen bei Algorithmuswechsel
            return True
        elif name == 'sensitivity':
            self.sensitivity = int(value)
            # Schwellwert am laufenden Subtractor anpassen (nur MOG2 unterstützt das)
            if self.algorithm == 'MOG2' and self._subtractor is not None:
                self._subtractor.setVarThreshold(self.sensitivity)
            return True
        elif name == 'learning_rate':
            self.learning_rate = float(value)
            return True
        elif name == 'learning_frames':
            self.learning_frames = int(value)
            return True
        elif name == 'morph_size':
            self.morph_size = int(value)
            return True
        elif name == 'edge_blur':
            self.edge_blur = int(value)
            return True
        elif name == 'shadow_removal':
            self.shadow_removal = str(value)
            return True
        elif name == 'bg_color':
            self.bg_color = self._hex_to_bgr(str(value))
            return True
        elif name == 'reset':
            if str(value) == 'yes':
                self._build_subtractor()
            return True
        return False

    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'algorithm': self.algorithm,
            'sensitivity': self.sensitivity,
            'learning_rate': self.learning_rate,
            'learning_frames': self.learning_frames,
            'morph_size': self.morph_size,
            'edge_blur': self.edge_blur,
            'shadow_removal': self.shadow_removal,
            'bg_color': f'#{self.bg_color[2]:02x}{self.bg_color[1]:02x}{self.bg_color[0]:02x}',
            'reset': 'no'
        }
