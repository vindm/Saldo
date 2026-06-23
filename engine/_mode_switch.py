"""_mode_switch.py — All/Team/Direct mode toggle, iOS segmented-control style.

Used in overview and in the plans (today/week/month).
State is persisted in localStorage.
"""
from _strings import t

_FUNNEL_SVG = ('<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">'
               '<path d="M3 5h18l-7 8v5l-4 2v-7z"/></svg>')


def render_mode_switch(n_all=None, n_team=None, n_direct=None):
    """All/Team/Direct toggle with live counts plus a 'filter active' banner.

    Pass real task counts per group; omit them to render without numbers (never
    the old hardcoded 15/6/9). When the operator leaves "All", a high-visibility
    banner states how many tasks are shown vs hidden and offers one-click reset —
    so a filter can never silently swallow tasks."""
    def _c(n):
        return (' <span class="mode-count">' + str(n) + '</span>') if n is not None else ''
    total_attr = (' data-total="' + str(n_all) + '"') if n_all is not None else ''
    total_txt = str(n_all) if n_all is not None else ''
    switch = (
        '<div class="mode-switch">'
        '<button class="mode-btn active" data-mode="all" data-label="' + t('All') + '">' + t('All') + _c(n_all) + '</button>'
        '<button class="mode-btn" data-mode="team" data-label="' + t('Team') + '">' + t('Team') + _c(n_team) + '</button>'
        '<button class="mode-btn" data-mode="direct" data-label="' + t('Direct') + '">' + t('Direct') + _c(n_direct) + '</button>'
        '</div>'
    )
    banner = (
        '<div class="mode-banner"' + total_attr + ' hidden>'
        '<span class="mode-banner-ic">' + _FUNNEL_SVG + '</span>'
        '<span class="mode-banner-txt">'
        + t('Showing') + ' <b class="mb-shown"></b> ' + t('of') + ' <b>' + total_txt + '</b> — '
        '<b class="mb-mode"></b> ' + t('only') + '. <b class="mb-hidden"></b> ' + t('hidden') + '.'
        '</span>'
        '<button class="mode-banner-clear" data-mode="all">' + t('Show all') + '</button>'
        '</div>'
    )
    return '<div class="mode-bar">' + switch + banner + '</div>'


MODE_SWITCH_HTML = render_mode_switch()

MODE_SWITCH_CSS = """
.mode-bar{margin:0 0 var(--space-md)}
.mode-switch{display:inline-flex;gap:0;padding:0;background:var(--bg-card);
  border:1px solid var(--border-strong);border-radius:9px;overflow:hidden;
  font-size:0;vertical-align:middle}
.mode-btn{padding:9px 17px;font-size:15px;border:0;border-left:1px solid var(--border);
  background:transparent;color:var(--text-secondary);cursor:pointer;border-radius:0;
  font-family:inherit;font-weight:500;transition:all 120ms;
  display:inline-flex;align-items:center;gap:7px;line-height:1.4}
.mode-btn:first-child{border-left:0}
.mode-btn:hover{color:var(--text-primary);background:var(--bg-page)}
.mode-btn.active{background:var(--accent);color:#fff;font-weight:600}
.mode-btn.active:hover{background:var(--accent-hover);color:#fff}
.mode-count{font-size:13px;color:var(--text-muted);font-weight:600;
  padding:1px 8px;background:var(--bg-page);border-radius:7px;line-height:1.5}
.mode-btn.active .mode-count{background:rgba(255,255,255,0.22);color:#fff}
/* Filter-active banner — impossible to miss; states shown vs hidden + reset. */
.mode-banner{display:flex;align-items:center;gap:10px;margin-top:11px;
  padding:10px 14px;background:var(--accent);border-radius:var(--radius-card);
  color:#fff;box-shadow:var(--shadow-pop)}
.mode-banner[hidden]{display:none}
.mode-banner-ic{display:inline-flex;flex-shrink:0}
.mode-banner-ic .ic{width:17px;height:17px;color:#fff}
.mode-banner-txt{font-size:14px;color:#fff;font-weight:500;flex:1;min-width:0}
.mode-banner-txt b{font-weight:700}
.mode-banner-clear{flex-shrink:0;font-size:13px;font-weight:700;color:var(--accent);
  background:#fff;border:0;border-radius:var(--radius-btn);padding:6px 13px;
  cursor:pointer;font-family:inherit;transition:transform 120ms}
.mode-banner-clear:hover{transform:translateY(-1px)}
body.mode-team [data-track-type="direct"]{display:none !important}
body.mode-direct [data-track-type="team"]{display:none !important}
"""

MODE_SWITCH_JS = (
    "<script>(function(){"
    "var saved=(function(){try{return localStorage.getItem('cowork_mode')||'all'}catch(e){return 'all'}})();"
    "function num(b){if(!b)return null;var c=b.querySelector('.mode-count');"
    "if(!c)return null;var n=parseInt(c.textContent,10);return isNaN(n)?null:n;}"
    "function updateBanner(m){"
    "var bn=document.querySelector('.mode-banner');if(!bn)return;"
    "if(m==='all'){bn.setAttribute('hidden','');return;}"
    "var btn=document.querySelector('.mode-btn[data-mode=\"'+m+'\"]');"
    "var total=parseInt(bn.getAttribute('data-total'),10);var shown=num(btn);"
    "var label=btn?(btn.getAttribute('data-label')||m):m;"
    "var em=bn.querySelector('.mb-mode');if(em)em.textContent=label;"
    "var es=bn.querySelector('.mb-shown');if(es)es.textContent=(shown==null?'':shown);"
    "var eh=bn.querySelector('.mb-hidden');"
    "if(eh)eh.textContent=((!isNaN(total)&&shown!=null)?(total-shown):'');"
    "bn.removeAttribute('hidden');}"
    "function applyMode(m){"
    "document.body.classList.remove('mode-all','mode-team','mode-direct');"
    "document.body.classList.add('mode-'+m);"
    "document.querySelectorAll('.mode-btn').forEach(function(b){"
    "b.classList.toggle('active',b.getAttribute('data-mode')===m)});"
    "updateBanner(m);"
    "try{localStorage.setItem('cowork_mode',m)}catch(e){}}"
    "document.addEventListener('click',function(e){"
    "var c=e.target.closest('.mode-banner-clear');if(c){applyMode('all');return;}"
    "var b=e.target.closest('.mode-btn');if(b)applyMode(b.getAttribute('data-mode'))});"
    "if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',function(){applyMode(saved)})}"
    "else{applyMode(saved)}"
    "})();</script>"
)
