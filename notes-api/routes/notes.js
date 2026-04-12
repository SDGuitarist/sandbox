const express = require('express');
const router = express.Router();
const {
  getAllNotes, getNoteById, createNote, updateNote, deleteNote,
  getTagsForNote, addTagToNote, removeTagFromNote
} = require('../models/notes');

router.get('/', (req, res) => {
  const db = req.app.locals.db;
  const notes = getAllNotes(db);
  res.json({ notes });
});

router.post('/', (req, res) => {
  const db = req.app.locals.db;

  if (typeof req.body.title !== 'string') {
    return res.status(400).json({ error: 'Title must be a string' });
  }
  const title = req.body.title.trim();
  if (!title) return res.status(400).json({ error: 'Title is required' });
  if (title.length > 200) return res.status(400).json({ error: 'Title must be 200 characters or less' });

  const rawContent = req.body.content;
  if (rawContent !== undefined && typeof rawContent !== 'string') {
    return res.status(400).json({ error: 'Content must be a string' });
  }
  const content = (rawContent || '').trim();
  if (content.length > 10000) return res.status(400).json({ error: 'Content must be 10000 characters or less' });

  const id = createNote(db, title, content);
  res.status(201).json({ id: Number(id) });
});

router.get('/:id', (req, res) => {
  const db = req.app.locals.db;

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  const note = getNoteById(db, id);
  if (!note) return res.status(404).json({ error: 'Note not found' });

  const tags = getTagsForNote(db, id);
  res.json({ note: { ...note, tags } });
});

router.put('/:id', (req, res) => {
  const db = req.app.locals.db;

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  if (typeof req.body.title !== 'string') {
    return res.status(400).json({ error: 'Title must be a string' });
  }
  const title = req.body.title.trim();
  if (!title) return res.status(400).json({ error: 'Title is required' });
  if (title.length > 200) return res.status(400).json({ error: 'Title must be 200 characters or less' });

  const rawContent = req.body.content;
  if (rawContent !== undefined && typeof rawContent !== 'string') {
    return res.status(400).json({ error: 'Content must be a string' });
  }
  const content = (rawContent || '').trim();
  if (content.length > 10000) return res.status(400).json({ error: 'Content must be 10000 characters or less' });

  const changes = updateNote(db, id, title, content);
  if (changes === 0) return res.status(404).json({ error: 'Note not found' });

  const note = getNoteById(db, id);
  res.json({ note });
});

router.delete('/:id', (req, res) => {
  const db = req.app.locals.db;

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  const changes = deleteNote(db, id);
  if (changes === 0) return res.status(404).json({ error: 'Note not found' });

  res.status(204).end();
});

router.post('/:id/tags', (req, res) => {
  const db = req.app.locals.db;

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  if (typeof req.body.tag_id !== 'number') {
    return res.status(400).json({ error: 'tag_id must be a number' });
  }
  const tagId = req.body.tag_id;
  if (!Number.isInteger(tagId) || tagId < 1) {
    return res.status(400).json({ error: 'Invalid tag_id' });
  }

  const note = getNoteById(db, id);
  if (!note) return res.status(404).json({ error: 'Note not found' });

  const inserted = addTagToNote(db, id, tagId);
  if (!inserted) return res.status(409).json({ error: 'Tag already assigned to this note' });

  res.status(201).json({ note_id: id, tag_id: tagId });
});

router.delete('/:id/tags/:tagId', (req, res) => {
  const db = req.app.locals.db;

  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  const tagId = Number(req.params.tagId);
  if (!Number.isInteger(tagId) || tagId < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }

  removeTagFromNote(db, id, tagId);
  res.status(204).end();
});

module.exports = router;
