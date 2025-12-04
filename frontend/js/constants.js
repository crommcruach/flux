/**
 * Constants and Configuration
 * Zentrale Konstanten für den Editor
 */

// Scale limits
export const MIN_SCALE = 0.3;
export const MAX_SCALE = 10;

// Handle configuration
export const HANDLE = {
    SIZE: 7,
    DISTANCE: 26,
    DISTANCE_Y: 50,
    DISTANCE_SCALE_Y: 50,
    HIT_RADIUS: 12,
    CONTROL_RADIUS: 10,
    ICON_SIZE_MULTIPLIER: 3
};

// Colors
export const COLORS = {
    CONNECTION_LINE: 'red',
    HANDLE_CORNER_FILL: 'rgba(0, 255, 255, 0.3)',
    HANDLE_CORNER_STROKE: 'cyan',
    HANDLE_ICON_TINT: 'cyan',
    HANDLE_FLIP_FALLBACK: '#9933ff',
    HANDLE_ROTATE_FALLBACK: 'orange',
    HANDLE_SCALE_Y_FALLBACK: 'lime',
    CONTROL_HANDLE_PRIMARY: 'green',
    CONTROL_HANDLE_SECONDARY: 'darkgreen',
    CONTROL_HANDLE_TERTIARY: 'forestgreen',
    POINT_FIRST: 'cyan',
    POINT_LAST: 'magenta',
    POINT_DEFAULT: 'blue',
    POINT_HOVER: 'yellow',
    TOOLTIP_BG: 'rgba(0, 0, 0, 0.8)',
    TOOLTIP_BORDER: 'yellow',
    TOOLTIP_TEXT: 'white',
    SHAPE_DEFAULT: 'cyan'
};

// Tooltip configuration
export const TOOLTIP = {
    PADDING: 8,
    FONT_SIZE: 14,
    OFFSET_Y: 10,
    MIN_MARGIN: 5
};

// Point rendering
export const POINT = {
    RADIUS: 3,
    HIT_RADIUS: 8
};
