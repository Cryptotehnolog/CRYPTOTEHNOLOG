import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { vanillaExtractPlugin } from "@vanilla-extract/vite-plugin";
export default defineConfig({
    plugins: [react(), vanillaExtractPlugin()],
    server: {
        host: "127.0.0.1",
        port: 5173,
        proxy: {
            "/dashboard": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
            },
        },
    },
    preview: {
        host: "127.0.0.1",
        port: 4173,
    },
});
