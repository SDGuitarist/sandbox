const express = require('express');
const router = express.Router();
const { getAllTags, getTagById, createTag, updateTag, deleteTag, getNotesForTag } = require('../models/tags');

router.get('/', (req, res) => {
  const db = req.app.locals.db;
  const tags = getAllTags(db);
  res.json({ tags });
});

router.post('/', (req, res) => {
  const db = req.app.locals.db;
  if (typeof req.body.name !== 'string') {
    return res.status(400).json({ error: 'Name must be a string' });
  }
  const name = req.body.name.trim();
  if (!name) return res.status(400).json({ error: 'Name is required' });
  if (name.length > 50) return res.status(400).json({ error: 'Name must be 50 characters or less' });
  try {
    const tagId = createTag(db, name);
    res.status(201).json({ id: tagId });
  } catch (err) {
    if (err.code === 'SQLITE_CONSTRAINT_UNIQUE') {
      return res.status(409).json({ error: 'Tag name already exists' });
    }
    throw err;
  }
});

router.get('/:id', (req, res) => {
  const db = req.app.locals.db;
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }
  const tag = getTagById(db, id);
  if (!tag) return res.status(404).json({ error: 'Tag not found' });
  res.json({ tag });
});

router.put('/:id', (req, res) => {
  const db = req.app.locals.db;
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }
  if (typeof req.body.name !== 'string') {
    return res.status(400).json({ error: 'Name must be a string' });
  }
  const name = req.body.name.trim();
  if (!name) return res.status(400).json({ error: 'Name is required' });
  if (name.length > 50) return res.status(400).json({ error: 'Name must be 50 characters or less' });
  try {
    const changes = updateTag(db, id, name);
    if (changes === 0) return res.status(404).json({ error: 'Tag not found' });
    const tag = getTagById(db, id);
    res.json({ tag });
  } catch (err) {
    if (err.code === 'SQLITE_CONSTRAINT_UNIQUE') {
      return res.status(409).json({ error: 'Tag name already exists' });
    }
    throw err;
  }
});

router.delete('/:id', (req, res) => {
  const db = req.app.locals.db;
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }
  const changes = deleteTag(db, id);
  if (changes === 0) return res.status(404).json({ error: 'Tag not found' });
  res.status(204).end();
});

router.get('/:id/notes', (req, res) => {
  const db = req.app.locals.db;
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id < 1) {
    return res.status(400).json({ error: 'Invalid ID' });
  }
  const tag = getTagById(db, id);
  if (!tag) return res.status(404).json({ error: 'Tag not found' });
  const notes = getNotesForTag(db, id);
  res.json({ notes });
});

module.exports = router;
