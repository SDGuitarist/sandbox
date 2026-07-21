// math.js — the REAL code. It knows nothing about testing.

function add(a, b) {
  return a + b;
}

// Make add() available to other files (like our test harness).
module.exports = { add };
