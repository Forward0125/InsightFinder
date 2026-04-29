import type { Config } from 'tailwindcss'
import typography from '@tailwindcss/typography'

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './providers/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ─── Colors via CSS variables ──────────────────────────────
      colors: {
        background:      'rgb(var(--color-background) / <alpha-value>)',
        surface:         'rgb(var(--color-surface) / <alpha-value>)',
        'surface-high':  'rgb(var(--color-surface-high) / <alpha-value>)',
        foreground:      'rgb(var(--color-foreground) / <alpha-value>)',
        'foreground-2':  'rgb(var(--color-foreground-2) / <alpha-value>)',
        'foreground-3':  'rgb(var(--color-foreground-3) / <alpha-value>)',
        border:          'rgb(var(--color-border) / <alpha-value>)',
        'accent-blue':   'rgb(var(--color-accent-blue) / <alpha-value>)',
        'accent-violet': 'rgb(var(--color-accent-violet) / <alpha-value>)',
        'accent-warm':   'rgb(var(--color-accent-warm) / <alpha-value>)',
      },

      // ─── Typography ────────────────────────────────────────────
      fontFamily: {
        sans:    ['var(--font-inter)',           'system-ui', 'sans-serif'],
        display: ['var(--font-space-grotesk)',   'system-ui', 'sans-serif'],
        mono:    ['var(--font-jetbrains-mono)',  'ui-monospace', 'monospace'],
      },

      // ─── Backgrounds ───────────────────────────────────────────
      backgroundImage: {
        'gradient-accent':
          'linear-gradient(135deg, rgb(var(--color-accent-blue)), rgb(var(--color-accent-warm)))',
        'gradient-accent-subtle':
          'linear-gradient(135deg, rgb(var(--color-accent-blue) / 0.12), rgb(var(--color-accent-warm) / 0.08))',
      },

      // ─── Animations ────────────────────────────────────────────
      animation: {
        'fade-in':    'fadeIn 0.4s ease-out both',
        'fade-up':    'fadeUp 0.5s ease-out both',
        'fade-up-sm': 'fadeUpSm 0.4s ease-out both',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        fadeUpSm: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },

      transitionTimingFunction: {
        spring: 'cubic-bezier(0.175, 0.885, 0.32, 1.275)',
      },
    },
  },
  plugins: [typography],
}

export default config
