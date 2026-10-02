const $ = (s) => document.querySelector(s);
let currentReport = null;
let pollTimer = null;

function escapeHtml(v='') { return String(v).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function severityRank(s){return ({critical:0,high:1,medium:2,low:3,info:4})[s] ?? 9}

async function api(path, options={}) {
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.detail || \`HTTP \${res.status}\`);
  return data;
}

function setScanning(active, msg='Launching browser') {
  $('#scan-button').disabled = active;
  $('#scan-status').classList.toggle('hidden', !active);
  $('#status-message').textContent = msg;
}

async function startScan(targetOverride=null) {
  clearTimeout(pollTimer);
  const target = targetOverride || $('#target').value.trim();
  if (!target) return;
  setScanning(true, 'Validating target');
  $('#report').classList.add('hidden');
  try {
    const body = {
      target_url: target,
      max_pages: Number($('#max-pages').value || 8),
      mobile_check: $('#mobile').checked,
      bilingual_parity: $('#parity').checked,
      safe_interactions: $('#interactions').checked
    };
    const created = await api('/api/scans', {method:'POST', body:JSON.stringify(body)});
    await pollScan(created.scan_id);
  } catch (err) {
    setScanning(false);
    alert(err.message);
  }
}

async function pollScan(id) {
  try {
    const report = await api(\`/api/scans/\${id}\`);
    $('#status-message').textContent = report.progress_message || report.status;
    if (report.status === 'completed') {
      setScanning(false);
      renderReport(report);
      return;
    }
    if (report.status === 'failed') {
      setScanning(false);
      alert(report.error || 'Scan failed');
      return;
    }
    pollTimer = setTimeout(()=>pollScan(id), 850);
  } catch (err) {
    setScanning(false); alert(err.message);
  }
}

function renderReport(r) {
  currentReport = r;
  $('#report').classList.remove('hidden');
  $('#report-target').textContent = r.target_url;
  $('#report-meta').textContent = \`\${r.pages_scanned} pages · \${(r.duration_ms/1000).toFixed(1)} s · \${new Date(r.finished_at).toLocaleString()}\`;
  $('#score').textContent = r.score ?? '—';
  $('#score-ring').style.setProperty('--score-angle', \`\${Math.round((r.score||0)*3.6)}deg\`);
  $('#metric-pages').textContent = r.pages_scanned;
  $('#metric-high').textContent = r.issues.filter(x=>['critical','high'].includes(x.severity)).length;
  $('#metric-low').textContent = r.issues.filter(x=>['medium','low'].includes(x.severity)).length;
  $('#metric-parity').textContent = r.parity_pairs_checked;
  renderIssues();
  $('#pages-body').innerHTML = r.pages.map(p => \`<tr><td>\${escapeHtml(p.url)}</td><td><span class="status-code \${(p.status_code||999)<400?'good':'bad'}">\${p.status_code ?? 'ERR'}</span></td><td>\${p.load_ms} ms</td><td>\${p.links_found}</td><td>\${p.console_errors}</td><td>\${p.request_failures}</td><td>\${p.safe_interactions_tested}</td></tr>\`).join('');
  $('#report').scrollIntoView({behavior:'smooth', block:'start'});
}

function renderIssues() {
  if (!currentReport) return;
  const filter = $('#severity-filter').value;
  const items = [...currentReport.issues].filter(i=>filter==='all'||i.severity===filter).sort((a,b)=>severityRank(a.severity)-severityRank(b.severity));
  if (!items.length) { $('#issues').innerHTML = \`<div class="empty">No issues match this filter.</div>\`; return; }
  $('#issues').innerHTML = items.map(i => \`<article class="issue"><div><span class="badge \${i.severity}">\${escapeHtml(i.severity)}</span></div><div><h4>\${escapeHtml(i.title)}</h4><p>\${escapeHtml(i.description)}</p><p class="url">\${escapeHtml(i.page_url)} · \${escapeHtml(i.viewport)}</p>\${i.recommendation?\`<p><strong>Fix:</strong> \${escapeHtml(i.recommendation)}</p>\`:''}<details><summary>Evidence</summary><pre>\${escapeHtml(JSON.stringify(i.evidence,null,2))}</pre></details></div><span class="muted">\${escapeHtml(i.category)}</span></article>\`).join('');
}

async function loadReports() {
  const wrap = $('#recent-reports'); wrap.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const list = await api('/api/reports?limit=20');
    if (!list.length) { wrap.innerHTML='<div class="empty">No reports yet.</div>'; return; }
    wrap.innerHTML = list.map(r=>\`<article class="recent"><div class="score-mini">\${r.score ?? '—'}</div><div><strong>\${escapeHtml(r.target_url)}</strong><small>\${r.pages_scanned} pages · \${r.issues.length} issues · \${new Date(r.created_at).toLocaleString()}</small></div><div><span class="badge \${r.status==='failed'?'critical':'low'}">\${escapeHtml(r.status)}</span></div><button class="secondary" data-report="\${r.scan_id}">Open</button></article>\`).join('');
    wrap.querySelectorAll('[data-report]').forEach(b=>b.addEventListener('click', async()=>{ const r=await api(\`/api/scans/\${b.dataset.report}\`); switchView('scanner'); renderReport(r); }));
  } catch(e) { wrap.innerHTML=\`<div class="empty">\${escapeHtml(e.message)}</div>\`; }
}

function switchView(view) {
  document.querySelectorAll('.nav[data-view]').forEach(n=>n.classList.toggle('active', n.dataset.view===view));
  $('#scanner-view').classList.toggle('hidden', view!=='scanner');
  $('#report').classList.toggle('hidden', view!=='scanner' || !currentReport);
  $('#reports-view').classList.toggle('hidden', view!=='reports');
  if (view==='reports') loadReports();
}

$('#scan-form').addEventListener('submit', e=>{e.preventDefault(); startScan();});
$('#demo-button').addEventListener('click', ()=>{ $('#target').value = \`\${location.origin}/demo/en\`; startScan(\`\${location.origin}/demo/en\`); });
$('#severity-filter').addEventListener('change', renderIssues);
$('#refresh-reports').addEventListener('click', loadReports);
document.querySelectorAll('.nav[data-view]').forEach(n=>n.addEventListener('click',()=>switchView(n.dataset.view)));
