/* Telepatch — the layer itself.

   A closed shadow root, so the host page cannot style this and this
   cannot style the host page. Every rule inside starts from `all:initial`
   for the same reason: a site with an aggressive reset should not be able
   to reach in here, and nothing in here should leak out.

   No token ever reaches this file. The panel asks the service worker to
   do things and is told only what it needs to draw. */

if (window.top === window && !document.getElementById("telepatch-root")) {
  const ask = (type, extra) =>
    chrome.runtime.sendMessage({ type, ...(extra || {}) }).then(res => {
      if (!res || !res.ok) throw new Error((res && res.error) || "Telepatch is not responding");
      return res.result;
    });

  const host = document.createElement("div");
  host.id = "telepatch-root";
  const root = host.attachShadow({ mode: "closed" });

  root.innerHTML = `
<style>
  :host, * { all: initial; box-sizing: border-box; }
  :host { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }

  .fab, .panel {
    position: fixed; right: 18px; z-index: 2147483647;
    color: #14181A;
  }
  .fab {
    bottom: 18px; width: 38px; height: 38px;
    display: flex; align-items: center; justify-content: center;
    background: #1C5A4E; color: #E8EAE6;
    border-radius: 50%; cursor: pointer;
    box-shadow: 0 2px 10px rgba(0,0,0,.28);
    font-size: 15px; font-weight: 700; line-height: 1;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    user-select: none;
  }
  .fab:hover { background: #14483E; }
  .fab.here { box-shadow: 0 0 0 3px #C4342A, 0 2px 10px rgba(0,0,0,.28); }

  .panel {
    bottom: 66px; width: 320px; max-height: 74vh; overflow-y: auto;
    background: #E8EAE6; border: 1px solid #C6CAC4; border-radius: 4px;
    box-shadow: 0 6px 28px rgba(0,0,0,.24);
    padding: 14px; display: block;
    transition: width .16s ease, max-height .16s ease;
  }
  /* Writing wants room. Bounded by the viewport so the panel never runs
     off a laptop screen or a phone held in portrait. */
  .panel.wide {
    width: min(620px, calc(100vw - 36px));
    max-height: min(84vh, 760px);
  }
  .panel[hidden] { display: none; }
  @media (prefers-reduced-motion: reduce) { .panel { transition: none; } }

  .head {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
    color: #5C6562; margin-bottom: 10px;
  }
  .head .right { display: flex; align-items: baseline; gap: 12px; }
  .mode {
    cursor: pointer; color: #1C5A4E;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
  }
  .mode:hover { color: #C4342A; }
  /* The all:initial rule above is an author rule, so it beats the user
     agent's [hidden] { display: none }. Anything hideable says it again. */
  .mode[hidden] { display: none; }
  .x { cursor: pointer; font-size: 15px; line-height: 1; color: #5C6562; }
  .x:hover { color: #C4342A; }

  label {
    display: block; margin: 0 0 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px; letter-spacing: .08em; text-transform: uppercase;
    color: #5C6562;
  }
  input, textarea, select {
    display: block; width: 100%; margin: 0 0 11px; padding: 7px 8px;
    font-family: Georgia, serif; font-size: 13px; line-height: 1.4;
    color: #14181A; background: #FFF;
    border: 1px solid #C6CAC4; border-radius: 3px;
  }
  textarea { resize: vertical; min-height: 56px; }
  input:focus, textarea:focus, select:focus { outline: 2px solid #1C5A4E; outline-offset: -2px; }

  button.go {
    width: 100%; padding: 9px; cursor: pointer;
    background: #1C5A4E; color: #E8EAE6;
    border-radius: 3px; text-align: center;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 11px; letter-spacing: .08em; text-transform: uppercase;
  }
  button.go:hover { background: #14483E; }
  button.go[disabled] { background: #9AA39F; cursor: default; }

  /* The writing surface. Serif at a readable size, because this is where
     somebody composes rather than fills in a field. */
  .write {
    min-height: 300px; font-size: 15px; line-height: 1.62;
    padding: 12px; margin-bottom: 8px;
  }
  .hint {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px; line-height: 1.7; color: #5C6562; margin: 0 0 11px;
  }
  .hint b { font-weight: 700; color: #14181A; }

  .note { font-size: 12px; line-height: 1.5; color: #5C6562; margin: 0 0 10px; }
  .note a { color: #1C5A4E; text-decoration: underline; cursor: pointer; }
  .bad { color: #C4342A; }
  .ok { color: #1C5A4E; }
  .drop { cursor: pointer; color: #5C6562; font-size: 11px; }
  .drop:hover { color: #C4342A; }
</style>

<div class="fab" title="Telepatch">T</div>
<div class="panel" hidden>
  <div class="head">
    <span>Telepatch</span>
    <span class="right"><span class="mode">New</span><span class="x">&times;</span></span>
  </div>
  <div class="body"></div>
</div>`;

  const fab = root.querySelector(".fab");
  const panel = root.querySelector(".panel");
  const body = root.querySelector(".body");
  const modeBtn = root.querySelector(".mode");

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  };

  /* What the page is about, guessed the way a reader would: the title, and
     whatever they had selected when they reached for the button. */
  const pick = sel => {
    const meta = document.querySelector(sel);
    return meta ? (meta.getAttribute("content") || "").trim() : "";
  };

  const suggest = () => ({
    url: location.href,
    title: (pick('meta[property="og:title"]') || document.title || location.hostname).trim(),
    note: (String(getSelection() || "").trim() ||
           pick('meta[name="description"]') ||
           pick('meta[property="og:description"]')).slice(0, 400)
  });

  let collections = [];
  let chosen = null;
  let mode = "save";

  /* Writing survives closing the panel, navigating away, and the tab being
     shut. A half-written post lost to a stray click is the fastest way to
     make somebody never use this again. */
  let draft = { title: "", cats: "", body: "" };
  let draftTimer = null;

  const saveDraft = () => {
    clearTimeout(draftTimer);
    draftTimer = null;
    chrome.storage.local.set({ draft });
  };

  /* A second, not the 400 ms this used to be: continuous typing meant up
     to 150 writes a minute for no gain. The cost of the longer wait is
     paid back by writing on the way out instead - closing the panel,
     leaving the field, or leaving the page. */
  const keepDraft = () => {
    if (draftTimer) return;
    draftTimer = setTimeout(saveDraft, 1000);
  };

  const clearDraft = () => {
    draft = { title: "", cats: "", body: "" };
    chrome.storage.local.remove("draft");
  };

  async function draw() {
    body.replaceChildren();

    try {
      collections = await ask("collections");
    } catch (err) {
      body.appendChild(el("p", "note bad", err.message));
      return;
    }

    const writing = mode === "write" && collections.length > 0;

    panel.classList.toggle("wide", writing);
    modeBtn.hidden = !collections.length;
    modeBtn.textContent = writing ? "← Save page" : "New";

    if (!collections.length) return drawSetup();

    if (writing) {
      const stored = await chrome.storage.local.get("draft");
      if (stored.draft) draft = stored.draft;
      return drawCompose();
    }

    drawSave();
  }

  function pickCollection(onChange) {
    if (!chosen || !collections.some(c => c.id === chosen)) chosen = collections[0].id;

    const where = el("select");

    for (const c of collections) {
      const option = el("option", null, c.label + (c.who ? "  ·  " + c.who : ""));
      option.value = c.id;
      if (c.id === chosen) option.selected = true;
      where.appendChild(option);
    }

    where.addEventListener("change", () => {
      chosen = where.value;
      if (onChange) onChange();
    });

    return where;
  }

  function drawCompose() {
    const where = pickCollection();

    const title = el("input");
    title.value = draft.title;
    title.placeholder = "Title";

    const cats = el("input");
    cats.value = draft.cats;
    cats.placeholder = "notes, drafts";

    const write = el("textarea", "write");
    write.value = draft.body;
    write.placeholder = "Write here. A blank line starts a new paragraph.";

    for (const [field, key] of [[title, "title"], [cats, "cats"], [write, "body"]]) {
      field.addEventListener("input", () => { draft[key] = field.value; keepDraft(); });
      // Leaving a field is a natural save point and costs nothing.
      field.addEventListener("blur", saveDraft);
    }

    // The same markers as /post, so what somebody learns in the chat still
    // works here.
    const hint = el("p", "hint");
    const mark = t => el("b", null, t);
    hint.append(
      mark("##"), " heading   ", mark("###"), " subheading   ", mark(">"), " quote",
      document.createElement("br"),
      "An image URL alone on a line becomes a picture."
    );

    const go = el("button", "go", "Publish to collection");
    const status = el("p", "note");

    go.addEventListener("click", async () => {
      go.disabled = true;
      status.className = "note";
      status.textContent = "Publishing…";

      try {
        const { url } = await ask("publish", {
          id: where.value,
          title: title.value.trim(),
          cats: cats.value.split(",").map(s => s.trim()).filter(Boolean),
          body: write.value
        });

        clearDraft();
        status.className = "note ok";
        status.replaceChildren("Published. ");

        const link = el("a", null, "Read it");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        status.appendChild(link);

        title.value = ""; cats.value = ""; write.value = "";
        go.disabled = false;
      } catch (err) {
        status.className = "note bad";
        status.textContent = err.message;
        go.disabled = false;
      }
    });

    body.append(
      el("label", null, "Collection"), where,
      el("label", null, "Title"), title,
      el("label", null, "Categories"), cats,
      el("label", null, "Post"), write,
      hint, go, status
    );

    title.focus();
  }

  function drawSetup() {
    body.appendChild(el("p", "note",
      "Paste the access token from your Telepatch identity in Telegram. " +
      "It is stored in this browser only, and is never sent anywhere but telegra.ph."));

    const field = el("input");
    field.type = "password";
    field.placeholder = "Telegraph access token";
    field.setAttribute("aria-label", "Telegraph access token");

    const go = el("button", "go", "Connect");
    const status = el("p", "note");

    go.addEventListener("click", async () => {
      go.disabled = true;
      status.className = "note";
      status.textContent = "Reading your account…";

      try {
        const { added } = await ask("connect", { token: field.value });
        status.className = "note ok";
        status.textContent = added + (added === 1 ? " collection" : " collections") + " connected.";
        setTimeout(draw, 700);
      } catch (err) {
        status.className = "note bad";
        status.textContent = err.message;
        go.disabled = false;
      }
    });

    body.append(el("label", null, "Access token"), field, go, status);
  }

  function drawSave() {
    const seed = suggest();
    const status = el("p", "note");
    const where = pickCollection(() => check());

    const title = el("input");
    title.value = seed.title;

    const cats = el("input");
    cats.placeholder = "reading, research";

    const note = el("textarea");
    note.value = seed.note;

    const go = el("button", "go", "Save to collection");

    const check = async () => {
      status.className = "note";
      status.textContent = "";
      fab.classList.remove("here");

      try {
        const collection = collections.find(c => c.id === chosen);
        const { saved } = await ask("lookup", { path: collection.path, url: seed.url });
        if (saved) {
          status.className = "note";
          status.textContent = "This page is already in that collection.";
          fab.classList.add("here");
        }
      } catch (err) {
        // A failed check is not worth an error: the save will say so.
      }
    };

    go.addEventListener("click", async () => {
      go.disabled = true;
      status.className = "note";
      status.textContent = "Saving…";

      try {
        await ask("save", {
          id: where.value,
          url: seed.url,
          title: title.value.trim() || seed.title,
          cats: cats.value.split(",").map(s => s.trim()).filter(Boolean),
          note: note.value.trim()
        });

        status.className = "note ok";
        status.textContent = "Saved. It is on your site now.";
        fab.classList.add("here");
        setTimeout(close, 1100);
      } catch (err) {
        status.className = "note bad";
        status.textContent = err.message;
        go.disabled = false;
      }
    });

    const drop = el("p", "drop", "Disconnect this collection");
    drop.addEventListener("click", async () => {
      await ask("forget", { id: where.value });
      draw();
    });

    body.append(
      el("label", null, "Collection"), where,
      el("label", null, "Title"), title,
      el("label", null, "Categories"), cats,
      el("label", null, "Note"), note,
      go, status, drop
    );

    check();
  }

  const open = () => { panel.hidden = false; draw(); };
  const close = () => { panel.hidden = true; saveDraft(); };
  const toggle = () => (panel.hidden ? open() : close());

  fab.addEventListener("click", toggle);
  root.querySelector(".x").addEventListener("click", close);

  modeBtn.addEventListener("click", () => {
    mode = mode === "write" ? "save" : "write";
    draw();
  });

  addEventListener("keydown", e => {
    if (e.key === "Escape" && !panel.hidden) close();
  });

  addEventListener("pagehide", saveDraft);

  chrome.runtime.onMessage.addListener(msg => {
    if (msg && msg.type === "toggle") toggle();
  });

  document.documentElement.appendChild(host);
}
