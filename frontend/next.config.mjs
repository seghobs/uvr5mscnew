/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
      {
        source: '/output/:path*',
        destination: 'http://127.0.0.1:8000/output/:path*',
      },
      {
        source: '/models',
        destination: 'http://127.0.0.1:8000/models',
      },
      {
        source: '/model_status/:path*',
        destination: 'http://127.0.0.1:8000/model_status/:path*',
      },
      {
        source: '/download_model',
        destination: 'http://127.0.0.1:8000/download_model',
      },
      {
        source: '/upload',
        destination: 'http://127.0.0.1:8000/upload',
      },
      {
        source: '/download',
        destination: 'http://127.0.0.1:8000/download',
      },
      {
        source: '/search',
        destination: 'http://127.0.0.1:8000/search',
      },
      {
        source: '/separate',
        destination: 'http://127.0.0.1:8000/separate',
      },
      {
        source: '/ensemble',
        destination: 'http://127.0.0.1:8000/ensemble',
      },
      {
        source: '/status/:path*',
        destination: 'http://127.0.0.1:8000/status/:path*',
      },
      {
        source: '/modify_audio',
        destination: 'http://127.0.0.1:8000/modify_audio',
      },
      {
        source: '/remix',
        destination: 'http://127.0.0.1:8000/remix',
      },
      {
        source: '/batch',
        destination: 'http://127.0.0.1:8000/batch',
      },
      {
        source: '/leaderboard',
        destination: 'http://127.0.0.1:8000/leaderboard',
      },
      {
        source: '/analyze_audio',
        destination: 'http://127.0.0.1:8000/analyze_audio',
      },
      {
        source: '/transcribe_lyrics',
        destination: 'http://127.0.0.1:8000/transcribe_lyrics',
      },
      {
        source: '/quick_clean',
        destination: 'http://127.0.0.1:8000/quick_clean',
      },
      {
        source: '/generate_visualizer',
        destination: 'http://127.0.0.1:8000/generate_visualizer',
      },
      {
        source: '/generate_karaoke_video',
        destination: 'http://127.0.0.1:8000/generate_karaoke_video',
      },
      {
        source: '/whisper_status',
        destination: 'http://127.0.0.1:8000/whisper_status',
      },
      {
        source: '/download_whisper',
        destination: 'http://127.0.0.1:8000/download_whisper',
      },
      {
        source: '/save_lyrics',
        destination: 'http://127.0.0.1:8000/save_lyrics',
      },
      {
        source: '/lyrics/:path*',
        destination: 'http://127.0.0.1:8000/lyrics/:path*',
      },
      {
        source: '/restore_audio',
        destination: 'http://127.0.0.1:8000/restore_audio',
      },
      {
        source: '/clear_memory',
        destination: 'http://127.0.0.1:8000/clear_memory',
      },
      {
        source: '/shutdown',
        destination: 'http://127.0.0.1:8000/shutdown',
      },
    ];
  },
};

export default nextConfig;
