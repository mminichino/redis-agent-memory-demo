import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#0A0D12",
        panel: "#111721",
        panelMuted: "#151D29",
        border: "#202C3A",
        foreground: "#E5E7EB",
        muted: "#9CA3AF",
        brand: "#3B82F6",
        success: "#22C55E",
        danger: "#EF4444"
      },
      boxShadow: {
        panel: "0 8px 30px rgba(5, 10, 20, 0.24)"
      }
    }
  },
  plugins: [typography]
};

export default config;
