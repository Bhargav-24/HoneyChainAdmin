const beekeeperList = document.querySelector('#beekeeper-list');
const batchList = document.querySelector('#batch-list');
const stats = document.querySelector('#ops-stats');
const errorMessage = document.querySelector('#ops-error');
const escapeHtml = (value) => String(value ?? '-').replace(/[&<>"']/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[character]));
const statusLabel = (status) => String(status || '').toLowerCase();

const showError = (message) => { errorMessage.textContent = message; errorMessage.hidden = false; };
const requestDecision = async (endpoint, status, button) => {
  button.disabled = true;
  const response = await fetch(endpoint, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({status}) });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'The operation could not be completed.');
};
const renderStats = (beekeepers, batches) => {
  const pending = beekeepers.filter((item) => item.kyc_status === 'pending').length;
  const processing = batches.filter((item) => item.status === 'HARVESTED').length;
  const distributed = batches.filter((item) => item.status === 'DISTRIBUTED').length;
  stats.innerHTML = [['Awaiting identity review',pending],['Ready for processing',processing],['Distributed batches',distributed]].map(([label,value]) => `<div class="stat"><span>${label}</span><strong>${value}</strong></div>`).join('');
};
const renderBeekeepers = (items) => {
  if (!items.length) { beekeeperList.innerHTML = '<p class="loading">No beekeeper applications yet.</p>'; return; }
  beekeeperList.innerHTML = items.map((item) => `<article class="request-card"><div><strong class="record-title">${escapeHtml(item.name || 'Incomplete application')}</strong><span class="record-meta">${escapeHtml(item.email)} · ${escapeHtml(item.location || 'Location not supplied')}</span></div><div><span class="status-chip ${statusLabel(item.kyc_status)}">${escapeHtml(item.kyc_status)}</span><span class="record-meta mono">${escapeHtml(item.beekeeper_id)}</span></div><div class="decision-actions"><button class="decision-button approve" data-id="${escapeHtml(item.beekeeper_id)}" data-status="approved" type="button">Approve</button><button class="decision-button reject" data-id="${escapeHtml(item.beekeeper_id)}" data-status="rejected" type="button">Reject</button></div></article>`).join('');
};
const renderBatches = (items) => {
  if (!items.length) { batchList.innerHTML = '<p class="loading">No batches have been recorded yet.</p>'; return; }
  batchList.innerHTML = items.map((item) => { const next = item.status === 'HARVESTED' ? 'PROCESSED' : item.status === 'PROCESSED' ? 'DISTRIBUTED' : ''; return `<article class="batch-card"><div><strong class="record-title">${escapeHtml(item.batch_id)}</strong><span class="record-meta">${escapeHtml(item.honey_type)} · Hive ${escapeHtml(item.hive_id)} · ${escapeHtml(item.quantity)} kg</span></div><div><span class="status-chip">${escapeHtml(item.status)}</span><span class="record-meta">Harvested ${escapeHtml(item.harvest_date)}</span></div><button class="status-button" data-id="${escapeHtml(item.batch_id)}" data-status="${next}" type="button" ${next ? '' : 'hidden'}>${next === 'PROCESSED' ? 'Release as processed' : 'Mark distributed'}</button></article>`; }).join('');
};
const loadDesk = async () => {
  errorMessage.hidden = true;
  const response = await fetch('/api/admin/requests');
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || 'The operations desk could not be loaded.');
  }
  const payload = await response.json();
  renderStats(payload.beekeepers, payload.batches); renderBeekeepers(payload.beekeepers); renderBatches(payload.batches);
};
beekeeperList.addEventListener('click', async (event) => { const button = event.target.closest('button[data-id]'); if (!button) return; try { await requestDecision(`/api/admin/beekeepers/${encodeURIComponent(button.dataset.id)}`, button.dataset.status, button); await loadDesk(); } catch (error) { button.disabled = false; showError(error.message); } });
batchList.addEventListener('click', async (event) => { const button = event.target.closest('button[data-id]'); if (!button) return; try { await requestDecision(`/api/admin/batches/${encodeURIComponent(button.dataset.id)}`, button.dataset.status, button); await loadDesk(); } catch (error) { button.disabled = false; showError(error.message); } });
document.querySelector('#refresh-button').addEventListener('click', () => loadDesk().catch((error) => showError(error.message)));
document.querySelector('#ops-date').textContent = new Intl.DateTimeFormat(undefined, {dateStyle:'medium'}).format(new Date());
loadDesk().catch((error) => showError(error.message));
