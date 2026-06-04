/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: '#0f1117',
        sidebar: '#1a1d27',
        card: '#1e2130',
        border: '#2a2d3e',
        primary: '#6366f1',
        'primary-hover': '#4f52d4',
        'text-primary': '#e2e8f0',
        'text-muted': '#64748b',
      },
    },
  },
  plugins: [],
}
