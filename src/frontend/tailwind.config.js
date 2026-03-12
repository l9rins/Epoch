/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'midnight': '#0B1120',
        'midnight-light': '#1e293b'
      }
    },
  },
  plugins: [],
}
