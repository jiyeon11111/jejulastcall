import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// /api 요청은 FastAPI(8000)로 넘긴다
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: { "/api": "http://localhost:8000" },
  },
});
