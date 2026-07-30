import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { authorOf, issueState, reactionsOf, filterIssues, facetCounts } = loadPure();

const issue = (n, o = {}) => ({
  number: n,
  title: o.title || ("issue " + n),
  state: o.state || "open",
  state_reason: o.reason || null,
  labels: (o.labels || []).map(name => ({ name })),
  milestone: o.milestone ? { title: o.milestone } : null,
  user: o.user === null ? null : { login: o.user || "ada" },
  author_association: o.assoc || "NONE",
  draft: o.draft || false,
  pull_request: o.pull || o.merged || o.draft
    ? { merged_at: o.merged || null } : undefined,
  reactions: o.reactions || null,
  comments: o.comments || 0
});

test("the author is read, and a missing one does not throw", () => {
  assert.equal(authorOf(issue(1, { user: "morgen" })), "morgen");
  assert.equal(authorOf(issue(2, { user: null })), "");
  assert.equal(authorOf({}), "");
});

test("merged is not the same as closed", () => {
  assert.equal(issueState(issue(1, { state: "closed", merged: "2026-07-01T00:00:00Z" })), "merged");
  assert.equal(issueState(issue(2, { state: "closed", pull: true })), "closed");
});

test("a draft pull request says so", () => {
  assert.equal(issueState(issue(1, { draft: true })), "draft");
});

test("closed as not planned is not the same as done", () => {
  assert.equal(issueState(issue(1, { state: "closed", reason: "not_planned" })), "not planned");
  assert.equal(issueState(issue(2, { state: "closed", reason: "completed" })), "closed");
  assert.equal(issueState(issue(3, { state: "closed" })), "closed");
});

test("an ordinary open issue is open", () => {
  assert.equal(issueState(issue(1)), "open");
  assert.equal(issueState({}), "open");
});

test("a merged pull request still reads as merged when draft was set", () => {
  // GitHub leaves draft true on some merged PRs; merged is the stronger fact.
  assert.equal(issueState(issue(1, { state: "closed", merged: "2026-07-01T00:00:00Z", draft: true })), "merged");
});

test("only reactions that happened are listed, biggest first", () => {
  const r = reactionsOf(issue(1, {
    reactions: { total_count: 16, "+1": 12, "-1": 0, laugh: 0, hooray: 1,
                 confused: 0, heart: 3, rocket: 0, eyes: 0 }
  }));
  assert.deepEqual(r, [["👍", 12], ["❤️", 3], ["🎉", 1]]);
});

test("no reactions is an empty list, not a row of zeroes", () => {
  assert.deepEqual(reactionsOf(issue(1)), []);
  assert.deepEqual(reactionsOf(issue(2, { reactions: { total_count: 0, "+1": 0 } })), []);
  assert.deepEqual(reactionsOf({}), []);
});

test("issues can be filtered by author", () => {
  const all = [
    issue(1, { user: "ada" }),
    issue(2, { user: "morgen" }),
    issue(3, { user: "ada" })
  ];
  assert.equal(filterIssues(all, { author: "ada" }).length, 2);
  assert.equal(filterIssues(all, { author: "morgen" }).length, 1);
  assert.equal(filterIssues(all, { author: "nobody" }).length, 0);
});

test("author: is understood in the filter field", () => {
  const all = [issue(1, { user: "ada", title: "tin" }), issue(2, { user: "morgen", title: "tin" })];
  assert.equal(filterIssues(all, { text: "author:ada" }).length, 1);
  assert.equal(filterIssues(all, { text: "author:ada tin" }).length, 1);
  assert.equal(filterIssues(all, { text: "author:nobody tin" }).length, 0);
});

test("an author facet is counted like the others, and keeps its zeroes", () => {
  const all = [
    issue(1, { user: "ada", labels: ["bug"] }),
    issue(2, { user: "morgen", labels: ["idea"] })
  ];
  const counts = facetCounts(all, { labels: ["bug"] });
  assert.equal(counts.authors.ada, 1);
  assert.equal(counts.authors.morgen, 0);
  assert.ok("morgen" in counts.authors);
});
