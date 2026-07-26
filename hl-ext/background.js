// Highlights Everywhere - Background Service Worker
// Handles communication between content script and local server

const SERVER_URLS = ['http://localhost:8899', 'http://localhost:8900', 'http://localhost:8901', 'http://localhost:8902'];
let SERVER_URL = 'http://localhost:8899';

// Try to find the running server
async function findServer() {
  for (const url of SERVER_URLS) {
    try {
      const resp = await fetch(url + '/api/highlights?limit=1', { signal: AbortSignal.timeout(2000) });
      if (resp.ok) {
        SERVER_URL = url;
        console.log('[HL] Connected to server at', url);
        return url;
      }
    } catch (e) {
      // Try next
    }
  }
  console.warn('[HL] No server found, run `hl server` first');
  return null;
}

// API helpers
async function api(method, path, body) {
  const url = `${SERVER_URL}${path}`;
  try {
    const opts = { method, signal: AbortSignal.timeout(5000) };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(url, opts);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } catch (e) {
    // Try to find server
    await findServer();
    if (SERVER_URL) {
      const resp = await fetch(`${SERVER_URL}${path}`, {
        method, signal: AbortSignal.timeout(5000),
        ...(body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
      });
      return await resp.json();
    }
    throw e;
  }
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const handler = {
    'get-highlights': async () => {
      const data = await api('GET', `/api/highlights?url=${encodeURIComponent(msg.url)}`);
      return data.highlights || [];
    },
    'save-highlight': async () => {
      const data = await api('POST', '/api/highlights', msg.data);
      return data;
    },
    'delete-highlight': async () => {
      const data = await api('POST', '/api/highlights/delete', { id: msg.id });
      return data;
    },
    'check-server': async () => {
      await findServer();
      return { connected: !!SERVER_URL, url: SERVER_URL };
    }
  };

  const fn = handler[msg.action];
  if (fn) {
    fn().then(result => sendResponse({ ok: true, data: result }))
       .catch(err => sendResponse({ ok: false, error: err.message }));
    return true; // Keep channel open for async response
  }
});

// Initialize: try to find server on startup
findServer();
