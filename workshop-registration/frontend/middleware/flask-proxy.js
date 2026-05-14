const { createProxyMiddleware } = require('http-proxy-middleware');

const FLASK_URL = process.env.FLASK_API_URL || 'http://127.0.0.1:5000';

const flaskProxy = createProxyMiddleware({
  target: FLASK_URL,
  pathFilter: '/api',
  changeOrigin: true,
  timeout: 30000,
  proxyTimeout: 30000,
  xfwd: true,
  on: {
    error: (err, req, res) => {
      if (res.headersSent) return;
      const status = err.code === 'ECONNREFUSED' ? 502
        : (err.code === 'ETIMEDOUT' ? 504 : 502);
      res.status(status).json({ error: 'API server unavailable', code: err.code });
    }
  }
});

module.exports = flaskProxy;
