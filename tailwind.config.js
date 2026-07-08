/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        pitch: {
          50: '#f0faf4',
          100: '#d9f2e2',
          200: '#b4e4c8',
          300: '#82cea6',
          400: '#4fb17f',
          500: '#2d9463',
          600: '#1f7750',
          700: '#1a5f42',
          800: '#174c37',
          900: '#143f2e',
          950: '#0a2419',
        },
      },
      fontFamily: {
        display: ['"Fraunces Variable"', '"Fraunces"', 'serif'],
        sans: ['"Inter Variable"', '"Inter"', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 1px 2px rgba(10, 36, 25, 0.06), 0 4px 12px rgba(10, 36, 25, 0.08)',
        lifted: '0 8px 24px rgba(10, 36, 25, 0.16), 0 2px 6px rgba(10, 36, 25, 0.1)',
      },
    },
  },
  plugins: [],
}
