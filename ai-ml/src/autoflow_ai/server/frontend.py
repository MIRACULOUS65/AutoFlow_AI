"""Single-page frontend (vanilla HTML/JS) served by the local API.

No build toolchain, no framework, no fake animation. Every state shown comes
from a real backend event: the timeline is the actual SSE mission event stream,
and the UI only shows COMPLETED when a mission_completed event arrives.
"""

from __future__ import annotations

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AutoFlow AI — Command Center</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --fg:#c9d1d9;
          --accent:#58a6ff; --ok:#3fb950; --fail:#f85149; --wait:#d29922; --muted:#8b949e; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
         background:var(--bg); color:var(--fg); }
  header { padding:12px 20px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:16px; }
  header h1 { font-size:16px; margin:0; color:var(--accent); }
  header .sub { color:var(--muted); font-size:12px; }
  .grid { display:grid; grid-template-columns:340px 1fr 320px; gap:12px; padding:12px; }
  .panel { background:var(--panel); border:1px solid var(--border);
           border-radius:8px; padding:14px; }
  .panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:.08em;
              color:var(--muted); margin:0 0 10px; }
  textarea { width:100%; height:90px; background:var(--bg); color:var(--fg);
             border:1px solid var(--border); border-radius:6px; padding:8px;
             font-family:inherit; font-size:13px; resize:vertical; }
  select, button { background:var(--bg); color:var(--fg); border:1px solid var(--border);
                   border-radius:6px; padding:8px 10px; font-family:inherit; font-size:13px; }
  button.run { background:var(--accent); color:#0d1117; border:none; font-weight:bold;
               cursor:pointer; width:100%; padding:10px; margin-top:10px; }
  button.run:disabled { opacity:.5; cursor:not-allowed; }
  .row { display:flex; gap:8px; margin-top:8px; }
  .row > * { flex:1; }
  #timeline { max-height:60vh; overflow:auto; font-size:12.5px; line-height:1.6; }
  .ev { padding:3px 0; border-bottom:1px dotted var(--border); }
  .ev .tag { color:var(--accent); }
  .ev.ok .tag { color:var(--ok); } .ev.fail .tag { color:var(--fail); }
  .ev.waiting .tag { color:var(--wait); }
  .status { font-weight:bold; }
  .status.complete { color:var(--ok); } .status.failed { color:var(--fail); }
  .status.awaiting_approval { color:var(--wait); } .status.running { color:var(--accent); }
  .kv { font-size:12px; color:var(--muted); margin:4px 0; }
  .badge { display:inline-block; padding:2px 6px; border-radius:4px; font-size:11px;
           border:1px solid var(--border); }
  .badge.ok { color:var(--ok); border-color:var(--ok); }
  .badge.fail { color:var(--fail); border-color:var(--fail); }
  code { color:var(--accent); }
</style>
</head>
<body>
<header>
  <h1>AutoFlow AI</h1>
  <span class="sub">local command center · events are real (no fake progress)</span>
  <span id="health" class="sub" style="margin-left:auto"></span>
</header>
<div class="grid">
  <!-- LEFT: mission input -->
  <div class="panel">
    <h2>Mission</h2>
    <textarea id="prompt" placeholder="Tell AutoFlow what you want done...">Research a topic, use my references, create a professional Word report, then prepare an email with the report attached.</textarea>
    <div class="row">
      <select id="mode">
        <option value="simulation">Simulation</option>
        <option value="real">Real (edit a file on disk)</option>
      </select>
      <select id="model"><option value="auto">auto</option></select>
    </div>
    <input id="target" type="text" placeholder="Real mode: absolute path to a .txt/.md/.docx file to edit"
           style="width:100%;margin-top:8px;padding:8px;box-sizing:border-box;display:none" />
    <button id="run" class="run">Run Mission</button>
    <div class="kv" id="mission-meta"></div>
    <h2 style="margin-top:16px">Agenticity</h2>
    <div class="kv" id="agenticity">—</div>
  </div>
  <!-- CENTER: live timeline -->
  <div class="panel">
    <h2>Live Execution — <span id="mstatus" class="status">idle</span></h2>
    <div id="timeline"></div>
  </div>
  <!-- RIGHT: verification / artifacts -->
  <div class="panel">
    <h2>Verification &amp; Artifacts</h2>
    <div class="kv" id="verify">no mission yet</div>
    <div id="artifacts"></div>
    <h2 style="margin-top:16px">Models</h2>
    <div class="kv" id="models">loading…</div>
  </div>
</div>
<script>
const $ = s => document.querySelector(s);
async function j(u, o){ const r = await fetch(u, o); return r.json(); }

async function loadHealth(){
  try { const h = await j('/health');
    const ok = (h.model_providers||[]).length;
    $('#health').textContent = 'health: ' + ok + ' model provider(s)';
  } catch(e){ $('#health').textContent = 'health: unavailable'; }
}
async function loadModels(){
  try {
    const d = await j('/models'); const sel = $('#model');
    (d.models||[]).forEach(m => {
      if(m.model_id){ const o=document.createElement('option'); o.value=m.model_id;
        o.textContent = m.model_id + (m.local?' (local)':''); sel.appendChild(o); }
    });
    $('#models').innerHTML = (d.models||[]).map(m =>
      m.model_id ? `<div><span class="badge ${m.healthy?'ok':'fail'}">${m.healthy?'up':'down'}</span> <code>${m.model_id}</code> ${m.model||''}</div>` : '').join('');
  } catch(e){ $('#models').textContent = 'unavailable'; }
}

function addEv(ev){
  const div = document.createElement('div');
  div.className = 'ev ' + (ev.status||'info');
  const tag = (ev.source||ev.type||'').toUpperCase();
  div.innerHTML = `<span class="tag">[${tag}]</span> ${ev.message||ev.type}`;
  $('#timeline').appendChild(div);
  $('#timeline').scrollTop = $('#timeline').scrollHeight;
}

function setStatus(s){ const el=$('#mstatus'); el.textContent=s; el.className='status '+s; }

async function run(){
  $('#run').disabled = true; $('#timeline').innerHTML=''; $('#artifacts').innerHTML='';
  $('#verify').textContent='running…'; $('#agenticity').textContent='—';
  setStatus('running');
  const prompt = $('#prompt').value, mode=$('#mode').value, model=$('#model').value;
  const target = $('#target').value.trim();
  if(mode==='real' && !target){
    $('#verify').textContent='Real mode needs a file path.'; setStatus('failed'); $('#run').disabled=false; return;
  }
  const rec = await j('/missions', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({prompt, mode, model, target_path: target})});
  $('#mission-meta').innerHTML = `id <code>${rec.mission_id}</code> · mode ${mode} · model ${rec.model}`;
  if(mode==='real'){
    await j('/missions/'+rec.mission_id+'/run', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({target_path: target, use_model: model!=='auto' && model.indexOf('local')<0})});
  } else {
    await j('/missions/'+rec.mission_id+'/simulate', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'});
  }

  const es = new EventSource('/missions/'+rec.mission_id+'/events');
  es.onmessage = e => { try{ addEv(JSON.parse(e.data)); }catch(_){} };
  ['mission_started','task_delegated','action_proposed','evidence_retrieved','plan_created',
   'observation_captured','verification_passed','verification_failed','approval_requested',
   'artifact_created','cleanup_completed','stage','mission_failed'].forEach(t =>
    es.addEventListener(t, e => { try{ addEv(JSON.parse(e.data)); }catch(_){} }));
  es.addEventListener('mission_completed', e => { addEv(JSON.parse(e.data)); });
  es.addEventListener('end', async () => {
    es.close();
    // ONLY read completion from real backend state — never fake it
    const m = await j('/missions/'+rec.mission_id);
    setStatus(m.status);
    const res = m.result||{};
    let vh = `document_verified: <b>${res.document_verified}</b><br>outcome: <b>${res.outcome}</b>`;
    if(res.target){ vh += `<br>file: <code>${res.target}</code>`; }
    if(res.reason){ vh += `<br>reason: ${res.reason}`; }
    if(res.draft_verified!==undefined){ vh += `<br>draft_verified: <b>${res.draft_verified}</b>`; }
    if(res.sent_verified!==undefined){ vh += `<br>sent_verified: <b>${res.sent_verified}</b>`; }
    $('#verify').innerHTML = vh;
    if(res.agenticity){ $('#agenticity').innerHTML = Object.entries(res.agenticity)
      .map(([k,v])=>`${k}: <b>${v}</b>`).join('<br>'); }
    const arts = await j('/missions/'+rec.mission_id+'/artifacts');
    $('#artifacts').innerHTML = (arts.artifacts||[]).map(a =>
      `<div class="badge ok">artifact</div> ${a.message}`).join('') || '<div class="kv">no artifacts</div>';
    $('#run').disabled = false;
  });
}

$('#run').addEventListener('click', run);
$('#mode').addEventListener('change', () => {
  $('#target').style.display = ($('#mode').value==='real') ? 'block' : 'none';
});
loadHealth(); loadModels();
</script>
</body>
</html>
"""
