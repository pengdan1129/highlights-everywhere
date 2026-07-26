// Highlights Everywhere - Content Script
// Injected into every page: handles text selection & highlight display

// Debug: show content script loaded
console.log('[HL] Content script loaded on:', window.location.href);

// Add a small debug indicator (removes after 5s)
const debugEl = document.createElement('div');
debugEl.textContent = '📌 HL loaded';
debugEl.style.cssText = 'position:fixed;bottom:10px;right:10px;z-index:2147483647;background:#667eea;color:white;padding:4px 10px;border-radius:4px;font-size:11px;font-family:sans-serif;opacity:0.8;';
document.body.appendChild(debugEl);
setTimeout(() => { debugEl.style.opacity = '0'; debugEl.style.transition = 'opacity 1s'; setTimeout(() => debugEl.remove(), 1000); }, 5000);

const COLORS = {
  yellow: { bg: '#FFF176', border: '#FDD835' },
  green:  { bg: '#A5D6A7', border: '#66BB6A' },
  blue:   { bg: '#90CAF9', border: '#42A5F5' },
  red:    { bg: '#EF9A9A', border: '#EF5350' },
  purple: { bg: '#CE93D8', border: '#AB47BC' },
  orange: { bg: '#FFCC80', border: '#FF9800' },
  pink:   { bg: '#F48FB1', border: '#EC407A' },
};

let toolbar = null;
let appliedIds = new Set();

// ─── Apply highlights on page load ──────────────────────────────────

async function loadAndApplyHighlights() {
  try {
    const resp = await chrome.runtime.sendMessage({
      action: 'get-highlights',
      url: window.location.href
    });
    if (!resp.ok) return;
    const highlights = resp.data || [];
    for (const h of highlights) {
      applyHighlight(h);
    }
    console.log(`[HL] Applied ${highlights.length} highlights`);
  } catch (e) {
    if (!e.message?.includes('Could not establish connection')) {
      console.warn('[HL] Load error:', e.message);
    }
  }
}

function applyHighlight(h) {
  if (appliedIds.has(h.id)) return;

  const color = h.color || 'yellow';
  const style = COLORS[color] || COLORS.yellow;
  const text = h.text || '';

  if (!text) return;

  // Try to find the text in the page
  const textNodes = findTextNodes(document.body, text);
  if (textNodes.length === 0) return;

  const node = textNodes[0];
  const range = document.createRange();
  range.setStart(node, node.textContent.indexOf(text));
  range.setEnd(node, node.textContent.indexOf(text) + text.length);

  const span = document.createElement('hl-span');
  span.setAttribute('data-hl-id', h.id);
  span.setAttribute('data-hl-color', color);
  span.style.backgroundColor = style.bg;
  span.style.borderBottom = `2px solid ${style.border}`;
  span.style.cursor = 'pointer';
  span.style.borderRadius = '2px';
  span.style.padding = '0 2px';
  span.title = h.note ? `💬 ${h.note}` : `🖍 ${color}`;

  range.surroundContents(span);
  appliedIds.add(h.id);

  // Add click handler to show note
  span.addEventListener('click', (e) => {
    e.stopPropagation();
    showTooltip(e, span);
  });
}

function findTextNodes(root, text) {
  const results = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
  let node;
  while (node = walker.nextNode()) {
    const idx = node.textContent.indexOf(text);
    if (idx !== -1 && !isInsideHighlight(node.parentElement)) {
      results.push(node);
      if (results.length >= 5) break; // Limit to avoid huge DOM walks
    }
  }
  return results;
}

function isInsideHighlight(el) {
  while (el) {
    if (el.tagName === 'HL-SPAN') return true;
    el = el.parentElement;
  }
  return false;
}

// ─── Selection toolbar ──────────────────────────────────────────────

function createToolbar() {
  if (toolbar) toolbar.remove();

  toolbar = document.createElement('hl-toolbar');
  toolbar.innerHTML = `
    <div style="display:flex;align-items:center;gap:4px;padding:6px 10px;background:white;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);border:1px solid #e0e0e0;font-family:-apple-system,sans-serif;font-size:13px;">
      ${Object.keys(COLORS).map(c => `
        <button class="hl-btn hl-${c}" data-color="${c}" title="${c}" 
          style="width:22px;height:22px;border-radius:50%;border:2px solid transparent;cursor:pointer;background:${COLORS[c].bg};transition:all 0.15s;"
          onmouseover="this.style.transform='scale(1.2)'" onmouseout="this.style.transform='scale(1)'"></button>
      `).join('')}
      <input type="text" id="hl-note-input" placeholder="备注..." 
        style="width:120px;padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;outline:none;">
      <button id="hl-save-btn" 
        style="padding:4px 12px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600;">✓</button>
      <button id="hl-cancel-btn" 
        style="padding:4px 8px;background:transparent;color:#999;border:none;cursor:pointer;font-size:16px;">×</button>
    </div>
  `;
  toolbar.style.cssText = 'position:fixed;z-index:2147483647;display:none;';
  document.body.appendChild(toolbar);

  // Color selection
  let selectedColor = 'yellow';
  toolbar.querySelectorAll('.hl-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      selectedColor = btn.dataset.color;
      toolbar.querySelectorAll('.hl-btn').forEach(b => b.style.borderColor = 'transparent');
      btn.style.borderColor = COLORS[selectedColor].border;
    });
    btn.style.borderColor = 'transparent';
  });
  // Default: first button highlighted
  const firstBtn = toolbar.querySelector('.hl-btn');
  if (firstBtn) { firstBtn.style.borderColor = COLORS.yellow.border; }

  // Save button
  toolbar.querySelector('#hl-save-btn').addEventListener('click', saveHighlight);
  toolbar.querySelector('#hl-cancel-btn').addEventListener('click', hideToolbar);

  return toolbar;
}

function showToolbar(range) {
  if (!toolbar) createToolbar();
  const rect = range.getBoundingClientRect();
  toolbar.style.display = 'block';
  toolbar.style.top = `${Math.max(rect.top - 50, 10) + window.scrollY}px`;
  toolbar.style.left = `${Math.min(rect.left + window.scrollX, window.innerWidth - 300)}px`;
  toolbar.querySelector('#hl-note-input').value = '';
  toolbar.querySelector('#hl-note-input').focus();
  toolbar._range = range;
}

function hideToolbar() {
  if (toolbar) {
    toolbar.style.display = 'none';
    toolbar._range = null;
  }
  if (window._hlSelection) {
    document.removeEventListener('selectionchange', window._hlSelection);
    window._hlSelection = null;
  }
}

async function saveHighlight() {
  if (!toolbar || !toolbar._range) return;

  const range = toolbar._range;
  const color = toolbar.querySelector('.hl-btn[style*="border"]')?.dataset.color || 
                toolbar.querySelector('.hl-btn:first-child')?.dataset.color || 'yellow';
  const noteInput = toolbar.querySelector('#hl-note-input');
  const note = noteInput?.value?.trim() || '';
  const text = range.toString().trim();

  if (!text) { hideToolbar(); return; }

  const style = COLORS[color] || COLORS.yellow;

  // Wrap selected text in highlight span
  const span = document.createElement('hl-span');
  const hlId = 'hl-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8);
  span.setAttribute('data-hl-id', hlId);
  span.setAttribute('data-hl-color', color);
  span.style.backgroundColor = style.bg;
  span.style.borderBottom = `2px solid ${style.border}`;
  span.style.cursor = 'pointer';
  span.style.borderRadius = '2px';
  span.style.padding = '0 2px';
  span.title = note ? `💬 ${note}` : `🖍 ${color}`;

  try {
    range.surroundContents(span);

    // Click to show note
    span.addEventListener('click', (e) => {
      e.stopPropagation();
      showTooltip(e, span);
    });

    // Save to server
    const selector = generateSelector(span);
    const resp = await chrome.runtime.sendMessage({
      action: 'save-highlight',
      data: {
        url: window.location.href,
        page_title: document.title,
        text: text,
        color: color,
        note: note,
        selector: selector,
      }
    });

    if (resp.ok && resp.data?.highlight?.id) {
      span.setAttribute('data-hl-id', resp.data.highlight.id);
      appliedIds.add(resp.data.highlight.id);
    }
  } catch (e) {
    console.warn('[HL] Save error:', e);
  }

  hideToolbar();
}

function generateSelector(el) {
  // Generate a simple CSS selector for the element
  let path = [];
  let current = el;
  while (current && current !== document.body) {
    let selector = current.tagName?.toLowerCase() || '';
    if (current.id) {
      selector = `#${current.id}`;
      path.unshift(selector);
      break;
    }
    if (current.className && typeof current.className === 'string') {
      const classes = current.className.trim().split(/\s+/).slice(0, 2).join('.');
      if (classes) selector += '.' + classes;
    }
    // Add nth-child
    const parent = current.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
      if (siblings.length > 1) {
        const idx = siblings.indexOf(current) + 1;
        selector += `:nth-child(${idx})`;
      }
    }
    path.unshift(selector);
    current = current.parentElement;
  }
  return { css: path.join(' > '), html: el.outerHTML?.slice(0, 200) };
}

// ─── Tooltip for clicked highlights ─────────────────────────────────

let tooltipEl = null;

function showTooltip(e, span) {
  if (tooltipEl) tooltipEl.remove();

  const hlId = span.getAttribute('data-hl-id');
  const color = span.getAttribute('data-hl-color') || 'yellow';
  const note = span.title?.replace(/^[💬🖍]\s*/, '') || '';

  tooltipEl = document.createElement('hl-tooltip');
  tooltipEl.innerHTML = `
    <div style="background:white;border-radius:8px;padding:10px 14px;box-shadow:0 4px 20px rgba(0,0,0,0.2);border:1px solid #e0e0e0;max-width:300px;font-family:-apple-system,sans-serif;font-size:13px;">
      <div style="font-size:11px;color:#86868b;margin-bottom:4px;">🖍 <strong>${color}</strong></div>
      <div style="margin:4px 0;">${span.textContent}</div>
      ${note ? `<div style="margin-top:6px;padding-top:6px;border-top:1px solid #eee;color:#555;">💬 ${note}</div>` : ''}
      <div style="margin-top:8px;display:flex;gap:6px;">
        <button class="hl-tooltip-delete" style="padding:3px 10px;background:#fee;color:#c33;border:1px solid #fcc;border-radius:4px;cursor:pointer;font-size:11px;">🗑 删除</button>
      </div>
    </div>
  `;
  tooltipEl.style.cssText = `position:fixed;z-index:2147483647;top:${Math.max(e.clientY - 10, 5)}px;left:${Math.min(e.clientX + 10, window.innerWidth - 320)}px;`;

  document.body.appendChild(tooltipEl);

  // Delete button
  tooltipEl.querySelector('.hl-tooltip-delete')?.addEventListener('click', async () => {
    chrome.runtime.sendMessage({ action: 'delete-highlight', id: hlId });
    span.style.backgroundColor = 'transparent';
    span.style.borderBottom = 'none';
    span.outerHTML = span.textContent;
    appliedIds.delete(hlId);
    if (tooltipEl) tooltipEl.remove();
  });

  // Click outside to close
  setTimeout(() => {
    document.addEventListener('click', closeTooltip, { once: true });
  }, 100);
}

function closeTooltip(e) {
  if (tooltipEl && !tooltipEl.contains(e.target)) {
    tooltipEl.remove();
    tooltipEl = null;
  }
}

// ─── Text selection listener ────────────────────────────────────────

document.addEventListener('mouseup', (e) => {
  // Don't trigger if clicking inside toolbar or highlight
  if (e.target.closest('hl-toolbar') || e.target.closest('hl-span') || e.target.closest('hl-tooltip')) return;

  const selection = window.getSelection();
  if (!selection || selection.isCollapsed || !selection.toString().trim()) {
    setTimeout(hideToolbar, 200);
    return;
  }

  const range = selection.getRangeAt(0);
  showToolbar(range);
});

// Prevent toolbar from closing when interacting with it
document.addEventListener('mousedown', (e) => {
  if (e.target.closest('hl-toolbar') || e.target.closest('hl-tooltip')) {
    e.stopPropagation();
  }
});

// ─── Initialize ─────────────────────────────────────────────────────

// Wait a bit for page to fully render, then apply highlights
setTimeout(loadAndApplyHighlights, 500);

// Also try after page fully loads
window.addEventListener('load', () => {
  setTimeout(loadAndApplyHighlights, 1000);
});
