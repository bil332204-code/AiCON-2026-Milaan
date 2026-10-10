/** Browser ES module. Session stays in memory; the Gemini key never belongs here. */
export class ApiError extends Error {
  constructor(status, detail) { super(typeof detail === 'string' ? detail : JSON.stringify(detail)); this.status = status; this.detail = detail; }
}
export class MilaanAPI {
  constructor(baseUrl = 'http://127.0.0.1:8000') {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.token = null;
  }
  async request(path, { method = 'GET', body, headers = {}, signal, blob = false } = {}) {
    const h = { ...headers };
    if (this.token) h.Authorization = `Bearer ${this.token}`;
    if (body !== undefined && !(body instanceof FormData)) { h['Content-Type'] = 'application/json'; body = JSON.stringify(body); }
    const response = await fetch(`${this.baseUrl}${path}`, { method, headers: h, body, signal, cache: 'no-store' });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      if (response.status === 401) this.token = null;
      throw new ApiError(response.status, error.detail || error);
    }
    if (response.status === 204) return null;
    return blob ? response.blob() : response.json();
  }
  async register(email, password, displayName) {
    const data = await this.request('/api/auth/register', { method: 'POST', body: { email, password, display_name: displayName } });
    this.token = data.access_token || null; return data;
  }
  async verifyEmail(challengeId, code) {
    const data = await this.request('/api/auth/verify-email', {method:'POST', body:{challenge_id:challengeId,code}});
    this.token = data.access_token; return data;
  }
  resendCode(challengeId) { return this.request('/api/auth/resend-code', {method:'POST',body:{challenge_id:challengeId}}); }
  async login(email, password) {
    const data = await this.request('/api/auth/login', { method: 'POST', body: { email, password } });
    this.token = data.access_token || null; return data;
  }
  async logout() { try { return await this.request('/api/auth/logout', { method: 'POST' }); } finally { this.token = null; } }
  me() { return this.request('/api/auth/me'); }
  health() { return this.request('/api/health'); }
  integrations() { return this.request('/api/integrations/status'); }
  content() { return this.request('/api/content'); }
  saveContent(key, value, expectedVersion) { return this.request(`/api/content/${encodeURIComponent(key)}`, { method: 'PUT', body: { value, expected_version: expectedVersion } }); }
  batches(offset = 0) { return this.request(`/api/batches?offset=${offset}&limit=50`); }
  createBatch(name) { return this.request('/api/batches', { method: 'POST', body: { name } }); }
  demo() { return this.request('/api/batches/demo', { method: 'POST' }); }
  batch(id) { return this.request(`/api/batches/${id}`); }
  deleteBatch(id) { return this.request(`/api/batches/${id}`, { method: 'DELETE' }); }
  reset(id, revision, reason) { return this.request(`/api/batches/${id}/reset`, { method: 'POST', body: { expected_revision: revision, reason } }); }
  orders(id) { return this.request(`/api/batches/${id}/orders`); }
  statements(id) { return this.request(`/api/batches/${id}/statements`); }
  claims(id) { return this.request(`/api/batches/${id}/claims`); }
  addOrder(id, order) { return this.request(`/api/batches/${id}/orders/item`, { method: 'POST', body: order }); }
  updateOrder(id, order, revision) { return this.request(`/api/orders/${id}`, { method: 'PATCH', body: { ...order, expected_revision: revision } }); }
  upload(path, file, fields) {
    const body = new FormData(); body.append('file', file);
    Object.entries(fields).forEach(([key, value]) => body.append(key, String(value)));
    return this.request(path, { method: 'POST', body });
  }
  uploadOrders(id, file, revision) { return this.upload(`/api/batches/${id}/orders`, file, { expected_revision: revision }); }
  uploadStatement(id, file, revision, metadata) { return this.upload(`/api/batches/${id}/statement`, file, { ...metadata, expected_revision: revision }); }
  uploadClaim(id, orderId, file, revision) { return this.upload(`/api/batches/${id}/claims`, file, { order_id: orderId, expected_revision: revision }); }
  updateClaim(id, version, fields, confirmed = false) { return this.request(`/api/claims/${id}`, { method: 'PATCH', body: { expected_version: version, fields, confirmed } }); }
  retryExtraction(id, version) { return this.request(`/api/claims/${id}/retry-extraction`, { method: 'POST', body: { expected_version: version } }); }
  deleteClaim(id, version) { return this.request(`/api/claims/${id}?expected_version=${version}`, { method: 'DELETE' }); }
  deleteStatement(id, revision) { return this.request(`/api/statements/${id}?expected_revision=${revision}`, { method: 'DELETE' }); }
  statementLines(id, offset = 0) { return this.request(`/api/statements/${id}/lines?offset=${offset}&limit=500`); }
  /** Retry the same network request with the same key. New work needs a new key. */
  extract(id, consentToCloud, key = crypto.randomUUID()) {
    if (consentToCloud !== true) throw new Error('Ask the user before sending receipt images to Google.');
    return this.request(`/api/batches/${id}/extract`, { method: 'POST', body: { consent_to_cloud: true }, headers: { 'Idempotency-Key': key } });
  }
  reconcile(id, key = crypto.randomUUID()) { return this.request(`/api/batches/${id}/reconcile`, { method: 'POST', headers: { 'Idempotency-Key': key } }); }
  job(id) { return this.request(`/api/jobs/${id}`); }
  async waitForJob(id, { signal, timeoutMs = 1800000, onProgress = () => {} } = {}) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      const job = await this.request(`/api/jobs/${id}`, { signal }); onProgress(job);
      if (job.status === 'done') return job;
      if (job.status === 'failed') throw new Error(job.error || 'Job failed');
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    throw new Error('Waiting timed out. The server job may still be running; poll its ID again.');
  }
  results(id) { return this.request(`/api/batches/${id}/results`); }
  decide(id, version, decision, reason, statementLineId = null) {
    return this.request(`/api/matches/${id}/decision`, { method: 'POST', body: { expected_version: version, decision, reason, statement_line_id: statementLineId } });
  }
  audit(id, offset = 0) { return this.request(`/api/batches/${id}/audit?offset=${offset}&limit=100`); }
  receiptBlob(id) { return this.request(`/api/claims/${id}/image`, { blob: true }); }
  exportCSV(id) { return this.request(`/api/batches/${id}/export.csv`, { blob: true }); }
}

/** A small, explicit view model for the existing dashboard. Keep raw data for review. */
export function dashboardRows(response) {
  return response.items.map(row => ({
    id: row.id, orderId: row.order.id, orderRef: row.order.order_ref,
    customer: row.order.customer_name, amountPaisa: row.order.amount_due_paisa,
    status: row.final_status, machineStatus: row.machine_verdict,
    reason: row.reason, reasonCode: row.reason_code, evidence: row.evidence,
    candidates: row.candidates, version: row.version, raw: row,
  }));
}
