function getAllTags(db) {
  return db.prepare('SELECT * FROM tags ORDER BY name LIMIT 200').all();
}

function getTagById(db, id) {
  return db.prepare('SELECT * FROM tags WHERE id = ?').get(id);
}

function createTag(db, name) {
  const result = db.prepare('INSERT INTO tags (name) VALUES (?)').run(name);
  return result.lastInsertRowid;
}

function updateTag(db, id, name) {
  return db.prepare('UPDATE tags SET name = ? WHERE id = ?').run(name, id).changes;
}

function deleteTag(db, id) {
  return db.prepare('DELETE FROM tags WHERE id = ?').run(id).changes;
}

function getNotesForTag(db, tagId) {
  return db.prepare(
    `SELECT n.id, n.title, n.content, n.created_at, n.updated_at
     FROM notes n
     JOIN note_tags nt ON n.id = nt.note_id
     WHERE nt.tag_id = ?
     ORDER BY n.created_at DESC`
  ).all(tagId);
}

module.exports = {
  getAllTags, getTagById, createTag, updateTag, deleteTag, getNotesForTag
};
