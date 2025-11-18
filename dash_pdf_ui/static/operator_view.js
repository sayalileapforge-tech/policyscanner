(function(){
  const params = new URLSearchParams(window.location.search);
  const reportId = params.get('report_id');
  const policyIdx = parseInt(params.get('policy_idx')||"0", 10);
  const operatorIdx = parseInt(params.get('operator_idx')||"0", 10);

  const main = document.getElementById('mainContent');
  const titleEl = document.getElementById('pageTitle');
  const subEl = document.getElementById('pageSub');
  const backBtn = document.getElementById('backBtn');

  backBtn.addEventListener('click', ()=>{
    try{ sessionStorage.setItem('reportId', reportId); }catch(e){ console.warn(e); }
    window.location.href = '/';
  });

  if (!reportId) { main.innerHTML = '<div class="muted">Missing report id.</div>'; return; }

  async function fetchReport(){
    try{
      const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}`);
      if (!res.ok) throw new Error('Failed to fetch report');
      const d = await res.json(); if (!d.ok) throw new Error('Report not found'); return d.report;
    }catch(e){ main.innerHTML = `<div class="muted">Error loading report: ${String(e)}</div>`; throw e; }
  }

  function escapeHtml(s){ return String(s||'').replace(/[&<>\"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

  function renderOperator(report){
    const policy = (report.policies||[])[policyIdx];
    if (!policy) { main.innerHTML = '<div class="muted">Policy not found.</div>'; return; }
    const op = (policy.operators||[])[operatorIdx];
    if (!op) { main.innerHTML = '<div class="muted">Operator not found.</div>'; return; }

    titleEl.textContent = `${op.operator_name || 'Operator'}`;
    subEl.textContent = `${report.header?.driver_name || ''} — Policy: ${policy.header?.policy_number || '(no #)'} `;

    const card = document.createElement('div'); card.className = 'card';

    // Layout similar to example: left column details, right column term dates etc.
    const grid = document.createElement('div'); grid.style.display='grid'; grid.style.gridTemplateColumns='1fr 320px'; grid.style.gap='16px';

    const left = document.createElement('div');
    // Key info
    const items = [
      ['Operator', op.operator_name],
      ['DLN', op.dln],
      ['Relationship to Policyholder', op.relationship],
      ['Year of Birth', op.year_of_birth]
    ];
    items.forEach(([k,v])=>{
      const box = document.createElement('div'); box.className='kv'; box.style.marginBottom='8px';
      const key = document.createElement('div'); key.className='key'; key.textContent = k;
      const val = document.createElement('div'); val.className='val'; val.textContent = v || '—';
      box.appendChild(key); box.appendChild(val); left.appendChild(box);
    });

    // Right column: terms / vehicles
    const right = document.createElement('div');
    const termBox = document.createElement('div'); termBox.className='card'; termBox.style.padding='12px'; termBox.style.marginBottom='8px';
    termBox.innerHTML = `<div style="font-weight:800">Vehicle Ref</div><div style="color:var(--muted)">${escapeHtml(op.vehicle_ref||'—')}</div>`;
    right.appendChild(termBox);

    const termDates = document.createElement('div'); termDates.className='card'; termDates.style.padding='12px';
    termDates.innerHTML = `<div style="font-weight:700">Start of the Earliest Term</div><div style="color:var(--muted)">${escapeHtml(op.start_term||'—')}</div><div style="margin-top:8px;font-weight:700">End of the Latest Term</div><div style="color:var(--muted)">${escapeHtml(op.end_term||'—')}</div>`;
    right.appendChild(termDates);

    grid.appendChild(left); grid.appendChild(right);
    card.appendChild(grid);

    main.innerHTML=''; main.appendChild(card);
  }

  (async ()=>{ const rpt = await fetchReport(); renderOperator(rpt); })();

})();
