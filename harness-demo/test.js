// test.js — the HARNESS plus the tests that use it.

// Pull in the real code we want to test.
const { add } = require("./math");

// --- the harness itself ---
let passed = 0;
let failed = 0;

function check(description, actual, expected) {
  if (actual === expected) {
    console.log(`✅ ${description}`);
    passed++;
  } else {
    console.log(`❌ ${description} — expected ${expected}, got ${actual}`);
    failed++;
  }
}
// --- end harness ---


// --- the actual tests (using the harness) ---
check("adds two positives", add(2, 3), 5);
check("adds a negative",    add(2, -1), 1);
check("adds zeros",         add(0, 0), 0);

console.log(`\n${passed} passed, ${failed} failed`);

// Exit with code 1 if anything failed — this is how CI systems
// know the test run "failed" without reading the text output.
process.exit(failed > 0 ? 1 : 0);
