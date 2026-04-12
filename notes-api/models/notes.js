function getAllNotes(db) {
  return db.prepare('SELECT * FROM notes ORDER BY created_at DESC LIMIT 200').all();
}

function getNoteById(db, id) {
  return db.prepare('SELECT * FROM notes WHERE id = ?').get(id);
}

function createNote(db, title, content) {
  const result = db.prepare('INSERT INTO notes (title, content) VALUES (?, ?)').run(title, content);
  return result.lastInsertRowid;
}

function updateNote(db, id, title, content) {
  const result = db.prepare("UPDATE notes SET title = ?, content = ?, updated_at = datetime('now') WHERE id = ?").run(title, content, id);
  return result.changes;
}

function deleteNote(db, id) {
  return db.prepare('DELETE FROM notes WHERE id = ?').run(id).changes;
}

function getTagsForNote(db, noteId) {
  return db.prepare(
    `SELECT t.id, t.name, t.created_at
     FROM tags t
     JOIN note_tags nt ON t.id = nt.tag_id
     WHERE nt.note_id = ?
     ORDER BY t.name`
  ).all(noteId);
}

function addTagToNote(db, noteId, tagId) {
  try {
    db.prepare('INSERT INTO note_tags (note_id, tag_id) VALUES (?, ?)').run(noteId, tagId);
    return true;
  } catch (err) {
    if (err.code === 'SQLITE_CONSTRAINT_PRIMARYKEY') {
      return false;
    }
    throw err;
  }
}

function removeTagFromNote(db, noteId, tagId) {
  db.prepare('DELETE FROM note_tags WHERE note_id = ? AND tag_id = ?').run(noteId, tagId);
}

module.exports = {
  getAllNotes, getNoteById, createNote, updateNote, deleteNote,
  getTagsForNote, addTagToNote, removeTagFromNote
};
