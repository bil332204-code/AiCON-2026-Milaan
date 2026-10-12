# Wire the cinematic website to this backend

The current Milaan website has a browser-local workflow. Keep its presentation and animations, and replace its data actions using this client. This ZIP supplies the backend and client; it does not change or publish that website.

## 1. Set the connection

Copy `integration/milaan-api.js` into your frontend assets and import it:

```js
import { MilaanAPI, dashboardRows } from './milaan-api.js';
const api = new MilaanAPI('http://127.0.0.1:8000');

// Call these from the actual login/registration form.
await api.register(email, password, displayName);
// Later sessions:
await api.login(email, password);
```

The token stays in memory. Refreshing the page requires another login. If persistent sessions are needed, design an HttpOnly secure cookie flow on a suitable same-site deployment; do not quietly put credentials in localStorage. Protected receipt images require a bearer fetch, so a plain `<img src="/api/...">` does not work by itself.

For the hosted Milaan website, set the API base to your deployed **HTTPS** backend and append its exact frontend origin to backend `.env`:

```dotenv
CORS_ORIGINS=https://milaan-studio.bil332204.chatgpt.site,http://localhost:5173,http://localhost:8080
```

Use your actual deployed origin if it differs. CORS URLs have no trailing slash or path. Restart the backend after changing settings. CORS is a browser permission setting, not authentication.

## 2. Replace the local handlers

| Existing UI action | Backend client call | UI update |
|---|---|---|
| Open dashboard | `api.batches()` | Render saved batches |
| Load demo | `api.demo()` | Store returned batch ID/revision and show SAMPLE |
| New batch | `api.createBatch(name)` | Store ID/revision |
| Orders file | `api.uploadOrders(id, file, revision)` | Replace order list and revision |
| Statement file | `api.uploadStatement(id, file, revision, metadata)` | Save returned revision |
| Receipt files | `api.uploadClaim(id, orderId, file, revision)` | Upload sequentially; refresh revision each time |
| Read receipts | `api.extract(id, true, key)` | Poll job; refresh claims and batch |
| Edit extraction | `api.updateClaim(claimId, version, fields, confirmed)` | Save new claim version and batch revision |
| Reconcile button | `api.reconcile(id, key)` | Poll job, then load results |
| Review decision | `api.decide(matchId, version, status, reason, lineId)` | Refresh results and counts |
| Download CSV | `api.exportCSV(id)` | Download returned Blob |
| Branding / messages | `api.content()` / `api.saveContent(...)` | Render saved JSON as text |
| Change imported data after a run | `api.reset(id, revision, reason)` | Clear current results and reload inputs |

Do not simultaneously run the old `engine.js` matching logic and the server reconciliation for the same live batch. The server's saved results and versions are authoritative. Do not interpret `dashboardRows()` as a magic replacement for every existing component; it is an explicit view model for adapting those components.

## 3. Concrete import and manual-match example

```js
let batch = await api.createBatch('Friday orders');
let uploaded = await api.uploadOrders(batch.id, ordersFile, batch.revision);
batch = uploaded.batch;
const orders = uploaded.items;

const statement = await api.uploadStatement(batch.id, statementFile, batch.revision, {
  account_id: 'wallet-main',
  coverage_start: '2026-10-09T08:00:00+05:00',
  coverage_end: '2026-10-09T20:00:00+05:00',
  complete: coverageConfirmedBySeller,
  references_verified: referenceCorrespondenceConfirmedBySeller,
  provider_pair: 'seller-validated-profile'
});
batch = statement.batch;

const receipt = await api.uploadClaim(batch.id, orders[0].id, receiptFile, batch.revision);
batch = receipt.batch;
const corrected = await api.updateClaim(receipt.claim.id, receipt.claim.version, {
  is_payment_receipt: true,
  amount_pkr: '3500.00',
  datetime_local: '2026-10-09T14:22:00+05:00',
  transaction_id: 'TXN123456',
  status_text: 'Successful',
  unreadable_fields: []
}, true); // Set true only after the person checks the original receipt.
batch = corrected.batch;

const jobKey = crypto.randomUUID(); // Retain for a network retry.
const job = await api.reconcile(batch.id, jobKey);
await api.waitForJob(job.id, { onProgress: job => updateProgress(job.progress, job.total) });
const result = await api.results(batch.id);
renderRows(dashboardRows(result));
renderCounts(result.summary);
```

`ordersFile`, `statementFile`, `receiptFile`, the confirmation booleans, `updateProgress`, and render functions are supplied by your UI. The screenshot's `orderId` must come from the user's explicit order selection, not file order or an array guess in a multi-order batch.

## 4. Gemini alternative and review

Instead of manual entry, show a clear consent control explaining that screenshots will be sent to Google, then:

```js
const job = await api.extract(batch.id, userConsentedToCloud, crypto.randomUUID());
await api.waitForJob(job.id, { onProgress: showExtractionProgress });
const { items: claims } = await api.claims(batch.id);
batch = await api.batch(batch.id);
// Show both reads and original image for failed/needs_review claims.
// Save human corrections, then call reconcile.
```

For receipt preview:

```js
const url = URL.createObjectURL(await api.receiptBlob(claimId));
imageElement.src = url;
// When preview closes or changes:
URL.revokeObjectURL(url);
```

For review and export:

```js
await api.decide(row.id, row.version, 'ship', reviewReason, selectedCandidate.id);
const refreshed = await api.results(batch.id);
renderRows(dashboardRows(refreshed));

const csv = await api.exportCSV(batch.id);
const url = URL.createObjectURL(csv);
const link = document.createElement('a');
link.href = url; link.download = 'milaan-results.csv'; link.click();
setTimeout(() => URL.revokeObjectURL(url), 1000);
```

A 409 means another edit, run, or allocation changed the data. Fetch fresh state and let the user decide again. Never bypass a conflict by replacing the returned version with a guessed number. Display machine and human decisions separately when they differ.
