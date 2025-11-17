"""
Zentrale Konstanten für Flux Anwendung
"""

# Art-Net / DMX Konstanten
DMX_CHANNELS_PER_UNIVERSE = 510
DMX_CHANNELS_PER_POINT = 3  # RGB
DMX_MAX_UNIVERSES_BEFORE_GAP = 8
DMX_MAX_CHANNELS_8_UNIVERSES = DMX_CHANNELS_PER_UNIVERSE * DMX_MAX_UNIVERSES_BEFORE_GAP  # 4080

# Video Konstanten
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.gif')
VIDEO_EXTENSIONS_LIST = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.gif']
GIF_EXTENSIONS = ('.gif',)
GIF_EXTENSIONS_LIST = ['.gif']

# Cache Konstanten
CACHE_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB für Hash-Berechnung
CACHE_HASH_LENGTH = 16  # Anzahl Zeichen für Video-Hash
CACHE_FILE_EXTENSION = '.msgpack'

# API / Console Konstanten
CONSOLE_LOG_MAX_LENGTH = 500
DEFAULT_API_PORT = 5000
DEFAULT_API_HOST = '0.0.0.0'

# Pfad Konstanten
DEFAULT_VIDEO_DIR = 'video'
DEFAULT_DATA_DIR = 'data'
DEFAULT_CACHE_DIR = 'cache'
DEFAULT_POINTS_FILE = 'punkte_export.json'

# Canvas Konstanten
DEFAULT_CANVAS_WIDTH = 1024
DEFAULT_CANVAS_HEIGHT = 768

# Playback Konstanten
DEFAULT_BRIGHTNESS = 100
DEFAULT_SPEED = 1.0
DEFAULT_FPS = 30.0
UNLIMITED_LOOPS = 0

# System Konstanten
DEFAULT_RESTART_DELAY = 1.0  # Sekunden
OUTPUT_TRUNCATE_SIZE = 60 * 1024  # 60KB für Terminal-Output

# Affirmative Antworten für Bestätigungen
AFFIRMATIVE_RESPONSES = ['j', 'ja', 'y', 'yes']
