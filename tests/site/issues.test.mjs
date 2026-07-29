import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { splitIssues, deriveSections, filterIssues, facetCounts } = loadPure();

const issue = (n, o = {}) => ({
  number: n,
  title: o.title || ("issue " + n),
  state: o.state || "open",
  labels: (o.labels || []).map(name => ({ name })),
  milestone: o.milestone ? { title: o.milestone } : null,
  pull_request: o.pull ? { url: "x" } : undefined,
  updated_at: o.updated || "2026-07-01T00:00:00Z"
});

const SAMPLE = [
  issue(144, { title: "Recognise a pasted token by shape", labels: ["idea"] }),
  issue(141, { title: "Tree API budget on a cold reader", labels: ["bug"] }),
  issue(138, { title: "Byline modes on hand-written indexes", labels: ["docs"], milestone: "v1" }),
  issue(127, { title: "Escaped slash splits the route", labels: ["bug"], milestone: "v1" }),
  issue(94,  { title: "One token, several collections", labels: ["idea"], state: "closed" }),
  issue(145, { title: "Read the README name from the tree", labels: [], pull: true })
];

test("a pull request is an issue wearing a key", () => {
  const { issues, pulls } = splitIssues(SAMPLE);
  assert.equal(pulls.length, 1);
  assert.equal(pulls[0].number, 145);
  assert.equal(issues.length, 5);
  assert.ok(issues.every(i => !i.pull_request));
});

test("splitting survives an empty list, and a missing one", () => {
  assert.deepEqual(splitIssues([]), { issues: [], pulls: [] });
  assert.deepEqual(splitIssues(undefined), { issues: [], pulls: [] });
});

test("sections are named by purpose, not by query", () => {
  const { issues } = splitIssues(SAMPLE);
  const names = deriveSections(issues).map(s => s.key);
  assert.ok(names.includes("bugs"));
  assert.ok(names.includes("ideas"));
  assert.ok(names.includes("completed"));
});

test("a section with nothing in it is not shown", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.ok(deriveSections(issues).every(s => s.items.length > 0));
});

test("a repository whose labels do not match still gets sections", () => {
  const plain = [issue(1), issue(2, { state: "closed" })];
  const keys = deriveSections(plain).map(s => s.key).sort();
  assert.deepEqual(keys, ["completed", "open"]);
});

test("filtering by state", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { state: "open" }).length, 4);
  assert.equal(filterIssues(issues, { state: "closed" }).length, 1);
  assert.equal(filterIssues(issues, { state: "all" }).length, 5);
});

test("filtering by label, and by two things at once", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { labels: ["bug"] }).length, 2);
  assert.equal(
    filterIssues(issues, { state: "open", labels: ["bug"], milestone: "v1" }).length,
    1
  );
});

test("the text filter reads titles and labels", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "route" }).length, 1);
  assert.equal(filterIssues(issues, { text: "TOKEN" }).length, 2, "case is ignored");
  assert.equal(filterIssues(issues, { text: "docs" }).length, 1, "matches a label");
});

test("is: and label: are understood but never required", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "is:closed" }).length, 1);
  assert.equal(filterIssues(issues, { text: "label:bug" }).length, 2);
  assert.equal(filterIssues(issues, { text: "label:bug route" }).length, 1);
});

test("a filter matching nothing returns nothing, not everything", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, { text: "zzzz" }).length, 0);
});

test("no filter at all is every issue", () => {
  const { issues } = splitIssues(SAMPLE);
  assert.equal(filterIssues(issues, {}).length, 5);
  assert.equal(filterIssues(issues, undefined).length, 5);
});

test("facet counts follow the filter, and zeroes are kept", () => {
  const { issues } = splitIssues(SAMPLE);
  const counts = facetCounts(issues, { labels: ["bug"] });
  assert.equal(counts.labels.bug, 2);
  assert.equal(counts.labels.idea, 0, "a facet that matches nothing must still be listed");
  assert.ok("idea" in counts.labels);
});

test("facet counts narrow with the text field too", () => {
  const { issues } = splitIssues(SAMPLE);
  const counts = facetCounts(issues, { text: "route" });
  assert.equal(counts.labels.bug, 1);
  assert.equal(counts.labels.idea, 0);
  assert.equal(counts.state.all, 1);
});
