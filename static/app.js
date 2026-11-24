const $ = (selector) => document.querySelector(selector);
const state = {
  userId: $("#user-select").value,
  role: "student",
  operatorConfigured: false,
  purposes: {},
  consents: {},
  consumers: [],
  notice: null,
  noticeHistory: [],
  auditMode: "timeline",
  ledgerEvents: [],
  integrity: null,
  consentRows: [],
  accessRows: [],
  revocations: [],
  visitedPrivacy: false,
  verifiedIntegrityManual: false,
  diagnosticsRun: false,
  selectedTourStep: 0,
  tourBaseline: (() => {
    try {
      const raw = localStorage.getItem("consentx-tour-baseline");
      return raw ? JSON.parse(raw) : null;
    } catch (_) {
      return null;
    }
  })(),
};
const consumerForPurpose = {
  P1: "notification-service",
  P2: "recommendation-service",
  P3: "analytics-service",
};
let auditVisibleLimit = 12;
let noticeEditorDirty = false;
let toastTimer = null;

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (char) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[char]
  ));

function showToast(message, type = "ok") {
  const toast = $("#toast");
  if (!toast) return;
  $("#toast-icon").textContent = type === "error" ? "⚠" : "✓";
  $("#toast-msg").textContent = message;
  toast.className = `toast ${type}`;
  toast.hidden = false;
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 5000);
}

$("#toast-close")?.addEventListener("click", () => { $("#toast").hidden = true; });

function applyTheme(theme) {
  const next = theme === "dark" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("consentx-theme", next);
  const btn = $("#theme-toggle");
  if (btn) btn.textContent = next === "dark" ? "☀" : "☾";
}
applyTheme(localStorage.getItem("consentx-theme") || "light");
$("#theme-toggle")?.addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  applyTheme(cur === "dark" ? "light" : "dark");
});

async function api(path, body, methodOverride = null) {
  const options = body !== undefined
    ? { method: methodOverride || "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : (methodOverride ? { method: methodOverride } : {});
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok && !data.decision && !data.revocation && data.status !== "broken") {
    throw new Error(data.error || data.reason_code || `HTTP ${response.status}`);
  }
  return { data, status: response.status, ok: response.ok };
}

function activateView(viewName) {
  const known = ["dashboard", "consent", "simulator", "privacy", "notices", "audit", "guide"];
  const active = known.includes(viewName) ? viewName : "dashboard";
  document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${active}`));
  document.querySelectorAll(".nav-link").forEach((link) => {
    const selected = link.dataset.view === active;
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const labels = {
    dashboard: "Dashboard",
    consent: "Consent & revocation",
    simulator: "Data access simulator",
    privacy: "My Privacy",
    notices: "Notice versions",
    audit: "Audit & verification",
    guide: "Judge Guide & Architecture",
  };
  $("#current-section").textContent = labels[active];
  if (active === "privacy") {
    state.visitedPrivacy = true;
    renderJudgeTour();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function getCurrentState(purposeId) {
  const event = state.consents[purposeId];
  const currentNotice = state.notice;
  const matchesNotice =
    event && currentNotice && event.notice_version === currentNotice.version && event.notice_hash === currentNotice.sha256;
  const granted = event?.action === "grant" && matchesNotice;
  const label = granted
    ? "Granted"
    : event?.action === "withdraw"
    ? "Withdrawn"
    : event?.action === "grant"
    ? "Re-consent needed"
    : "Not granted";
  return { event, granted: Boolean(granted), label, matchesNotice: Boolean(matchesNotice) };
}

function renderPurposeCards() {
  const entries = Object.entries(state.purposes);
  $("#purpose-list").innerHTML = entries
    .map(([id, purpose]) => {
      const current = getCurrentState(id);
      const className = current.granted ? "granted" : current.event?.action === "withdraw" ? "withdrawn" : "";
      const action = current.granted ? "withdraw" : "grant";
      const button = current.granted
        ? "Withdraw consent"
        : current.event?.action === "grant"
        ? "Confirm under current notice"
        : "Grant consent";
      return `<article class="purpose-card">
        <div class="purpose-card-top"><span class="purpose-id">${esc(id)}</span><span class="status ${className}">${esc(current.label)}</span></div>
        <h2>${esc(purpose.name)}</h2>
        <p>${esc(purpose.description)}</p>
        <div class="purpose-data"><span>Only releases</span><strong>${esc(Object.keys(purpose.payload).join(" · "))}</strong></div>
        <button type="button" data-purpose="${esc(id)}" data-action="${action}">${button}</button>
      </article>`;
    })
    .join("");

  $("#dashboard-purposes").innerHTML = entries
    .map(([id, purpose]) => {
      const current = getCurrentState(id);
      const cls = current.granted ? "granted" : current.event?.action === "withdraw" ? "withdrawn" : "";
      return `<div class="dashboard-purpose">
        <span class="purpose-id">${esc(id)}</span>
        <span class="purpose-name">${esc(purpose.name)}</span>
        <span class="status ${cls}">${esc(current.label)}</span>
      </div>`;
    })
    .join("");

  $("#simulate-work-buttons").innerHTML = entries
    .map(([id]) => `<button type="button" class="secondary btn-sm" data-sim-work="${esc(id)}">+ Queue ${esc(id)} job</button>`)
    .join("");

  const selectedRequestPurpose = $("#request-purpose").value;
  $("#request-purpose").innerHTML = entries
    .map(([id, purpose]) => `<option value="${esc(id)}">${esc(id)} · ${esc(purpose.name)}</option>`)
    .join("");
  if (state.purposes[selectedRequestPurpose]) $("#request-purpose").value = selectedRequestPurpose;
  renderRequestFields();
  renderSimLiveStatus();
  $("#consent-notice-current").textContent = state.notice ? `Current notice v${state.notice.version}` : "";
  updateRequestPreview();
  updateDashboardMetrics();
  renderJudgeTour();
}

function renderSimLiveStatus() {
  const box = $("#sim-live-status");
  if (!box) return;
  const purposeId = $("#request-purpose").value || "P1";
  const current = getCurrentState(purposeId);
  const name = $("#user-select").selectedOptions[0]?.textContent || state.userId;
  if (current.granted) {
    box.className = "sim-live-status ok";
    box.textContent = `Live policy state for ${name} · ${purposeId}: Granted under v${state.notice?.version} (allowed READ fields will ALLOW).`;
  } else {
    box.className = "sim-live-status blocked";
    box.textContent = `Live policy state for ${name} · ${purposeId}: ${current.label} (requests will DENY with zero payload).`;
  }
}

function renderConsumers() {
  const consumers = state.consumers || [];
  const dash = $("#dashboard-consumers");
  if (dash) {
    dash.innerHTML = consumers
      .map((c) => `<div class="consumer-mini"><code>${esc(c.consumer_id)}</code><span class="status ${c.available ? "granted" : "withdrawn"}">${c.available ? "Online" : "Offline"}</span></div>`)
      .join("");
  }
  const panel = $("#consumer-adapter-list");
  if (panel) {
    panel.innerHTML = consumers
      .map(
        (c) => `<article class="consumer-card">
          <div class="consumer-card-head">
            <strong>${esc(c.display_name)}</strong>
            <span class="status ${c.available ? "granted" : "withdrawn"}">${c.available ? "ONLINE" : "OFFLINE"}</span>
          </div>
          <p>${esc(c.description)}</p>
          <small>Scope: <strong>${esc(c.purpose_id)}</strong> · Processed acks: <strong>${c.revocations_processed}</strong></small>
          <button type="button" class="${c.available ? "danger-outline" : "secondary"} btn-sm"
            data-toggle-consumer="${esc(c.consumer_id)}" data-next-available="${!c.available}">
            ${c.available ? "Simulate service outage" : "Restore service online"}
          </button>
        </article>`
      )
      .join("");
  }
}

function renderNotice() {
  const notice = state.notice;
  if (!notice) return;
  $("#notice-pill").textContent = `CURRENT · v${notice.version}`;
  $("#dashboard-notice-version").textContent = `Notice version ${notice.version}`;
  $("#dashboard-notice-text").textContent = notice.text;
  $("#dashboard-notice-hash").textContent = notice.sha256;
  if (!noticeEditorDirty) $("#notice-text").value = notice.text;
  updateNoticeCharCount();
  const versions = state.noticeHistory;
  $("#notice-history-count").textContent = `${versions.length} version${versions.length === 1 ? "" : "s"}`;
  $("#notice-history").innerHTML = versions
    .map(
      (version, index) => `<article class="notice-version ${index === 0 ? "current" : ""}">
        <div class="notice-version-heading"><strong>Version ${esc(version.version)}</strong>${index === 0 ? '<span class="status granted">CURRENT</span>' : ""}<time>${esc(version.created_at)}</time></div>
        <p>${esc(version.text)}</p>
        <div class="version-digest"><span>SHA-256</span><code title="${esc(version.sha256)}">${esc(version.sha256)}</code></div>
      </article>`
    )
    .join("");
}

function updateNoticeCharCount() {
  const editor = $("#notice-text");
  $("#notice-char-count").textContent = `${editor.value.length} / 4,000 characters`;
}

function updateRequestPreview() {
  const purposeId = $("#request-purpose").value || Object.keys(state.purposes)[0] || "P1";
  const selected = [...document.querySelectorAll("#request-fields input:checked")].map((input) => input.value);
  $("#request-json").textContent = JSON.stringify(
    {
      endpoint: "/api/data-access",
      user_id: state.userId,
      consumer_id: $("#request-consumer").value,
      purpose_id: purposeId,
      operation: $("#request-operation").value,
      requested_fields: selected,
    },
    null,
    2
  );
}

function renderRequestFields(includeExtra = []) {
  const purposeId = $("#request-purpose").value || "P1";
  const allowedFields = Object.keys(state.purposes[purposeId]?.payload || {});
  const extraOutOfScope = ["student_email"].filter((f) => !allowedFields.includes(f));
  $("#request-consumer").value = consumerForPurpose[purposeId] || "";

  const allowedHtml = allowedFields
    .map(
      (field) => `<label class="field-option">
        <input type="checkbox" value="${esc(field)}" checked>
        <code>${esc(field)}</code>
      </label>`
    )
    .join("");
  const extraHtml = extraOutOfScope
    .map(
      (field) => `<label class="field-option out-of-scope" title="Unauthorized field to test field-scope enforcement">
        <input type="checkbox" value="${esc(field)}" ${includeExtra.includes(field) ? "checked" : ""}>
        <code>${esc(field)} (out-of-scope)</code>
      </label>`
    )
    .join("");

  $("#request-fields").innerHTML = allowedHtml + extraHtml;
  updateRequestPreview();
}

function updateDashboardMetrics(accessRows) {
  const consentCount = Object.keys(state.purposes).filter((id) => getCurrentState(id).granted).length;
  $("#metric-grants").textContent = String(consentCount);
  $("#metric-grants-caption").textContent = `For ${$("#user-select").selectedOptions[0]?.textContent || "selected account"}`;
  if (!accessRows) return;
  $("#metric-requests").textContent = String(accessRows.length);
  $("#metric-denied").textContent = String(accessRows.filter((row) => row.result === "DENY").length);
  $("#metric-allowed").textContent = String(accessRows.filter((row) => row.result === "ALLOW").length);
  $("#audit-access-count").textContent = String(accessRows.length);
  const recent = accessRows.slice(-5).reverse();
  $("#dashboard-recent-list").innerHTML = recent.length
    ? recent
        .map((row) => {
          const purpose = state.purposes[row.purpose_id];
          const name = purpose ? `${row.purpose_id} · ${purpose.name}` : row.purpose_id;
          let fields = [];
          try {
            fields = JSON.parse(row.requested_fields || "[]");
          } catch (_) {
            fields = [];
          }
          return `<div class="recent-decision">
            <span class="status ${row.result === "ALLOW" ? "granted" : "withdrawn"}">${esc(row.result)}</span>
            <div><strong>${esc(name)}</strong><small>${esc(row.consumer_id)} · ${esc((fields || []).join(", "))}</small></div>
            <code>${esc(row.request_id)}</code>
          </div>`;
        })
        .join("")
    : '<p class="empty-state">No requests yet. Open the simulator to make the first policy check.</p>';
}

function renderDecisionTrace(data) {
  const trace = data.decision_trace || [];
  $("#response-empty").hidden = true;
  $("#response-status").textContent = `${data.decision} · HTTP ${data.http_status}`;
  $("#response-status").className = `response-status ${data.decision === "ALLOW" ? "allow" : "deny"}`;
  $("#decision-trace").innerHTML = trace
    .map(
      (item) => `<li class="trace-${esc(item.status.toLowerCase())}">
        <span class="trace-state">${
          item.status === "PASS" ? "✓" : item.status === "FAIL" ? "×" : item.status === "SKIPPED" ? "–" : item.status === "RELEASED" ? "↗" : "⊘"
        }</span>
        <div><strong>${esc(item.check)}</strong><small>${esc(item.detail)}</small></div>
        <span class="trace-result">${esc(item.status)}</span>
      </li>`
    )
    .join("");
  $("#request-result").textContent = JSON.stringify(
    {
      request_id: data.request_id,
      consumer_id: data.consumer_id,
      operation: data.operation,
      requested_fields: data.requested_fields,
      decision: data.decision,
      reason_code: data.reason_code,
      payload: data.payload,
    },
    null,
    2
  );
}

function clearDecisionTrace() {
  $("#response-status").textContent = "READY";
  $("#response-status").className = "response-status idle";
  $("#response-empty").hidden = false;
  $("#decision-trace").innerHTML = "";
  $("#request-result").textContent = "Choose a purpose and send a request.";
}

function renderIntegrity(integrity) {
  if (!integrity) return;
  state.integrity = integrity;
  const intact = integrity.status === "intact";
  const dashPill = $("#dashboard-ledger-pill");
  if (dashPill) {
    dashPill.className = `server-badge ${intact ? "" : "broken"}`;
    dashPill.innerHTML = `<span class="live-dot"></span>Ledger ${intact ? "INTACT" : "BROKEN"} · ${integrity.verified_count} blocks`;
  }
  const badge = $("#integrity-badge");
  if (badge) {
    badge.className = `status ${intact ? "granted" : "withdrawn"}`;
    badge.textContent = intact ? `100% INTACT (${integrity.verified_count}/${integrity.total_count})` : "INTEGRITY BROKEN";
  }
  const details = $("#integrity-details");
  if (details) {
    details.innerHTML = `<strong>${esc(integrity.message)}</strong><br>Tip hash: <code>${esc(integrity.tip_hash || "—")}</code>`;
  }
  const ledgerCount = $("#audit-ledger-count");
  if (ledgerCount) ledgerCount.textContent = String(integrity.total_count ?? 0);
}

async function refreshAudit() {
  const [{ data: allRows }, { data: ledgerData }] = await Promise.all([
    api("/api/audit?format=json"),
    api("/api/audit/ledger"),
  ]);
  state.ledgerEvents = ledgerData.events || [];
  renderIntegrity(ledgerData.integrity);

  const activeName = $("#user-select").selectedOptions[0]?.textContent || state.userId;
  const scopeLabel = $("#audit-identity-scope");
  if (scopeLabel) scopeLabel.textContent = `Identity: ${activeName} (session-pinned)`;
  const auditUserSel = $("#audit-user");
  if (auditUserSel) {
    auditUserSel.innerHTML = `<option value="">${esc(activeName)} (active session)</option>`;
  }

  const purpose = $("#audit-purpose").value;
  const decision = $("#audit-decision").value;

  if (state.auditMode === "ledger") {
    const filteredLedger = state.ledgerEvents.filter(
      (ev) =>
        (!purpose || ev.purpose_id === purpose) &&
        (!decision || (decision === "ALLOW" && ev.event_type === "ACCESS_ALLOW") || (decision === "DENY" && ev.event_type === "ACCESS_DENY"))
    );
    const visibleCount = Math.min(auditVisibleLimit, filteredLedger.length);
    const visibleLedger = filteredLedger.slice(0, visibleCount);
    $("#audit-count").textContent = filteredLedger.length
      ? `Showing ${visibleCount} of ${filteredLedger.length} chained ledger events`
      : "No matching ledger events";
    $("#audit-load-older").hidden = visibleCount >= filteredLedger.length;
    $("#audit-list").innerHTML = visibleLedger.length
      ? visibleLedger
          .map(
            (ev) => `<article class="audit-row">
              <div class="audit-row-heading">
                <div><span class="audit-kind">Block #${esc(ev.id)} · ${esc(ev.event_type)}</span><strong>${esc(ev.user_id)}</strong></div>
                <time>${esc(ev.created_at)}</time>
              </div>
              <dl class="audit-details">
                <div><dt>Purpose / Service</dt><dd>${esc(ev.purpose_id || "SYSTEM")} ${ev.consumer_id ? `· ${esc(ev.consumer_id)}` : ""}</dd></div>
                <div><dt>Notice</dt><dd>${ev.notice_version ? `v${esc(ev.notice_version)}` : "—"}</dd></div>
                <div><dt>Prev hash</dt><dd><code>${esc(ev.prev_hash)}</code></dd></div>
                <div><dt>Row hash (SHA-256)</dt><dd><code>${esc(ev.row_hash)}</code></dd></div>
              </dl>
              <div class="audit-record-id">Ledger ID · <code>${esc(ev.event_id)}</code> · Details · <code>${esc(ev.details)}</code></div>
            </article>`
          )
          .join("")
      : '<p class="empty-state">No chained events yet.</p>';
  } else {
    const rows = allRows.filter(
      (row) => (!purpose || row.purpose_id === purpose) && (!decision || (row.record_type === "access" && row.result === decision))
    );
    const filters = new URLSearchParams();
    if (purpose) filters.set("purpose_id", purpose);
    if (decision) filters.set("decision", decision);
    const suffix = filters.toString();
    $("#export-json").href = `/api/audit?format=json${suffix ? `&${suffix}` : ""}`;
    $("#export-csv").href = `/api/audit?format=csv${suffix ? `&${suffix}` : ""}`;
    const visibleCount = Math.min(auditVisibleLimit, rows.length);
    const visibleRows = rows.slice(Math.max(0, rows.length - visibleCount)).reverse();
    $("#audit-count").textContent = rows.length ? `Showing ${visibleCount} of ${rows.length} matching events` : "No matching events";
    $("#audit-load-older").hidden = visibleCount >= rows.length;
    $("#audit-list").innerHTML = visibleRows.length
      ? visibleRows
          .map((row) => {
            const account = Array.from($("#user-select").options).find((option) => option.value === row.user_id);
            const userName = account?.textContent || row.user_id || "Unknown";
            const purposeInfo = state.purposes[row.purpose_id];
            const purposeName = purposeInfo
              ? `${row.purpose_id} · ${purposeInfo.name}`
              : row.purpose_id === "SYSTEM"
              ? "System event"
              : row.purpose_id;
            const recordName = row.record_type === "access" ? "Data request" : row.record_type === "consent" ? "Consent choice" : "System event";
            const resultLabel = row.record_type === "access" ? "Decision" : row.record_type === "consent" ? "Action" : "Event";
            const detailLabel = row.record_type === "access" ? "Reason" : row.record_type === "system" ? "Details" : "Record ID";
            const detailValue = row.record_type === "access" ? row.reason_code : row.record_type === "system" ? row.reason_code : row.record_id;
            const decisionClass = row.result === "ALLOW" || row.result === "DENY" ? `decision ${row.result}` : "audit-value";
            let fields = [];
            try { fields = JSON.parse(row.requested_fields || "[]"); } catch (_) { fields = []; }
            const context =
              row.record_type === "access"
                ? `<div class="audit-record-id">Consumer · <code>${esc(row.consumer_id)}</code> &nbsp; ${esc(row.operation)} · <code>${esc((fields || []).join(", "))}</code></div>`
                : "";
            return `<article class="audit-row">
              <div class="audit-row-heading"><div><span class="audit-kind">${esc(recordName)}</span><strong>${esc(userName)}</strong></div><time>${esc(row.created_at)}</time></div>
              <dl class="audit-details">
                <div><dt>Purpose</dt><dd>${esc(purposeName)}</dd></div>
                <div><dt>${resultLabel}</dt><dd class="${decisionClass}">${esc(row.result)}</dd></div>
                <div><dt>${detailLabel}</dt><dd>${esc(detailValue || "—")}</dd></div>
                <div><dt>Notice</dt><dd>${row.notice_version ? `Version ${esc(row.notice_version)}` : "No notice reference"}<code title="Full SHA-256 digest">${esc(row.notice_hash || "—")}</code></dd></div>
              </dl>
              ${context}
              <div class="audit-record-id">Event ID · <code>${esc(row.record_id)}</code></div>
            </article>`;
          })
          .join("")
      : '<p class="empty-state">No events yet. Grant consent or send a mock request to begin.</p>';
  }

  state.consentRows = allRows.filter((row) => row.record_type === "consent");
  $("#audit-consent-count").textContent = String(state.consentRows.length);
  state.accessRows = allRows.filter((row) => row.record_type === "access");
  updateDashboardMetrics(state.accessRows);
  renderJudgeTour();
}

async function refreshRevocations() {
  const [{ data }, actions] = await Promise.all([
    api(`/api/revocations?user_id=${encodeURIComponent(state.userId)}`),
    api(`/api/pending-actions?user_id=${encodeURIComponent(state.userId)}`),
  ]);
  const rows = data.revocations || [];
  state.revocations = rows;
  $("#revocation-list").innerHTML = rows.length
    ? rows
        .map((row) => {
          const statusCls =
            row.status === "ACKNOWLEDGED" ? "granted" : row.status === "FAILED" ? "withdrawn" : "pending";
          const actionBtn =
            row.status === "PENDING"
              ? `<button type="button" class="btn-sm" data-deliver-rev="${esc(row.revocation_id)}">Deliver to service</button>`
              : row.status === "FAILED"
              ? `<button type="button" class="btn-sm" data-retry-rev="${esc(row.revocation_id)}">Retry delivery</button>`
              : `<a class="btn-link secondary btn-sm" href="/api/privacy-receipt/${esc(row.revocation_id)}?format=html" target="_blank" rel="noreferrer">View receipt</a>`;
          const ackInfo = row.adapter_event_id ? ` · Ack: <code>${esc(row.adapter_event_id)}</code>` : "";
          const errInfo = row.last_error ? `<div class="revocation-row-error">${esc(row.last_error)}</div>` : "";
          return `<article class="revocation-row">
            <div class="revocation-row-info">
              <div><strong>${esc(row.consumer_id)}</strong> <span class="status ${statusCls}">${esc(row.status)}</span></div>
              <span class="revocation-row-meta">${esc(row.purpose_id)} · ${row.pending_actions_cancelled} queued job(s) cancelled · Attempts: ${row.attempts}${ackInfo}</span>
              <code>${esc(row.revocation_id)}</code>
              ${errInfo}
            </div>
            <time class="revocation-row-meta">${esc(row.acknowledged_at || row.delivered_at || row.created_at)}</time>
            <div class="revocation-actions">${actionBtn}</div>
          </article>`;
        })
        .join("")
    : '<p class="empty-state">No withdrawal instructions yet. Withdraw a purpose to queue one for its connected service.</p>';

  const pendingRows = actions.data.pending_actions || [];
  $("#pending-action-list").innerHTML = pendingRows.length
    ? pendingRows
        .map(
          (action) => `<article class="revocation-row">
            <div class="revocation-row-info">
              <strong>${esc(action.action_type.replaceAll("_", " "))}</strong>
              <span class="revocation-row-meta">${esc(action.consumer_id)} · ${esc(action.purpose_id)} · <span class="status ${action.status === "CANCELLED" ? "withdrawn" : "pending"}">${esc(action.status)}</span>${action.revocation_id ? ` · Linked: <code>${esc(action.revocation_id)}</code>` : ""}</span>
            </div>
            <time class="revocation-row-meta">${esc(action.cancelled_at || action.created_at)}</time>
            <code>${esc(action.action_id)}</code>
          </article>`
        )
        .join("")
    : '<p class="empty-state">No queued work for this demo user.</p>';
}

async function refreshMyPrivacy() {
  const { data } = await api(`/api/my-privacy?user_id=${encodeURIComponent(state.userId)}`);
  $("#privacy-user-pill").textContent = `${data.display_name} (${data.user_id})`;

  const banner = $("#privacy-alert-banner");
  if (data.summary.unresolved_revocations > 0) {
    banner.hidden = false;
    banner.textContent = `⚠ ${data.summary.unresolved_revocations} withdrawal instruction(s) have not yet been acknowledged by the downstream service. Deliver or retry them in Consent & revocation.`;
  } else {
    banner.hidden = true;
  }

  $("#privacy-summary-grid").innerHTML = `
    <div class="privacy-stat"><span>Active grants</span><strong>${data.summary.granted_count} / 3</strong></div>
    <div class="privacy-stat"><span>Withdrawn purposes</span><strong>${data.summary.withdrawn_count}</strong></div>
    <div class="privacy-stat"><span>Cancelled queued jobs</span><strong>${data.summary.cancelled_actions}</strong></div>
    <div class="privacy-stat"><span>Unresolved withdrawals</span><strong>${data.summary.unresolved_revocations}</strong></div>
  `;

  $("#privacy-permissions-list").innerHTML = data.permissions
    .map((p) => {
      const cls = p.granted ? "granted" : p.status_label === "Withdrawn" ? "withdrawn" : "";
      return `<div class="privacy-item">
        <div class="privacy-item-top">
          <strong>${esc(p.purpose_id)} · ${esc(p.name)}</strong>
          <span class="status ${cls}">${esc(p.status_label)}</span>
        </div>
        <small>${esc(p.description)}</small>
        <small>${p.notice_version ? `Recorded under Notice v${esc(p.notice_version)} · ${esc(p.updated_at)}` : "No decision recorded yet."}</small>
      </div>`;
    })
    .join("");

  $("#privacy-services-list").innerHTML = data.connected_services
    .map(
      (s) => `<div class="privacy-item">
        <div class="privacy-item-top">
          <strong>${esc(s.display_name)} (<code>${esc(s.consumer_id)}</code>)</strong>
          <span class="status ${s.currently_authorized ? "granted" : "withdrawn"}">${s.currently_authorized ? "Authorized" : "Blocked"}</span>
        </div>
        <small>Purpose: ${esc(s.purpose_id)} · ${esc(s.purpose_name)} · Service ${s.available ? "Online" : "Offline"}</small>
        <div class="field-tags">${s.authorized_fields.map((f) => `<span class="field-tag">${esc(f)}</span>`).join("")}</div>
        <small>Queued work: ${s.queued_work_count} · Cancelled: ${s.cancelled_work_count}</small>
      </div>`
    )
    .join("");

  const revs = data.revocations || [];
  $("#privacy-withdrawals-list").innerHTML = revs.length
    ? revs
        .map((r) => {
          const cls = r.status === "ACKNOWLEDGED" ? "granted" : r.status === "FAILED" ? "withdrawn" : "pending";
          return `<article class="revocation-row">
            <div class="revocation-row-info">
              <div><strong>${esc(r.purpose_id)} · ${esc(r.purpose_name)}</strong> <span class="status ${cls}">${esc(r.status)}</span></div>
              <span class="revocation-row-meta">Service: <code>${esc(r.consumer_id)}</code> · Cancelled jobs: ${r.pending_actions_cancelled} · Attempts: ${r.attempts}</span>
              <code>${esc(r.revocation_id)}</code>
              ${r.last_error ? `<div class="revocation-row-error">${esc(r.last_error)}</div>` : ""}
            </div>
            <time class="revocation-row-meta">${esc(r.created_at)}</time>
            <div class="revocation-actions">
              <a class="btn-link btn-sm" href="${esc(r.receipt_html_url)}" target="_blank" rel="noreferrer">Printable receipt</a>
              <a class="btn-link secondary btn-sm" href="${esc(r.receipt_json_url)}">JSON receipt</a>
            </div>
          </article>`;
        })
        .join("")
    : '<p class="empty-state">No withdrawals recorded for this identity yet.</p>';

  $("#privacy-disclaimer").textContent = data.disclaimer;
  renderJudgeTour();
}

const TOUR_STEPS = [
  {
    short: "1. Grant P1",
    title: "Step 1: Grant P1 (Event reminders) only",
    why: "Proves PS-002 purpose isolation: saying yes to P1 never unlocks P2 or P3.",
    how: "Open Consent & revocation and click Grant consent on P1.",
    view: "consent",
    done: () => {
      if (state.tourBaseline) {
        return state.consentRows.filter((r) => r.result === "grant").length > state.tourBaseline.grants;
      }
      return Object.keys(state.purposes).some((pid) => getCurrentState(pid).granted) || state.accessRows.some((r) => r.result === "ALLOW");
    },
  },
  {
    short: "2. PEP + Attack",
    title: "Step 2: Test Allowed READ & Field Overreach Attack",
    why: "Shows ConsentX's field-level edge: checks consumer, READ/WRITE, and individual fields.",
    how: "In Simulator, run Valid P1 read (ALLOW) then Field overreach student_email (DENY).",
    view: "simulator",
    done: () => {
      const allows = state.accessRows.filter((r) => r.result === "ALLOW").length;
      const denies = state.accessRows.filter((r) => r.result === "DENY").length;
      if (state.tourBaseline) {
        return allows > state.tourBaseline.allows && denies > state.tourBaseline.denies;
      }
      return allows > 0 && denies > 0;
    },
  },
  {
    short: "3. Withdraw",
    title: "Step 3: Withdraw P1 & Cancel Queued Work",
    why: "Proves withdrawal isn't just a checkbox—it cancels queued P1 jobs while leaving P2/P3 alone.",
    how: "Click Withdraw consent on P1 and watch 2 P1 reminder jobs turn CANCELLED.",
    view: "consent",
    done: () => state.tourBaseline
      ? state.revocations.length > state.tourBaseline.revocations
      : state.revocations.length > 0,
  },
  {
    short: "4. Outage/Ack",
    title: "Step 4: Simulate Outage → Fail → Retry → Acknowledge",
    why: "Proves ConsentX never fakes success when a downstream service is down.",
    how: "Toggle notification-service offline, Deliver (FAILED), restore online, and Retry (ACKNOWLEDGED).",
    view: "consent",
    done: () => {
      const acks = state.revocations.filter((r) => r.status === "ACKNOWLEDGED").length;
      return state.tourBaseline ? acks > state.tourBaseline.acks : acks > 0;
    },
  },
  {
    short: "5. My Privacy",
    title: "Step 5: Inspect My Privacy & Printable Receipt",
    why: "Gives the student clear visibility and downloadable withdrawal evidence.",
    how: "Open My Privacy and inspect Connected Services & Printable receipt.",
    view: "privacy",
    done: () => state.tourBaseline
      ? state.visitedPrivacy
      : state.visitedPrivacy && state.revocations.length > 0,
  },
  {
    short: "6. Notice v2",
    title: "Step 6: Publish Notice v2.0 (Operator Boundary)",
    why: "Proves policy changes invalidate older grants until re-confirmed under the new SHA-256.",
    how: "Open Notice versions, unlock operator mode (demo-operator-secret locally), edit text, and publish.",
    view: "notices",
    done: () => state.tourBaseline
      ? (state.noticeHistory || []).length > state.tourBaseline.notices
      : (state.noticeHistory || []).length > 1,
  },
  {
    short: "7. SHA-256",
    title: "Step 7: Verify SHA-256 Ledger & Live Diagnostics",
    why: "Proves all 12 event types are tamper-evidently chained and live checks pass.",
    how: "Open Audit & verification and click Verify audit integrity + Run live diagnostics.",
    view: "audit",
    done: () => state.verifiedIntegrityManual || state.diagnosticsRun,
  },
];

function setTourOpen(open) {
  const panel = $("#judge-tour");
  if (!panel) return;
  panel.hidden = !open;
  localStorage.setItem("consentx-tour-open", open ? "true" : "false");
}

function renderJudgeTour() {
  const grid = $("#tour-steps-grid");
  if (!grid) return;
  const doneCount = TOUR_STEPS.filter((step) => step.done()).length;
  const pill = $("#tour-progress-pill");
  if (pill) pill.textContent = `${doneCount}/${TOUR_STEPS.length}`;

  const firstIncomplete = TOUR_STEPS.findIndex((step) => !step.done());
  if (state.selectedTourStep < 0 || state.selectedTourStep >= TOUR_STEPS.length) {
    state.selectedTourStep = firstIncomplete >= 0 ? firstIncomplete : 0;
  }

  grid.innerHTML = TOUR_STEPS.map((step, idx) => {
    const isDone = step.done();
    const isCurrent = idx === state.selectedTourStep;
    return `<button type="button" class="tour-step-chip ${isDone ? "done" : ""} ${isCurrent ? "current" : ""}" data-tour-idx="${idx}">
      <small>${isDone ? "✓ Done" : "Pending"}</small>
      <span>${esc(step.short)}</span>
    </button>`;
  }).join("");

  const active = TOUR_STEPS[state.selectedTourStep];
  $("#tour-active-title").textContent = active.title;
  $("#tour-active-why").textContent = `Why it matters: ${active.why}`;
  $("#tour-active-how").textContent = `Action: ${active.how}`;
  $("#tour-jump-btn").dataset.jumpView = active.view;
}

if (localStorage.getItem("consentx-tour-open") === "false") {
  setTourOpen(false);
} else {
  setTourOpen(true);
}

function updateOperatorControls() {
  const isOperator = state.role === "operator";
  const publishButton = $("#publish-notice");
  const operatorState = $("#operator-state");
  if (publishButton) publishButton.disabled = !isOperator;
  if (operatorState) {
    if (isOperator) {
      operatorState.textContent = "Operator mode · publishing enabled for this session";
    } else if (!state.operatorConfigured) {
      operatorState.textContent = "Operator token not configured on server (set CONSENTX_OPERATOR_TOKEN to unlock publishing)";
    } else {
      operatorState.textContent = "Student mode · enter configured operator token to unlock publishing";
    }
  }
}

async function refresh() {
  state.userId = $("#user-select").value;
  const identity = await api("/api/demo-session");
  state.role = identity.data.role;
  state.operatorConfigured = Boolean(identity.data.operator_configured);
  updateOperatorControls();

  const { data } = await api(`/api/state?user_id=${encodeURIComponent(state.userId)}`);
  state.purposes = data.purposes;
  state.consents = data.consents;
  state.consumers = data.consumers || [];
  state.notice = data.active_notice;
  state.noticeHistory = data.notice_history || [data.active_notice];
  renderNotice();
  renderPurposeCards();
  renderConsumers();
  renderIntegrity(data.ledger_integrity);
  await Promise.all([refreshRevocations(), refreshMyPrivacy(), refreshAudit()]);
}

/* ==================== EVENT LISTENERS ==================== */
$("#user-select").addEventListener("change", async () => {
  try {
    await api("/api/demo-session", { user_id: $("#user-select").value });
    clearDecisionTrace();
    await refresh();
    showToast(`Switched active demo identity to ${$("#user-select").selectedOptions[0]?.textContent}`);
  } catch (error) {
    showError(error);
  }
});

$("#operator-enable")?.addEventListener("click", async () => {
  const token = $("#operator-token")?.value || "";
  try {
    await api("/api/operator-session", { token });
    state.role = "operator";
    updateOperatorControls();
    $("#notice-publish-result").textContent = "Operator access enabled for this browser session.";
    showToast("Operator publishing unlocked");
  } catch (error) {
    showError(error);
  } finally {
    if ($("#operator-token")) $("#operator-token").value = "";
  }
});

$("#request-purpose").addEventListener("change", () => { renderRequestFields(); renderSimLiveStatus(); clearDecisionTrace(); });
$("#request-consumer").addEventListener("change", updateRequestPreview);
$("#request-operation").addEventListener("change", updateRequestPreview);
$("#request-fields").addEventListener("change", updateRequestPreview);
$("#notice-text").addEventListener("input", () => { noticeEditorDirty = true; updateNoticeCharCount(); });

for (const link of document.querySelectorAll(".nav-link")) {
  link.addEventListener("click", () => activateView(link.dataset.view));
}
window.addEventListener("hashchange", () => activateView(location.hash.slice(1)));
activateView(location.hash.slice(1) || "dashboard");

for (const selector of ["#audit-user", "#audit-purpose", "#audit-decision"]) {
  $(selector).addEventListener("change", () => {
    auditVisibleLimit = 12;
    refreshAudit().catch(showError);
  });
}
$("#audit-load-older").addEventListener("click", () => {
  auditVisibleLimit += 12;
  refreshAudit().catch(showError);
});

$("#mode-timeline-btn")?.addEventListener("click", () => {
  state.auditMode = "timeline";
  $("#mode-timeline-btn").classList.add("active");
  $("#mode-ledger-btn").classList.remove("active");
  refreshAudit().catch(showError);
});
$("#mode-ledger-btn")?.addEventListener("click", () => {
  state.auditMode = "ledger";
  $("#mode-ledger-btn").classList.add("active");
  $("#mode-timeline-btn").classList.remove("active");
  refreshAudit().catch(showError);
});

$("#purpose-list").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-purpose]");
  if (!button) return;
  button.disabled = true;
  try {
    const { data } = await api("/api/consent", {
      user_id: state.userId,
      purpose_id: button.dataset.purpose,
      action: button.dataset.action,
    });
    clearDecisionTrace();
    await refresh();
    if (data.action === "withdraw" && data.revocations?.length) {
      const cancelled = data.revocations[0].pending_actions_cancelled;
      const msg = `Withdrawal recorded. New access blocked, ${cancelled} queued job(s) cancelled, and service instruction queued (PENDING).`;
      $("#withdrawal-feedback").textContent = msg;
      showToast(msg);
    } else if (data.action === "grant") {
      const msg = `Consent granted for ${data.purpose_id} under Notice v${data.notice_version}.`;
      $("#withdrawal-feedback").textContent = msg;
      showToast(msg);
    }
  } catch (error) {
    showError(error);
    button.disabled = false;
  }
});

$("#simulate-work-buttons").addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-sim-work]");
  if (!btn) return;
  try {
    await api("/api/pending-actions/simulate", { user_id: state.userId, purpose_id: btn.dataset.simWork });
    await refreshRevocations();
    await refreshMyPrivacy();
    showToast(`Queued new synthetic job for ${btn.dataset.simWork}`);
  } catch (error) {
    showError(error);
  }
});

$("#consumer-adapter-list").addEventListener("click", async (event) => {
  const btn = event.target.closest("button[data-toggle-consumer]");
  if (!btn) return;
  const cid = btn.dataset.toggleConsumer;
  const available = btn.dataset.nextAvailable === "true";
  try {
    await api(`/api/consumers/${encodeURIComponent(cid)}/availability`, { available });
    await refresh();
    showToast(`${cid} is now ${available ? "ONLINE" : "OFFLINE"}`, available ? "ok" : "error");
  } catch (error) {
    showError(error);
  }
});

$("#revocation-list").addEventListener("click", async (event) => {
  const deliverBtn = event.target.closest("button[data-deliver-rev]");
  const retryBtn = event.target.closest("button[data-retry-rev]");
  const btn = deliverBtn || retryBtn;
  if (!btn) return;
  const revId = deliverBtn ? deliverBtn.dataset.deliverRev : retryBtn.dataset.retryRev;
  const endpoint = deliverBtn ? `/api/revocations/${encodeURIComponent(revId)}/deliver` : `/api/revocations/${encodeURIComponent(revId)}/retry`;
  btn.disabled = true;
  try {
    const { data, ok } = await api(endpoint, {});
    await refresh();
    if (ok) {
      showToast(`Service acknowledged ${revId} (${data.revocation.adapter_event_id})`);
    } else {
      showToast(data.error || "Consumer unavailable — job marked FAILED", "error");
    }
  } catch (error) {
    showError(error);
    btn.disabled = false;
  }
});

document.querySelector(".preset-buttons")?.addEventListener("click", (event) => {
  const btn = event.target.closest("button[data-preset]");
  if (!btn) return;
  const preset = btn.dataset.preset;
  if (preset === "valid-p1") {
    $("#request-purpose").value = "P1";
    renderRequestFields();
    $("#request-consumer").value = "notification-service";
    $("#request-operation").value = "READ";
  } else if (preset === "field-overreach") {
    $("#request-purpose").value = "P1";
    renderRequestFields(["student_email"]);
    $("#request-consumer").value = "notification-service";
    $("#request-operation").value = "READ";
  } else if (preset === "wrong-consumer") {
    $("#request-purpose").value = "P1";
    renderRequestFields();
    $("#request-consumer").value = "analytics-service";
    $("#request-operation").value = "READ";
  } else if (preset === "write-op") {
    $("#request-purpose").value = "P1";
    renderRequestFields();
    $("#request-consumer").value = "notification-service";
    $("#request-operation").value = "WRITE";
  }
  updateRequestPreview();
  $("#request-data").click();
});

$("#request-data").addEventListener("click", async () => {
  const purpose_id = $("#request-purpose").value;
  try {
    const consumer_id = $("#request-consumer").value;
    const operation = $("#request-operation").value;
    const requested_fields = [...document.querySelectorAll("#request-fields input:checked")].map((input) => input.value);
    const { data, status } = await api("/api/data-access", {
      user_id: state.userId,
      purpose_id,
      consumer_id,
      operation,
      requested_fields,
    });
    renderDecisionTrace({ ...data, http_status: status });
    await refreshAudit();
  } catch (error) {
    showError(error);
  }
});

$("#publish-notice").addEventListener("click", async () => {
  const text = $("#notice-text").value.trim();
  if (!text) {
    $("#notice-publish-result").textContent = "Enter notice text before publishing.";
    return;
  }
  if (text === state.notice?.text) {
    $("#notice-publish-result").textContent = "Change the notice text before publishing a new version.";
    return;
  }
  const latestNumber = Math.max(1, ...state.noticeHistory.map((item) => Number.parseFloat(item.version)).filter(Number.isFinite));
  const version = `${Math.floor(latestNumber) + 1}.0`;
  const button = $("#publish-notice");
  button.disabled = true;
  try {
    const { data } = await api("/api/notices", { version, text });
    $("#notice-publish-result").textContent = `Published v${data.version}. Existing grants now require fresh confirmation. SHA-256: ${data.sha256}`;
    noticeEditorDirty = false;
    await refresh();
    showToast(`Published Notice v${data.version}`);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = state.role !== "operator";
  }
});

$("#verify-integrity-btn")?.addEventListener("click", async () => {
  try {
    const { data } = await api("/api/audit/verify");
    state.verifiedIntegrityManual = true;
    renderIntegrity(data);
    renderJudgeTour();
    showToast(data.message, data.status === "intact" ? "ok" : "error");
  } catch (error) {
    showError(error);
  }
});

$("#run-diagnostics-btn")?.addEventListener("click", async () => {
  try {
    const { data } = await api("/api/diagnostics");
    state.diagnosticsRun = true;
    renderJudgeTour();
    const rowsHtml = data.checks
      .map(
        (c) => `<tr>
          <td><code>${esc(c.id)}</code></td>
          <td><strong>${esc(c.name)}</strong></td>
          <td>${esc(c.expected)}</td>
          <td>${esc(c.observed)}</td>
          <td><span class="status ${c.passed ? "granted" : "withdrawn"}">${c.passed ? "PASS" : "FAIL"}</span></td>
        </tr>`
      )
      .join("");
    $("#diagnostics-results").innerHTML = `
      <p class="muted" style="margin: 0 0 10px;"><strong>${data.passed}/${data.total} live checks passed</strong> · Checked at ${esc(data.checked_at)}</p>
      <table class="diag-table">
        <thead><tr><th>ID</th><th>Check</th><th>Expected</th><th>Observed</th><th>Status</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>`;
    showToast(`Live diagnostics: ${data.passed}/${data.total} passed`, data.all_passed ? "ok" : "error");
  } catch (error) {
    showError(error);
  }
});

function showError(error) {
  const msg = error?.message || String(error);
  showToast(msg, "error");
  const target = $("#notice-publish-result");
  if (target && $("#view-notices").classList.contains("active")) target.textContent = msg;
  const result = $("#request-result");
  if (result && $("#view-simulator").classList.contains("active")) result.textContent = msg;
}

$("#tour-toggle")?.addEventListener("click", () => {
  const panel = $("#judge-tour");
  if (panel) setTourOpen(panel.hidden);
});
$("#tour-hide-btn")?.addEventListener("click", () => setTourOpen(false));
$("#tour-steps-grid")?.addEventListener("click", (event) => {
  const chip = event.target.closest("button[data-tour-idx]");
  if (!chip) return;
  state.selectedTourStep = Number(chip.dataset.tourIdx) || 0;
  renderJudgeTour();
});
$("#tour-next-btn")?.addEventListener("click", () => {
  const nextIdx = TOUR_STEPS.findIndex((step) => !step.done());
  state.selectedTourStep = nextIdx >= 0 ? nextIdx : 0;
  renderJudgeTour();
  const targetView = TOUR_STEPS[state.selectedTourStep].view;
  location.hash = targetView;
  activateView(targetView);
});
$("#tour-restart-btn")?.addEventListener("click", () => {
  state.tourBaseline = {
    grants: state.consentRows.filter((r) => r.result === "grant").length,
    allows: state.accessRows.filter((r) => r.result === "ALLOW").length,
    denies: state.accessRows.filter((r) => r.result === "DENY").length,
    revocations: state.revocations.length,
    acks: state.revocations.filter((r) => r.status === "ACKNOWLEDGED").length,
    notices: (state.noticeHistory || []).length,
  };
  localStorage.setItem("consentx-tour-baseline", JSON.stringify(state.tourBaseline));
  state.visitedPrivacy = false;
  state.verifiedIntegrityManual = false;
  state.diagnosticsRun = false;
  state.selectedTourStep = 0;
  clearDecisionTrace();
  renderJudgeTour();
  location.hash = "consent";
  activateView("consent");
  showToast("Tour restarted from 0/7 (existing database records preserved)");
});
$("#tour-reset-btn")?.addEventListener("click", async () => {
  if (!window.confirm("Wipe all synthetic demo data and restore Notice v1.0? (Use 'Restart tour' instead if you want to keep your data.)")) return;
  const btn = $("#tour-reset-btn");
  btn.disabled = true;
  try {
    await api("/api/demo-reset", {});
    state.tourBaseline = null;
    localStorage.removeItem("consentx-tour-baseline");
    state.visitedPrivacy = false;
    state.verifiedIntegrityManual = false;
    state.diagnosticsRun = false;
    state.selectedTourStep = 0;
    noticeEditorDirty = false;
    $("#user-select").value = "student-001";
    $("#withdrawal-feedback").textContent = "";
    $("#notice-publish-result").textContent = "The server calculates and stores the SHA-256 digest.";
    $("#diagnostics-results").innerHTML = '<p class="empty-state">Click <strong>Run live diagnostics</strong> to verify live backend guarantees.</p>';
    clearDecisionTrace();
    await refresh();
    location.hash = "dashboard";
    activateView("dashboard");
    showToast("All demo data reset to clean Notice v1.0 baseline (0/7)");
  } catch (error) {
    showError(error);
  } finally {
    btn.disabled = false;
  }
});
document.addEventListener("click", (event) => {
  const jump = event.target.closest("[data-jump-view]");
  if (!jump) return;
  const target = jump.dataset.jumpView;
  if (target) {
    location.hash = target;
    activateView(target);
  }
});

$("#notice-text").value = "";
refresh().catch(showError);
