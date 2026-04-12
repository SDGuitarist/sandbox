const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

function createDb(dbPath) {
  if (!dbPath) {
    dbPath = process.env.DATABASE_PATH || path.join(__dirname, 'data', 'app.db');
  }

  if (dbPath !== ':memory:') {
    fs.mkdirSync(path.dirname(dbPath), { recursive: true });
  }

  const db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');

  const schema = fs.readFileSync(path.join(__dirname, 'schema.sql'), 'utf-8');
  db.exec(schema);

  return db;
}

function createTestDb() {
  return createDb(':memory:');
}

module.exports = { createDb, createTestDb };
