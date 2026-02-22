import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/assist': 'http://localhost:8000',
      '/evaluate': 'http://localhost:8000',
      '/evaluate-files': 'http://localhost:8000',
      '/samples': 'http://localhost:8000',
      '/health': 'http://localhost:8000'
    }
  }
});
