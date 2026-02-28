"""
Monitor detection utilities
Uses screeninfo library to detect available displays
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Try to import screeninfo
try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False
    logger.warning("screeninfo not available - monitor detection disabled")


def get_available_monitors() -> List[Dict]:
    """
    Get list of available monitors with positions and resolutions
    
    Returns:
        list: List of monitor dictionaries with keys:
              - index: Monitor index (0-based)
              - name: Monitor name
              - x, y: Position
              - width, height: Resolution
              - is_primary: Whether this is the primary monitor
    """
    if not SCREENINFO_AVAILABLE:
        logger.warning("screeninfo not available, returning single default monitor")
        return [{
            'index': 0,
            'name': 'Monitor 1',
            'x': 0,
            'y': 0,
            'width': 1920,
            'height': 1080,
            'is_primary': True
        }]
    
    try:
        monitors = get_monitors()
        
        # Log detected monitors for debugging
        logger.info(f"🖥️ Detected {len(monitors)} monitor(s):")
        for i, m in enumerate(monitors):
            logger.info(f"  Monitor {i}: {getattr(m, 'name', 'Unknown')} @ {m.x},{m.y} - {m.width}x{m.height} (primary: {getattr(m, 'is_primary', i == 0)})")
        
        return [
            {
                'index': i,
                'name': getattr(m, 'name', f'Monitor {i+1}'),
                'x': m.x,
                'y': m.y,
                'width': m.width,
                'height': m.height,
                'is_primary': getattr(m, 'is_primary', i == 0)
            }
            for i, m in enumerate(monitors)
        ]
    
    except Exception as e:
        logger.error(f"❌ Failed to detect monitors: {e}", exc_info=True)
        return [{
            'index': 0,
            'name': 'Monitor 1',
            'x': 0,
            'y': 0,
            'width': 1920,
            'height': 1080,
            'is_primary': True
        }]


def get_monitor_by_index(index: int) -> Dict:
    """
    Get specific monitor by index
    
    Args:
        index: Monitor index
        
    Returns:
        dict: Monitor information
    """
    monitors = get_available_monitors()
    
    if 0 <= index < len(monitors):
        return monitors[index]
    
    logger.warning(f"Monitor index {index} out of range, using primary monitor")
    return monitors[0] if monitors else {
        'index': 0,
        'name': 'Monitor 1',
        'x': 0,
        'y': 0,
        'width': 1920,
        'height': 1080,
        'is_primary': True
    }
