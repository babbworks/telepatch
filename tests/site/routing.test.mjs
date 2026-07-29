import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { ghFromParts, ghToParts, ghSection } = loadPure();

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

test("sections are read from github's own paths", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "issues"]), "gh:o/r@issues");
  assert.equal(ghFromParts(["github.com", "o", "r", "issues", "144"]), "gh:o/r@issues/144");
  assert.equal(ghFromParts(["github.com", "o", "r", "releases"]), "gh:o/r@releases");
  assert.equal(ghFromParts(["github.com", "o", "r", "pulse"]), "gh:o/r@pulse");
});

test("a section round-trips", () => {
  for (const id of ["gh:o/r@issues", "gh:o/r@issues/144", "gh:o/r@releases", "gh:o/r@pulse"]) {
    assert.equal(ghFromParts(ghToParts(id)), id, id);
  }
});

test("a section URL is a real github.com address", () => {
  assert.deepEqual(ghToParts("gh:o/r@issues/144"), ["github.com", "o", "r", "issues", "144"]);
});

test("blob and tree are untouched by sections", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "blob", "HEAD", "bot.py"]), "gh:o/r/bot.py");
  assert.equal(ghFromParts(["github.com", "o", "r", "tree", "HEAD", "docs"]), "ght:o/r/docs");
});

test("ghSection splits a resource id", () => {
  assert.deepEqual(ghSection("gh:o/r"), { repo: "o/r", section: "overview", arg: null });
  assert.deepEqual(ghSection("gh:o/r@issues"), { repo: "o/r", section: "issues", arg: null });
  assert.deepEqual(ghSection("gh:o/r@issues/144"), { repo: "o/r", section: "issue", arg: "144" });
  assert.deepEqual(ghSection("gh:o/r@pulse"), { repo: "o/r", section: "pulse", arg: null });
});

test("a file is not a section", () => {
  assert.equal(ghSection("gh:o/r/bot.py"), null);
  assert.equal(ghSection("ght:o/r/docs"), null);
});

test("an unknown github path is not invented into a section", () => {
  assert.equal(ghFromParts(["github.com", "o", "r", "settings"]), "gh:o/r");
});
