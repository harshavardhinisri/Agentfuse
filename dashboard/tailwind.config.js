/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        green: {
          500: "#10B981",
          600: "#059669",
        },
        yellow: {
          500: "#F59E0B",
          600: "#D97706",
        },
        red: {
          500: "#EF4444",
          600: "#DC2626",
        },
      },
    },
  },
  plugins: [],
};
