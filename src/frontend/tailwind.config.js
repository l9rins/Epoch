/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg:      '#080B0F',
          surface: '#0D1117',
          border:  '#1C2333',
          muted:   '#8B949E',
          text:    '#E6EDF3',
          accent:  '#58A6FF',
          green:   '#3FB950',
          red:     '#F85149',
          yellow:  '#D29922',
          orange:  '#DB6D28',
          purple:  '#BC8CFF',
        }
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
