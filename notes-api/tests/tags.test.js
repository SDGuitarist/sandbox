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

describe('GET /api/tags', () => {
  test('returns empty array when no tags exist', async () => {
    const res = await request(app).get('/api/tags');
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ tags: [] });
  });

  test('returns all tags ordered by name', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('beta');
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('alpha');
    const res = await request(app).get('/api/tags');
    expect(res.status).toBe(200);
    expect(res.body.tags).toHaveLength(2);
    expect(res.body.tags[0].name).toBe('alpha');
    expect(res.body.tags[1].name).toBe('beta');
  });
});

describe('POST /api/tags', () => {
  test('creates a tag and returns its id', async () => {
    const res = await request(app).post('/api/tags').send({ name: 'urgent' });
    expect(res.status).toBe(201);
    expect(typeof res.body.id).toBe('number');
  });

  test('returns 400 when name is missing', async () => {
    const res = await request(app).post('/api/tags').send({});
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Name must be a string');
  });

  test('returns 400 when name is not a string', async () => {
    const res = await request(app).post('/api/tags').send({ name: 123 });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Name must be a string');
  });

  test('returns 400 when name is empty after trim', async () => {
    const res = await request(app).post('/api/tags').send({ name: '   ' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Name is required');
  });

  test('returns 400 when name exceeds 50 characters', async () => {
    const res = await request(app).post('/api/tags').send({ name: 'a'.repeat(51) });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Name must be 50 characters or less');
  });

  test('returns 409 when tag name already exists', async () => {
    await request(app).post('/api/tags').send({ name: 'urgent' });
    const res = await request(app).post('/api/tags').send({ name: 'urgent' });
    expect(res.status).toBe(409);
    expect(res.body.error).toBe('Tag name already exists');
  });
});

describe('GET /api/tags/:id', () => {
  test('returns a tag by id', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('urgent');
    const res = await request(app).get('/api/tags/1');
    expect(res.status).toBe(200);
    expect(res.body.tag.name).toBe('urgent');
    expect(res.body.tag.id).toBe(1);
  });

  test('returns 404 when tag does not exist', async () => {
    const res = await request(app).get('/api/tags/999');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Tag not found');
  });

  test('returns 400 for invalid id', async () => {
    const res = await request(app).get('/api/tags/abc');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid ID');
  });
});

describe('PUT /api/tags/:id', () => {
  test('updates a tag and returns the updated tag', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('old-name');
    const res = await request(app).put('/api/tags/1').send({ name: 'new-name' });
    expect(res.status).toBe(200);
    expect(res.body.tag.name).toBe('new-name');
    expect(res.body.tag.id).toBe(1);
  });

  test('returns 404 when tag does not exist', async () => {
    const res = await request(app).put('/api/tags/999').send({ name: 'new-name' });
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Tag not found');
  });

  test('returns 400 for invalid id', async () => {
    const res = await request(app).put('/api/tags/abc').send({ name: 'new-name' });
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid ID');
  });

  test('returns 409 when updating to a duplicate name', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('alpha');
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('beta');
    const res = await request(app).put('/api/tags/2').send({ name: 'alpha' });
    expect(res.status).toBe(409);
    expect(res.body.error).toBe('Tag name already exists');
  });
});

describe('DELETE /api/tags/:id', () => {
  test('deletes a tag and returns 204', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('urgent');
    const res = await request(app).delete('/api/tags/1');
    expect(res.status).toBe(204);
    expect(res.body).toEqual({});
  });

  test('returns 404 when tag does not exist', async () => {
    const res = await request(app).delete('/api/tags/999');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Tag not found');
  });

  test('returns 400 for invalid id', async () => {
    const res = await request(app).delete('/api/tags/abc');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid ID');
  });

  test('cascades delete to note_tags', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('urgent');
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('test', 'content');
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(1, 1);
    await request(app).delete('/api/tags/1');
    const rows = db.prepare('SELECT * FROM note_tags WHERE tag_id = ?').all(1);
    expect(rows).toHaveLength(0);
  });
});

describe('GET /api/tags/:id/notes', () => {
  test('returns notes for a tag', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('urgent');
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note 1', 'Content 1');
    db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run('Note 2', 'Content 2');
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(1, 1);
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(2, 1);
    const res = await request(app).get('/api/tags/1/notes');
    expect(res.status).toBe(200);
    expect(res.body.notes).toHaveLength(2);
    expect(res.body.notes[0]).toHaveProperty('id');
    expect(res.body.notes[0]).toHaveProperty('title');
    expect(res.body.notes[0]).toHaveProperty('content');
    expect(res.body.notes[0]).toHaveProperty('created_at');
    expect(res.body.notes[0]).toHaveProperty('updated_at');
  });

  test('returns empty array when tag has no notes', async () => {
    db.prepare('INSERT INTO tags (name) VALUES (?)').run('urgent');
    const res = await request(app).get('/api/tags/1/notes');
    expect(res.status).toBe(200);
    expect(res.body.notes).toEqual([]);
  });

  test('returns 404 when tag does not exist', async () => {
    const res = await request(app).get('/api/tags/999/notes');
    expect(res.status).toBe(404);
    expect(res.body.error).toBe('Tag not found');
  });

  test('returns 400 for invalid id', async () => {
    const res = await request(app).get('/api/tags/abc/notes');
    expect(res.status).toBe(400);
    expect(res.body.error).toBe('Invalid ID');
  });
});
