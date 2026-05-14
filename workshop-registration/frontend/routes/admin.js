var express = require('express');
var router = express.Router();
var basicAuth = require('../middleware/auth');

router.use(basicAuth);

router.get('/', function (req, res) {
  res.render('admin/dashboard');
});

module.exports = router;
