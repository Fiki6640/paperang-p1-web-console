import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Flask 后端地址:本机开发默认 localhost:5000,连树莓派时设 VITE_API_TARGET=http://<pi-ip>:5000
const apiTarget = process.env.VITE_API_TARGET ?? "http://localhost:5000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: apiTarget, changeOrigin: true },
      "/weather": { target: apiTarget, changeOrigin: true },
      "/temp-chart": { target: apiTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
  },
});
