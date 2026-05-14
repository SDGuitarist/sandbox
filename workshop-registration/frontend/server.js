require('dotenv').config();
const { createApp } = require('./app');
const app = createApp();
const PORT = process.env.EXPRESS_PORT || 3000;
app.listen(PORT, () => {
  console.log(`Express frontend running on port ${PORT}`);
});
