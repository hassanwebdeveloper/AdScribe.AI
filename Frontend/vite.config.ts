import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";
import { nodePolyfills } from 'vite-plugin-node-polyfills';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => {
          // Ensure paths to the API have trailing slashes
          if (path.endsWith('/')) {
            return path;
          } else if (path.includes('?')) {
            // If the path has query parameters, add the slash before them
            const [pathPart, queryPart] = path.split('?');
            return `${pathPart}/?${queryPart}`;
          } else {
            return `${path}/`;
          }
        }
      }
    }
  },
  plugins: [
    react(),
    nodePolyfills({
      // Whether to polyfill specific globals.
      globals: {
        Buffer: true,
        global: true,
        process: true,
      },
      // Whether to polyfill `node:` protocol imports.
      protocolImports: true,
    }),
    mode === 'development' &&
    componentTagger(),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  define: {
    // Fix for Plotly.js
    'process.env': {},
    'global': {}
  }
}));
