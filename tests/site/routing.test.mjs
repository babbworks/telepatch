import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { ghFromParts, ghToParts } = loadPure();

test("a bare repository is the overview", () => {
  assert.equal(ghFromParts(["github.com", "o", "r"]), "gh:o/r");
});

test("a blob is a file", () => {
  assert.equal(
    ghFromParts(["github.com", "o", "r", "blob", "HEAD", "bot.py"]),
    "gh:o/r/bot.py"
  );
});

test("a tree is a directory", () => {
  assert.equal(
    ghFromParts(["github.com", "o", "r", "tree", "HEAD", "docs"]),
    "ght:o/r/docs"
  );
});

test("anything that is not github is not a resource", () => {
  assert.equal(ghFromParts(["some-telegraph-path"]), null);
  assert.equal(ghFromParts([]), null);
});

test("a resource round-trips through the URL and back", () => {
  for (const id of ["gh:o/r", "gh:o/r/bot.py", "ght:o/r/docs"]) {
    assert.equal(ghFromParts(ghToParts(id)), id, id);
  }
});

test("prefixed ids already in the wild still parse", () => {
  assert.equal(ghFromParts(["gh:o/r/docs/a.md"]), "gh:o/r/docs/a.md");
  assert.equal(ghFromParts(["ght:o/r", "docs"]), "ght:o/r/docs");
});
