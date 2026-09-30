/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./*/templates/**/*.html",
    "./*/templatetags/*.py",
    "./*/forms.py",
    "./static/js/**/*.js",
  ],
  theme: {
    container: { center: true, padding: "1rem", screens: { "2xl": "1232px" } },
    extend: {
      colors: {
        ink: { DEFAULT: "#110b08", 2: "#170f0b", 3: "#1d140f" },
        line: { DEFAULT: "rgba(196,132,84,.2)", strong: "rgba(196,132,84,.38)" },
        copper: { DEFAULT: "#c47a45", dark: "#8a4119" },
        gold: { DEFAULT: "#e7b98c", soft: "#d8a77a" },
        cream: "#f0dcc6",
        body: "#dccab8",
        muted: "#9b8574",
        danger: "#e0806a",
        success: "#9cc28a",
      },
      fontFamily: {
        sans: ["Vazirmatn", "Tahoma", "sans-serif"],
        display: ["Aref Ruqaa", "Vazirmatn", "serif"],
      },
      boxShadow: { luxe: "0 18px 40px rgba(0,0,0,.45)" },
    },
  },
  plugins: [],
};
