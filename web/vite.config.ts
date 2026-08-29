import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite replacement for the retired create-react-app toolchain.
// - `npm start` / `npm run dev` runs the dev server (honours PORT, binds 0.0.0.0
//   so the Docker/nginx setups keep working unchanged).
// - `npm run build` emits static assets to build/.
// - REACT_APP_API_BASE_URL keeps working via the define shim below, so
//   src/config/appConfig.ts and local_runner env injection are untouched.
export default defineConfig({
  plugins: [react()],
  // @mui/icons-material has no package.json "exports" map, so deep imports
  // like `@mui/icons-material/Menu` resolve to the CJS file. Vite 8's
  // rolldown-based dep optimizer then wraps the CJS module in a way that
  // yields a double-nested `default` (the memo component sits at
  // `mod.default.default`), which crashes React with "Element type is
  // invalid ... got: object" (white screen). Redirect deep icon imports to
  // the package's ESM build (./esm/*.js) so they keep their real shape.
  resolve: {
    alias: [
      {
        find: /^@mui\/icons-material\/(.+)\.js$/,
        replacement: fileURLToPath(
          new URL("./node_modules/@mui/icons-material/esm/$1.js", import.meta.url),
        ),
      },
      {
        find: /^@mui\/icons-material\/(.+)$/,
        replacement: fileURLToPath(
          new URL("./node_modules/@mui/icons-material/esm/$1.js", import.meta.url),
        ),
      },
    ],
  },
  // REACT_APP_* vars are exposed in both dev and build (Vite injects
  // import.meta.env.REACT_APP_*), so Dockerfile build-time injection and the
  // local runner env injection keep working. The old `define` shim is kept
  // only as a build-time fallback for any straggling process.env readers.
  envPrefix: "REACT_APP_",
  define: {
    "process.env.REACT_APP_API_BASE_URL": JSON.stringify(
      process.env.REACT_APP_API_BASE_URL ?? "/api"
    ),
  },
  server: {
    host: true,
    port: Number(process.env.PORT ?? 3000),
    strictPort: true,
    allowedHosts: true,
    // Local development: forward API calls to the orchestrator service so the
    // default '/api' base URL works without nginx or REACT_APP_API_BASE_URL.
    proxy: {
      "/api": {
        target: process.env.ORCHESTRATOR_URL ?? "http://127.0.0.1:8009",
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api/, ""),
      },
    },
  },
  build: {
    outDir: "build",
  },
  publicDir: "public",
});
