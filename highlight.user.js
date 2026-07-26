// ==UserScript==
// @name         Highlights Everywhere
// @name:zh-CN   高亮无处不在
// @namespace    http://localhost:8899/
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

    var SERVER = 'http://localhost:8899';
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
        var div = document.createElement('hl-toolbar');
        div.style.cssText = 'position:fixed;z-index:2147483647;font-family:sans-serif;font-size:13px;';

        var btns = '';
        for (var i=0;i<CNAMES.length;i++) {
            var cn=CNAMES[i], b=cn==='yellow'?'2px solid '+COLORS[cn].border:'2px solid transparent';
            btns += '<button class="hc" data-c="'+cn+'" style="width:24px;height:24px;border-radius:50%;cursor:pointer;background:'+COLORS[cn].bg+';border:'+b+';margin:0 1px;display:inline-block;vertical-align:middle;" title="'+cn+'"></button>';
        }
        div.innerHTML = '<div style="display:flex;align-items:center;gap:3px;padding:6px 10px;background:white;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.15);border:1px solid #e0e0e0;">'
            + btns
            + '<input class="hn" placeholder="备注..." style="width:120px;padding:4px 8px;border:1px solid #ddd;border-radius:4px;font-size:12px;outline:none;vertical-align:middle;">'
            + '<button class="hs" style="padding:4px 12px;background:#667eea;color:white;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:600;vertical-align:middle;">✓</button>'
            + '<button class="hx" style="padding:4px 8px;background:none;color:#999;border:none;cursor:pointer;font-size:16px;vertical-align:middle;">×</button>'
            + '</div>';
        document.body.appendChild(div);

        var savedId = null;
        var savedColor = null;
        var savedSpan = null;

        // Color button: immediately highlight
        div.querySelectorAll('.hc').forEach(function(b) {
            b.addEventListener('click', function() {
                // Restore text selection visually before highlighting
                try {
                    var sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                } catch(e) {}
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
        // Restore text selection highlight - must be AFTER toolbar creation AND no focus stealing
        requestAnimationFrame(function() {
            try { var sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range); } catch(e) {}
        });
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
