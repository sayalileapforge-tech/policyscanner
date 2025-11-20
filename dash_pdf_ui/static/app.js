/* PolicyScanner Dashboard - Merged UI + Backend API Logic */

let currentReport = null;
let currentReportId = null;

/* ========== Modal Handlers ========== */
const reloadModal = document.getElementById('reloadModal');
const reloadFilesBtn = document.getElementById('reloadFilesBtn');
const modalCloseBtn = document.getElementById('modalCloseBtn');
const exportPdfBtn = document.getElementById('exportPdfBtn');

if (reloadFilesBtn) {
  reloadFilesBtn.addEventListener('click', openReloadModal);
}

if (modalCloseBtn) {
  modalCloseBtn.addEventListener('click', closeReloadModal);
}

if (reloadModal) {
  reloadModal.addEventListener('click', (e) => {
    if (e.target === reloadModal) {
      closeReloadModal();
    }
  });
}

if (exportPdfBtn) {
  exportPdfBtn.addEventListener('click', exportCurrentReportPDF);
}

function closeReloadModal() {
  if (reloadModal) {
    reloadModal.classList.add('hidden');
  }
}

function openReloadModal() {
  if (reloadModal) {
    reloadModal.classList.remove('hidden');
    loadSavedReports();
  }
}

async function loadSavedReports() {
  const filesList = document.getElementById('savedFilesList');
  try {
    const res = await fetch('/api/reports');
    const data = await res.json();
    
    if (!data.ok || !data.reports || data.reports.length === 0) {
      filesList.innerHTML = '<div class="muted">No saved reports found.</div>';
      return;
    }
    
    filesList.innerHTML = '';
    data.reports.forEach(report => {
      const item = document.createElement('div');
      item.className = 'saved-file-item';
      
      const driverName = (report.header?.driver_name || 'Unknown Driver').toUpperCase();
      const reportDate = report.header?.report_date || '—';
      const docId = report._id || report.id || '';
      
      const nameDiv = document.createElement('div');
      nameDiv.className = 'saved-file-name';
      nameDiv.textContent = driverName;
      
      const dateDiv = document.createElement('div');
      dateDiv.className = 'saved-file-date';
      dateDiv.textContent = `Loaded: ${reportDate}`;
      
      const buttonsContainer = document.createElement('div');
      buttonsContainer.style.display = 'flex';
      buttonsContainer.style.gap = '8px';
      buttonsContainer.style.alignItems = 'center';
      
      const actionBtn = document.createElement('button');
      actionBtn.className = 'saved-file-btn';
      actionBtn.textContent = 'Load';
      actionBtn.addEventListener('click', () => {
        loadReportById(docId);
      });
      
      const deleteBtn = document.createElement('button');
      deleteBtn.className = 'saved-file-delete-btn';
      deleteBtn.textContent = '🗑️';
      deleteBtn.title = 'Delete this report';
      deleteBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (confirm('Are you sure you want to delete this report?')) {
          try {
            const deleteRes = await fetch(`/api/reports/${docId}`, { method: 'DELETE' });
            if (deleteRes.ok) {
              item.remove();
              // Refresh the list
              loadSavedReports();
            } else {
              alert('Failed to delete report');
            }
          } catch (e) {
            console.error('Delete error:', e);
            alert('Error deleting report');
          }
        }
      });
      
      item.appendChild(nameDiv);
      item.appendChild(dateDiv);
      buttonsContainer.appendChild(actionBtn);
      buttonsContainer.appendChild(deleteBtn);
      item.appendChild(buttonsContainer);
      filesList.appendChild(item);
    });
  } catch (e) {
    console.error('Failed to load saved reports:', e);
    filesList.innerHTML = '<div class="muted">Error loading reports.</div>';
  }
}

async function loadReportById(docId) {
  try {
    const res = await fetch(`/api/reports/${docId}`);
    if (!res.ok) throw new Error('Failed to load report');
    
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Load failed');
    
    currentReport = data.report;
    currentReportId = docId;
    renderReport(currentReport);
    sessionStorage.setItem('currentReport', JSON.stringify(currentReport));
    sessionStorage.setItem('reportId', docId);
    
    closeReloadModal();
  } catch (e) {
    console.error('Error loading report:', e);
    alert(`Failed to load report: ${String(e)}`);
  }
}

async function exportCurrentReportPDF() {
  if (!currentReportId || !currentReport) {
    alert('Please load a report first before exporting.');
    return;
  }
  
  try {
    exportPdfBtn.disabled = true;
    exportPdfBtn.textContent = '⏳ Exporting...';
    
    const res = await fetch(`/api/export/${currentReportId}`);
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    
    // Get filename from response headers if available
    const contentDisposition = res.headers.get('content-disposition');
    let filename = 'report.pdf';
    if (contentDisposition) {
      const match = contentDisposition.match(/filename=([^;]+)/);
      if (match) filename = match[1].replace(/['"]/g, '');
    }
    
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    
    exportPdfBtn.textContent = '✓ Exported!';
    setTimeout(() => {
      exportPdfBtn.textContent = '⬇️ Export PDF';
      exportPdfBtn.disabled = false;
    }, 2000);
  } catch (e) {
    console.error('Export error:', e);
    alert(`Export failed: ${String(e)}`);
    exportPdfBtn.textContent = '⬇️ Export PDF';
    exportPdfBtn.disabled = false;
  }
}

/* ========== File Upload Handlers ========== */
const fileUploadArea = document.getElementById('fileUploadArea');
const fileInput = document.getElementById('fileInput');
const uploadButton = document.querySelector('.upload-button');

if (fileUploadArea) {
  fileUploadArea.addEventListener('click', () => {
    fileInput.click();
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      const fileName = e.target.files[0].name;
      uploadButton.textContent = fileName;
      uploadPDF(e.target.files[0]);
    }
  });

  fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadArea.style.background = 'var(--accent-light)';
  });

  fileUploadArea.addEventListener('dragleave', () => {
    fileUploadArea.style.background = 'var(--accent-lighter)';
  });

  fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadArea.style.background = 'var(--accent-lighter)';
    if (e.dataTransfer.files.length > 0) {
      fileInput.files = e.dataTransfer.files;
      uploadButton.textContent = e.dataTransfer.files[0].name;
      uploadPDF(e.dataTransfer.files[0]);
    }
  });
}

async function uploadPDF(file) {
  try {
    uploadButton.disabled = true;
    uploadButton.textContent = 'Uploading...';
    
    const form = new FormData();
    form.append('file', file);
    const res = await fetch('/api/parse', { method: 'POST', body: form });
    
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`HTTP ${res.status}: ${errText}`);
    }
    
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || 'Parse failed');
    
    currentReport = data.report;
    currentReportId = data.report._id || data.report.id;
    renderReport(currentReport);
    sessionStorage.setItem('currentReport', JSON.stringify(currentReport));
    sessionStorage.setItem('reportId', currentReportId);
    
    uploadButton.textContent = 'Upload successful!';
    setTimeout(() => {
      uploadButton.disabled = false;
      uploadButton.textContent = 'Choose File';
    }, 2000);
  } catch (e) {
    console.error('Upload error:', e);
    alert(`Upload failed: ${String(e)}`);
    uploadButton.disabled = false;
    uploadButton.textContent = 'Choose File';
  }
}

/* ========== Copy Button Functionality ========== */
document.addEventListener('click', (e) => {
  if (!e.target.classList.contains('copy-btn')) return;
  
  const fieldId = e.target.getAttribute('data-copy');
  const text = document.getElementById(fieldId)?.textContent || '';
  
  if (!text || text === '—') {
    e.target.textContent = 'empty';
    setTimeout(() => { e.target.textContent = '📋'; }, 1500);
    return;
  }
  
  navigator.clipboard.writeText(text).then(() => {
    const originalText = e.target.textContent;
    e.target.textContent = '✓';
    e.target.style.color = 'var(--success)';
    setTimeout(() => {
      e.target.textContent = originalText;
      e.target.style.color = '';
    }, 1500);
  }).catch(err => {
    console.error('Copy failed:', err);
    e.target.textContent = 'failed';
    setTimeout(() => { e.target.textContent = '📋'; }, 1500);
  });
});

/* ========== Report Rendering ========== */
function setText(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = v || '—';
}

function setAddressWithCopyButtons(addressText) {
  const wrapper = document.getElementById('addressWrapper');
  
  if (!wrapper) return;
  
  // Completely clear the wrapper
  wrapper.innerHTML = '';
  
  if (!addressText || addressText === '—') {
    const emptySpan = document.createElement('span');
    emptySpan.textContent = '—';
    emptySpan.className = 'driver-info-value';
    wrapper.appendChild(emptySpan);
    return;
  }
  
  // Split address by comma
  const parts = addressText.split(',').map(p => p.trim()).filter(p => p.length > 0);
  
  if (parts.length === 0) {
    const emptySpan = document.createElement('span');
    emptySpan.textContent = '—';
    emptySpan.className = 'driver-info-value';
    wrapper.appendChild(emptySpan);
    return;
  }
  
  const container = document.createElement('div');
  container.style.display = 'flex';
  container.style.alignItems = 'center';
  container.style.gap = '2px';
  container.style.flexWrap = 'wrap';
  
  // Check the last part for postal code (e.g., "M9V2J5") and province code (e.g., "ON")
  const lastPart = parts[parts.length - 1];
  const postalCodeMatch = lastPart.match(/^([A-Z]{2})\s+([A-Z0-9]{6})$/i);
  
  let addressParts = parts;
  let provinceCode = null;
  let postalCode = null;
  
  if (postalCodeMatch) {
    // Last part contains both province and postal code
    addressParts = parts.slice(0, -1);
    provinceCode = postalCodeMatch[1];
    postalCode = postalCodeMatch[2];
  }
  
  // Add each address part (excluding province) with comma and copy button
  addressParts.forEach((part, index) => {
    // Add the text part
    const textSpan = document.createElement('span');
    textSpan.textContent = part;
    textSpan.className = 'driver-info-value';
    container.appendChild(textSpan);
    
    // Add comma after each part except the last
    if (index < addressParts.length - 1) {
      const commaSpan = document.createElement('span');
      commaSpan.textContent = ',';
      container.appendChild(commaSpan);
      
      // Add copy button after the comma
      const copyBtn = document.createElement('button');
      copyBtn.className = 'copy-btn';
      copyBtn.textContent = '📋';
      copyBtn.title = 'Copy this section';
      copyBtn.style.padding = '2px 6px';
      copyBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const textToCopy = part;
        navigator.clipboard.writeText(textToCopy).then(() => {
          const originalText = copyBtn.textContent;
          copyBtn.textContent = '✓';
          copyBtn.style.color = 'var(--success)';
          setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.color = '';
          }, 1500);
        }).catch(err => {
          console.error('Copy failed:', err);
          copyBtn.textContent = 'failed';
          setTimeout(() => { copyBtn.textContent = '📋'; }, 1500);
        });
      });
      container.appendChild(copyBtn);
    }
  });
  
  // Add a copy button for the last address part if it exists
  if (addressParts.length > 0) {
    // Add copy button after last address part before postal code
    const finalCopyBtn = document.createElement('button');
    finalCopyBtn.className = 'copy-btn';
    finalCopyBtn.textContent = '📋';
    finalCopyBtn.title = 'Copy this section';
    finalCopyBtn.style.padding = '2px 6px';
    finalCopyBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const textToCopy = addressParts[addressParts.length - 1];
      navigator.clipboard.writeText(textToCopy).then(() => {
        const originalText = finalCopyBtn.textContent;
        finalCopyBtn.textContent = '✓';
        finalCopyBtn.style.color = 'var(--success)';
        setTimeout(() => {
          finalCopyBtn.textContent = originalText;
          finalCopyBtn.style.color = '';
        }, 1500);
      }).catch(err => {
        console.error('Copy failed:', err);
        finalCopyBtn.textContent = 'failed';
        setTimeout(() => { finalCopyBtn.textContent = '📋'; }, 1500);
      });
    });
    container.appendChild(finalCopyBtn);
  }
  
  // Add province code and postal code separately (displayed but ON not copied)
  if (provinceCode && postalCode) {
    // Add comma before province/postal
    const commaSpan = document.createElement('span');
    commaSpan.textContent = ',';
    container.appendChild(commaSpan);
    
    // Add province code (display only, not copyable)
    const provinceSpan = document.createElement('span');
    provinceSpan.textContent = provinceCode;
    provinceSpan.className = 'driver-info-value';
    provinceSpan.style.opacity = '0.7';
    provinceSpan.style.fontSize = '0.95em';
    container.appendChild(provinceSpan);
    
    // Add space between province and postal
    const spaceSpan = document.createElement('span');
    spaceSpan.textContent = ' ';
    container.appendChild(spaceSpan);
    
    // Add postal code with copy button (only postal code is copied, not province)
    const postalSpan = document.createElement('span');
    postalSpan.textContent = postalCode;
    postalSpan.className = 'driver-info-value';
    container.appendChild(postalSpan);
    
    const postalCopyBtn = document.createElement('button');
    postalCopyBtn.className = 'copy-btn';
    postalCopyBtn.textContent = '📋';
    postalCopyBtn.title = 'Copy postal code';
    postalCopyBtn.style.padding = '2px 6px';
    postalCopyBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      navigator.clipboard.writeText(postalCode).then(() => {
        const originalText = postalCopyBtn.textContent;
        postalCopyBtn.textContent = '✓';
        postalCopyBtn.style.color = 'var(--success)';
        setTimeout(() => {
          postalCopyBtn.textContent = originalText;
          postalCopyBtn.style.color = '';
        }, 1500);
      }).catch(err => {
        console.error('Copy failed:', err);
        postalCopyBtn.textContent = 'failed';
        setTimeout(() => { postalCopyBtn.textContent = '📋'; }, 1500);
      });
    });
    container.appendChild(postalCopyBtn);
  }
  
  wrapper.appendChild(container);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

function parseMaybeDate(s) {
  if (!s) return null;
  // Try parsing MM/DD/YYYY format (new format)
  const mmddyyyy = s.match(/\b(\d{2})\/(\d{2})\/(\d{4})\b/);
  if (mmddyyyy) return new Date(`${mmddyyyy[3]}-${mmddyyyy[1]}-${mmddyyyy[2]}T00:00:00`);
  // Try parsing YYYY-MM-DD format (old format, for backwards compatibility)
  const m = s.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
  if (m) return new Date(`${m[1]}-${m[2]}-${m[3]}T00:00:00`);
  const t = Date.parse(s);
  return isNaN(t) ? null : new Date(t);
}

function formatDateToMMDDYYYY(dateObj) {
  if (!dateObj) return '—';
  const month = String(dateObj.getMonth() + 1).padStart(2, '0');
  const day = String(dateObj.getDate()).padStart(2, '0');
  const year = dateObj.getFullYear();
  return `${month}/${day}/${year}`;
}

function monthsBetween(d1, d2) {
  if (!d1 || !d2) return null;
  const m = (d2.getFullYear() - d1.getFullYear()) * 12 + (d2.getMonth() - d1.getMonth());
  return m;
}

function renderReport(rep) {
  // Driver info
  const h = rep.header || {};
  setText('driverName', h.driver_name);
  setAddressWithCopyButtons(h.address);
  setText('dln', h.dln);
  setText('dob', h.date_of_birth);
  setText('gender', h.gender);
  setText('maritalStatus', h.marital_status);
  
  // Years continuous insurance = Last Policy start of earliest term
  // Current Insurance = First Policy (Policy 0) start of earliest term
  const policies = rep.policies || [];
  console.log('[DEBUG] All policies:', JSON.stringify(policies, null, 2));
  let yearsContinuousInsuranceDate = '—';
  let currentInsuranceDate = '—';
  
  if (policies.length > 0) {
    // Last Policy = policies[policies.length - 1]
    const lastPolicy = policies[policies.length - 1];
    console.log('[DEBUG] Last Policy:', lastPolicy);
    console.log('[DEBUG] Last Policy start_of_earliest_term:', lastPolicy.start_of_earliest_term);
    yearsContinuousInsuranceDate = lastPolicy.start_of_earliest_term || '—';
    
    // Current Insurance = First Policy (policies[0])
    const firstPolicy = policies[0];
    console.log('[DEBUG] First Policy:', firstPolicy);
    console.log('[DEBUG] First Policy start_of_earliest_term:', firstPolicy.start_of_earliest_term);
    let insuranceDate = firstPolicy.start_of_earliest_term;
    if (!insuranceDate || insuranceDate === '—' || insuranceDate === '') {
      // Fallback to policy header effective_date
      const policyHeader = firstPolicy.header || {};
      insuranceDate = policyHeader.effective_date;
      console.log('[DEBUG] Using policy effective_date as fallback:', insuranceDate);
    }
    currentInsuranceDate = insuranceDate || '—';
  }
  
  console.log('[DEBUG] yearsContinuousInsuranceDate (last policy):', yearsContinuousInsuranceDate);
  console.log('[DEBUG] currentInsuranceDate (first policy):', currentInsuranceDate);
  setText('yearsContinuousInsurance', yearsContinuousInsuranceDate);
  setText('currentInsurance', currentInsuranceDate);
  setText('claimsSixYears', h.num_claims_6y);
  setText('atFaultClaimsSixYears', h.num_atfault_6y);
  
  // Get years licensed and calculate date
  if (h.years_licensed) {
    const yearsLicensed = h.years_licensed;
    const today = new Date();
    const licenseDate = new Date(today.getFullYear() - yearsLicensed, today.getMonth(), today.getDate());
    const formattedDate = (licenseDate.getMonth() + 1).toString().padStart(2, '0') + '/' + 
                          licenseDate.getDate().toString().padStart(2, '0') + '/' + 
                          licenseDate.getFullYear();
    setText('yearsLicensed', yearsLicensed + ' years (since ' + formattedDate + ')');
  } else {
    setText('yearsLicensed', '—');
  }
  
  // Get current policy expiry date (from latest active policy)
  let currentPolicyExpiry = '—';
  if (policies.length > 0) {
    const latestPolicy = policies[0];
    const policyHeader = latestPolicy.header || {};
    currentPolicyExpiry = policyHeader.end_of_latest_term || policyHeader.expiry_date || '—';
  }
  setText('currentPolicyExpiryDate', currentPolicyExpiry);
  
  // Get Policy #1 VIN (Policy #1 is the last one in reversed display order)
  if (policies.length > 0) {
    const reversed = [...policies].reverse();
    const policyOne = reversed[reversed.length - 1]; // Policy #1 is the LAST in reversed array
    const vehicles = policyOne.vehicles || [];
    const firstVin = vehicles.length > 0 ? (vehicles[0].vin || '—') : '—';
    setText('firstPolicyVin', firstVin);
  } else {
    setText('firstPolicyVin', '—');
  }
  
  // Calculate days to expiry
  if (currentPolicyExpiry && currentPolicyExpiry !== '—') {
    const expiryDate = new Date(currentPolicyExpiry);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    expiryDate.setHours(0, 0, 0, 0);
    const daysToExpiry = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24));

    const daysEl = document.getElementById('daysToExpiry');
    if (daysEl) {
      // Set numeric content (show 0 for same-day expiry)
      daysEl.textContent = Math.max(0, daysToExpiry).toString();
      daysEl.classList.remove('expired', 'warning', 'ok');
      if (daysToExpiry < 0) {
        daysEl.classList.add('expired');
      } else if (daysToExpiry <= 30) {
        daysEl.classList.add('warning');
      } else {
        daysEl.classList.add('ok');
      }
    }
  } else {
    const daysEl = document.getElementById('daysToExpiry');
    if (daysEl) daysEl.textContent = '—';
  }
  
  // Stats
  setText('statPolicies', policies.length);
  
  const claims = rep.claims || [];
  setText('statTotalClaims', claims.length);
  
  // Calculate claims totals
  let totalSubtotal = 0;
  claims.forEach(claim => {
    const subtotal = parseFloat(claim.subtotal) || 0;
    totalSubtotal += subtotal;
  });
  
  setText('statClaimsSubtotal', totalSubtotal > 0 ? '$' + totalSubtotal.toFixed(2) : '—');
  
  renderPolicies(rep.policies || [], h.dln);
  renderClaims(claims);
}

/* ========== Policies Rendering ========== */
function renderPolicies(policies, driverDLN) {
  const container = document.getElementById('policiesList');
  container.innerHTML = '';
  
  if (!policies.length) {
    container.innerHTML = '<div class="muted">No policies found.</div>';
    return;
  }
  
  const reversed = [...policies].reverse();
  
  // Display all policies (no filtering)
  reversed.forEach((policy, reversedIdx) => {
    const h = policy.header || {};
    const ops = policy.operators || [];
    const totalPolicies = reversed.length;
    const policyNum = totalPolicies - reversedIdx;
    
    const item = document.createElement('div');
    item.className = 'policy-item';
    
    // Header
    const header = document.createElement('div');
    header.className = 'policy-header';
    const titleArea = document.createElement('div');
    titleArea.className = 'policy-title-area';
    
    const badge = document.createElement('div');
    badge.className = 'policy-number-badge';
    badge.textContent = policyNum;
    titleArea.appendChild(badge);
    
    const titleDiv = document.createElement('div');
    const titleEl = document.createElement('div');
    titleEl.className = 'policy-title';
    titleEl.textContent = h.insurer || h.range_insurer_status || '—';
    const numEl = document.createElement('div');
    numEl.className = 'policy-number';
    numEl.textContent = h.policy_number ? `Policy #: ${h.policy_number}` : 'Policy #: —';
    titleDiv.appendChild(titleEl);
    titleDiv.appendChild(numEl);
    titleArea.appendChild(titleDiv);
    
    const statusDiv = document.createElement('div');
    statusDiv.className = 'policy-status status-active';
    statusDiv.textContent = h.status || 'Active';
    if (h.status && h.status.toLowerCase().includes('cancel')) statusDiv.className = 'policy-status status-cancelled';
    else if (h.status && h.status.toLowerCase().includes('expir')) statusDiv.className = 'policy-status status-expired';
    
    header.appendChild(titleArea);
    header.appendChild(statusDiv);
    item.appendChild(header);
    
    // Sections
    const sections = document.createElement('div');
    sections.className = 'policy-sections';
    
    const leftSec = document.createElement('div');
    leftSec.className = 'policy-section';
    const leftTitle = document.createElement('div');
    leftTitle.className = 'section-title';
    leftTitle.textContent = 'Policy Details';
    leftSec.appendChild(leftTitle);
    
    // Find operator that matches policyholder name
    // Try exact match first, then try matching all name parts regardless of order
    const policyholderName = (h.policyholder_name || '').trim().toLowerCase();
    const policyholderParts = policyholderName.split(/\s+/).filter(p => p.length > 0 && p !== 'and');
    
    console.log('[DEBUG] Policy:', h.policy_number);
    console.log('[DEBUG] Policyholder Name:', policyholderName);
    console.log('[DEBUG] Operators in policy:', ops.map(o => ({ name: o.operator_name, rel: o.relationship, yob: o.year_of_birth })));
    
    let matchedOp = ops.find(o => o.operator_name && o.operator_name.trim().toLowerCase() === policyholderName);
    
    // If no exact match, try to find operator containing all parts of policyholder name (excluding 'and')
    if (!matchedOp && policyholderParts.length > 0) {
      matchedOp = ops.find(o => {
        if (!o.operator_name) return false;
        const opNameLower = o.operator_name.trim().toLowerCase();
        // Remove commas and compare parts - be more lenient with punctuation
        const opNameNormalized = opNameLower.replace(/[,\s]+/g, ' ').split(/\s+/).filter(p => p.length > 0);
        return policyholderParts.every(part => opNameLower.includes(part));
      });
    }
    
    console.log('[DEBUG] Matched operator:', matchedOp?.operator_name || 'NONE');
    
    const displayOp = matchedOp?.operator_name || (ops[0]?.operator_name || '—');
    const displayRelationship = matchedOp?.relationship || '—';
    const displayYearOfBirth = matchedOp?.year_of_birth || '—';
    
    // Get End of Latest Term and Start of Earliest Term
    // Priority: use policy-level field if available, otherwise use operator field
    let displayEndTerm = '—';
    let displayStartTerm = '—';
    
    // First check if policy has calculated start_of_earliest_term (from backend reverse-shift logic)
    if (policy.start_of_earliest_term) {
      displayStartTerm = policy.start_of_earliest_term;
    }
    
    // Get End of Latest Term from DLN-matched operator
    if (driverDLN) {
      let dlnMatchedOp = ops.find(o => o && o.dln === driverDLN);
      if (dlnMatchedOp) {
        // End of Latest Term from matched operator
        if (dlnMatchedOp.end_term) {
          const endTermParsed = parseMaybeDate(dlnMatchedOp.end_term);
          displayEndTerm = endTermParsed ? formatDateToMMDDYYYY(endTermParsed) : dlnMatchedOp.end_term;
        }
        
        // If policy doesn't have start_of_earliest_term, fall back to operator.start_term
        if (!policy.start_of_earliest_term && dlnMatchedOp.start_term) {
          const startTermParsed = parseMaybeDate(dlnMatchedOp.start_term);
          displayStartTerm = startTermParsed ? formatDateToMMDDYYYY(startTermParsed) : dlnMatchedOp.start_term;
        }
      }
    }
    
    // Calculate GAP using the DISPLAYED dates (displayStartTerm and displayEndTerm)
    let gapText = '—';
    let gapLabel = 'Gap';
    
    if (reversedIdx < reversed.length - 1) {
      // Not the last policy: gap between current start (displayStartTerm) and current end (displayEndTerm)
      // displayStartTerm shows previous policy's start, displayEndTerm shows current policy's end
      let currentStartDate = null;
      let currentEndDate = null;
      
      // Parse displayStartTerm (which is the Start of Earliest Term being displayed)
      if (displayStartTerm && displayStartTerm !== '—') {
        currentStartDate = parseMaybeDate(displayStartTerm);
      }
      
      // Parse displayEndTerm (which is the End of Latest Term being displayed)
      if (displayEndTerm && displayEndTerm !== '—') {
        currentEndDate = parseMaybeDate(displayEndTerm);
      }
      
      // Calculate gap
      if (currentStartDate && currentEndDate) {
        const gapDays = Math.floor((currentStartDate - currentEndDate) / (1000 * 60 * 60 * 24));
        gapText = `${gapDays} days`;
        gapLabel = `Gap (Policy ${policyNum - 1} start − Policy ${policyNum} end)`;
      }
    } else {
      // Last policy (Policy 1): gap from its own start to end using displayed dates
      let startDate = null;
      let endDate = null;
      
      // Parse displayStartTerm
      if (displayStartTerm && displayStartTerm !== '—') {
        startDate = parseMaybeDate(displayStartTerm);
      }
      
      // Parse displayEndTerm
      if (displayEndTerm && displayEndTerm !== '—') {
        endDate = parseMaybeDate(displayEndTerm);
      }
      
      if (startDate && endDate) {
        const gapDays = Math.floor((endDate - startDate) / (1000 * 60 * 60 * 24));
        gapText = `${gapDays} days`;
        gapLabel = `Gap (Policy ${policyNum} start − Policy ${policyNum} end)`;
      }
    }
    
    const policyFields = [
      ['Operator', displayOp],
      ['Year of Birth', displayYearOfBirth],
      ['End of Latest Term', displayEndTerm],
      ['Start of Earliest Term', displayStartTerm],
      [gapLabel, gapText]
    ];
    
    policyFields.forEach(([label, val]) => {
      const field = document.createElement('div');
      field.className = 'policy-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'policy-label';
      labelEl.textContent = label + ':';
      const valDiv = document.createElement('div');
      valDiv.className = 'policy-value-wrapper';
      const valEl = document.createElement('div');
      valEl.className = 'policy-value';

      // Check if this is a Gap field with positive value
      if (label.includes('Gap')) {
        valEl.textContent = escapeHtml(val);
        // Apply red color if gap shows positive days
        // Extract the number (handle negative numbers with minus sign)
        if (val !== '—' && val.includes('days')) {
          const numberMatch = val.match(/(-?\d+)/);
          if (numberMatch) {
            const gapNumber = parseInt(numberMatch[1]);
            if (gapNumber > 0) {
              valEl.classList.add('gap-positive');
            }
          }
        }
        valDiv.appendChild(valEl);
      } else if (label === 'End of Latest Term' || label === 'Start of Earliest Term') {
        // For start/end term fields, add a copy button and unique id
        const shortKey = label === 'End of Latest Term' ? 'end' : 'start';
        const fieldId = `policy-${policyNum}-${shortKey}`;
        valEl.id = fieldId;
        valEl.textContent = escapeHtml(val);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.setAttribute('data-copy', fieldId);
        copyBtn.textContent = '📋';
        valDiv.appendChild(valEl);
        valDiv.appendChild(copyBtn);
      } else {
        valEl.textContent = escapeHtml(val);
        valDiv.appendChild(valEl);
      }

      field.appendChild(labelEl);
      field.appendChild(valDiv);
      leftSec.appendChild(field);
    });
    
    sections.appendChild(leftSec);
    
    const rightSec = document.createElement('div');
    rightSec.className = 'policy-section';
    const rightTitle = document.createElement('div');
    rightTitle.className = 'section-title';
    rightTitle.textContent = 'Vehicle Information';
    rightSec.appendChild(rightTitle);
    
    const vhs = policy.vehicles || [];
    const vehicleText = vhs.length > 0 ? `${vhs[0].year || ''} ${vhs[0].make_model || ''}`.trim() : '—';
    const vinText = vhs[0]?.vin || '—';
    const coverageText = vhs[0]?.coverage || '—';
    
    const vehicleFields = [
      ['Vehicle', vehicleText],
      ['VIN', vinText],
      ['Coverage', coverageText]
    ];
    
    vehicleFields.forEach(([label, val]) => {
      const field = document.createElement('div');
      field.className = 'policy-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'policy-label';
      labelEl.textContent = label + ':';
      const valDiv = document.createElement('div');
      valDiv.className = 'policy-value-wrapper';
      const valEl = document.createElement('div');
      valEl.className = 'policy-value';

      // Add copy button for VIN in policy view
      if (label === 'VIN') {
        const fieldId = `policy-${policyNum}-vin`;
        valEl.id = fieldId;
        valEl.textContent = escapeHtml(val);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.setAttribute('data-copy', fieldId);
        copyBtn.textContent = '📋';
        valDiv.appendChild(valEl);
        valDiv.appendChild(copyBtn);
      } else {
        valEl.textContent = escapeHtml(val);
        valDiv.appendChild(valEl);
      }

      field.appendChild(labelEl);
      field.appendChild(valDiv);
      rightSec.appendChild(field);
    });
    
    sections.appendChild(rightSec);
    item.appendChild(sections);
    
    // (Removed inter-policy bottom banner; Gap is shown in Policy Details now)
    
    container.appendChild(item);
  });
}

/* ========== Claims Rendering ========== */
function renderClaims(claims) {
  const container = document.getElementById('claimsList');
  container.innerHTML = '';
  
  if (!claims.length) {
    container.innerHTML = '<div class="muted">No claims found.</div>';
    return;
  }
  
  claims.forEach((claim, idx) => {
    const item = document.createElement('div');
    item.className = 'claim-item';
    
    const header = document.createElement('div');
    header.className = 'claim-header';
    const titleArea = document.createElement('div');
    titleArea.className = 'claim-title-area';
    
    const badge = document.createElement('div');
    badge.className = 'claim-number-badge';
    badge.textContent = idx + 1;
    titleArea.appendChild(badge);

    // Show insurer name in the header (visible next to the badge)
    const titleEl = document.createElement('div');
    titleEl.className = 'claim-title';
    titleEl.textContent = claim.insurer || '—';
    titleArea.appendChild(titleEl);
    
    const statusBadge = document.createElement('div');
    statusBadge.className = 'badge';
    const atFault = !!claim.at_fault;
    statusBadge.className = atFault ? 'badge badge-at-fault' : 'badge badge-not-at-fault';
    statusBadge.textContent = atFault ? 'At Fault' : 'Not At Fault';
    
    header.appendChild(titleArea);
    header.appendChild(statusBadge);
    item.appendChild(header);
    
    // Sections
    const sections = document.createElement('div');
    sections.className = 'claim-sections';
    
    const leftSec = document.createElement('div');
    leftSec.className = 'claim-section';
    const leftTitle = document.createElement('div');
    leftTitle.className = 'section-title';
    leftTitle.textContent = 'Claim Details';
    leftSec.appendChild(leftTitle);
    
    const claimFields = [
      ['Date of Loss', claim.date_of_loss || '—'],
      ['Coverage', claim.coverage || '—'],
      ['Claim Status', claim.claim_status || '—']
    ];
    
    claimFields.forEach(([label, val]) => {
      const field = document.createElement('div');
      field.className = 'claim-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'claim-label';
      labelEl.textContent = label + ':';
      const valDiv = document.createElement('div');
      valDiv.className = 'claim-value-wrapper';
      const valEl = document.createElement('div');
      valEl.className = 'claim-value';

      // Add copy button for Date of Loss in claims view
      if (label === 'Date of Loss') {
        const fieldId = `claim-${idx}-date_of_loss`;
        valEl.id = fieldId;
        valEl.textContent = escapeHtml(val);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.setAttribute('data-copy', fieldId);
        copyBtn.textContent = '📋';
        valDiv.appendChild(valEl);
        valDiv.appendChild(copyBtn);
      } else {
        valEl.textContent = escapeHtml(val);
        valDiv.appendChild(valEl);
      }

      field.appendChild(labelEl);
      field.appendChild(valDiv);
      leftSec.appendChild(field);
    });
    
    sections.appendChild(leftSec);
    
    const rightSec = document.createElement('div');
    rightSec.className = 'claim-section';
    const rightTitle = document.createElement('div');
    rightTitle.className = 'section-title';
    rightTitle.textContent = 'Vehicle Information';
    rightSec.appendChild(rightTitle);
    
    const claimVehicleFields = [
      ['Vehicle', claim.vehicle || '—'],
      ['VIN', claim.vin || '—']
    ];

    claimVehicleFields.forEach(([label, val]) => {
      const field = document.createElement('div');
      field.className = 'claim-field';
      const labelEl = document.createElement('div');
      labelEl.className = 'claim-label';
      labelEl.textContent = label + ':';
      const valDiv = document.createElement('div');
      valDiv.className = 'claim-value-wrapper';
      const valEl = document.createElement('div');
      valEl.className = 'claim-value';

      if (label === 'VIN') {
        const fieldId = `claim-${idx}-vin`;
        valEl.id = fieldId;
        valEl.textContent = escapeHtml(val);

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.setAttribute('data-copy', fieldId);
        copyBtn.textContent = '📋';
        valDiv.appendChild(valEl);
        valDiv.appendChild(copyBtn);
      } else {
        valEl.textContent = escapeHtml(val);
        valDiv.appendChild(valEl);
      }

      field.appendChild(labelEl);
      field.appendChild(valDiv);
      rightSec.appendChild(field);
    });
    
    sections.appendChild(rightSec);
    item.appendChild(sections);
    
    // Loss section
    if (claim.total_loss || claim.total_expense || claim.subtotal) {
      const lossDiv = document.createElement('div');
      lossDiv.className = 'loss-section';
      const lossTitle = document.createElement('div');
      lossTitle.className = 'loss-section-title';
      lossTitle.textContent = 'Loss Information';
      lossDiv.appendChild(lossTitle);
      
      const lossRows = [
        ['Total Loss', claim.total_loss || '—'],
        ['Total Expense', claim.total_expense || '—'],
        ['Subtotal', claim.subtotal || '—']
      ];
      
      lossRows.forEach(([label, val]) => {
        const row = document.createElement('div');
        row.className = 'loss-total-row';
        const labelEl = document.createElement('div');
        labelEl.className = 'loss-total-label';
        labelEl.textContent = label + ':';
        const valDiv = document.createElement('div');
        valDiv.className = 'loss-total-value-wrapper';
        const valEl = document.createElement('div');
        valEl.className = 'loss-total-value';

        // Add copy buttons for numeric fields in claims
        if (label === 'Total Loss' || label === 'Total Expense' || label === 'Subtotal') {
          const key = label === 'Total Loss' ? 'total_loss' : (label === 'Total Expense' ? 'total_expense' : 'subtotal');
          const fieldId = `claim-${idx}-${key}`;
          valEl.id = fieldId;
          valEl.textContent = escapeHtml(val);
          
          // Style Subtotal in purple
          if (label === 'Subtotal') {
            valEl.style.color = '#6366f1';
            valEl.style.fontWeight = '600';
          }

          const copyBtn = document.createElement('button');
          copyBtn.className = 'copy-btn';
          copyBtn.setAttribute('data-copy', fieldId);
          copyBtn.textContent = '📋';
          valDiv.appendChild(valEl);
          valDiv.appendChild(copyBtn);
        } else {
          valEl.textContent = escapeHtml(val);
          valDiv.appendChild(valEl);
        }

        row.appendChild(labelEl);
        row.appendChild(valDiv);
        lossDiv.appendChild(row);
      });
      
      // Add Kind of Loss (KOL) information after subtotal as simple inline text
      if (claim.kind_of_loss && claim.kind_of_loss.length > 0) {
        claim.kind_of_loss.forEach((kol) => {
          const kolRow = document.createElement('div');
          kolRow.style.marginTop = '6px';
          kolRow.style.paddingLeft = '0';
          
          const kolText = document.createElement('div');
          kolText.style.fontSize = '11px';
          kolText.style.color = '#666';
          kolText.style.fontWeight = '500';
          kolText.textContent = `${kol.code} - ${kol.description}: $${kol.loss} (Loss); $${kol.expense} (Expense)`;
          
          kolRow.appendChild(kolText);
          lossDiv.appendChild(kolRow);
        });
      }
      
      // Detailed loss lines
      if (claim.loss_details && claim.loss_details.length) {
        const detailsWrap = document.createElement('div');
        detailsWrap.className = 'loss-details';
        claim.loss_details.forEach(ld => {
          const line = document.createElement('div');
          line.className = 'loss-detail-line';
          if (ld.code) {
            line.textContent = `${ld.code} - ${ld.description}  ${ld.loss ? '$'+ld.loss : ''} ${ld.expense ? '(Expense: $'+ld.expense+')' : ''}`;
          } else {
            line.textContent = ld.raw || JSON.stringify(ld);
          }
          detailsWrap.appendChild(line);
        });
        lossDiv.appendChild(detailsWrap);
      }

      item.appendChild(lossDiv);
    }
    
    // First / Third party driver summary - two column layout
    const driversWrap = document.createElement('div');
    driversWrap.className = 'drivers-section';
    
    // Create two-column layout for First Party Driver and Third Party Driver
    const driversContainer = document.createElement('div');
    driversContainer.style.display = 'flex';
    driversContainer.style.gap = '20px';
    driversContainer.style.marginTop = '12px';
    
    // First Party Driver column
    if (claim.first_party_driver) {
      const fp = claim.first_party_driver || {};
      const fpCol = document.createElement('div');
      fpCol.style.flex = '1';
      fpCol.style.backgroundColor = '#f0ebf8';
      fpCol.style.padding = '12px 16px';
      fpCol.style.borderRadius = '8px';
      
      const fpTitle = document.createElement('div');
      fpTitle.style.fontSize = '13px';
      fpTitle.style.fontWeight = '600';
      fpTitle.style.color = '#6366f1';
      fpTitle.style.marginBottom = '10px';
      fpTitle.textContent = 'First Party Driver';
      fpCol.appendChild(fpTitle);
      
      const fpNameDiv = document.createElement('div');
      fpNameDiv.style.display = 'flex';
      fpNameDiv.style.justifyContent = 'space-between';
      fpNameDiv.style.fontSize = '12px';
      fpNameDiv.style.color = '#666';
      fpNameDiv.style.marginBottom = '6px';
      const fpNameLabel = document.createElement('span');
      fpNameLabel.textContent = 'Name:';
      const fpNameValue = document.createElement('span');
      fpNameValue.textContent = escapeHtml(fp.name || '—');
      fpNameDiv.appendChild(fpNameLabel);
      fpNameDiv.appendChild(fpNameValue);
      fpCol.appendChild(fpNameDiv);
      
      const fpLicenseDiv = document.createElement('div');
      fpLicenseDiv.style.display = 'flex';
      fpLicenseDiv.style.justifyContent = 'space-between';
      fpLicenseDiv.style.fontSize = '12px';
      fpLicenseDiv.style.color = '#666';
      const fpLicenseLabel = document.createElement('span');
      fpLicenseLabel.textContent = 'License:';
      const fpLicenseValue = document.createElement('span');
      fpLicenseValue.textContent = escapeHtml(fp.license || '—');
      fpLicenseDiv.appendChild(fpLicenseLabel);
      fpLicenseDiv.appendChild(fpLicenseValue);
      fpCol.appendChild(fpLicenseDiv);
      
      driversContainer.appendChild(fpCol);
    }
    
    // Third Party Driver column
    if (claim.third_party_driver) {
      const tp = claim.third_party_driver || {};
      const tpCol = document.createElement('div');
      tpCol.style.flex = '1';
      tpCol.style.backgroundColor = '#f0ebf8';
      tpCol.style.padding = '12px 16px';
      tpCol.style.borderRadius = '8px';
      
      const tpTitle = document.createElement('div');
      tpTitle.style.fontSize = '13px';
      tpTitle.style.fontWeight = '600';
      tpTitle.style.color = '#6366f1';
      tpTitle.style.marginBottom = '10px';
      tpTitle.textContent = 'Third Party Driver';
      tpCol.appendChild(tpTitle);
      
      const tpNameDiv = document.createElement('div');
      tpNameDiv.style.display = 'flex';
      tpNameDiv.style.justifyContent = 'space-between';
      tpNameDiv.style.fontSize = '12px';
      tpNameDiv.style.color = '#666';
      tpNameDiv.style.marginBottom = '6px';
      const tpNameLabel = document.createElement('span');
      tpNameLabel.textContent = 'Name:';
      const tpNameValue = document.createElement('span');
      tpNameValue.textContent = escapeHtml(tp.name || '—');
      tpNameDiv.appendChild(tpNameLabel);
      tpNameDiv.appendChild(tpNameValue);
      tpCol.appendChild(tpNameDiv);
      
      const tpLicenseDiv = document.createElement('div');
      tpLicenseDiv.style.display = 'flex';
      tpLicenseDiv.style.justifyContent = 'space-between';
      tpLicenseDiv.style.fontSize = '12px';
      tpLicenseDiv.style.color = '#666';
      const tpLicenseLabel = document.createElement('span');
      tpLicenseLabel.textContent = 'License:';
      const tpLicenseValue = document.createElement('span');
      tpLicenseValue.textContent = escapeHtml(tp.license || '—');
      tpLicenseDiv.appendChild(tpLicenseLabel);
      tpLicenseDiv.appendChild(tpLicenseValue);
      tpCol.appendChild(tpLicenseDiv);
      
      driversContainer.appendChild(tpCol);
    }
    
    if (driversContainer.childElementCount) {
      driversWrap.appendChild(driversContainer);
      item.appendChild(driversWrap);
    }
    
    container.appendChild(item);
  });
}

/* ========== Initialization ========== */
function restoreReportFromSession() {
  try {
    // Force complete cache clear to prevent stale data.
    // Remove from both sessionStorage and localStorage.
    sessionStorage.removeItem('currentReport');
    sessionStorage.removeItem('reportId');
    localStorage.removeItem('currentReport');
    localStorage.removeItem('reportId');
    // Additionally, force a cache-busting reload of app.js
    console.log('[CACHE] Cleared all stored reports and IDs.');
  } catch (e) {
    console.warn('Failed to restore report:', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  restoreReportFromSession();
});
