 (function(){
  // Parse query params
  const params = new URLSearchParams(window.location.search);
  const reportId = params.get('report_id');
  const policyIdx = parseInt(params.get('policy_idx')||"0", 10);

  const main = document.getElementById('mainContent');
  const titleEl = document.getElementById('pageTitle');
  const subEl = document.getElementById('pageSub');
  const backBtn = document.getElementById('backBtn');
  const exportBtn = document.getElementById('exportBtn');

  backBtn.addEventListener('click', ()=>{
    // Navigate back to main app with report stub so it can be restored
    try{ sessionStorage.setItem('reportId', reportId); }catch(e){ console.warn(e); }
    window.location.href = '/';
  });

  exportBtn.addEventListener('click', async ()=>{
    try{
      exportBtn.disabled = true; exportBtn.textContent = 'Preparing…';
      const resp = await fetch(`/api/export/${encodeURIComponent(reportId)}`);
      if (!resp.ok) throw new Error('Export failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `report_${reportId.substring(0,8)}.pdf`; a.click();
      URL.revokeObjectURL(url);
      exportBtn.textContent = 'Export PDF';
      exportBtn.disabled = false;
    }catch(e){
      console.warn(e);
      exportBtn.textContent = 'Export PDF';
      exportBtn.disabled = false;
      alert('Export failed');
    }
  });

  if (!reportId) {
    main.innerHTML = '<div class="muted">Missing report id.</div>';
    throw new Error('Missing report_id');
  }

  async function fetchReport(){
    try{
      const res = await fetch(`/api/reports/${encodeURIComponent(reportId)}`);
      if (!res.ok) throw new Error('Failed to fetch report');
      const d = await res.json();
      if (!d.ok) throw new Error('Report not found');
      return d.report;
    }catch(e){
      main.innerHTML = `<div class="muted">Error loading report: ${String(e)}</div>`;
      throw e;
    }
  }

  function parseMaybeDate(s){
    if (!s) return null;
    // Try parsing MM/DD/YYYY format (new format)
    const mmddyyyy = s.match(/\b(\d{2})\/(\d{2})\/(\d{4})\b/);
    if (mmddyyyy) return new Date(`${mmddyyyy[3]}-${mmddyyyy[1]}-${mmddyyyy[2]}T00:00:00`);
    // Try parsing YYYY-MM-DD format (old format, for backwards compatibility)
    const m = s.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
    if (m) return new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00`);
    const t = Date.parse(s); return isNaN(t)?null:new Date(t);
  }

  function daysBetween(a,b){
    if (!a||!b) return null;
    const DAY = 1000*60*60*24;
    return Math.round((a - b)/DAY);
  }

  function monthsBetween(d1, d2){
    if (!d1 || !d2) return null;
    const m = (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth());
    return m;
  }

  function renderPolicyFull(report, policyIndex){
    const policy = (report.policies||[])[policyIndex];
    if (!policy) { main.innerHTML = '<div class="muted">Policy not found.</div>'; return; }

    const h = policy.header || {};
    titleEl.textContent = `Policy #${policyIndex+1} — ${h.policy_number || '(no #)'}`;
    subEl.textContent = report.header?.driver_name || '';

    const container = document.createElement('div');
    container.className = 'card';

    // Top summary row (mimic compact 3rd image layout)
    const top = document.createElement('div');
    top.style.display = 'grid';
    top.style.gridTemplateColumns = '60px 1fr 340px';
    top.style.gap = '16px';
    top.style.alignItems = 'center';

    const numBox = document.createElement('div');
    numBox.style.fontWeight = '800';
    numBox.style.fontSize = '20px';
    numBox.style.color = 'var(--muted)';
    numBox.textContent = policyIndex+1;
    top.appendChild(numBox);

    const company = document.createElement('div');
    company.innerHTML = `<div style="font-weight:800">${escapeHtml(h.insurer || h.range_insurer_status || '—')}</div>`;
    top.appendChild(company);

    // driver name block
    const driverBlock = document.createElement('div');
    const driverNameVal = h.policyholder_name || report.header?.driver_name || '—';
    driverBlock.innerHTML = `<div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Driver Name</div><div style="font-weight:800">${escapeHtml(driverNameVal)}</div>`;
    top.appendChild(driverBlock);

    container.appendChild(top);

    // Dates - show operator terms if available, otherwise fall back to policy dates
    const datesRow = document.createElement('div');
    datesRow.style.display = 'grid';
    datesRow.style.gridTemplateColumns = '1fr 1fr';
    datesRow.style.gap = '16px';
    datesRow.style.marginTop = '16px';

    // Find the main operator (matching main driver DLN) to get operator terms
    const mainDriverDln = (report.header?.dln || '').trim();
    let mainOp = null;
    const ops = policy.operators || [];
    for (let i = 0; i < ops.length; i++) {
      if ((ops[i].dln || '').trim() === mainDriverDln) {
        mainOp = ops[i];
        break;
      }
    }
    
    // Use operator end/start terms if available, otherwise use policy dates.
    // If the main operator lacks terms, search any operator in the policy for term data.
    const endLatest = document.createElement('div'); endLatest.className='term-date'; endLatest.style.padding='12px';
    const startEarliest = document.createElement('div'); startEarliest.className='term-date'; startEarliest.style.padding='12px';

    (function(){
      let chosenOp = null;
      if (mainOp && (mainOp.end_term || mainOp.start_term)) chosenOp = mainOp;
      else if (ops && ops.length) chosenOp = ops.find(o => o && (o.end_term || o.start_term)) || null;

      endLatest.textContent = (chosenOp && chosenOp.end_term) ? chosenOp.end_term : (h.expiry_date || h.cancellation_date || '—');
      startEarliest.textContent = (chosenOp && chosenOp.start_term) ? chosenOp.start_term : (h.effective_date || '—');
    })();

    datesRow.appendChild(endLatest); datesRow.appendChild(startEarliest);

    container.appendChild(datesRow);

      // Show total years between effective and expiry (approximate by year difference)
      (function(){
        const s = parseMaybeDate(h.effective_date);
        const e = parseMaybeDate(h.expiry_date || h.cancellation_date);
        if (s && e){
          const years = Math.abs(e.getFullYear() - s.getFullYear());
          const yearsDiv = document.createElement('div');
          yearsDiv.style.marginTop = '12px';
          yearsDiv.innerHTML = `<div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Policy Years</div><div style="font-weight:800">${years} year${years===1? '': 's'}</div>`;
          container.appendChild(yearsDiv);
        }
      })();

    // Gap badge
    const endDate = parseMaybeDate(h.expiry_date || h.cancellation_date);
    const startDate = parseMaybeDate(h.effective_date);
    let gapMsg = '';
    if (endDate && startDate){
      const months = monthsBetween(endDate, startDate);
      if (months > 0) gapMsg = `Coverage Gap — ${months} month${months === 1 ? '' : 's'}`;
      else if (months === 0) gapMsg = `No Coverage Gap`;
      else gapMsg = `Overlap — ${Math.abs(months)} month${Math.abs(months) === 1 ? '' : 's'}`;
    }
    if (gapMsg){
      const gapDiv = document.createElement('div');
      gapDiv.className = 'policy-gap';
      gapDiv.style.marginTop = '16px';
      gapDiv.textContent = gapMsg;
      container.appendChild(gapDiv);
    }

    // Inter-policy overlap: compare this policy's start to previous policy's expiry
    const allPolicies = report.policies || [];
    if (policyIndex > 0 && allPolicies[policyIndex - 1]){
      const prev = allPolicies[policyIndex - 1];
      const prevEnd = parseMaybeDate((prev.header || {}).expiry_date || (prev.header || {}).cancellation_date);
      const curStart = parseMaybeDate(h.effective_date);
      if (prevEnd && curStart){
        const m = monthsBetween(prevEnd, curStart);
        let interMsg = '';
        if (m > 0) interMsg = `Coverage Gap vs Prev Policy — ${m} month${m === 1 ? '' : 's'}`;
        else if (m === 0) interMsg = `No Coverage Gap vs Prev Policy`;
        else interMsg = `Overlap vs Prev Policy — ${Math.abs(m)} month${Math.abs(m) === 1 ? '' : 's'}`;

        const interDiv = document.createElement('div');
        interDiv.className = 'policy-gap';
        interDiv.style.marginTop = '12px';
        interDiv.style.background = 'linear-gradient(90deg,#fff7ed,#fff)';
        interDiv.textContent = interMsg;
        container.appendChild(interDiv);
      }
    }

    // Full details (use existing policyAcc builder by creating similar content)
    const details = document.createElement('div');
    details.style.marginTop = '18px';

    // Header block
    const headerBlock = document.createElement('div');
    headerBlock.innerHTML = `<h3 style="margin-top:0">Full Policy Details</h3>`;
    details.appendChild(headerBlock);

    // Key/Value list
    const kvs = [
      ['Policy #', h.policy_number],
      ['Policyholder', h.policyholder_name],
      ['Address', h.policyholder_address],
      ['Effective Date', h.effective_date],
      ['Expiry Date', h.expiry_date],
      ['Cancellation Date', h.cancellation_date],
      ['# Reported Operators', h.num_reported_operators],
      ['# PP Vehicles', h.num_pp_vehicles]
    ];
    kvs.forEach(([k,v])=>{
      const box = document.createElement('div'); box.className='kv'; box.style.marginBottom='8px';
      const key = document.createElement('div'); key.className='key'; key.textContent = k;
      const val = document.createElement('div'); val.className='val'; val.textContent = v || '—';
      box.appendChild(key); box.appendChild(val);
      details.appendChild(box);
    });

    // Operators: show only if DLN matches main driver's DLN
    // reuse `mainDriverDln` and `ops` declared above
    const opsTitle = document.createElement('div'); opsTitle.className='group-title'; opsTitle.textContent = `Operators (${ops.length})`;
    details.appendChild(opsTitle);
    
    // Find operator matching main driver DLN
    let matchingOp = null;
    for (let i = 0; i < ops.length; i++) {
      if ((ops[i].dln || '').trim() === mainDriverDln) {
        matchingOp = ops[i];
        break;
      }
    }
    
    // Display operator info or blanks if no match
    const opBox = document.createElement('div'); opBox.className='card'; opBox.style.marginBottom='8px';
    const displayName = matchingOp ? (matchingOp.operator_name || '—') : (ops[0]?.operator_name || '—');
    const displayRelationship = matchingOp ? (matchingOp.relationship || '—') : (ops[0]?.relationship || '—');
    const displayYob = matchingOp ? (matchingOp.year_of_birth || '—') : (ops[0]?.year_of_birth || '—');
    // If matching operator lacks term fields, try any operator that has them
    let displayStartTerm = '—';
    let displayEndTerm = '—';
    if (matchingOp && (matchingOp.start_term || matchingOp.end_term)){
      displayStartTerm = matchingOp.start_term || '—';
      displayEndTerm = matchingOp.end_term || '—';
    } else {
      const anyOpWithTerms = ops.find(o => o && (o.start_term || o.end_term));
      if (anyOpWithTerms){
        displayStartTerm = anyOpWithTerms.start_term || '—';
        displayEndTerm = anyOpWithTerms.end_term || '—';
      } else {
        displayStartTerm = h.effective_date || '—';
        displayEndTerm = h.expiry_date || h.cancellation_date || '—';
      }
    }
    
    opBox.innerHTML = `
      <div style="display:grid;gap:8px">
        <div><div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Operator</div><div style="font-weight:800">${escapeHtml(displayName)}</div></div>
        <div><div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Relationship to Policyholder</div><div style="font-weight:800">${escapeHtml(displayRelationship)}</div></div>
        <div><div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Year of Birth</div><div style="font-weight:800">${escapeHtml(displayYob)}</div></div>
        <div><div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">Start of Earliest Term</div><div style="font-weight:800">${escapeHtml(displayStartTerm)}</div></div>
        <div><div style="font-size:12px;color:var(--muted);font-weight:700;text-transform:uppercase">End of Latest Term</div><div style="font-weight:800">${escapeHtml(displayEndTerm)}</div></div>
      </div>
    `;
    details.appendChild(opBox);

    container.appendChild(details);

    main.innerHTML = '';
    main.appendChild(container);
  }

  function escapeHtml(s){ return String(s||'').replace(/[&<>\"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

  // boot
  (async ()=>{
    const rpt = await fetchReport();
    renderPolicyFull(rpt, policyIdx);
  })();

})();