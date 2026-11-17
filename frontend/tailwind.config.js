const c = (name) => `rgb(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: c('bg'), // Deep Graphite
        panel: c('panel'), // Midnight Navy
        surface: c('surface'), // Secondary Surface
        elevated: c('elevated'), // Elevated Surface
        line: c('line'), // Subtle Steel
        ink: c('ink'),
        mute: c('mute'),
        cyan: c('cyan'),
        emerald: c('emerald'),
        violet: c('violet'),
        amber: c('amber'),
        bull: c('bull'),
        bear: c('bear'),
      },
      fontFamily: {
        sans: ['Inter', 'IBM Plex Sans Arabic', 'system-ui', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      keyframes: {
        slideUp: { from: { transform: 'translateY(24px)', opacity: '0' }, to: { transform: 'none', opacity: '1' } },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
      },
      animation: {
        slideUp: 'slideUp 200ms ease-out',
        fadeIn: 'fadeIn 150ms ease-out',
      },
    },
  },
  plugins: [],
};
