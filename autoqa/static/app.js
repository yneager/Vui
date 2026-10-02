const $ = (s) => document.querySelector(s);
let currentReport = null;
let currentScanId = null;
let pollTimer = null;

function escapeHtml(v='') { return String(v).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function severityRank(s){return ({critical:0,high:1,medium:2,low:3,info:4})[s] ?? 9}
function fmtMs(v){ return v == null ? '—' : `${v} ms`; }

async function api(path, options={}) {
  const res = await fetch(path, {headers:{'Content-Type':'application/json'}, ...options});
  const data = await res.json().catch(()=>({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

function setScanning(active, msg='Launching browser') {
  $('#scan-button').disabled = active;
  $('#demo-button').disabled = active;
  $('#scan-status').classList.toggle('hidden', !active);
  $('#status-message').textContent = msg;
}

async function startScan(targetOverride=null) {
  clearTimeout(pollTimer);
  const target = targetOverride || $('#target').value.trim();
  if (!target) return;
  currentScanId = null;
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
    currentScanId = created.scan_id;
    await pollScan(created.scan_id);
  } catch (err) {
    setScanning(false);
    alert(err.message);
  }
}

async function cancelCurrentScan() {
  if (!currentScanId) return;
  $('#cancel-button').disabled = true;
  try {
    await api(`/api/scans/${currentScanId}`, {method:'DELETE'});
    clearTimeout(pollTimer);
    setScanning(false);
    $('#status-message').textContent = 'Canceled';
  } catch (err) {
    alert(err.message);
  } finally {
    $('#cancel-button').disabled = false;
  }
}

async function pollScan(id) {
  try {
    const report = await api(`/api/scans/${id}`);
    $('#status-message').textContent = report.progress_message || report.status;
    if (report.status === 'completed') {
      setScanning(false);
      renderReport(report);
      return;
    }
    if (report.status === 'failed' || report.status === 'canceled') {
      setScanning(false);
      if (report.status === 'failed') alert(report.error || 'Scan failed');
      return;
    }
    pollTimer = setTimeout(()=>pollScan(id), 700);
  } catch (err) {
    setScanning(false); alert(err.message);
  }
}

function populateCategories(r) {
  const select = $('#category-filter');
  const selected = select.value;
  const cats = [...new Set(r.issues.map(x=>x.category))].sort();
  select.innerHTML = '<option value="all">All categories</option>' + cats.map(c=>`<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  if (cats.includes(selected)) select.value = selected;
}

function renderReport(r) {
  currentReport = r;
  currentScanId = r.scan_id;
  $('#report').classList.remove('hidden');
  $('#report-target').textContent = r.target_url;
  $('#report-meta').textContent = `${r.pages_scanned} pages · ${((r.duration_ms||0)/1000).toFixed(1)} s · ${new Date(r.finished_at).toLocaleString()} · scan ${r.scan_id.slice(0,8)}`;
  $('#score').textContent = r.score ?? '—';
  $('#score-ring').style.setProperty('--score-angle', `${Math.round((r.score||0)*3.6)}deg`);
  $('#metric-pages').textContent = r.pages_scanned;
  $('#metric-high').textContent = r.issues.filter(x=>['critical','high'].includes(x.severity)).length;
  $('#metric-low').textContent = r.issues.filter(x=>['medium','low'].includes(x.severity)).length;
  $('#metric-parity').textContent = r.parity_pairs_checked;
  $('#metric-new').textContent = r.baseline_scan_id ? r.new_issue_ids.length : '—';
  $('#metric-resolved').textContent = r.baseline_scan_id ? r.resolved_issue_ids.length : '—';
  $('#export-json').href = `/api/scans/${r.scan_id}/export.json`;
  $('#export-html').href = `/api/scans/${r.scan_id}/export.html`;

  const regression = $('#regression');
  if (r.baseline_scan_id) {
    regression.classList.remove('hidden');
    regression.innerHTML = `<strong>Regression comparison</strong><p>Compared with <code>${escapeHtml(r.baseline_scan_id.slice(0,8))}</code>: <b>${r.new_issue_ids.length}</b> new, <b>${r.resolved_issue_ids.length}</b> resolved, <b>${r.unchanged_issue_ids.length}</b> unchanged.</p>`;
  } else {
    regression.classList.add('hidden');
  }

  populateCategories(r);
  renderIssues();
  $('#pages-body').innerHTML = r.pages.map(p => `<tr><td>${escapeHtml(p.url)}</td><td><span class="status-code ${(p.status_code||999)<400?'good':'bad'}">${p.status_code ?? 'ERR'}</span></td><td>${p.load_ms} ms</td><td>${fmtMs(p.dom_content_loaded_ms)}</td><td>${p.dom_elements || '—'}</td><td>${p.resource_count || '—'}</td><td>${p.transfer_kb ? `${p.transfer_kb} KB` : '—'}</td><td>${p.console_errors}</td><td>${p.request_failures}</td><td>${p.safe_interactions_tested}</td></tr>`).join('');
  $('#report').scrollIntoView({behavior:'smooth', block:'start'});
}

function renderIssues() {
  if (!currentReport) return;
  const severity = $('#severity-filter').value;
  const category = $('#category-filter').value;
  const newIds = new Set(currentReport.new_issue_ids || []);
  const items = [...currentReport.issues]
    .filter(i => (severity==='all'||i.severity===severity) && (category==='all'||i.category===category))
    .sort((a,b)=>severityRank(a.severity)-severityRank(b.severity) || a.title.localeCompare(b.title));
  if (!items.length) { $('#issues').innerHTML = `<div class="empty">No issues match these filters.</div>`; return; }
  $('#issues').innerHTML = items.map(i => `<article class="issue"><div><span class="badge ${i.severity}">${escapeHtml(i.severity)}</span>${newIds.has(i.id)?'<span class="new-chip">NEW</span>':''}</div><div><h4>${escapeHtml(i.title)}</h4><p>${escapeHtml(i.description)}</p><p class="url">${escapeHtml(i.page_url)} · ${escapeHtml(i.viewport)} · #${escapeHtml(i.id)}</p>${i.recommendation?`<p><strong>Fix:</strong> ${escapeHtml(i.recommendation)}</p>`:''}<details><summary>Evidence</summary><pre>${escapeHtml(JSON.stringify(i.evidence,null,2))}</pre></details></div><span class="muted">${escapeHtml(i.category)}</span></article>`).join('');
}

async function loadReports() {
  const wrap = $('#recent-reports'); wrap.innerHTML = '<div class="empty">Loading…</div>';
  try {
    const list = await api('/api/reports?limit=20');
    if (!list.length) { wrap.innerHTML='<div class="empty">No reports yet.</div>'; return; }
    wrap.innerHTML = list.map(r=>`<article class="recent"><div class="score-mini">${r.score ?? '—'}</div><div><strong>${escapeHtml(r.target_url)}</strong><small>${r.pages_scanned} pages · ${r.issues.length} issues · ${new Date(r.created_at).toLocaleString()}${r.baseline_scan_id?` · ${r.new_issue_ids.length} new / ${r.resolved_issue_ids.length} resolved`:''}</small></div><div><span class="badge ${r.status==='failed'?'critical':r.status==='canceled'?'medium':'low'}">${escapeHtml(r.status)}</span></div><button class="secondary" data-report="${r.scan_id}">Open</button></article>`).join('');
    wrap.querySelectorAll('[data-report]').forEach(b=>b.addEventListener('click', async()=>{ const r=await api(`/api/scans/${b.dataset.report}`); switchView('scanner'); renderReport(r); }));
  } catch(e) { wrap.innerHTML=`<div class="empty">${escapeHtml(e.message)}</div>`; }
}

function switchView(view) {
  document.querySelectorAll('.nav[data-view]').forEach(n=>n.classList.toggle('active', n.dataset.view===view));
  $('#scanner-view').classList.toggle('hidden', view!=='scanner');
  $('#report').classList.toggle('hidden', view!=='scanner' || !currentReport);
  $('#reports-view').classList.toggle('hidden', view!=='reports');
  if (view==='reports') loadReports();
}

$('#scan-form').addEventListener('submit', e=>{e.preventDefault(); startScan();});
$('#demo-button').addEventListener('click', ()=>{ $('#target').value = `${location.origin}/demo/en`; startScan(`${location.origin}/demo/en`); });
$('#cancel-button').addEventListener('click', cancelCurrentScan);
$('#severity-filter').addEventListener('change', renderIssues);
$('#category-filter').addEventListener('change', renderIssues);
$('#refresh-reports').addEventListener('click', loadReports);
document.querySelectorAll('.nav[data-view]').forEach(n=>n.addEventListener('click',()=>switchView(n.dataset.view)));
