function basicAuth(req, res, next) {
  var auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Basic ')) {
    res.set('WWW-Authenticate', 'Basic realm="Admin"');
    return res.status(401).json({ error: 'Authentication required', code: 'UNAUTHORIZED' });
  }

  var decoded = Buffer.from(auth.slice(6), 'base64').toString();
  var password = decoded.split(':').slice(1).join(':');

  if (password !== process.env.ADMIN_PASSWORD) {
    res.set('WWW-Authenticate', 'Basic realm="Admin"');
    return res.status(401).json({ error: 'Invalid credentials', code: 'UNAUTHORIZED' });
  }

  next();
}

module.exports = basicAuth;
