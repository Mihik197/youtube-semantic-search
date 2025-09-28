import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    base: '/static/react/',
    build: {
        outDir: '../static/react',
        emptyOutDir: true,
    },
    server: {
        host: true,
        port: 5173,
        proxy: {
            '/search': {
                target: 'http://localhost:5000',
                changeOrigin: true,
            },
            '/channels': {
                target: 'http://localhost:5000',
                changeOrigin: true,
            },
            '/channel_videos': {
                target: 'http://localhost:5000',
                changeOrigin: true,
            },
            '/topics': {
                target: 'http://localhost:5000',
                changeOrigin: true,
            },
            '/app-config': {
                target: 'http://localhost:5000',
                changeOrigin: true,
            },
        },
    },
    preview: {
        port: 4173,
    },
})
