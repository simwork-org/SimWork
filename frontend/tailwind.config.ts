import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        primary: "#6467f2",
        "background-light": "#f6f6f8",
        "background-dark": "#101122"
      },
      fontFamily: {
        display: ["var(--font-inter)", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"]
      },
      boxShadow: {
        panel: "0 24px 60px rgba(15, 23, 42, 0.16)"
      }
    }
  },
  plugins: []
};

export default config;
