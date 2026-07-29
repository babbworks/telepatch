import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { looksLikeGhToken, ghTokenKind } = loadPure();

test("a token is recognised by shape, not by position", () => {
  assert.ok(looksLikeGhToken("ghp_" + "A".repeat(36)));
  assert.ok(looksLikeGhToken("gho_" + "A".repeat(36)));
  assert.ok(looksLikeGhToken("github_pat_" + "A".repeat(60)));
});

test("surrounding whitespace does not stop it being a token", () => {
  assert.ok(looksLikeGhToken("  ghp_" + "A".repeat(36) + "\n"));
});

test("things that are not tokens are not tokens", () => {
  assert.equal(looksLikeGhToken("hello"), false);
  assert.equal(looksLikeGhToken(""), false);
  assert.equal(looksLikeGhToken(null), false);
  assert.equal(looksLikeGhToken("ghp_short"), false);
  // A Telegraph token is 60 hex characters and must never be taken for one.
  assert.equal(looksLikeGhToken("a".repeat(60)), false);
});

test("the fine-grained token is told apart from the broad one", () => {
  assert.equal(ghTokenKind("github_pat_" + "A".repeat(60)), "fine");
  assert.equal(ghTokenKind("gho_" + "A".repeat(36)), "broad");
  assert.equal(ghTokenKind("ghp_" + "A".repeat(36)), "broad");
  assert.equal(ghTokenKind("nonsense"), null);
});
