const $ = (selector) => document.querySelector(selector);
const state = { userId: $("#user-select").value, purposes: {}, consents: {}, notice: null, noticeHistory: [] };
let auditVisibleLimit = 12;
let noticeEditorDirty = false;
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[char]));

async function api(path, body) {
  const options = body ? { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) } : {};
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok && !data.decision) throw new Error(data.error || data.reason_code || `HTTP ${response.status}`);
  return { data, status:response.status };
}

function activateView(viewName) {
  const known = ["dashboard", "consent", "simulator", "notices", "audit"];
  const active = known.includes(viewName) ? viewName : "dashboard";
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === `view-${active}`));
  document.querySelectorAll(".nav-link").forEach(link => {
    const selected = link.dataset.view === active;
    link.classList.toggle("active", selected);
    if (selected) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
  });
  $("#current-section").textContent = ({dashboard:"Dashboard",consent:"Consent management",simulator:"Data access simulator",notices:"Notice versions",audit:"Audit & tests"})[active];
}

function getCurrentState(purposeId) {
  const event = state.consents[purposeId];
  const currentNotice = state.notice;
  const matchesNotice = event && currentNotice && event.notice_version === currentNotice.version && event.notice_hash === currentNotice.sha256;
  const granted = event?.action === "grant" && matchesNotice;
  const label = granted ? "Granted" : event?.action === "withdraw" ? "Withdrawn" : event?.action === "grant" ? "Re-consent needed" : "Not granted";
  return { event, granted:Boolean(granted), label, matchesNotice:Boolean(matchesNotice) };
}

function renderPurposeCards() {
  const entries = Object.entries(state.purposes);
  $("#purpose-list").innerHTML = entries.map(([id, purpose]) => {
    const current = getCurrentState(id);
    const className = current.granted ? "granted" : current.event?.action === "withdraw" ? "withdrawn" : "";
    const action = current.granted ? "withdraw" : "grant";
    const button = current.granted ? "Withdraw consent" : current.event?.action === "grant" ? "Confirm under current notice" : "Grant consent";
    return `<article class="purpose-card"><div class="purpose-card-top"><span class="purpose-id">${esc(id)}</span><span class="status ${className}">${esc(current.label)}</span></div><h2>${esc(purpose.name)}</h2><p>${esc(purpose.description)}</p><div class="purpose-data"><span>ONLY RELEASES</span><strong>${esc(Object.keys(purpose.payload).join(" · "))}</strong></div><button data-purpose="${esc(id)}" data-action="${action}">${button}</button></article>`;
  }).join("");
  $("#dashboard-purposes").innerHTML = entries.map(([id, purpose]) => {
    const current = getCurrentState(id);
    return `<div class="dashboard-purpose"><span class="purpose-id">${esc(id)}</span><span class="purpose-name">${esc(purpose.name)}</span><span class="status ${current.granted ? "granted" : current.event?.action === "withdraw" ? "withdrawn" : ""}">${esc(current.label)}</span></div>`;
  }).join("");
  const selectedRequestPurpose = $("#request-purpose").value;
  $("#request-purpose").innerHTML = entries.map(([id, purpose]) => `<option value="${esc(id)}">${esc(id)} · ${esc(purpose.name)}</option>`).join("");
  if (state.purposes[selectedRequestPurpose]) $("#request-purpose").value = selectedRequestPurpose;
  $("#consent-notice-current").textContent = state.notice ? `Current notice v${state.notice.version}` : "";
  updateRequestPreview();
  updateDashboardMetrics();
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
  $("#notice-history").innerHTML = versions.map((version, index) => `
    <article class="notice-version ${index === 0 ? "current" : ""}">
      <div class="notice-version-heading"><strong>Version ${esc(version.version)}</strong>${index === 0 ? '<span class="status granted">CURRENT</span>' : ""}<time>${esc(version.created_at)}</time></div>
      <p>${esc(version.text)}</p><div class="version-digest"><span>SHA-256</span><code title="${esc(version.sha256)}">${esc(version.sha256)}</code></div>
    </article>`).join("");
}

function updateNoticeCharCount() {
  const editor = $("#notice-text");
  $("#notice-char-count").textContent = `${editor.value.length} / 4,000 characters`;
}

function updateRequestPreview() {
  const purposeId = $("#request-purpose").value || Object.keys(state.purposes)[0] || "P1";
  $("#request-json").textContent = JSON.stringify({endpoint:"/api/data-access",user_id:state.userId,purpose_id:purposeId}, null, 2);
}

function updateDashboardMetrics(accessRows) {
  const consentCount = Object.keys(state.purposes).filter(id => getCurrentState(id).granted).length;
  $("#metric-grants").textContent = String(consentCount);
  $("#metric-grants-caption").textContent = `For ${$("#user-select").selectedOptions[0]?.textContent || "selected account"}`;
  if (!accessRows) return;
  $("#metric-requests").textContent = String(accessRows.length);
  $("#metric-denied").textContent = String(accessRows.filter(row => row.result === "DENY").length);
  $("#audit-access-count").textContent = String(accessRows.length);
}

function renderDecisionTrace(data) {
  const trace = data.decision_trace || [];
  $("#response-empty").hidden = true;
  $("#response-status").textContent = `${data.decision} · HTTP ${data.http_status}`;
  $("#response-status").className = `response-status ${data.decision === "ALLOW" ? "allow" : "deny"}`;
  $("#decision-trace").innerHTML = trace.map(item => `
    <li class="trace-${esc(item.status.toLowerCase())}"><span class="trace-state">${item.status === "PASS" ? "✓" : item.status === "FAIL" ? "×" : item.status === "SKIPPED" ? "–" : item.status === "RELEASED" ? "↗" : "⊘"}</span>
      <div><strong>${esc(item.check)}</strong><small>${esc(item.detail)}</small></div><span class="trace-result">${esc(item.status)}</span></li>`).join("");
  $("#request-result").textContent = JSON.stringify({request_id:data.request_id,decision:data.decision,reason_code:data.reason_code,payload:data.payload}, null, 2);
}

function clearDecisionTrace() {
  $("#response-status").textContent = "READY";
  $("#response-status").className = "response-status idle";
  $("#response-empty").hidden = false;
  $("#decision-trace").innerHTML = "";
  $("#request-result").textContent = "Choose a purpose and send a request.";
}

async function refreshAudit() {
  const {data:allRows} = await api("/api/audit?format=json");
  const user = $("#audit-user").value;
  const purpose = $("#audit-purpose").value;
  const decision = $("#audit-decision").value;
  const rows = allRows.filter(row => (!user || row.user_id === user)
    && (!purpose || row.purpose_id === purpose)
    && (!decision || (row.record_type === "access" && row.result === decision)));
  const filters = new URLSearchParams();
  if (user) filters.set("user_id", user);
  if (purpose) filters.set("purpose_id", purpose);
  if (decision) filters.set("decision", decision);
  const suffix = filters.toString();
  $("#export-json").href = `/api/audit?format=json${suffix ? `&${suffix}` : ""}`;
  $("#export-csv").href = `/api/audit?format=csv${suffix ? `&${suffix}` : ""}`;
  const visibleCount = Math.min(auditVisibleLimit, rows.length);
  const visibleRows = rows.slice(Math.max(0, rows.length - visibleCount)).reverse();
  $("#audit-count").textContent = rows.length ? `Showing ${visibleCount} of ${rows.length} matching events` : "No matching events";
  $("#audit-load-older").hidden = visibleCount >= rows.length;
  $("#audit-consent-count").textContent = String(allRows.filter(row => row.record_type === "consent").length);
  updateDashboardMetrics(allRows.filter(row => row.record_type === "access"));
  $("#audit-list").innerHTML = visibleRows.length ? visibleRows.map(row => {
    const account = Array.from($("#user-select").options).find(option => option.value === row.user_id);
    const userName = account?.textContent || row.user_id || "Unknown";
    const purposeInfo = state.purposes[row.purpose_id];
    const purposeName = purposeInfo ? `${row.purpose_id} · ${purposeInfo.name}` : row.purpose_id === "SYSTEM" ? "System event" : row.purpose_id;
    const recordName = row.record_type === "access" ? "Data request" : row.record_type === "consent" ? "Consent choice" : "System event";
    const resultLabel = row.record_type === "access" ? "Decision" : row.record_type === "consent" ? "Action" : "Event";
    const detailLabel = row.record_type === "access" ? "Reason" : row.record_type === "system" ? "Details" : "Record ID";
    const detailValue = row.record_type === "access" ? row.reason_code : row.record_type === "system" ? row.reason_code : row.record_id;
    const decisionClass = row.result === "ALLOW" || row.result === "DENY" ? `decision ${row.result}` : "audit-value";
    return `<article class="audit-row"><div class="audit-row-heading"><div><span class="audit-kind">${esc(recordName)}</span><strong>${esc(userName)}</strong></div><time>${esc(row.created_at)}</time></div><dl class="audit-details"><div><dt>Purpose</dt><dd>${esc(purposeName)}</dd></div><div><dt>${resultLabel}</dt><dd class="${decisionClass}">${esc(row.result)}</dd></div><div><dt>${detailLabel}</dt><dd>${esc(detailValue || "—")}</dd></div><div><dt>Notice</dt><dd>${row.notice_version ? `Version ${esc(row.notice_version)}` : "No notice reference"}<code title="Full SHA-256 digest">${esc(row.notice_hash || "—")}</code></dd></div></dl><div class="audit-record-id">Event ID · <code>${esc(row.record_id)}</code></div></article>`;
  }).join("") : '<p class="empty-state">No events yet. Grant consent or send a mock request to begin.</p>';
}

async function refresh() {
  state.userId = $("#user-select").value;
  const {data} = await api(`/api/state?user_id=${encodeURIComponent(state.userId)}`);
  state.purposes = data.purposes;
  state.consents = data.consents;
  state.notice = data.active_notice;
  state.noticeHistory = data.notice_history || [data.active_notice];
  renderNotice();
  renderPurposeCards();
  await refreshAudit();
}

$("#user-select").addEventListener("change", () => { clearDecisionTrace(); refresh().catch(showError); });
$("#request-purpose").addEventListener("change", () => { updateRequestPreview(); clearDecisionTrace(); });
$("#notice-text").addEventListener("input", () => { noticeEditorDirty = true; updateNoticeCharCount(); });
for (const link of document.querySelectorAll(".nav-link")) link.addEventListener("click", () => activateView(link.dataset.view));
window.addEventListener("hashchange", () => activateView(location.hash.slice(1)));
activateView(location.hash.slice(1) || "dashboard");

for (const selector of ["#audit-user", "#audit-purpose", "#audit-decision"]) {
  $(selector).addEventListener("change", () => { auditVisibleLimit = 12; refreshAudit().catch(showError); });
}
$("#audit-load-older").addEventListener("click", () => { auditVisibleLimit += 12; refreshAudit().catch(showError); });
$("#purpose-list").addEventListener("click", async event => {
  const button = event.target.closest("button[data-purpose]");
  if (!button) return;
  button.disabled = true;
  try { await api("/api/consent", {user_id:state.userId,purpose_id:button.dataset.purpose,action:button.dataset.action}); clearDecisionTrace(); await refresh(); }
  catch (error) { showError(error); button.disabled = false; }
});
$("#request-data").addEventListener("click", async () => {
  const purpose_id = $("#request-purpose").value;
  try {
    const {data,status} = await api("/api/data-access", {user_id:state.userId,purpose_id});
    renderDecisionTrace({...data,http_status:status});
    await refreshAudit();
  } catch (error) { showError(error); }
});
$("#publish-notice").addEventListener("click", async () => {
  const text = $("#notice-text").value.trim();
  if (!text) { $("#notice-publish-result").textContent = "Enter notice text before publishing."; return; }
  if (text === state.notice?.text) { $("#notice-publish-result").textContent = "Change the notice text before publishing a new version."; return; }
  const latestNumber = Math.max(1, ...state.noticeHistory.map(item => Number.parseFloat(item.version)).filter(Number.isFinite));
  const version = `${Math.floor(latestNumber) + 1}.0`;
  const button = $("#publish-notice");
  button.disabled = true;
  try {
    const {data} = await api("/api/notices", {version,text});
    $("#notice-publish-result").textContent = `Published v${data.version}. Existing grants now require fresh confirmation. SHA-256: ${data.sha256}`;
    noticeEditorDirty = false;
    await refresh();
  } catch (error) { showError(error); }
  finally { button.disabled = false; }
});

function showError(error) {
  const target = $("#notice-publish-result");
  if (target) target.textContent = error.message;
  const result = $("#request-result");
  if (result) result.textContent = error.message;
}

$("#notice-text").value = "";
refresh().catch(showError);
