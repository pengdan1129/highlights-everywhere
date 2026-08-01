#!/usr/bin/env python3
"""
hl-server - Web UI + API server for Highlights Everywhere.
Provides REST API for the Chrome extension and web UI.
Run with: hl server
"""

import sys
import os
import re
import json
import uuid
import hashlib
import datetime
import webbrowser
import http.server
import socketserver
import urllib.parse
from pathlib import Path
from collections import Counter

HIGHLIGHTS_DIR = Path.home() / "Highlights"
EXT_DIR = HIGHLIGHTS_DIR / "_web"  # Chrome extension highlights
WEB_PORT = 8899

VALID_COLORS = {
    'yellow': '#FFF176',
    'green': '#A5D6A7',
    'blue': '#90CAF9',
    'red': '#EF9A9A',
    'purple': '#CE93D8',
    'orange': '#FFCC80',
    'pink': '#F48FB1',
}

COLOR_NAMES_CN = {
    'yellow': '黄色', 'green': '绿色', 'blue': '蓝色',
    'red': '红色', 'purple': '紫色', 'orange': '橙色', 'pink': '粉色',
}

EXT_DIR.mkdir(parents=True, exist_ok=True)

# Per-source aggregated markdown directory (same URL → one file)
SOURCES_DIR = HIGHLIGHTS_DIR / 'sources'
SOURCES_DIR.mkdir(parents=True, exist_ok=True)

# ─── Storage ──────────────────────────────────────────────────────────

def save_web_highlight(url, text, color, note, selector, page_title=""):
    """Save a highlight from the Chrome extension."""
    ts = datetime.datetime.now()
    ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    date_str = ts.strftime("%Y-%m-%d")
    hl_id = ts.strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]

    dir_path = EXT_DIR / str(ts.year) / f"{ts.month:02d}"
    dir_path.mkdir(parents=True, exist_ok=True)

    filepath = dir_path / f"{hl_id}.json"

    data = {
        "id": hl_id,
        "url": url,
        "page_title": page_title,
        "text": text,
        "color": color,
        "hex_color": VALID_COLORS.get(color, '#FFF176'),
        "note": note or "",
        "selector": selector or {},
        "created_at": ts_str,
        "date": date_str,
        "time": ts.strftime("%H:%M:%S"),
    }

    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    # Also save a markdown copy for human reading and Spotlight indexing
    md_dir = HIGHLIGHTS_DIR / str(ts.year) / f"{ts.month:02d}"
    md_dir.mkdir(parents=True, exist_ok=True)
    safe_text = re.sub(r'[\\/:*?"<>|]', ' ', text)[:50]
    md_path = md_dir / f"{ts.strftime('%Y-%m-%d-%H%M%S')}-{color}-web-{safe_text}.md"
    md_content = f"""---
url: {url}
color: {color}
hex_color: {data['hex_color']}
page_title: "{page_title}"
date: {date_str}
time: {data['time']}
type: web_highlight
---

## <span style="background-color:{data['hex_color']};padding:2px 6px;border-radius:3px">📌 Web Highlight</span>

> {text}
{chr(10) + '💬 **备注**: ' + note if note else ''}

---
*Source: [{page_title}]({url})* | *Color: {color}* | *{ts_str}*
"""
    md_path.write_text(md_content.strip() + "\n")

    # Also append to the per-source aggregated markdown file
    upsert_highlight_in_md(data)

    return data


# ─── Per-source aggregated markdown ──────────────────────────────────

COLOR_EMOJI = {
    'yellow': '🟡', 'green': '🟢', 'blue': '🔵', 'red': '🔴',
    'purple': '🟣', 'orange': '🟠', 'pink': '🩷',
}


def md_path_for_url(url):
    """Stable per-source markdown file path for a URL."""
    p = urllib.parse.urlparse(url)
    domain = p.netloc or 'local'
    path_slug = re.sub(r'[^a-zA-Z0-9]+', '-', p.path.strip('/')).strip('-')[:60]
    h = hashlib.md5(url.encode('utf-8')).hexdigest()[:6]
    fname = f"{domain}-{path_slug or 'home'}-{h}.md"
    return SOURCES_DIR / fname


def _hl_entry_block(data):
    """Build the markdown block for one highlight entry."""
    hl_id = data.get('id', '')
    emoji = COLOR_EMOJI.get(data.get('color', 'yellow'), '🟡')
    ts = data.get('created_at', '') or ''
    text = (data.get('text', '') or '').replace('\n', ' ')
    note = (data.get('note', '') or '').strip()
    block = f"<!--hl:{hl_id}-->\n### {emoji} {ts}\n> {text}\n"
    if note:
        block += f"> 💬 **备注**: {note}\n"
    return block + "\n"


def upsert_highlight_in_md(data, remove=False):
    """Insert/update/remove one highlight entry in the per-source md file."""
    url = data.get('url', '')
    hl_id = data.get('id', '')
    if not url or not hl_id:
        return
    md_path = md_path_for_url(url)
    marker = f"<!--hl:{hl_id}-->"

    if remove:
        if md_path.exists():
            content = md_path.read_text(encoding='utf-8')
            new_content = re.sub(
                re.escape(marker) + r'.*?(?=<!--hl:|\Z)',
                '', content, flags=re.DOTALL)
            if new_content.strip() != content.strip():
                md_path.write_text(new_content.rstrip() + "\n", encoding='utf-8')
        return

    block = _hl_entry_block(data)
    if md_path.exists():
        content = md_path.read_text(encoding='utf-8')
        # Replace existing entry if present, otherwise append
        if marker in content:
            content = re.sub(
                re.escape(marker) + r'.*?(?=<!--hl:|\Z)',
                block, content, flags=re.DOTALL)
        else:
            content = content.rstrip() + "\n\n" + block
        md_path.write_text(content.rstrip() + "\n", encoding='utf-8')
    else:
        SOURCES_DIR.mkdir(parents=True, exist_ok=True)
        md = f"""---
source: {url}
page_title: "{data.get('page_title', '')}"
type: web_highlight
---

## 📌 Web Highlights

{block}"""
        md_path.write_text(md, encoding='utf-8')


def load_web_highlight(filepath):
    """Load a web highlight JSON file."""
    try:
        data = json.loads(filepath.read_text(encoding='utf-8'))
        data['_path'] = str(filepath)
        data['_type'] = 'web'
        data.setdefault('note', '')
        return data
    except Exception:
        return None


def load_all_highlights(limit=None):
    """Load all highlights (both web JSON and CLI markdown)."""
    results = []

    # Load web highlights (JSON)
    web_files = sorted(EXT_DIR.rglob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    for fp in web_files:
        h = load_web_highlight(fp)
        if h:
            results.append(h)

    # Load CLI highlights (markdown) - only those not already in web format
    # Markdown files with type: web_highlight are already covered by JSON
    md_files = sorted(HIGHLIGHTS_DIR.rglob('*.md'), key=lambda p: p.stat().st_mtime, reverse=True)
    for fp in md_files:
        # Check if it's a web highlight duplicate (has corresponding JSON)
        content = fp.read_text(encoding='utf-8')
        if 'type: web_highlight' in content or '_web/' in str(fp):
            continue
        # Parse basic info
        h = parse_md_highlight(fp, content)
        if h:
            results.append(h)

    if limit:
        results = results[:limit]
    return results


def parse_md_highlight(fp, content):
    """Parse a markdown highlight file."""
    h = {
        '_path': str(fp),
        '_type': 'cli',
        'filename': fp.name,
        'mtime': datetime.datetime.fromtimestamp(fp.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
        'quote': '',
        'color': 'yellow',
        'note': '',
        'url': '',
    }

    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)
        for line in fm_text.split('\n'):
            m = re.match(r'^(\w+):\s*(.*)', line)
            if m:
                key = m.group(1)
                val = m.group(2).strip().strip('"\'')
                h[key] = val

        qm = re.search(r'(?:\n|^)> (.+?)(?:\n|$)', body)
        if qm:
            h['quote'] = qm.group(1).strip()

        cm = re.search(r'📝\s*\*\*(?:注释|笔记|Note)\*\*:\s*(.+?)(?:\n|$)', body)
        if cm:
            h['note'] = cm.group(1).strip()

        um = re.search(r'Source:\s*\[(.+?)\]\((.+?)\)', body)
        if um:
            h['url'] = um.group(2)

    h.setdefault('hex_color', VALID_COLORS.get(h['color'], '#FFF176'))
    h.setdefault('text', h.get('quote', fp.stem[:80]))
    h.setdefault('page_title', '')
    return h


def get_highlights_for_url(url):
    """Get all web highlights for a specific URL."""
    results = []
    for fp in sorted(EXT_DIR.rglob('*.json'), key=lambda p: p.stat().st_mtime):
        h = load_web_highlight(fp)
        if h and h.get('url') == url:
            results.append(h)
    return results


def delete_highlight(hl_id):
    """Delete a highlight by ID."""
    count = 0
    for fp in EXT_DIR.rglob('*.json'):
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            if data.get('id') == hl_id:
                fp.unlink()
                count += 1
                # Remove its entry from the per-source aggregated markdown
                upsert_highlight_in_md(data, remove=True)
                break
        except Exception:
            pass
    return count


# ─── Web UI HTML ──────────────────────────────────────────────────────

WEB_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Highlights Everywhere</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f7; color: #1d1d1f;
}
.header {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white; padding: 40px 20px; text-align: center;
}
.header h1 { font-size: 32px; margin-bottom: 8px; }
.header p { opacity: 0.85; }
.header .stats { margin-top: 12px; font-size: 14px; opacity: 0.75; }

.toolbar {
    display: flex; gap: 12px; padding: 16px 24px;
    background: white; border-bottom: 1px solid #e5e5e7;
    flex-wrap: wrap; align-items: center;
    position: sticky; top: 0; z-index: 10;
}
.toolbar input[type="text"] {
    flex: 1; min-width: 200px; padding: 10px 14px;
    border: 1px solid #d2d2d7; border-radius: 8px; font-size: 14px; outline: none;
}
.toolbar input:focus { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102,126,234,0.15); }
.toolbar select, .toolbar button {
    padding: 10px 14px; border: 1px solid #d2d2d7; border-radius: 8px;
    font-size: 14px; background: white; cursor: pointer;
}
.toolbar button { background: #667eea; color: white; border: none; font-weight: 600; }
.toolbar button:hover { background: #5a6fd6; }

.grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 16px; padding: 24px; max-width: 1400px; margin: 0 auto;
}
.card {
    background: white; border-radius: 12px; overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    transition: transform 0.2s, box-shadow 0.2s;
    border-left: 4px solid #ccc;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.1); }
.card-body { padding: 16px 20px; }
.card .meta {
    font-size: 12px; color: #86868b; margin-bottom: 8px;
    display: flex; justify-content: space-between; align-items: center;
}
.card .color-badge {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 11px; font-weight: 600; text-transform: uppercase;
}
.card .quote {
    font-size: 15px; line-height: 1.6; padding: 12px 16px;
    border-radius: 8px; margin: 8px 0;
    position: relative;
}
.card .note {
    background: #f0f4ff; padding: 10px 14px; border-radius: 8px;
    margin-top: 10px; font-size: 14px; border-left: 3px solid #667eea;
}
.card .note .label { font-weight: 600; font-size: 11px; color: #667eea; text-transform: uppercase; display: block; margin-bottom: 4px; }
.card .footer {
    padding: 10px 20px; background: #fafafa; border-top: 1px solid #f0f0f0;
    font-size: 12px; color: #86868b;
}
.card .footer a { color: #667eea; text-decoration: none; }
.card .footer a:hover { text-decoration: underline; }
.tag-badge {
    display: inline-block; background: #f0f0f5; padding: 2px 8px;
    border-radius: 4px; font-size: 11px; margin: 2px; color: #515154;
}
.empty-state { text-align: center; padding: 80px 20px; color: #86868b; }
.empty-state h2 { font-size: 24px; margin-bottom: 8px; }

.source-web::before { content: '🌐 '; }
.source-cli::before { content: '💻 '; }

@media (max-width: 600px) {
    .grid { grid-template-columns: 1fr; padding: 12px; }
    .toolbar { padding: 12px; }
}
</style>
</head>
<body>
<div class="header">
    <h1>📌 Highlights Everywhere</h1>
    <p>网页标注 + 笔记，Spotlight 搜索</p>
    <div class="stats" id="header-stats"></div>
</div>
<div class="toolbar">
    <input type="text" id="search-input" placeholder="🔍 搜索高亮内容..." oninput="filterCards()">
    <select id="color-filter" onchange="filterCards()">
        <option value="">全部颜色</option>
        <option value="yellow">🟡 黄色</option>
        <option value="green">🟢 绿色</option>
        <option value="blue">🔵 蓝色</option>
        <option value="red">🔴 红色</option>
        <option value="purple">🟣 紫色</option>
        <option value="orange">🟠 橙色</option>
        <option value="pink">🩷 粉色</option>
    </select>
    <select id="source-filter" onchange="filterCards()">
        <option value="">全部来源</option>
        <option value="web">🌐 网页</option>
        <option value="cli">💻 命令行</option>
    </select>
    <button onclick="resetFilters()">✕ 重置</button>
</div>
<div class="grid" id="card-grid"></div>

<script>
const STYLES = {
    yellow:{bg:'#FFF9C4',border:'#FDD835',badge:'#F9A825'},
    green:{bg:'#C8E6C9',border:'#66BB6A',badge:'#388E3C'},
    blue:{bg:'#BBDEFB',border:'#42A5F5',badge:'#1565C0'},
    red:{bg:'#FFCDD2',border:'#EF5350',badge:'#D32F2F'},
    purple:{bg:'#E1BEE7',border:'#AB47BC',badge:'#7B1FA2'},
    orange:{bg:'#FFE0B2',border:'#FF9800',badge:'#E65100'},
    pink:{bg:'#F8BBD0',border:'#EC407A',badge:'#C2185B'},
};
const COLOR_NAMES = {yellow:'黄色',green:'绿色',blue:'蓝色',red:'红色',purple:'紫色',orange:'橙色',pink:'粉色'};

let allItems = [];

async function load() {
    try {
        const r = await fetch('/api/highlights');
        const d = await r.json();
        allItems = d.highlights || [];
        document.getElementById('header-stats').textContent =
            `共 ${allItems.length} 条高亮 · ${d.stats?.by_type?.web||0} 网页 · ${d.stats?.by_type?.cli||0} 笔记`;
        render(allItems);
    } catch(e) {
        document.getElementById('card-grid').innerHTML = `<div class="empty-state"><h2>❌ 加载失败</h2><p>${e.message}</p></div>`;
    }
}

function render(items) {
    const grid = document.getElementById('card-grid');
    if (!items.length) {
        grid.innerHTML = `<div class="empty-state"><h2>📭 还没有高亮</h2><p>安装 Chrome 扩展后，选中网页文字就能标注</p></div>`;
        return;
    }
    grid.innerHTML = items.map(h => {
        const c = h.color || 'yellow';
        const s = STYLES[c] || STYLES.yellow;
        const isWeb = h._type === 'web';
        const url = h.url || '';
        const note = h.note || '';
        const text = h.text || h.quote || '';

        return `<div class="card" style="border-left-color:${s.border}">
            <div class="card-body">
                <div class="meta">
                    <span class="${isWeb ? 'source-web' : 'source-cli'}">${h.mtime || ''}</span>
                    <span class="color-badge" style="background:${s.badge};color:white">${COLOR_NAMES[c]||c}</span>
                </div>
                <div class="quote" style="background:${s.bg}">
                    ${esc(text)}
                </div>
                ${note ? `<div class="note"><span class="label">💬 笔记</span>${esc(note)}</div>` : ''}
                ${h.page_title ? `<div style="margin-top:8px;font-size:12px;color:#86868b;">📄 ${esc(h.page_title)}</div>` : ''}
            </div>
            <div class="footer">
                ${url ? `<a href="${esc(url)}" target="_blank">🔗 ${trunc(url.replace(/https?:\/\//,''), 40)}</a>` : '<span>📱 本地笔记</span>'}
                <span>${isWeb ? '🌐 网页标注' : '💻 本地保存'}</span>
            </div>
        </div>`;
    }).join('');
}

function esc(s) { if(!s)return ''; const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
function trunc(s,n) { return s.length > n ? s.slice(0,n)+'...' : s; }

function resetFilters() {
    document.getElementById('search-input').value = '';
    document.getElementById('color-filter').value = '';
    document.getElementById('source-filter').value = '';
    render(allItems);
}

function filterCards() {
    const q = document.getElementById('search-input').value.toLowerCase();
    const cf = document.getElementById('color-filter').value;
    const sf = document.getElementById('source-filter').value;
    const filtered = allItems.filter(h => {
        if (cf && h.color !== cf) return false;
        if (sf && h._type !== sf) return false;
        if (q) {
            const t = ((h.text||'') + ' ' + (h.note||'') + ' ' + (h.page_title||'') + ' ' + (h.url||'')).toLowerCase();
            return t.includes(q);
        }
        return true;
    });
    render(filtered);
}
load();
</script>
</body>
</html>"""


# ─── HTTP Server ──────────────────────────────────────────────────────

class HighlightHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/':
            self.send_html(WEB_HTML)

        elif parsed.path == '/api/highlights':
            self.handle_get_highlights(params)

        elif parsed.path == '/highlight.user.js':
            self.send_userscript()

        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else '{}'
        data = json.loads(body) if body else {}

        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == '/api/highlights':
            self.handle_create_highlight(data)
        elif parsed.path == '/api/highlights/delete':
            self.handle_delete_highlight(data)
        elif parsed.path == '/api/highlights/update':
            self.handle_update_highlight(data)
        else:
            self.send_json({'error': 'Not found'}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    # --- Handlers ---

    def handle_get_highlights(self, params):
        url = params.get('url', [None])[0]

        if url:
            # Filter by URL (for Chrome extension)
            highlights = get_highlights_for_url(url)
        else:
            # All highlights (for web UI)
            highlights = load_all_highlights(limit=500)

        # Stats
        n_web = sum(1 for h in highlights if h.get('_type') == 'web')
        n_cli = len(highlights) - n_web
        latest = highlights[0].get('mtime', 'N/A') if highlights else 'N/A'

        self.send_json({
            'highlights': highlights,
            'total': len(highlights),
            'latest': latest,
            'stats': {'by_type': {'web': n_web, 'cli': n_cli}},
            'colors': list(VALID_COLORS.keys()),
        })

    def handle_create_highlight(self, data):
        """Create a web highlight (from Chrome extension)."""
        url = data.get('url', '')
        text = data.get('text', '')
        color = data.get('color', 'yellow')
        note = data.get('note', '')
        selector = data.get('selector', {})
        page_title = data.get('page_title', '')

        if not url or not text:
            self.send_json({'error': 'Missing url or text'}, 400)
            return

        result = save_web_highlight(url, text, color, note, selector, page_title)
        self.send_json({'success': True, 'highlight': result})

    def handle_delete_highlight(self, data):
        hl_id = data.get('id', '')
        if not hl_id:
            self.send_json({'error': 'Missing id'}, 400)
            return
        count = delete_highlight(hl_id)
        self.send_json({'success': True, 'deleted': count})

    def handle_clear_url_highlights(self):
        """Clear all highlights for a URL."""
        pass

    def handle_update_highlight(self, data):
        """Update a highlight's note and/or color."""
        hl_id = data.get('id', '')
        new_note = data.get('note', None)
        new_color = data.get('color', None)
        if not hl_id:
            self.send_json({'error': 'Missing id'}, 400)
            return
        count = 0
        for fp in EXT_DIR.rglob('*.json'):
            try:
                existing = json.loads(fp.read_text(encoding='utf-8'))
                if existing.get('id') == hl_id:
                    if new_note is not None:
                        existing['note'] = new_note
                    if new_color is not None:
                        existing['color'] = new_color
                        existing['hex_color'] = VALID_COLORS.get(new_color, '#FFF176')
                    existing['updated_at'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    fp.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n")
                    count = 1
                    break
            except Exception:
                pass
        if count:
            # Also update the corresponding markdown file
            id_prefix = hl_id[:14]  # YYYYMMDDHHMMSS
            md_date = f"{hl_id[:4]}-{hl_id[4:6]}-{hl_id[6:8]}"
            md_time = hl_id[8:14]
            md_dir = HIGHLIGHTS_DIR / hl_id[:4] / hl_id[4:6]
            for md_fp in md_dir.glob(f"{md_date}-{md_time}-*.md"):
                try:
                    md_content = md_fp.read_text(encoding='utf-8')
                    # Update note in frontmatter
                    if new_note is not None:
                        # Update body note line: (optionally quoted) 💬 **备注**: ...
                        md_content = re.sub(
                            r'^>? *💬 \*\*备注\*\*: .*$',
                            f'> 💬 **备注**: {new_note}',
                            md_content,
                            flags=re.MULTILINE
                        )
                    if new_color is not None:
                        new_hex = VALID_COLORS.get(new_color, '#FFF176')
                        md_content = re.sub(r'^color: .*', f'color: {new_color}', md_content, flags=re.MULTILINE)
                        md_content = re.sub(r'^hex_color: .*', f'hex_color: {new_hex}', md_content, flags=re.MULTILINE)
                        # Also update the inline style span
                        md_content = re.sub(
                            r'background-color:#[0-9A-Fa-f]+',
                            f'background-color:{new_hex}',
                            md_content
                        )
                    md_fp.write_text(md_content, encoding='utf-8')
                except Exception:
                    pass
            # Sync the per-source aggregated markdown entry
            try:
                upsert_highlight_in_md(existing)
            except Exception:
                pass
            self.send_json({'success': True, 'highlight': existing})
        else:
            self.send_json({'error': 'Not found'}, 404)

    # --- Helpers ---

    def send_userscript(self):
        """Serve the Tampermonkey userscript."""
        port = self.server.server_address[1]
        script = """// ==UserScript==
// @name         Highlights Everywhere
// @name:zh-CN   高亮无处不在
// @namespace    http://localhost:__PORT__/
// @version      1.1.1
// @description  Highlight text on any webpage with colors + notes. Click highlights to edit/delete.
// @author       pengdan
// @match        http://*/*
// @match        https://*/*
// @match        file:///*
// @connect      localhost
// @grant        none
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';
    if (window.__hlInjected) return;
    window.__hlInjected = true;

    var SERVER = 'http://localhost:__PORT__';
    var COLORS = {
        yellow:  {bg:'#FFF9C4',border:'#FDD835'},
        green:   {bg:'#C8E6C9',border:'#66BB6A'},
        blue:    {bg:'#BBDEFB',border:'#42A5F5'},
        red:     {bg:'#FFCDD2',border:'#EF5350'},
        purple:  {bg:'#E1BEE7',border:'#AB47BC'},
        orange:  {bg:'#FFE0B2',border:'#FF9800'},
        pink:    {bg:'#F8BBD0',border:'#EC407A'},
    };
    var CNAMES = Object.keys(COLORS);
    var applied = {};
    var toolbar = null;
    var tooltipEl = null;

    function api(m, p, b) {
        var o = {method:m, headers:{'Content-Type':'application/json'}};
        if (b) o.body = JSON.stringify(b);
        return fetch(SERVER + p, o).then(function(r){return r.json()}).catch(function(e){console.warn('[HL]',e);return null});
    }

    function loadHL() {
        api('GET', '/api/highlights?url='+encodeURIComponent(location.href)).then(function(d) {
            if (!d||!d.highlights) return;
            d.highlights.forEach(applyHL);
            console.log('[HL] Loaded', d.highlights.length);
        });
    }

    function applyHL(h) {
        if (applied[h.id]) return;
        var t = (h.text||'').trim();
        if (!t) return;
        var nodes = findText(document.body, t);
        if (!nodes.length) return;
        var n = nodes[0], idx = n.textContent.indexOf(t);
        var r = document.createRange();
        r.setStart(n, idx); r.setEnd(n, idx + t.length);
        var c = h.color||'yellow', s = COLORS[c]||COLORS.yellow;
        var sp = document.createElement('hl-span');
        sp.setAttribute('data-hl-id', h.id);
        sp.setAttribute('data-hl-color', c);
        sp.setAttribute('data-hl-note', h.note||'');
        sp.style.cssText = 'background:'+s.bg+';border-bottom:2px solid '+s.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
        sp.title = h.note ? (h.note.length > 50 ? h.note.slice(0,50)+'...' : h.note) : c;
        try {
            r.surroundContents(sp);
            applied[h.id] = true;
            sp.addEventListener('click', function(e) { e.stopPropagation(); showEdit(e, sp, h); });
        } catch(e) {}
    }

    function findText(root, text) {
        var r=[],w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null,false),n;
        while (n=w.nextNode()) {
            if (n.textContent.indexOf(text)>=0&&!inHL(n.parentElement)) { r.push(n); if(r.length>=5) break; }
        }
        return r;
    }
    function inHL(el) { while(el) { if (el.tagName==='HL-SPAN') return true; el=el.parentElement; } return false; }

    // ── Selection → Toolbar ──
    document.addEventListener('mouseup', function(e) {
        if (e.target.closest('hl-toolbar')||e.target.closest('hl-span')||e.target.closest('hl-tooltip')) return;
        var sel = window.getSelection();
        if (!sel||sel.isCollapsed||!sel.toString().trim()) return;
        showToolbar(sel.getRangeAt(0), sel.toString().trim());
    });

    document.addEventListener('mousedown', function(e) {
        if (e.target.closest('hl-toolbar')||e.target.closest('hl-tooltip')) e.stopPropagation();
    });

    function showToolbar(range, text) {
        hideToolbar();
        // Wrap selected text in a temporary transparent-blue span to replace native selection
        var tempSpan = null;
        try {
            var c = range.cloneContents();
            if (c.textContent.trim() === text) {
                tempSpan = document.createElement('hl-temp');
                tempSpan.style.cssText = 'background:rgba(59,130,246,0.2);border-radius:2px;padding:0 2px;';
                range.surroundContents(tempSpan);
            }
        } catch(e) {}
        // If surroundContents failed, range might be invalid; get current selection
        if (!tempSpan) {
            try {
                var sel2 = window.getSelection();
                if (sel2 && !sel2.isCollapsed) {
                    range = sel2.getRangeAt(0);
                    tempSpan = document.createElement('hl-temp');
                    tempSpan.style.cssText = 'background:rgba(59,130,246,0.2);border-radius:2px;padding:0 2px;';
                    range.surroundContents(tempSpan);
                }
            } catch(e2) {}
        }

        var div = document.createElement('hl-toolbar');
        div.style.cssText = 'position:fixed;z-index:2147483647;font-family:sans-serif;font-size:13px;';

        var btns = '';
        for (var i=0;i<CNAMES.length;i++) {
            var cn=CNAMES[i], b=cn==='yellow'?'2px solid '+COLORS[cn].border:'2px solid transparent';
            btns += '<button class="hc" data-c="'+cn+'" style="width:24px;height:24px;border-radius:50%;cursor:pointer;background:'+COLORS[cn].bg+';border:'+b+';margin:0 1px;display:inline-block;vertical-align:middle;" title="'+cn+'"></button>';
        }
        div.innerHTML = '<div style="display:flex;align-items:center;gap:3px;padding:6px 10px;background:white;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);border:1px solid #e0e0e0;">'
            + btns
            + '<input class="hn" placeholder="\u5907\u6CE8..." style="width:120px;padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;outline:none;vertical-align:middle;">'
            + '<button class="hs" style="padding:4px 12px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600;vertical-align:middle;">\u2713</button>'
            + '<button class="hx" style="padding:4px 8px;background:none;color:#999;border:none;cursor:pointer;font-size:16px;vertical-align:middle;">\u00D7</button>'
            + '</div>';
        document.body.appendChild(div);

        var savedId = null;
        var savedColor = null;
        var savedSpan = null;

        // Color button: immediately highlight
        div.querySelectorAll('.hc').forEach(function(b) {
            b.addEventListener('click', function() {
                var col = this.dataset.c;
                // If already highlighted with a color, update it
                if (savedSpan) {
                    // Just update the visual
                    var ns = COLORS[col]||COLORS.yellow;
                    savedSpan.style.cssText = 'background:'+ns.bg+';border-bottom:2px solid '+ns.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
                    savedSpan.setAttribute('data-hl-color', col);
                    savedColor = col;
                    // Update on server
                    if (savedId) {
                        var inp = div.querySelector('.hn');
                        var note = inp?inp.value.trim():'';
                        api('POST', '/api/highlights/update', {id:savedId, color:col, note:note});
                    }
                } else {
                    // First time: do the highlight
                    var s = COLORS[col]||COLORS.yellow;
                    var sp = document.createElement('hl-span');
                    sp.style.cssText = 'background:'+s.bg+';border-bottom:2px solid '+s.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
                    try { range.surroundContents(sp); } catch(e) { return; }

                    api('POST', '/api/highlights', {
                        url: location.href, page_title: document.title,
                        text: text, color: col, note: '', selector: {}
                    }).then(function(data) {
                        if (data&&data.highlight&&data.highlight.id) {
                            sp.setAttribute('data-hl-id', data.highlight.id);
                            sp.setAttribute('data-hl-color', col);
                            sp.setAttribute('data-hl-note', '');
                            sp.title = col;
                            applied[data.highlight.id] = true;
                            sp.addEventListener('click', function(e) { e.stopPropagation(); showEdit(e, sp, data.highlight); });
                            savedId = data.highlight.id;
                        }
                    });
                    savedSpan = sp;
                    savedColor = col;
                }
                // Visual feedback
                div.querySelectorAll('.hc').forEach(function(x){x.style.border='2px solid transparent'});
                this.style.border = '2px solid #333';
            });
        });

        // Save note
        div.querySelector('.hs').addEventListener('click', function() {
            var inp = div.querySelector('.hn');
            var note = inp?inp.value.trim():'';
            if (savedId) {
                api('POST', '/api/highlights/update', {id:savedId, note:note, color:savedColor});
                if (savedSpan) {
                    savedSpan.setAttribute('data-hl-note', note);
                    savedSpan.title = note||savedColor;
                }
            } else if (text) {
                // No color clicked yet, use default yellow
                var s = COLORS.yellow;
                var sp = document.createElement('hl-span');
                sp.style.cssText = 'background:'+s.bg+';border-bottom:2px solid '+s.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
                try { range.surroundContents(sp); } catch(e) { hideToolbar(); return; }
                api('POST', '/api/highlights', {
                    url: location.href, page_title: document.title,
                    text: text, color: 'yellow', note: note, selector: {}
                }).then(function(data) {
                    if (data&&data.highlight&&data.highlight.id) {
                        sp.setAttribute('data-hl-id', data.highlight.id);
                        sp.setAttribute('data-hl-color', 'yellow');
                        sp.setAttribute('data-hl-note', note);
                        sp.title = note||'yellow';
                        applied[data.highlight.id] = true;
                        sp.addEventListener('click', function(e) { e.stopPropagation(); showEdit(e, sp, data.highlight); });
                    }
                });
            }
            hideToolbar();
        });
        div.querySelector('.hx').addEventListener('click', function() {
            // If already highlighted, delete it
            if (savedId) {
                api('POST', '/api/highlights/delete', {id:savedId});
                if (savedSpan) { savedSpan.outerHTML = savedSpan.textContent; delete applied[savedId]; }
            }
            hideToolbar();
        });

        var rect = range.getBoundingClientRect();
        var top = rect.top - 56 + window.scrollY;
        var left = rect.left + window.scrollX;
        if (top < 10) { top = rect.bottom + 8 + window.scrollY; }
        div.style.top = Math.max(top, 8) + 'px';
        div.style.left = Math.max(Math.min(left, window.innerWidth-340), 8) + 'px';
        div.style.display = 'block';
        toolbar = div;
        var inp = div.querySelector('.hn');
    }

    function hideToolbar() { if (toolbar) { toolbar.remove(); toolbar=null; } }

    function saveHL(range, text, color, div) {
        if (!text) { hideToolbar(); return; }
        var inp = div?div.querySelector('.hn'):null;
        var note = inp?inp.value.trim():'';
        var s = COLORS[color]||COLORS.yellow;
        var sp = document.createElement('hl-span');
        sp.style.cssText = 'background:'+s.bg+';border-bottom:2px solid '+s.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
        try { range.surroundContents(sp); } catch(e) { hideToolbar(); return; }

        api('POST', '/api/highlights', {
            url: location.href, page_title: document.title,
            text: text, color: color, note: note, selector: {}
        }).then(function(data) {
            if (data&&data.highlight&&data.highlight.id) {
                sp.setAttribute('data-hl-id', data.highlight.id);
                sp.setAttribute('data-hl-color', color);
                sp.setAttribute('data-hl-note', note);
                sp.title = note||color;
                applied[data.highlight.id] = true;
                sp.addEventListener('click', function(e) { e.stopPropagation(); showEdit(e, sp, data.highlight); });
            }
        });
        hideToolbar();
    }

    // ── Click highlight → Edit popup ──
    function showEdit(e, sp, h) {
        if (tooltipEl) tooltipEl.remove();
        var t = document.createElement('hl-tooltip');
        var color = h.color||'yellow';
        var note = h.note||'';
        var s = COLORS[color]||COLORS.yellow;

        var colorOpts = '';
        for (var i=0;i<CNAMES.length;i++) {
            var cn=CNAMES[i];
            var chk = cn===color ? 'border:2px solid #333;transform:scale(1.15);' : 'border:2px solid transparent;';
            colorOpts += '<button class="ec" data-c="'+cn+'" style="width:20px;height:20px;border-radius:50%;cursor:pointer;background:'+COLORS[cn].bg+';'+chk+'margin:0 1px;display:inline-block;vertical-align:middle;" title="'+cn+'"></button>';
        }

        t.innerHTML = '<div style="background:white;border-radius:8px;padding:10px 12px;box-shadow:0 4px 20px rgba(0,0,0,0.2);border:1px solid #e0e0e0;max-width:300px;font-family:sans-serif;font-size:13px;">'
            + '<div style="margin-bottom:6px;color:#666;font-size:11px;">'+String.fromCharCode(0x1F58D)+' <b>'+esc(h.text||'')+'</b></div>'
            + '<div style="margin-bottom:6px;">'+colorOpts+'</div>'
            + '<textarea class="en" style="width:100%;padding:6px;border:1px solid #ddd;border-radius:4px;font-size:12px;resize:vertical;min-height:40px;box-sizing:border-box;" placeholder="'+String.fromCharCode(0x5907,0x6CE8)+'...">'+esc(note)+'</textarea>'
            + '<div style="margin-top:6px;display:flex;gap:6px;">'
            + '<button class="es" style="flex:1;padding:5px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600;">'+String.fromCharCode(0x4FDD,0x5B58)+'</button>'
            + '<button class="ed" style="padding:5px 10px;background:#fee;color:#c33;border:1px solid #fcc;border-radius:4px;cursor:pointer;font-size:12px;">'+String.fromCharCode(0x1F5D1)+' '+String.fromCharCode(0x5220,0x9664)+'</button>'
            + '</div>'
            + '</div>';
        t.style.cssText = 'position:fixed;z-index:2147483647;top:'+Math.max(e.clientY-10,5)+'px;left:'+Math.min(e.clientX+10,window.innerWidth-320)+'px;';
        document.body.appendChild(t);
        tooltipEl = t;

        // Color change
        var newColor = color;
        t.querySelectorAll('.ec').forEach(function(b) {
            b.addEventListener('click', function() {
                newColor = this.dataset.c;
                t.querySelectorAll('.ec').forEach(function(x){x.style.borderColor='transparent';x.style.transform='scale(1)'});
                this.style.borderColor='#333'; this.style.transform='scale(1.15)';
            });
        });

        // Save edits
        t.querySelector('.es').addEventListener('click', function() {
            var newNote = (t.querySelector('.en').value||'').trim();
            api('POST', '/api/highlights/update', {id: h.id, note: newNote, color: newColor}).then(function(d) {
                if (d&&d.success) {
                    sp.setAttribute('data-hl-color', newColor);
                    sp.setAttribute('data-hl-note', newNote);
                    var ns = COLORS[newColor]||COLORS.yellow;
                    sp.style.cssText = 'background:'+ns.bg+';border-bottom:2px solid '+ns.border+';cursor:pointer;border-radius:2px;padding:0 2px;';
                    sp.title = newNote||newColor;
                    h.note = newNote;
                    h.color = newColor;
                }
                if (tooltipEl) tooltipEl.remove();
            });
        });

        // Delete
        t.querySelector('.ed').addEventListener('click', function() {
            api('POST', '/api/highlights/delete', {id: h.id}).then(function() {
                sp.outerHTML = sp.textContent;
                delete applied[h.id];
                if (tooltipEl) tooltipEl.remove();
            });
        });

        setTimeout(function() {
            document.addEventListener('click', function _c(e2) {
                if (tooltipEl&&!tooltipEl.contains(e2.target)) { tooltipEl.remove();tooltipEl=null;document.removeEventListener('click',_c); }
            });
        }, 100);
    }

    function esc(s) { if (!s) return ''; var d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

    setTimeout(loadHL, 500);
    window.addEventListener('load', function(){setTimeout(loadHL,1000)});
    console.log('[HL] Ready');
})();
"""
        script = script.replace('__PORT__', str(port))
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Type', 'application/javascript; charset=utf-8')
        self.end_headers()
        self.wfile.write(script.encode('utf-8'))

    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, format, *args):
        pass  # Suppress logs


def start_server(daemon=False):
    """Start the highlights server."""
    port = WEB_PORT
    for attempt in range(10):
        try:
            server = socketserver.TCPServer(("", port), HighlightHandler)
            break
        except OSError:
            port += 1
    else:
        if not daemon:
            print("❌ Could not find a free port")
        return port

    if not daemon:
        print(f"\n{'='*50}")
        print(f"  🌐 Highlights Everywhere Server")
        print(f"  {'='*50}")
        print(f"  Web UI:       http://localhost:{port}")
        print(f"  API:          http://localhost:{port}/api/highlights")
        print(f"  Data:         {HIGHLIGHTS_DIR}")
        print(f"  {'='*50}\n")
        print("  Press Ctrl+C to stop\n")
        webbrowser.open(f'http://localhost:{port}')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        if not daemon:
            print("\n👋 Server stopped.")
        server.shutdown()
    return port


if __name__ == '__main__':
    daemon = '--daemon' in sys.argv
    start_server(daemon=daemon)
