const express = require('express');
const helmet = require('helmet');

function createApp(db) {
  if (!db) throw new Error('db argument is required');

  const app = express();
  app.locals.db = db;

  app.use(helmet());
  app.use(express.json({ limit: '50kb' }));

  app.use('/api/notes', require('./routes/notes'));
  app.use('/api/tags', require('./routes/tags'));

  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  app.use((err, req, res, next) => {
    console.error(err.stack);
    const status = err.status || 500;
    const message = status === 500 ? 'Internal server error' : err.message;
    res.status(status).json({ error: message });
  });

  return app;
}

module.exports = createApp;
