/**
 * Stroke Font Definition - Vektorbasierte Buchstaben
 * Koordinaten normalisiert auf 0-100 Einheiten (Breite) x 0-140 (Höhe mit Unterlängen)
 * Baseline bei y=100, Caps bei y=0, Descender bis y=140
 */

const STROKE_FONT = {
  // Großbuchstaben
  'A': [
    { type: 'line', points: [[20, 100], [50, 0], [80, 100]] },
    { type: 'line', points: [[35, 60], [65, 60]] }
  ],
  'B': [
    { type: 'line', points: [[20, 100], [20, 0]] },
    { type: 'arc', center: [50, 25], radius: 30, startAngle: -90, endAngle: 90 },
    { type: 'arc', center: [50, 75], radius: 30, startAngle: -90, endAngle: 90 }
  ],
  'C': [
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 120, endAngle: -120 }
  ],
  'D': [
    { type: 'line', points: [[20, 100], [20, 0]] },
    { type: 'arc', center: [20, 50], radius: 50, startAngle: -90, endAngle: 90 }
  ],
  'E': [
    { type: 'line', points: [[70, 0], [20, 0], [20, 100], [70, 100]] },
    { type: 'line', points: [[20, 50], [60, 50]] }
  ],
  'F': [
    { type: 'line', points: [[70, 0], [20, 0], [20, 100]] },
    { type: 'line', points: [[20, 50], [60, 50]] }
  ],
  'G': [
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 135, endAngle: -90 },
    { type: 'line', points: [[50, 90], [90, 90], [90, 50], [55, 50]] }
  ],
  'H': [
    { type: 'line', points: [[20, 0], [20, 100]] },
    { type: 'line', points: [[80, 0], [80, 100]] },
    { type: 'line', points: [[20, 50], [80, 50]] }
  ],
  'I': [
    { type: 'line', points: [[30, 0], [70, 0]] },
    { type: 'line', points: [[50, 0], [50, 100]] },
    { type: 'line', points: [[30, 100], [70, 100]] }
  ],
  'J': [
    { type: 'line', points: [[70, 0], [70, 80]] },
    { type: 'arc', center: [50, 80], radius: 20, startAngle: 0, endAngle: 180 }
  ],
  'K': [
    { type: 'line', points: [[20, 0], [20, 100]] },
    { type: 'line', points: [[80, 0], [20, 50]] },
    { type: 'line', points: [[20, 50], [80, 100]] }
  ],
  'L': [
    { type: 'line', points: [[20, 0], [20, 100], [70, 100]] }
  ],
  'M': [
    { type: 'line', points: [[10, 100], [10, 0], [50, 40], [90, 0], [90, 100]] }
  ],
  'N': [
    { type: 'line', points: [[20, 100], [20, 0], [80, 100], [80, 0]] }
  ],
  'O': [
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 0, endAngle: 360 }
  ],
  'P': [
    { type: 'line', points: [[20, 100], [20, 0]] },
    { type: 'arc', center: [50, 25], radius: 30, startAngle: -90, endAngle: 90 }
  ],
  'Q': [
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 0, endAngle: 360 },
    { type: 'line', points: [[70, 70], [90, 100]] }
  ],
  'R': [
    { type: 'line', points: [[20, 100], [20, 0]] },
    { type: 'arc', center: [50, 25], radius: 30, startAngle: -90, endAngle: 90 },
    { type: 'line', points: [[50, 50], [80, 100]] }
  ],
  'S': [
    { type: 'arc', center: [50, 25], radius: 30, startAngle: 0, endAngle: 270 },
    { type: 'arc', center: [50, 75], radius: 30, startAngle: 180, endAngle: -90 }
  ],
  'T': [
    { type: 'line', points: [[20, 0], [80, 0]] },
    { type: 'line', points: [[50, 0], [50, 100]] }
  ],
  'U': [
    { type: 'line', points: [[20, 0], [20, 70]] },
    { type: 'arc', center: [50, 70], radius: 30, startAngle: 180, endAngle: 0 },
    { type: 'line', points: [[80, 70], [80, 0]] }
  ],
  'V': [
    { type: 'line', points: [[20, 0], [50, 100], [80, 0]] }
  ],
  'W': [
    { type: 'line', points: [[10, 0], [25, 100], [50, 50], [75, 100], [90, 0]] }
  ],
  'X': [
    { type: 'line', points: [[20, 0], [80, 100]] },
    { type: 'line', points: [[80, 0], [20, 100]] }
  ],
  'Y': [
    { type: 'line', points: [[20, 0], [50, 50]] },
    { type: 'line', points: [[80, 0], [50, 50]] },
    { type: 'line', points: [[50, 50], [50, 100]] }
  ],
  'Z': [
    { type: 'line', points: [[20, 0], [80, 0], [20, 100], [80, 100]] }
  ],

  // Zahlen
  '0': [
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 0, endAngle: 360 },
    { type: 'line', points: [[30, 30], [70, 70]] }
  ],
  '1': [
    { type: 'line', points: [[40, 20], [50, 0], [50, 100]] },
    { type: 'line', points: [[30, 100], [70, 100]] }
  ],
  '2': [
    { type: 'arc', center: [50, 25], radius: 25, startAngle: 180, endAngle: 0 },
    { type: 'line', points: [[75, 25], [20, 100], [80, 100]] }
  ],
  '3': [
    { type: 'arc', center: [50, 25], radius: 30, startAngle: 180, endAngle: 0 },
    { type: 'arc', center: [50, 75], radius: 30, startAngle: 180, endAngle: 0 }
  ],
  '4': [
    { type: 'line', points: [[60, 0], [20, 70], [80, 70]] },
    { type: 'line', points: [[60, 0], [60, 100]] }
  ],
  '5': [
    { type: 'line', points: [[70, 0], [20, 0], [20, 50]] },
    { type: 'arc', center: [50, 75], radius: 30, startAngle: 180, endAngle: -90 }
  ],
  '6': [
    { type: 'arc', center: [50, 75], radius: 30, startAngle: 0, endAngle: 360 },
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 180, endAngle: 270 }
  ],
  '7': [
    { type: 'line', points: [[20, 0], [80, 0], [40, 100]] }
  ],
  '8': [
    { type: 'arc', center: [50, 25], radius: 25, startAngle: 0, endAngle: 360 },
    { type: 'arc', center: [50, 75], radius: 25, startAngle: 0, endAngle: 360 }
  ],
  '9': [
    { type: 'arc', center: [50, 25], radius: 30, startAngle: 0, endAngle: 360 },
    { type: 'arc', center: [50, 50], radius: 40, startAngle: 90, endAngle: 0 }
  ],

  // Sonderzeichen
  ' ': [], // Leerzeichen
  '.': [
    { type: 'arc', center: [50, 95], radius: 5, startAngle: 0, endAngle: 360 }
  ],
  ',': [
    { type: 'line', points: [[50, 95], [45, 110]] }
  ],
  '!': [
    { type: 'line', points: [[50, 0], [50, 70]] },
    { type: 'arc', center: [50, 90], radius: 5, startAngle: 0, endAngle: 360 }
  ],
  '?': [
    { type: 'arc', center: [50, 20], radius: 25, startAngle: 180, endAngle: 0 },
    { type: 'line', points: [[75, 20], [75, 40], [50, 60]] },
    { type: 'arc', center: [50, 85], radius: 5, startAngle: 0, endAngle: 360 }
  ],
  '-': [
    { type: 'line', points: [[25, 50], [75, 50]] }
  ],
  '+': [
    { type: 'line', points: [[50, 20], [50, 80]] },
    { type: 'line', points: [[20, 50], [80, 50]] }
  ],
  '=': [
    { type: 'line', points: [[25, 40], [75, 40]] },
    { type: 'line', points: [[25, 60], [75, 60]] }
  ],
  '/': [
    { type: 'line', points: [[20, 100], [80, 0]] }
  ],
  '\\': [
    { type: 'line', points: [[20, 0], [80, 100]] }
  ],
  '(': [
    { type: 'arc', center: [70, 50], radius: 40, startAngle: 135, endAngle: -135 }
  ],
  ')': [
    { type: 'arc', center: [30, 50], radius: 40, startAngle: -45, endAngle: 45 }
  ],
  ':': [
    { type: 'arc', center: [50, 35], radius: 5, startAngle: 0, endAngle: 360 },
    { type: 'arc', center: [50, 75], radius: 5, startAngle: 0, endAngle: 360 }
  ]
};

// Buchstaben-Breiten (für Spacing)
const LETTER_WIDTHS = {
  'I': 60, '1': 60, '.': 40, ',': 40, '!': 40, ':': 40,
  'W': 120, 'M': 120,
  ' ': 50
};

// Standard-Breite falls nicht definiert
const DEFAULT_LETTER_WIDTH = 100;

// Letter Spacing
const DEFAULT_LETTER_SPACING = 20;
