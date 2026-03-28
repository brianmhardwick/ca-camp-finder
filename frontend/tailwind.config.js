/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{html,ts}",
  ],
  theme: {
    extend: {
      colors: {
        ocean: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        },
        navy: {
          950: '#060e1d',
          900: '#0a1628',
          800: '#0d1f3c',
          700: '#1a2d4a',
          600: '#1e3a5f',
          500: '#254d7a',
        }
      }
    },
  },
  plugins: [],
};
