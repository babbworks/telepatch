import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { mergeActivity, deriveContributors, countSince } = loadPure();

const COMMITS = [
  { sha: "9be2aaa", commit: { message: "Sites and Web\n\nbody", author: { name: "Morgen", date: "2026-07-29T09:00:00Z" } } },
  { sha: "d0efbbb", commit: { message: "Stop serving a stale index", author: { name: "Morgen", date: "2026-07-28T09:00:00Z" } } },
  { sha: "a4aaccc", commit: { message: "A monogram", author: { name: "Ada", date: "2026-06-01T09:00:00Z" } } }
];

const ISSUES = [
  { number: 144, title: "Recognise a pasted token", created_at: "2026-07-28T12:00:00Z" },
  { number: 145, title: "Read the README name", created_at: "2026-07-27T12:00:00Z", pull_request: { url: "x" } }
];

const RELEASES = [
  { tag_name: "v0.4", name: "A cable in the gutter", published_at: "2026-07-28T18:00:00Z" }
];

test("everything lands on one timeline, newest first", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: ISSUES, releases: RELEASES });
  assert.equal(feed.length, 6);
  const times = feed.map(e => e.when);
  assert.deepEqual(times, [...times].sort().reverse());
});

test("each kind keeps its identity", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: ISSUES, releases: RELEASES });
  const kinds = new Set(feed.map(e => e.kind));
  assert.deepEqual([...kinds].sort(), ["commit", "issue", "pull", "release"]);
});

test("a commit is titled by its first line only", () => {
  const feed = mergeActivity({ commits: COMMITS, issues: [], releases: [] });
  assert.equal(feed[0].title, "Sites and Web");
  assert.equal(feed[0].id, "9be2aaa");
});

test("missing sources are simply absent", () => {
  assert.deepEqual(mergeActivity({}), []);
  assert.deepEqual(mergeActivity(undefined), []);
  assert.equal(mergeActivity({ commits: COMMITS }).length, 3);
  assert.equal(mergeActivity({ commits: { error: new Error("x") } }).length, 0,
    "a call that failed is an object, not an array, and must not throw");
});

test("an entry with no date is dropped rather than sorted arbitrarily", () => {
  const feed = mergeActivity({ releases: [{ tag_name: "v0.1", name: "draft" }] });
  assert.equal(feed.length, 0);
});

test("contributors are counted from authorship, busiest first", () => {
  assert.deepEqual(deriveContributors(COMMITS),
    [{ name: "Morgen", count: 2 }, { name: "Ada", count: 1 }]);
});

test("a commit with no author does not become a contributor", () => {
  assert.deepEqual(deriveContributors([{ sha: "x", commit: { message: "m" } }]), []);
  assert.deepEqual(deriveContributors(undefined), []);
});

test("commits since an instant", () => {
  assert.equal(countSince(COMMITS, "2026-07-01T00:00:00Z"), 2);
  assert.equal(countSince(COMMITS, "2020-01-01T00:00:00Z"), 3);
  assert.equal(countSince([], "2026-07-01T00:00:00Z"), 0);
});
