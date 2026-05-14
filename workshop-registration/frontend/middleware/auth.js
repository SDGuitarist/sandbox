var crypto = require('crypto');

function basicAuth(req, res, next) {
  var auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Basic ')) {
    res.set('WWW-Authenticate', 'Basic realm="Admin"');
    return res.status(401).json({ error: 'Authentication required', code: 'UNAUTHORIZED' });
  }

  var decoded = Buffer.from(auth.slice(6), 'base64').toString();
  var password = decoded.split(':').slice(1).join(':');

  var expected = process.env.ADMIN_PASSWORD || '';
  if (password.length !== expected.length || !crypto.timingSafeEqual(Buffer.from(password), Buffer.from(expected))) {
    res.set('WWW-Authenticate', 'Basic realm="Admin"');
    return res.status(401).json({ error: 'Invalid credentials', code: 'UNAUTHORIZED' });
  }

  next();
}

module.exports = basicAuth;
