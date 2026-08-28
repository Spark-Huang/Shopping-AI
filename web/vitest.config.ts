import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
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
  test: {
    environment: "jsdom",
    globals: false,
    restoreMocks: true,
  },
});
