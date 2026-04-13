/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   '#0a0c12',
          secondary: '#10131c',
          card:      '#161a26',
          hover:     '#1c2133',
          active:    '#1e2538',
        },
        border: {
          DEFAULT: '#1e2538',
          light:   '#252d42',
        },
        text: {
          primary:   '#e8edf5',
          secondary: '#8892a8',
          muted:     '#50586a',
        },
        accent: {
          indigo:  '#6366f1',
          blue:    '#3b82f6',
          cyan:    '#22d3ee',
          green:   '#10b981',
          amber:   '#f59e0b',
          red:     '#ef4444',
          purple:  '#8b5cf6',
          pink:    '#ec4899',
        },
      },
      fontFamily: {
        sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
      boxShadow: {
        card:    '0 1px 3px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.04)',
        glow:    '0 0 20px rgba(99,102,241,0.15)',
        'glow-green': '0 0 20px rgba(16,185,129,0.15)',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-dot': 'pulseDot 2s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:   { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:  { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        pulseDot: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.4 } },
      },
    },
  },
  plugins: [],
}
