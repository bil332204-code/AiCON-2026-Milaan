/* Simple seller flow: type or paste orders, read a statement PDF, check rows, import.
   Pure helpers are exported for tests; dialogs use the DOM only when called. */

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const AMOUNT = /^(?:rs\.?|pkr)?\s*(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?$/i;

/** "3,500" / "Rs 3500.5" -> "3500.50", or null. */
export function cleanAmount(text) {
  const m = String(text ?? "").trim().match(AMOUNT);
  if (!m) return null;
  const whole = m[1].replace(/,/g, "");
  if (Number(whole) <= 0 && !Number(m[2] || 0)) return null;
  return `${Number(whole)}.${(m[2] || "").padEnd(2, "0")}`;
}

/** Split one pasted line into cells: tabs, commas, pipes, semicolons or 2+ spaces. */
function cells(line) {
  if (/\t/.test(line)) return line.split("\t");
  if (/[|;]/.test(line)) return line.split(/[|;]/);
  if (/,/.test(line)) {
    // "1042, Hira Khan, 3,500": drop thousands separators before splitting on commas
    const parts = line.replace(/(\d),(?=\d{3}(?!\d))/g, "$1").split(",");
    if (parts.length >= 3) return parts;
  }
  if (/\s{2,}/.test(line.trim())) return line.trim().split(/\s{2,}/);
  // "#1042 Hira Khan 3500": first word = order number, last word = amount, middle = name
  const words = line.trim().split(/\s+/);
  if (words.length >= 3) return [words[0], words.slice(1, -1).join(" "), words[words.length - 1]];
  return [line];
}

/**
 * Turn pasted text into orders. Accepts "order number, customer name, amount" in any common
 * separator, with or without a header row. Returns { orders, errors }.
 */
export function parsePastedOrders(text, existingRefs = []) {
  const orders = [], errors = [], seen = new Set(existingRefs.map((r) => String(r).toLowerCase()));
  const lines = String(text ?? "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  lines.forEach((line, index) => {
    const parts = cells(line).map((c) => c.trim()).filter((c, i, a) => c || i < a.length - 1);
    if (parts.length < 3) {
      errors.push(`Line ${index + 1}: write order number, customer name and amount.`);
      return;
    }
    let ref = parts[0].replace(/^#/, "");
    let amount = cleanAmount(parts[parts.length - 1]);
    let name = parts.slice(1, -1).join(" ").trim();
    if (!amount && index === 0) return; // header row such as "Order, Name, Amount"
    if (!amount) {
      errors.push(`Line ${index + 1}: "${parts[parts.length - 1]}" is not an amount.`);
      return;
    }
    if (!ref || ref.length > 100) {
      errors.push(`Line ${index + 1}: add an order number.`);
      return;
    }
    if (!name) name = "Customer";
    if (seen.has(ref.toLowerCase())) {
      errors.push(`Line ${index + 1}: order ${ref} is already in this batch.`);
      return;
    }
    seen.add(ref.toLowerCase());
    orders.push({ order_ref: ref, customer_name: name.slice(0, 150), amount_due: amount });
  });
  if (orders.length > 2000) errors.push("Add at most 2,000 orders at a time.");
  return { orders, errors };
}

const q = (v) => '"' + String(v ?? "").replaceAll('"', '""') + '"';

export function ordersCSV(orders, account) {
  return ["order_ref,customer_name,amount_due,account_id,currency",
    ...orders.map((o) => [o.order_ref, o.customer_name, o.amount_due, account, "PKR"].map(q).join(","))].join("\r\n");
}

export function statementCSV(rows) {
  return ["posted_at,direction,amount,counterparty,transaction_id",
    ...rows.map((r) => [r.posted_at, r.direction, r.amount, r.counterparty || "Unknown", r.transaction_id || ""].map(q).join(","))].join("\r\n");
}

/** "2026-11-02T14:22:00+05:00" -> "2026-11-02T14:22" for datetime-local inputs. */
export const toLocalInput = (iso) => (iso ? String(iso).slice(0, 16) : "");
/** "2026-11-02T14:22" -> "2026-11-02T14:22:00+05:00" (Pakistan time). */
export const fromLocalInput = (value, seconds = "00") => (value ? `${value.slice(0, 16)}:${seconds}+05:00` : "");

/** Check reviewed statement rows before import. Returns a list of plain-language problems. */
export function checkStatement(rows, period) {
  const problems = [];
  if (!rows.length) problems.push("Keep at least one transaction.");
  if (!period.start || !period.end) problems.push("Enter the first and last day this statement covers.");
  const start = Date.parse(period.start), end = Date.parse(period.end);
  if (period.start && period.end && !(end > start)) problems.push("The last day must be after the first day.");
  rows.forEach((r, i) => {
    const at = Date.parse(r.posted_at);
    if (!Number.isFinite(at)) problems.push(`Row ${i + 1}: add the date and time.`);
    else if (Number.isFinite(start) && Number.isFinite(end) && (at < start || at > end))
      problems.push(`Row ${i + 1}: its date is outside the statement period.`);
    if (!cleanAmount(r.amount)) problems.push(`Row ${i + 1}: the amount is not valid.`);
    if (!["CREDIT", "DEBIT"].includes(r.direction)) problems.push(`Row ${i + 1}: choose money in or money out.`);
  });
  return problems;
}

/* ---------- dialogs ---------- */

function dialog(className, html) {
  const d = document.createElement("dialog");
  d.className = "help-dialog " + className;
  d.innerHTML = html;
  document.body.append(d);
  return d;
}

export function newBatchDialog(defaultAccount = "") {
  return new Promise((resolve) => {
    const today = new Date().toLocaleDateString("en-GB", { day: "numeric", month: "short" });
    const d = dialog("seller-dialog", `<form method="dialog" class="seller-form">
      <h2>New batch</h2>
      <p class="account-intro">A batch is one set of orders you want to check before shipping, for example today's orders.</p>
      <label class="field">Batch name<input name="name" required maxlength="120" value="Orders · ${esc(today)}"></label>
      <label class="field">Where do customers send you money?<input name="account" required maxlength="100" value="${esc(defaultAccount)}" placeholder="e.g. JazzCash 0300-1234567 or Meezan Bank"></label>
      <p class="field-help">Use the same account whose statement you will upload. You only need to type it once per batch.</p>
      <div class="dialog-actions"><button class="btn btn-outline" value="cancel" type="submit" formnovalidate>Cancel</button><button class="btn btn-forest" value="ok" type="submit">Create batch</button></div>
    </form>`);
    d.addEventListener("close", () => {
      const f = d.querySelector("form");
      const out = d.returnValue === "ok" ? { name: f.name.value.trim(), account: f.account.value.trim() } : null;
      d.remove();
      resolve(out && out.name && out.account ? out : null);
    });
    d.showModal();
  });
}

export function statementReviewDialog(result) {
  return new Promise((resolve) => {
    let rows = result.rows.map((r) => ({ ...r }));
    const d = dialog("statement-review", "");
    const flag = (r, key) => (r.needs_check || []).includes(key) ? " needs-check" : "";
    const draw = (problems = []) => {
      d.innerHTML = `<form method="dialog" class="seller-form">
        <h2>Check your statement</h2>
        <p class="account-intro">We read <b>${rows.length}</b> transactions from <b>${esc(result.filename || "your PDF")}</b>. Fix anything highlighted, remove rows that are not real transactions, then import.</p>
        ${(result.warnings || []).map((w) => `<p class="notice">${esc(w)}</p>`).join("")}
        <div class="field-grid"><label class="field">Statement starts<input type="datetime-local" name="start" value="${esc(toLocalInput(result.period?.start))}" required></label>
        <label class="field">Statement ends<input type="datetime-local" name="end" value="${esc(toLocalInput(result.period?.end))}" required></label></div>
        <div class="table-wrap statement-rows"><table><thead><tr><th>Date &amp; time</th><th>In / out</th><th>Amount (PKR)</th><th>From / to</th><th>Transaction ID</th><th></th></tr></thead><tbody>
        ${rows.map((r, i) => `<tr data-row="${i}">
          <td><input type="datetime-local" data-f="posted_at" value="${esc(toLocalInput(r.posted_at))}" class="${flag(r, "time")}" aria-label="Date and time, row ${i + 1}"></td>
          <td><select data-f="direction" class="${flag(r, "direction")}" aria-label="Money in or out, row ${i + 1}"><option value="CREDIT" ${r.direction === "CREDIT" ? "selected" : ""}>Money in</option><option value="DEBIT" ${r.direction === "DEBIT" ? "selected" : ""}>Money out</option></select></td>
          <td><input data-f="amount" inputmode="decimal" value="${esc(r.amount)}" aria-label="Amount, row ${i + 1}"></td>
          <td><input data-f="counterparty" value="${esc(r.counterparty)}" maxlength="200" aria-label="From or to, row ${i + 1}"></td>
          <td><input data-f="transaction_id" value="${esc(r.transaction_id)}" maxlength="150" class="${flag(r, "transaction_id")}" placeholder="Not found" aria-label="Transaction ID, row ${i + 1}"></td>
          <td><button type="button" class="link-button" data-drop-row="${i}" aria-label="Remove row ${i + 1}">Remove</button></td></tr>`).join("")}
        </tbody></table></div>
        <label class="checkbox-row"><input type="checkbox" name="complete" checked><span>This statement includes every transaction between these dates.</span></label>
        <label class="checkbox-row"><input type="checkbox" name="refs"><span>The Transaction ID on my customers' screenshots is the same number shown in this statement.</span></label>
        ${problems.length ? `<div class="validation-error" role="alert">${problems.slice(0, 6).map(esc).join("<br>")}</div>` : ""}
        <div class="dialog-actions"><button class="btn btn-outline" value="cancel" type="submit" formnovalidate>Cancel</button><button class="btn btn-forest" value="ok" type="submit">Import ${rows.length} transactions</button></div>
      </form>`;
    };
    const sync = () => {
      d.querySelectorAll("tr[data-row]").forEach((tr) => {
        const r = rows[Number(tr.dataset.row)];
        tr.querySelectorAll("[data-f]").forEach((el) => {
          const f = el.dataset.f;
          r[f] = f === "posted_at" ? fromLocalInput(el.value) : el.value.trim();
        });
        if (cleanAmount(r.amount)) r.amount = cleanAmount(r.amount);
      });
    };
    draw();
    d.addEventListener("click", (e) => {
      const b = e.target.closest("[data-drop-row]");
      if (!b) return;
      sync();
      const keep = { start: d.querySelector("[name=start]").value, end: d.querySelector("[name=end]").value };
      rows.splice(Number(b.dataset.dropRow), 1);
      result = { ...result, period: { start: fromLocalInput(keep.start), end: fromLocalInput(keep.end, "59") } };
      draw();
    });
    d.addEventListener("submit", (e) => {
      if (e.submitter?.value !== "ok") return;
      sync();
      const form = d.querySelector("form");
      const period = { start: fromLocalInput(form.start.value), end: fromLocalInput(form.end.value, "59") };
      const problems = checkStatement(rows, period);
      if (problems.length) {
        e.preventDefault();
        result = { ...result, period };
        draw(problems);
        return;
      }
      d.dataset.out = JSON.stringify({ rows, period, complete: form.complete.checked, refsVerified: form.refs.checked });
    });
    d.addEventListener("close", () => {
      const out = d.returnValue === "ok" && d.dataset.out ? JSON.parse(d.dataset.out) : null;
      d.remove();
      resolve(out);
    });
    d.showModal();
  });
}

/* ---------- workspace step view ---------- */

export function sellerImportsHTML({ state, account, icon, money, proofCard }) {
  const locked = !!state.remote.latest_run_id;
  const saved = state.statements || [];
  const orderRows = state.orders.slice(0, 50).map((o) =>
    `<tr><td>#${esc(String(o.id).replace(/^#/, ""))}</td><td>${esc(o.name)}</td><td class="amount-cell"><span>Rs</span>${money(o.due)}</td></tr>`).join("");
  const step = (n, done, title, body) =>
    `<section class="import-card wide-card seller-step ${done ? "is-done" : ""}"><h2><span class="step-label">${done ? "✓" : n}</span>${title}</h2>${body}</section>`;
  return `<div class="page-intro"><div><div class="eyebrow">BATCH</div><h1>${esc(state.remote.name)}</h1>
      <p>Customers pay into <b>${esc(account)}</b>. Add your orders, your statement and the payment screenshots, then check.</p></div>
      <div class="intro-actions"><button class="btn btn-outline" data-action="refresh-batch">Refresh</button></div></div>
    <input type="hidden" id="statement-account" value="${esc(account)}">
    ${state.error ? `<div class="validation-error" role="alert">${esc(state.error)}</div>` : ""}
    ${locked ? `<div class="demo-notice"><span>This batch has been checked, so its records are locked. Unlock it to add or change records; your earlier decisions stay in the history.</span><button data-action="edit-inputs">Unlock and edit →</button></div>` : ""}
    <fieldset class="plain-fieldset" ${locked ? "disabled" : ""}>
    ${step(1, state.orders.length, "Your orders", `
      ${state.orders.length ? `<div class="table-wrap compact-table"><table><thead><tr><th>Order</th><th>Customer</th><th>Amount</th></tr></thead><tbody>${orderRows}</tbody></table></div>${state.orders.length > 50 ? `<p class="field-help">Showing 50 of ${state.orders.length} orders.</p>` : ""}` : `<p>Paste them from WhatsApp notes, Excel or Google Sheets. One order per line: <b>order number, customer name, amount</b>.</p>`}
      <label class="field">${state.orders.length ? "Add more orders" : "Paste or type orders"}<textarea id="paste-orders" rows="5" placeholder="1042, Hira Khan, 3500&#10;1043, Sana Malik, 4200&#10;1044, Usman Tariq, 2800"></textarea></label>
      <p class="field-help" id="paste-preview" aria-live="polite"></p>
      <div class="step-actions"><button class="btn btn-forest btn-small" data-action="add-orders">${icon("plus")}Add orders</button>
      ${state.orders.length ? "" : `<label class="link-button file-link">or upload a CSV file<input class="file-input" type="file" accept=".csv,text/csv" data-upload="orders"></label>`}</div>`)}
    ${step(2, saved.length, "Your statement", saved.length
      ? saved.map((s) => `<div class="saved-statement"><b>${esc(s.filename)}</b><small>${state.lines.length} transactions · ${s.complete ? "complete period" : "period not confirmed"}</small><button class="link-button" data-remove-statement="${esc(s.id)}">Remove and upload again</button></div>`).join("")
      : `<p>Download the statement from your bank or wallet app (JazzCash, Easypaisa, any bank) for the days you took orders, and upload the PDF here. You'll check the transactions before anything is saved.</p>
      <label class="dropzone" data-drop="statement">${icon("upload")}<span>Upload statement PDF</span><small>PDF from your bank or wallet · CSV also works</small><input class="file-input" type="file" accept=".pdf,application/pdf,.csv,text/csv" data-upload="statement"></label>
      <details class="csv-help"><summary>Uploading a CSV instead?</summary><p>Set the period the CSV covers first.</p><div class="field-grid"><label class="field">From<input type="datetime-local" data-coverage="start" value="${esc(state.coverage.start)}"></label><label class="field">To<input type="datetime-local" data-coverage="end" value="${esc(state.coverage.end)}"></label></div><label class="checkbox-row"><input type="checkbox" data-coverage="complete" ${state.coverage.complete ? "checked" : ""}><span>The CSV includes every transaction in this period.</span></label><label class="checkbox-row"><input type="checkbox" data-coverage="references" ${state.referenceVerified ? "checked" : ""}><span>Customers' Transaction IDs are the same numbers shown in this statement.</span></label><button class="link-button" data-template="statement" type="button">Download a CSV template</button></details>`)}
    ${step(3, state.claims.length, "Payment screenshots", `<p>Choose an order, then add the screenshot the customer sent you for it.</p>
      <div class="field-grid"><label class="field">Order<select id="upload-order"><option value="">Choose an order</option>${state.orders.map((o) => `<option value="${esc(o.serverId)}">#${esc(String(o.id).replace(/^#/, ""))} · ${esc(o.name)} · Rs ${money(o.due)}</option>`).join("")}</select></label></div>
      <label class="dropzone">${icon("plus")}<span>Add screenshots</span><small>JPG, PNG or WEBP · up to 10 MB each</small><input class="file-input" type="file" multiple accept="image/png,image/jpeg,image/webp" data-upload="claims"></label>
      ${state.claims.length ? `<div class="upload-header"><p>Type the amount, date and Transaction ID from each screenshot (or let AI read them), then tick the box and save.</p><button class="btn btn-outline btn-small" data-action="ocr-all" type="button">${icon("spark")}Read with AI</button></div>` : ""}
      <div class="proof-list">${state.claims.map(proofCard).join("")}</div>`)}
    </fieldset>
    <div class="import-run"><p>${state.orders.length} orders · ${state.lines.length} statement transactions · ${state.claims.length} screenshots</p>
      <button class="btn btn-forest" data-action="reconcile" ${!state.orders.length || !state.lines.length ? "disabled" : ""}>Check payments →</button></div>`;
}
