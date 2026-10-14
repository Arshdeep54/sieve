const REQUIRED_COLUMNS = ['user_id', 'email', 'monthly_income', 'credit_score', 'employment_status', 'age'];
const MAX_BYTES = 50 * 1024 * 1024;
const POLL_MS = 2000;
const FINAL_STATUSES = new Set(['done', 'failed', 'duplicate']);
const STEPS = ['upload', 'ingest', 'match', 'notify'];
const ACTIVE_STEP = { pending: 0, ingesting: 1, ingested: 2, matching: 2, matched: 3, notifying: 3, done: 4 };

const byId = (id) => document.getElementById(id);
const count = new Intl.NumberFormat('en-IN');
const clock = new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit' });

const view = {
  dropzone: byId('dropzone'),
  fileInput: byId('file-input'),
  dropTitle: byId('dropzone-title'),
  progress: byId('upload-progress'),
  progressBar: byId('upload-progress-bar'),
  uploadError: byId('upload-error'),
  batch: byId('batch'),
  batchTitle: byId('batch-title'),
  batchMeta: byId('batch-meta'),
  notice: byId('batch-notice'),
  timeline: byId('timeline'),
  ingestFigures: byId('ingest-figures'),
  errorsLink: byId('errors-link'),
  funnelSection: byId('funnel-section'),
  funnel: byId('funnel'),
  productsSection: byId('products-section'),
  productsBody: byId('products-body'),
  emailsSection: byId('emails-section'),
  uploadAnother: byId('upload-another'),
};

let trackedBatch = null;
let pollTimer = null;
let funnelSignature = '';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function setText(id, value) {
  byId(id).textContent = count.format(value ?? 0);
}

function showUploadError(message) {
  view.uploadError.textContent = message;
  view.uploadError.hidden = false;
}

function setDropzone(state, title) {
  view.dropzone.dataset.state = state;
  view.progress.hidden = state !== 'uploading';
  view.fileInput.disabled = state === 'uploading';
  view.dropTitle.textContent = title ?? 'Drop a users CSV here, or choose a file';
  if (state !== 'uploading') view.progressBar.style.transform = 'scaleX(0)';
}

async function checkFile(file) {
  if (!file.name.toLowerCase().endsWith('.csv')) return 'Choose a .csv file.';
  if (file.size === 0) return 'This file is empty.';
  if (file.size > MAX_BYTES) return 'This file is larger than 50 MB. Split it and upload the parts.';
  const head = await file.slice(0, 64 * 1024).text();
  const header = head.replace(/^﻿/, '').split(/\r?\n/, 1)[0];
  const columns = header.split(',').map((column) => column.trim().replace(/^"|"$/g, '').toLowerCase());
  const missing = REQUIRED_COLUMNS.filter((column) => !columns.includes(column));
  if (missing.length) return `This file is missing the ${missing.join(', ')} column${missing.length > 1 ? 's' : ''}.`;
  return null;
}

async function requestJson(method, path) {
  const response = await fetch(path, { method, headers: { Accept: 'application/json' } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw Object.assign(new Error(body.error ?? `Request failed (${response.status}).`), { status: response.status });
  return body;
}

function sendToStorage(upload, file) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    Object.entries(upload.fields).forEach(([name, value]) => form.append(name, value));
    form.append('file', file);
    const request = new XMLHttpRequest();
    request.open('POST', upload.url);
    request.upload.addEventListener('progress', (event) => {
      if (event.lengthComputable) view.progressBar.style.transform = `scaleX(${event.loaded / event.total})`;
    });
    request.addEventListener('load', () =>
      request.status < 300 ? resolve() : reject(new Error(`The upload was refused (${request.status}). Try again.`)),
    );
    request.addEventListener('error', () => reject(new Error('The upload was interrupted. Check your connection and try again.')));
    request.send(form);
  });
}

async function handleFile(file) {
  view.uploadError.hidden = true;
  const problem = await checkFile(file);
  if (problem) {
    showUploadError(problem);
    return;
  }
  setDropzone('uploading', `Uploading ${file.name}`);
  try {
    const created = await requestJson('POST', 'uploads');
    await sendToStorage(created.upload, file);
    setDropzone('idle');
    track(created.batch_id);
  } catch (error) {
    setDropzone('idle');
    showUploadError(error.message);
  }
}

function track(batchId) {
  clearTimeout(pollTimer);
  trackedBatch = batchId;
  funnelSignature = '';
  history.replaceState(null, '', `#batch=${batchId}`);
  view.funnel.replaceChildren();
  view.batch.hidden = false;
  view.batch.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  poll(batchId);
}

async function poll(batchId) {
  try {
    const report = await requestJson('GET', `uploads/${batchId}`);
    if (batchId !== trackedBatch) return;
    render(report);
    if (!FINAL_STATUSES.has(report.batch.status)) pollTimer = setTimeout(() => poll(batchId), POLL_MS);
  } catch (error) {
    if (batchId !== trackedBatch) return;
    if (error.status === 404) {
      showNotice('This upload could not be found. Upload the file again.', 'warn');
      view.uploadAnother.hidden = false;
      return;
    }
    view.batchMeta.textContent = 'Connection lost. Retrying…';
    pollTimer = setTimeout(() => poll(batchId), POLL_MS * 2);
  }
}

function showNotice(message, tone, action) {
  view.notice.replaceChildren(document.createTextNode(message));
  if (action) {
    const link = element('a', null, action.label);
    link.href = action.href;
    view.notice.append(' ', link);
  }
  view.notice.dataset.tone = tone ?? '';
  view.notice.hidden = false;
}

function failedStep(report) {
  if (report.batch.total_rows === null) return 1;
  if (!report.funnel) return 2;
  return 3;
}

function renderTimeline(report) {
  const { batch, funnel, notifications } = report;
  const active = batch.status === 'failed' ? failedStep(report) : (ACTIVE_STEP[batch.status] ?? 1);
  const details = {
    upload: 'File received',
    ingest: batch.valid_rows === null ? '' : `${count.format(batch.valid_rows)} users`,
    match: funnel ? `${count.format(funnel.total_matches)} matches` : '',
    notify: batch.status === 'done' ? `${count.format(notifications.sent ?? 0)} sent` : '',
  };
  view.timeline.querySelectorAll('li').forEach((item, index) => {
    const step = STEPS[index];
    let state = 'idle';
    if (batch.status === 'duplicate') state = index === 0 ? 'done' : 'idle';
    else if (index < active) state = 'done';
    else if (index === active) state = batch.status === 'failed' ? 'failed' : 'active';
    item.dataset.state = state;
    item.querySelector('.step-detail').textContent = state === 'done' ? details[step] : '';
  });
}

function renderIngest(batch, errorsUrl) {
  view.ingestFigures.hidden = batch.total_rows === null;
  if (batch.total_rows === null) return;
  setText('rows-total', batch.total_rows);
  setText('rows-valid', batch.valid_rows);
  setText('rows-rejected', batch.rejected_rows);
  view.errorsLink.hidden = !errorsUrl;
  if (errorsUrl) view.errorsLink.href = errorsUrl;
}

function funnelRows(funnel, notifications, done) {
  const seconds = (funnel.duration_ms / 1000).toLocaleString('en-IN', { maximumFractionDigits: 1 });
  const rows = [
    {
      label: 'User and loan pairs',
      hint: `${count.format(funnel.users_in_batch)} users × ${funnel.products_active} loans`,
      value: funnel.pairs_total,
    },
    { label: 'Pass the hard rules', hint: 'Income, CIBIL, age and employment, in SQL', value: funnel.pairs_after_sql },
    {
      label: 'Profile groups to review',
      hint: `${count.format(funnel.cache_hits)} answered from earlier reviews`,
      value: funnel.classes_to_judge,
      tone: 'quiet',
    },
    { label: 'OpenAI calls', hint: 'Up to 20 profile groups per call', value: funnel.llm_calls, tone: 'quiet' },
    { label: 'Matches', hint: `Found in ${seconds} s`, value: funnel.total_matches },
  ];
  if (done) rows.push({ label: 'Emails sent', hint: 'Best-matched users only', value: notifications.sent ?? 0 });
  return rows;
}

function renderFunnel(report) {
  const { funnel, notifications, batch } = report;
  view.funnelSection.hidden = !funnel;
  if (!funnel) return;
  const rows = funnelRows(funnel, notifications, batch.status === 'done');
  const signature = JSON.stringify(rows);
  if (signature === funnelSignature) return;
  const firstRender = funnelSignature === '';
  funnelSignature = signature;

  const scale = Math.log10(Math.max(...rows.map((row) => row.value)) + 1);
  view.funnel.toggleAttribute('data-enter', firstRender);
  view.funnel.replaceChildren(
    ...rows.map((row, index) => {
      const item = element('li', 'funnel-row');
      if (row.tone) item.dataset.tone = row.tone;
      const label = element('span', 'funnel-label', row.label);
      label.append(element('span', 'funnel-hint', row.hint));
      const track = element('span', 'funnel-track');
      const bar = element('span', 'funnel-bar');
      bar.style.width = `${Math.max(0.6, (Math.log10(row.value + 1) / scale) * 82)}%`;
      bar.style.setProperty('--index', index);
      track.append(bar, element('span', 'funnel-value', count.format(row.value)));
      item.append(label, track);
      return item;
    }),
  );
}

function renderResults(report) {
  const settled = ['notifying', 'done'].includes(report.batch.status) || report.products.length > 0;
  view.productsSection.hidden = !settled || report.products.length === 0;
  view.productsBody.replaceChildren(
    ...report.products.map((product) => {
      const row = element('tr');
      const name = element('td', null, product.product_name);
      name.prepend(element('span', 'product-lender', product.lender));
      row.append(
        name,
        element('td', 'num', count.format(product.matches)),
        element('td', 'num', `${Math.round(product.avg_score * 100)}%`),
      );
      return row;
    }),
  );
  view.emailsSection.hidden = report.batch.status !== 'done';
  setText('emails-sent', report.notifications.sent);
  setText('emails-suppressed', report.notifications.suppressed);
  setText('emails-failed', report.notifications.failed);
}

function renderHeader(batch) {
  view.batchTitle.textContent = `Upload ${batch.batch_id.slice(0, 8)}`;
  view.batchMeta.textContent = `Started at ${clock.format(new Date(batch.created_at))}`;
  view.notice.hidden = true;
  if (batch.status === 'duplicate') {
    showNotice('This exact file was uploaded before, so it was not processed again.', '', {
      label: 'View the earlier results',
      href: `#batch=${batch.duplicate_of}`,
    });
  } else if (batch.status === 'failed') {
    showNotice(batch.error ?? 'Processing stopped. Upload the file again.', 'warn');
  }
}

function render(report) {
  renderHeader(report.batch);
  renderTimeline(report);
  renderIngest(report.batch, report.errors_url);
  renderFunnel(report);
  renderResults(report);
  view.uploadAnother.hidden = !FINAL_STATUSES.has(report.batch.status);
}

function batchFromHash() {
  const match = location.hash.match(/^#batch=([0-9a-f-]{36})$/i);
  return match ? match[1] : null;
}

view.fileInput.addEventListener('change', () => {
  const [file] = view.fileInput.files;
  if (file) handleFile(file);
  view.fileInput.value = '';
});

view.dropzone.addEventListener('dragover', (event) => {
  event.preventDefault();
  if (view.dropzone.dataset.state !== 'uploading') view.dropzone.dataset.state = 'dragging';
});

view.dropzone.addEventListener('dragleave', () => {
  if (view.dropzone.dataset.state === 'dragging') view.dropzone.dataset.state = 'idle';
});

view.dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  if (view.dropzone.dataset.state === 'uploading') return;
  view.dropzone.dataset.state = 'idle';
  const [file] = event.dataTransfer.files;
  if (file) handleFile(file);
});

view.uploadAnother.addEventListener('click', () => {
  clearTimeout(pollTimer);
  trackedBatch = null;
  history.replaceState(null, '', location.pathname);
  view.batch.hidden = true;
  window.scrollTo({ top: 0 });
  view.fileInput.click();
});

window.addEventListener('hashchange', () => {
  const batchId = batchFromHash();
  if (batchId && batchId !== trackedBatch) track(batchId);
});

const initialBatch = batchFromHash();
if (initialBatch) track(initialBatch);
