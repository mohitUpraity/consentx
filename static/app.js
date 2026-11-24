const $ = (s) => document.querySelector(s);
const state = { userId: $("#user-select").value, purposes: {} };
const esc = (s) => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));

async function api(path, body) {
  const opts = body ? { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body) } : {};
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok && !data.decision) throw new Error(data.error || data.reason_code || `HTTP ${res.status}`);
  return { data, status:res.status };
}

async function refresh() {
  state.userId = $("#user-select").value;
  const {data} = await api(`/api/state?user_id=${encodeURIComponent(state.userId)}`);
  state.purposes = data.purposes;
  $("#notice-version").textContent = `Version ${data.active_notice.version}`;
  $("#notice-text").textContent = data.active_notice.text;
  $("#notice-hash").textContent = `SHA-256 ${data.active_notice.sha256}`;
  $("#notice-pill").textContent = `Notice v${data.active_notice.version}`;
  $("#purpose-list").innerHTML = Object.entries(data.purposes).map(([id,p]) => {
    const c = data.consents[id];
    const current = c && c.notice_version === data.active_notice.version && c.notice_hash === data.active_notice.sha256;
    const granted = c?.action === "grant" && current;
    const label = granted ? "Granted" : (c?.action === "withdraw" ? "Withdrawn" : (c?.action === "grant" ? "Re-consent needed" : "Not granted"));
    const cls = granted ? "granted" : (c?.action === "withdraw" ? "withdrawn" : "");
    return `<article class="purpose"><div class="purpose-top"><span class="purpose-id">${id}</span><span class="status ${cls}">${label}</span></div><h3>${esc(p.name)}</h3><p>${esc(p.description)}</p><button data-purpose="${id}" data-action="${granted ? "withdraw" : "grant"}">${granted ? "Withdraw consent" : "Grant consent"}</button></article>`;
  }).join("");
  $("#request-purpose").innerHTML = Object.entries(data.purposes).map(([id,p]) => `<option value="${id}">${id} · ${esc(p.name)}</option>`).join("");
  await refreshAudit();
}

async function refreshAudit() {
  const filters = new URLSearchParams();
  for (const [key, selector] of [["user_id", "#audit-user"], ["purpose_id", "#audit-purpose"], ["decision", "#audit-decision"]]) {
    const value = $(selector)?.value; if (value) filters.set(key, value);
  }
  const suffix = filters.toString();
  const {data} = await api(`/api/audit?format=json${suffix ? `&${suffix}` : ""}`);
  const jsonExport = $("#export-json");
  const csvExport = $("#export-csv");
  if (jsonExport) jsonExport.href = `/api/audit?format=json${suffix ? `&${suffix}` : ""}`;
  if (csvExport) csvExport.href = `/api/audit?format=csv${suffix ? `&${suffix}` : ""}`;
  const rows = data.slice(-12).reverse();
  const auditList = $("#audit-list");
  if (auditList) {
    auditList.innerHTML = rows.length ? rows.map(r => {
      const userOption = Array.from($("#user-select").options).find(option => option.value === r.user_id);
      const userName = userOption?.textContent || r.user_id || "Unknown";
      const purpose = state.purposes[r.purpose_id];
      const purposeName = purpose ? `${r.purpose_id} · ${purpose.name}` : (r.purpose_id === "SYSTEM" ? "System event" : r.purpose_id);
      const eventName = r.record_type === "access" ? "Data request" : r.record_type === "consent" ? "Consent choice" : "System event";
      const eventLabel = r.record_type === "access" ? "Decision" : r.record_type === "consent" ? "Action" : "Event";
      const detailLabel = r.record_type === "access" ? "Reason" : r.record_type === "system" ? "Details" : "Record";
      const detailValue = r.record_type === "access" ? r.reason_code : r.record_type === "system" ? r.reason_code : r.record_id;
      const decisionClass = r.result === "ALLOW" || r.result === "DENY" ? `decision ${r.result}` : "audit-value";
      const noticeVersion = r.notice_version ? `Version ${r.notice_version}` : "No notice reference";
      const noticeHash = r.notice_hash || "—";
      return `<article class="audit-row">
        <div class="audit-row-heading"><div><span class="audit-kind">${esc(eventName)}</span><strong>${esc(userName)}</strong></div><time datetime="${esc(r.created_at)}">${esc(r.created_at)}</time></div>
        <dl class="audit-details">
          <div><dt>Purpose</dt><dd>${esc(purposeName)}</dd></div>
          <div><dt>${eventLabel}</dt><dd class="${decisionClass}">${esc(r.result)}</dd></div>
          <div><dt>${detailLabel}</dt><dd>${esc(detailValue || "—")}</dd></div>
          <div><dt>Notice</dt><dd>${esc(noticeVersion)}<code title="Full SHA-256 hash">${esc(noticeHash)}</code></dd></div>
        </dl>
        <div class="audit-record-id">Event ID · <code>${esc(r.record_id)}</code></div>
      </article>`;
    }).join("") : `<p class="muted">No events yet. Grant consent or send a mock request to begin.</p>`;
  }
}

$("#user-select").addEventListener("change", refresh);
for (const selector of ["#audit-user", "#audit-purpose", "#audit-decision"]) {
  $(selector)?.addEventListener("change", refreshAudit);
}
$("#purpose-list").addEventListener("click", async e => {
  const b = e.target.closest("button[data-purpose]"); if (!b) return;
  b.disabled = true;
  try { await api("/api/consent", {user_id:state.userId,purpose_id:b.dataset.purpose,action:b.dataset.action}); await refresh(); }
  catch(err) { alert(err.message); b.disabled = false; }
});
$("#request-data").addEventListener("click", async () => {
  const purpose_id = $("#request-purpose").value;
  try { const {data,status} = await api("/api/data-access", {user_id:state.userId,purpose_id}); $("#request-result").textContent = JSON.stringify({...data,http_status:status},null,2); await refreshAudit(); }
  catch(err) { $("#request-result").textContent = err.message; }
});
$("#publish-notice").addEventListener("click", async () => {
  const text = "CampusPulse notice v2: updated event-data purposes. Review the current notice and confirm each purpose again before data is shared.";
  try { const {data} = await api("/api/notices", {version:"2.0",text}); $("#request-result").textContent = `Published notice v2 · SHA-256 ${data.sha256}`; await refresh(); }
  catch(err) { $("#request-result").textContent = err.message; }
});
refresh().catch(e => { $("#request-result").textContent = e.message; });
