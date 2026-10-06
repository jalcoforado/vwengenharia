import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "VW Engenharia",
        short_name: "VW Engenharia",
        description: "Gestao operacional de campo",
        display: "standalone",
        start_url: "/",
        theme_color: "#111827",
        background_color: "#ffffff"
      }
    })
  ]
});
