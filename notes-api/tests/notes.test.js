const createApp = require('../app');
const { createTestDb } = require('../db');
const request = require('supertest');

let db;
let app;

beforeEach(() => {
  db = createTestDb();
  app = createApp(db);
});

afterEach(() => {
  db.close();
});

describe('GET /api/notes', () => {
  test('returns empty array when no notes exist', async () => {
    const res = await request(app).get('/api/notes');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ notes: [] });
  });

  test('returns populated array of notes', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note 1', 'Content 1');
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note 2', 'Content 2');

    const res = await request(app).get('/api/notes');
    expect(res.status).toBe(200);
    expect(res.body.notes).toHaveLength(2);
    expect(res.body.notes[0]).toHaveProperty('title');
    expect(res.body.notes[0]).toHaveProperty('content');
  });
});

describe('POST /api/notes', () => {
  test('creates a note with valid data', async () => {
    const res = await request(app)
      .post('/api/notes')
      .send({ title: 'Test Note', content: 'Test content' });
    expect(res.status).toBe(201);
    expect(res.body).toHaveProperty('id');
    expect(typeof res.body.id).toBe('number');
  });

  test('returns 400 when title is missing', async () => {
    const res = await request(app)
      .post('/api/notes')
      .send({ content: 'No title' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Title must be a string');
  });

  test('returns 400 when title is not a string', async () => {
    const res = await request(app)
      .post('/api/notes')
      .send({ title: 123 });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Title must be a string');
  });

  test('returns 400 when title is empty after trim', async () => {
    const res = await request(app)
      .post('/api/notes')
      .send({ title: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Title is required');
  });

  test('returns 400 when title exceeds 200 characters', async () => {
    const res = await request(app)
      .post('/api/notes')
      .send({ title: 'a'.repeat(201) });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Title must be 200 characters or less');
  });
});

describe('GET /api/notes/:id', () => {
  test('returns note with tags when found', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('My Note', 'My content');

    const res = await request(app).get('/api/notes/1');
    expect(res.status).toBe(200);
    expect(res.body.note.title).toBe('My Note');
    expect(res.body.note.content).toBe('My content');
    expect(res.body.note.tags).toEqual([]);
  });

  test('returns 404 when note not found', async () => {
    const res = await request(app).get('/api/notes/999');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Note not found');
  });

  test('returns 400 for invalid ID', async () => {
    const res = await request(app).get('/api/notes/abc');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid ID');
  });
});

describe('PUT /api/notes/:id', () => {
  test('updates an existing note', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Old Title', 'Old content');

    const res = await request(app)
      .put('/api/notes/1')
      .send({ title: 'New Title', content: 'New content' });
    expect(res.status).toBe(200);
    expect(res.body.note.title).toBe('New Title');
    expect(res.body.note.content).toBe('New content');
  });

  test('returns 404 when note does not exist', async () => {
    const res = await request(app)
      .put('/api/notes/999')
      .send({ title: 'Title', content: 'Content' });
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Note not found');
  });
});

describe('DELETE /api/notes/:id', () => {
  test('deletes an existing note', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('To Delete', 'Content');

    const res = await request(app).delete('/api/notes/1');
    expect(res.status).toBe(204);

    const check = await request(app).get('/api/notes/1');
    expect(check.status).toBe(404);
  });

  test('cascades deletion to note_tags', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');
    db.prepare("INSERT INTO tags (name) VALUES (?)").run('test-tag');
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(1, 1);

    await request(app).delete('/api/notes/1');

    const rows = db.prepare('SELECT * FROM note_tags WHERE note_id = ?').all(1);
    expect(rows).toHaveLength(0);
  });

  test('returns 404 when note does not exist', async () => {
    const res = await request(app).delete('/api/notes/999');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Note not found');
  });
});

describe('POST /api/notes/:id/tags', () => {
  test('adds a tag to a note', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');
    db.prepare("INSERT INTO tags (name) VALUES (?)").run('test-tag');

    const res = await request(app)
      .post('/api/notes/1/tags')
      .send({ tag_id: 1 });
    expect(res.status).toBe(201);
    expect(res.body).toEqual({ note_id: 1, tag_id: 1 });
  });

  test('returns 409 when tag is already assigned', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');
    db.prepare("INSERT INTO tags (name) VALUES (?)").run('test-tag');
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(1, 1);

    const res = await request(app)
      .post('/api/notes/1/tags')
      .send({ tag_id: 1 });
    expect(res.status).toBe(409);
    expect(res.body.error).toBe('Tag already assigned to this note');
  });

  test('returns 404 when note does not exist', async () => {
    db.prepare("INSERT INTO tags (name) VALUES (?)").run('test-tag');

    const res = await request(app)
      .post('/api/notes/999/tags')
      .send({ tag_id: 1 });
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Note not found');
  });

  test('returns 400 when tag_id is missing', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');

    const res = await request(app)
      .post('/api/notes/1/tags')
      .send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('tag_id must be a number');
  });

  test('returns 400 when tag_id is invalid', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');

    const res = await request(app)
      .post('/api/notes/1/tags')
      .send({ tag_id: -1 });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid tag_id');
  });
});

describe('DELETE /api/notes/:id/tags/:tagId', () => {
  test('removes a tag from a note', async () => {
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note', 'Content');
    db.prepare("INSERT INTO tags (name) VALUES (?)").run('test-tag');
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(1, 1);

    const res = await request(app).delete('/api/notes/1/tags/1');
    expect(res.status).toBe(204);

    const rows = db.prepare('SELECT * FROM note_tags WHERE note_id = 1 AND tag_id = 1').all();
    expect(rows).toHaveLength(0);
  });

  test('succeeds silently when tag is not assigned', async () => {
    const res = await request(app).delete('/api/notes/1/tags/1');
    expect(res.status).toBe(204);
  });
});
