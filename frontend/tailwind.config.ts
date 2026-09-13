import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    {
      pattern: /(bg|text|border|ring|shadow|from|to)-(indigo|emerald|rose|amber|violet)-(400|500|600|700)/,
    },
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-inter)', 'sans-serif'],
        outfit: ['var(--font-outfit)', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: { xl: '1rem', '2xl': '1.5rem', '3xl': '2rem' },
      colors: {
        preset: 'rgb(var(--preset-accent, 183 161 245) / <alpha-value>)',
        indigo: { 300:'#d0c3ff',400:'#b7a1f5',500:'#9275d6',600:'#7252b5',700:'#5b3e94' },
        violet: { 300:'#ddc2f4',400:'#ca9fe9',500:'#ac74d1',600:'#8850ae',700:'#6e3c90' },
        rose: { 300:'#f3bbcc',400:'#e99ab4',500:'#d7658c',600:'#b7466d',700:'#953757' },
        emerald: { 300:'#ade0cf',400:'#81c8b2',500:'#45a98c',600:'#278368',700:'#226954' },
        slate: {
          850: '#292537',
          900: '#211e2c',
          950: '#14121c',
        },
      },
      animation: {
        'spin-slow': 'spin 3s linear infinite',
        'pulse-glow': 'pulseGlow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '1', filter: 'drop-shadow(0 0 8px rgba(99, 102, 241, 0.6))' },
          '50%': { opacity: '.6', filter: 'drop-shadow(0 0 2px rgba(99, 102, 241, 0.2))' },
        },
      },
    },
  },
  plugins: [],
};
export default config;
