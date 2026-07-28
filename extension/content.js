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
  }
  .panel[hidden] { display: none; }

  .head {
    display: flex; justify-content: space-between; align-items: baseline;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10px; letter-spacing: .1em; text-transform: uppercase;
    color: #5C6562; margin-bottom: 10px;
  }
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

  .note { font-size: 12px; line-height: 1.5; color: #5C6562; margin: 0 0 10px; }
  .note a { color: #1C5A4E; text-decoration: underline; cursor: pointer; }
  .bad { color: #C4342A; }
  .ok { color: #1C5A4E; }
  .drop { cursor: pointer; color: #5C6562; font-size: 11px; }
  .drop:hover { color: #C4342A; }
</style>

<div class="fab" title="Telepatch">T</div>
<div class="panel" hidden>
  <div class="head"><span>Telepatch</span><span class="x">&times;</span></div>
  <div class="body"></div>
</div>`;

  const fab = root.querySelector(".fab");
  const panel = root.querySelector(".panel");
  const body = root.querySelector(".body");

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

  async function draw() {
    body.replaceChildren();

    try {
      collections = await ask("collections");
    } catch (err) {
      body.appendChild(el("p", "note bad", err.message));
      return;
    }

    if (!collections.length) return drawSetup();
    drawSave();
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
    if (!chosen || !collections.some(c => c.id === chosen)) chosen = collections[0].id;

    const status = el("p", "note");

    const where = el("select");
    for (const c of collections) {
      const option = el("option", null, c.label + (c.who ? "  ·  " + c.who : ""));
      option.value = c.id;
      if (c.id === chosen) option.selected = true;
      where.appendChild(option);
    }

    const title = el("input");
    title.value = seed.title;

    const cats = el("input");
    cats.placeholder = "reading, research";

    const note = el("textarea");
    note.value = seed.note;

    const go = el("button", "go", "Save to collection");

    const check = async () => {
      chosen = where.value;
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

    where.addEventListener("change", check);

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
  const close = () => { panel.hidden = true; };
  const toggle = () => (panel.hidden ? open() : close());

  fab.addEventListener("click", toggle);
  root.querySelector(".x").addEventListener("click", close);

  addEventListener("keydown", e => {
    if (e.key === "Escape" && !panel.hidden) close();
  });

  chrome.runtime.onMessage.addListener(msg => {
    if (msg && msg.type === "toggle") toggle();
  });

  document.documentElement.appendChild(host);
}
