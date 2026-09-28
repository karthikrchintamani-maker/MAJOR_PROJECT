/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        darkbg: '#07111F',
        sidebarbg: '#0B1728',
        cardbg: '#101F33',
        cardhover: '#162A43',
        borderblue: '#263B55',
        primaryaccent: '#00A8FF',
        secondaryaccent: '#00E5FF',
        successgreen: '#22C55E',
        warningamber: '#F59E0B',
        criticalred: '#FF3B4D',
        lidarorange: '#FF9F1C',
        riskscore: '#FF3D81',
        textlight: '#F8FAFC',
        textgrey: '#94A3B8',
      }
    },
  },
  plugins: [],
}
