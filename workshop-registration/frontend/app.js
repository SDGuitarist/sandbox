const express = require('express');
const path = require('path');
const helmet = require('helmet');
const compression = require('compression');
const flaskProxy = require('./middleware/flask-proxy');

function createApp() {
  const app = express();

  app.set('view engine', 'ejs');
  app.set('views', path.join(__dirname, 'views'));

  app.use(express.static(path.join(__dirname, 'public')));

  app.use(helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'", "cdn.jsdelivr.net", "'unsafe-inline'"],
        styleSrc: ["'self'", "'unsafe-inline'"],
        connectSrc: ["'self'", "wss://*.supabase.co", "https://*.supabase.co"],
      }
    }
  }));
  app.use(compression());

  app.use(flaskProxy);

  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  app.get('/register', (req, res) => {
    res.render('register');
  });

  app.get('/register/success', (req, res) => {
    res.render('success', { registrant_id: req.query.registrant_id || null });
  });

  try {
    const adminRoutes = require('./routes/admin');
    app.use('/admin', adminRoutes);
  } catch (err) {
    // Admin routes not available yet
  }

  app.use((req, res) => {
    if (req.path.startsWith('/api')) {
      return res.status(404).json({ error: 'Not found', code: 'NOT_FOUND' });
    }
    res.status(404).send('<!DOCTYPE html><html><head><title>404</title></head><body><h1>Page Not Found</h1><p>The page you are looking for does not exist.</p></body></html>');
  });

  app.use((err, req, res, next) => {
    console.error(err.stack);
    if (req.path.startsWith('/api')) {
      return res.status(500).json({ error: 'Internal server error', code: 'INTERNAL_ERROR' });
    }
    res.status(500).send('<!DOCTYPE html><html><head><title>500</title></head><body><h1>Internal Server Error</h1></body></html>');
  });

  return app;
}

module.exports = { createApp };
