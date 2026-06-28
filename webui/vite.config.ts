import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import vue from "@vitejs/plugin-vue";
import tailwindcss from "@tailwindcss/vite";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function buildFingerprint(): Plugin {
  const SRC_EXTS = new Set([".vue", ".ts", ".js", ".css", ".json", ".html"]);

  return {
    name: "build-fingerprint",
    apply: "build",
    closeBundle() {
      const srcDir = path.resolve(__dirname, "src");
      const distDir = path.resolve(__dirname, "dist");

      const relPaths: string[] = [];

      function collect(dir: string) {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const full = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            collect(full);
          } else if (entry.isFile() && SRC_EXTS.has(path.extname(entry.name))) {
            relPaths.push(path.relative(srcDir, full));
          }
        }
      }

      collect(srcDir);
      relPaths.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0));

      const hasher = crypto.createHash("sha256");
      for (const rel of relPaths) {
        hasher.update(rel);
        hasher.update(fs.readFileSync(path.join(srcDir, rel)));
      }

      fs.writeFileSync(
        path.join(distDir, ".build_fingerprint"),
        hasher.digest("hex"),
      );
    },
  };
}

export default defineConfig({
  plugins: [vue(), tailwindcss(), buildFingerprint()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
