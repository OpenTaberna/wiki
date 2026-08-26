#!/usr/bin/env python3
"""
Serve the wiki locally so it can be read the way a reader will read it.

    python3 tools/serve.py        # http://localhost:8090

Renders the markdown with Mermaid diagrams, a page index and working internal
links, so a change can be checked before it reaches wiki.opentaberna.de.

Standard library only — no install step, nothing added to the repository's
dependencies. Marked and Mermaid are pulled from a CDN at view time, so the
first load needs a network connection.
"""

from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
PORT = 8090

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenTaberna Wiki (local)</title>
<style>
  :root {
    --bg: #ffffff; --fg: #1f2328; --muted: #59636e; --line: #d1d9e0;
    --accent: #0969da; --code-bg: #f6f8fa; --sidebar: #f6f8fa;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --line: #3d444d;
      --accent: #4493f8; --code-bg: #151b23; --sidebar: #010409;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    display: flex; min-height: 100vh;
  }
  nav {
    width: 260px; flex-shrink: 0; background: var(--sidebar);
    border-right: 1px solid var(--line); padding: 24px 16px;
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
  }
  nav h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .06em;
           color: var(--muted); margin: 0 0 12px; }
  nav a { display: block; padding: 6px 10px; border-radius: 6px;
          color: var(--fg); text-decoration: none; font-size: 14px; }
  nav a:hover { background: var(--line); }
  nav a.active { background: var(--accent); color: #fff; }
  main { flex: 1; min-width: 0; padding: 40px 48px 96px; max-width: 900px; }
  .banner {
    background: #fff8c5; border: 1px solid #d4a72c; color: #4d2d00;
    padding: 8px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 28px;
  }
  @media (prefers-color-scheme: dark) {
    .banner { background: #2d2200; border-color: #6b5200; color: #f0d68a; }
  }
  h1, h2, h3 { line-height: 1.25; margin-top: 1.6em; }
  h1 { border-bottom: 1px solid var(--line); padding-bottom: .3em; }
  h2 { border-bottom: 1px solid var(--line); padding-bottom: .3em; }
  a { color: var(--accent); }
  code { background: var(--code-bg); padding: .2em .4em; border-radius: 6px;
         font-size: 85%; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  pre { background: var(--code-bg); padding: 16px; border-radius: 6px; overflow-x: auto; }
  pre code { background: none; padding: 0; font-size: 13px; }
  table { border-collapse: collapse; width: 100%; margin: 1em 0; display: block; overflow-x: auto; }
  th, td { border: 1px solid var(--line); padding: 6px 13px; text-align: left; }
  th { background: var(--code-bg); }
  blockquote { margin: 1em 0; padding: 0 1em; color: var(--muted);
               border-left: .25em solid var(--line); }
  .mermaid { text-align: center; margin: 1.5em 0; }
  .meta { color: var(--muted); font-size: 13px; margin-bottom: 24px; }
</style>
</head>
<body>
<nav><h2>Pages</h2><div id="index"></div></nav>
<main>
  <div class="banner">Local preview — served from your working tree, not wiki.opentaberna.de</div>
  <div id="content">Loading…</div>
</main>
<script type="module">
import { marked } from 'https://cdn.jsdelivr.net/npm/marked@12/lib/marked.esm.js';
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';

const dark = matchMedia('(prefers-color-scheme: dark)').matches;
mermaid.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'default' });

const PAGES = __PAGES__;

function slugify(name) { return name.replace(/\\.md$/, ''); }

function renderIndex(current) {
  document.getElementById('index').innerHTML = PAGES.map(p => {
    const s = slugify(p);
    const cls = s === current ? 'active' : '';
    return `<a class="${cls}" href="#${s}">${s.replace(/\\//g, ' › ')}</a>`;
  }).join('');
}

function stripFrontmatter(text) {
  const m = text.match(/^---\\n([\\s\\S]*?)\\n---\\n/);
  if (!m) return { body: text, meta: null };
  const meta = {};
  for (const line of m[1].split('\\n')) {
    const i = line.indexOf(':');
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return { body: text.slice(m[0].length), meta };
}

async function load(page) {
  const res = await fetch('/raw/' + page + '.md');
  if (!res.ok) {
    document.getElementById('content').innerHTML = `<h1>Not found</h1><p><code>${page}.md</code></p>`;
    return;
  }
  const { body, meta } = stripFrontmatter(await res.text());

  const blocks = [];
  const held = body.replace(/```mermaid\\n([\\s\\S]*?)```/g, (_, code) => {
    blocks.push(code);
    return `\\n@@MERMAID${blocks.length - 1}@@\\n`;
  });

  let html = marked.parse(held);
  html = html.replace(/<p>@@MERMAID(\\d+)@@<\\/p>/g,
    (_, i) => `<div class="mermaid">${blocks[i].replace(/</g, '&lt;')}</div>`);

  const header = meta
    ? `<div class="meta">${meta.description || ''}${meta.date ? ' · updated ' + meta.date.slice(0, 10) : ''}</div>`
    : '';
  document.getElementById('content').innerHTML = header + html;

  // Rewrite wiki-absolute links (/Getting-Started) onto the hash router.
  for (const a of document.querySelectorAll('#content a[href^="/"]')) {
    const [path, anchor] = a.getAttribute('href').split('#');
    const target = PAGES.find(p => slugify(p).toLowerCase() === path.slice(1).toLowerCase());
    a.setAttribute('href', target ? '#' + slugify(target) + (anchor ? '#' + anchor : '') : a.getAttribute('href'));
    if (!target) a.style.color = 'crimson';
  }

  await mermaid.run({ querySelector: '.mermaid' });
  renderIndex(page);
}

function route() {
  const page = decodeURIComponent(location.hash.slice(1).split('#')[0]) || 'home';
  load(page);
}
addEventListener('hashchange', route);
route();
</script>
</body>
</html>
"""


def pages() -> list[str]:
    found = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*.md")
        if ".git" not in p.parts and p.name != "README.md"
    )
    # home first, it is the landing page
    found.sort(key=lambda p: (p != "home.md", p))
    return found


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        path = unquote(self.path.split("?")[0])

        if path in ("/", "/index.html"):
            body = SHELL.replace("__PAGES__", json.dumps(pages())).encode()
            self._send(body, "text/html; charset=utf-8")
            return

        if path.startswith("/raw/"):
            target = (ROOT / path[len("/raw/"):]).resolve()
            if ROOT in target.parents and target.is_file():
                self._send(target.read_bytes(), "text/markdown; charset=utf-8")
            else:
                self.send_error(404)
            return

        super().do_GET()

    def _send(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def main() -> None:
    import os

    os.chdir(ROOT)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print(f"Wiki preview: http://localhost:{PORT}  (Ctrl-C to stop)")
        print(f"Serving {len(pages())} pages from {ROOT}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
