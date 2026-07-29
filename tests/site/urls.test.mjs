import { test } from "node:test";
import assert from "node:assert/strict";
import { loadPure } from "./extract.mjs";

const { mdUrl } = loadPure();

const BASE = "https://raw.githubusercontent.com/o/r/HEAD/";

/* An issue body is written by somebody the publisher did not choose, and
   its links are the only place a stranger's text becomes something a
   reader can click. Everything below is the boundary that makes that safe.
   If one of these ever returns a non-empty string, the site has a hole. */
test("a scripting scheme never survives", () => {
  for (const bad of [
    "javascript:alert(1)",
    "JaVaScript:alert(1)",
    "  javascript:alert(1)  ",
    "vbscript:msgbox(1)",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "data:image/svg+xml;base64,PHN2Zz48c2NyaXB0Lz48L3N2Zz4=",
    "file:///etc/passwd",
    "blob:https://example.com/1234",
    "chrome://settings"
  ]) {
    assert.equal(mdUrl(bad, BASE), "", bad);
  }
});

test("the schemes a reader may follow do survive", () => {
  assert.equal(mdUrl("https://ok.example/x.png", BASE), "https://ok.example/x.png");
  assert.equal(mdUrl("http://ok.example/x", BASE), "http://ok.example/x");
  assert.equal(mdUrl("mailto:a@b.c", BASE), "mailto:a@b.c");
});

test("a relative address resolves against the repository", () => {
  assert.equal(mdUrl("./docs/a.md", BASE), BASE + "docs/a.md");
  assert.equal(mdUrl("img.png", BASE), BASE + "img.png");
});

test("a protocol-relative address becomes https, not a scheme of its own", () => {
  assert.equal(mdUrl("//other.example/x.png", BASE), "https://other.example/x.png");
});

test("nothing, a bare fragment, and rubbish all render as text", () => {
  assert.equal(mdUrl("", BASE), "");
  assert.equal(mdUrl(null, BASE), "");
  assert.equal(mdUrl(undefined, BASE), "");
  assert.equal(mdUrl("#heading", BASE), "");
});

/* The bypass that would work against a scheme check alone: the URL parser
   strips tabs and newlines, so "jav\tascript:" would parse as javascript:.
   It cannot arrive here, because the markdown pattern that finds an address
   captures [^)\s]+ and whitespace ends the capture. This pins the pattern,
   not mdUrl, because that is where the protection actually lives. */
test("whitespace cannot be used to smuggle a scheme past the pattern", () => {
  const MD_INLINE = new RegExp(
    "`([^`]+)`" +
    "|!\\[([^\\]]*)\\]\\(\\s*([^)\\s]+)[^)]*\\)" +
    "|\\[([^\\]]*)\\]\\(\\s*([^)\\s]+)[^)]*\\)" +
    "|\\*\\*([^*]+)\\*\\*|__([^_]+)__" +
    "|\\*([^*]+)\\*|_([^_]+)_", "g");

  assert.equal(new URL("jav\tascript:alert(1)", BASE).protocol, "javascript:",
    "the URL parser really does strip the tab — this is the threat");

  for (const smuggled of [
    "![x](jav\tascript:alert(1))",
    "![x](jav\nascript:alert(1))",
    "[y](java\rscript:alert(1))"
  ]) {
    MD_INLINE.lastIndex = 0;
    const m = MD_INLINE.exec(smuggled);
    const captured = m && (m[3] || m[5]);
    assert.ok(captured && !/script:/i.test(captured),
      "capture must stop at the whitespace, got " + JSON.stringify(captured));
    assert.ok(!mdUrl(captured, BASE).startsWith("javascript:"));
  }
});
