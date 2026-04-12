const createApp = require('./app');
const { createDb } = require('./db');

const PORT = process.env.PORT || 3000;
const db = createDb();
const app = createApp(db);

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
