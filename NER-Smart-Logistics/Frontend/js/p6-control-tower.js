/**
 * PRAVAH — P6 Control Tower & Incident Management Controller
 * 100% Dynamic Real-Time Field Incident Verification & Alert Severity Engine
 */

const P6ControlTower = {
  currentFilter: "ALL",

  init() {
    this.renderOverviewStats();
    this.renderIncidentsTable();
    this.renderImdBulletins();
    this.renderNotifications();
    this.startLiveAlertTracking();
    this.bindIncidentForm();
    this.bindAlertForm();
  },

  startLiveAlertTracking() {
    if (!this.imdRefreshTimer) {
      this.imdRefreshTimer = setInterval(() => {
        this.renderOverviewStats();
        this.renderImdBulletins();
        this.renderNotifications();
      }, 60000);
    }
    if (this.alertSocket && (this.alertSocket.readyState === WebSocket.OPEN || this.alertSocket.readyState === WebSocket.CONNECTING)) return;
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socketUrl = `${protocol}//${window.location.host}/ws/alerts`;
    try {
      this.alertSocket = new WebSocket(socketUrl);
      this.alertSocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type !== "imd_cap_alert") return;
          const alert = message.alert || {};
          this.renderOverviewStats();
          this.renderImdBulletins();
          this.renderNotifications();
          App.showToast(`New official IMD warning: ${alert.headline || alert.event || "CAP alert"}`, "warning");
        } catch (_) {
          // Ignore malformed websocket messages; periodic live polling remains active.
        }
      };
      this.alertSocket.onclose = () => {
        this.alertSocket = null;
        setTimeout(() => this.startLiveAlertTracking(), 10000);
      };
    } catch (_) {
      // The 60-second official-feed refresh continues if WebSocket is unavailable.
    }
  },

  async renderImdBulletins() {
    const container = document.getElementById("imdBulletinList");
    if (!container) return;
    container.innerHTML = `<div class="p6-bulletin"><div style="color:var(--text-muted);">Loading official IMD CAP bulletins…</div></div>`;
    try {
      const payload = await PravahAPI.getImdAlerts();
      const alerts = Array.isArray(payload.alerts) ? payload.alerts : [];
      if (!alerts.length) {
        container.innerHTML = `<div class="p6-bulletin"><div style="color:var(--text-muted);">No active official IMD CAP warnings.</div></div>`;
        return;
      }
      container.innerHTML = alerts.map((alert) => {
        const level = String(alert.risk_level || "LOW").toUpperCase();
        const tone = level === "CRITICAL" || level === "HIGH" ? "danger" : "warning";
        const icon = tone === "danger" ? "🚨" : "⚠️";
        const title = this.escapeHtml(alert.headline || alert.event || "IMD weather warning");
        const area = this.escapeHtml(alert.area || "Affected area not specified");
        const description = this.escapeHtml(alert.description || alert.instruction || "Official CAP warning received.");
        return `<div class="p6-bulletin p6-bulletin-${tone}">
          <div class="p6-bulletin-meta"><b style="color:var(--status-${tone});">${icon} ${title}</b><span style="font-size:10px;color:var(--text-muted);">IMD WIS2 · ${area}</span></div>
          <div style="color:var(--text-primary);line-height:1.4;">${description}</div>
        </div>`;
      }).join("");
    } catch (error) {
      container.innerHTML = `<div class="p6-bulletin"><div style="color:var(--text-muted);">Official IMD CAP feed is currently unavailable.</div></div>`;
    }
  },

  escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
    }[char]));
  },

  updateNotificationBadge(count) {
    const badge = document.getElementById("notificationBadgeCount");
    const bell = document.getElementById("btnNotificationBell");
    const isAvailable = Number.isFinite(count);
    const alertCount = isAvailable ? Math.max(0, Math.floor(count)) : 0;

    if (badge) {
      badge.textContent = String(alertCount);
      badge.hidden = !isAvailable || alertCount === 0;
    }
    if (bell) {
      const label = !isAvailable
        ? "Emergency alerts and notifications"
        : alertCount === 0
          ? "No active emergency alerts"
          : `${alertCount} active emergency alert${alertCount === 1 ? "" : "s"}`;
      bell.title = label;
      bell.setAttribute("aria-label", label);
    }
  },

  async renderNotifications() {
    const container = document.getElementById("notificationsContent");
    if (!container) return;
    try {
      const alerts = await PravahAPI.getControlTowerAlerts();
      if (!Array.isArray(alerts) || !alerts.length) {
        this.updateNotificationBadge(0);
        container.innerHTML = "<div>No active control-tower or official IMD alerts.</div>";
        return;
      }
      this.updateNotificationBadge(alerts.length);
      container.innerHTML = alerts.map((alert) => {
        const level = String(alert.severity || "LOW").toUpperCase();
        const tone = level === "CRITICAL" || level === "HIGH" ? "danger" : "warning";
        return `<div style="background:var(--status-${tone}-light);border:1px solid var(--status-${tone}-border);padding:12px;border-radius:8px;">
          <div style="display:flex;justify-content:space-between;gap:10px;"><b style="color:var(--status-${tone});">${this.escapeHtml(alert.title || "Control-tower warning")}</b><span style="font-size:10px;color:var(--text-muted);">${this.escapeHtml(alert.source || "P6")}</span></div>
          <p style="font-size:12px;color:var(--text-primary);margin-top:4px;">Action: ${this.escapeHtml(alert.recommended_action || "MONITOR")}</p>
        </div>`;
      }).join("");
    } catch (error) {
      this.updateNotificationBadge(null);
      container.innerHTML = "<div>Live control-tower alerts are currently unavailable.</div>";
    }
  },

  async renderOverviewStats() {
    let data = null;
    try {
      data = await PravahAPI.getControlTowerOverview();
    } catch (e) {
      // Control Tower API unavailable
    }

    const openEl = document.getElementById("kpiOpenIncidents");
    const alertsEl = document.getElementById("kpiActiveAlerts");
    const criticalEl = document.getElementById("kpiCriticalAtRisk");
    const imdEl = document.getElementById("kpiImdAlerts");

    if (openEl) openEl.textContent = data ? (data.open_incidents ?? 0) : "—";
    if (alertsEl) alertsEl.textContent = data ? (data.active_alerts ?? 0) : "—";
    if (criticalEl) criticalEl.textContent = data ? (data.shipments_monitored ?? 0) : "—";
    if (imdEl) imdEl.textContent = data ? (data.imd_alert_count ?? 0) : "—";

    // Master Overview Dashboard KPIs
    const ovActive = document.getElementById("kpiOverviewActiveShipments");
    const ovIncidents = document.getElementById("kpiOverviewOpenIncidents");
    const ovHighRisk = document.getElementById("kpiOverviewHighRiskCorridors");
    const ovRunway = document.getElementById("kpiOverviewRunway");
    const ovHealth = document.getElementById("kpiOverviewHealth");

    if (ovActive) ovActive.textContent = data ? (data.shipments_monitored ?? 0) : "—";
    if (ovIncidents) ovIncidents.textContent = data ? (data.open_incidents ?? 0) : "—";
    if (ovHighRisk) ovHighRisk.textContent = data ? (data.active_alerts ?? 0) : "—";
    if (ovRunway) ovRunway.textContent = "—";
    if (ovHealth) {
      const health = await PravahAPI.checkHealth();
      const liveCount = Object.values(health).filter(Boolean).length;
      ovHealth.textContent = `${liveCount} / ${Object.keys(health).length} Live`;
    }
  },

  filterIncidents(type) {
    this.currentFilter = type;
    const group = document.getElementById("incidentFilterGroup");
    if (group) {
      group.querySelectorAll(".pill-btn").forEach(b => {
        const text = b.textContent.toUpperCase();
        if ((type === 'ALL' && text.includes('ALL')) ||
            (type === 'LANDSLIDE' && text.includes('LANDSLIDE')) ||
            (type === 'FLOOD' && text.includes('FLOOD')) ||
            (type === 'VERIFIED' && text.includes('VERIFIED'))) {
          b.classList.add("active");
        } else {
          b.classList.remove("active");
        }
      });
    }
    this.renderIncidentsTable();
  },

  async renderIncidentsTable() {
    const tbody = document.getElementById("incidentsTableBody");
    if (!tbody) return;

    let incidents = null;
    try {
      incidents = await PravahAPI.getIncidents();
    } catch (e) {
      // API error
    }

    if (!Array.isArray(incidents)) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:16px;color:var(--text-muted);">
            Unable to connect to live P6 incident service.
          </td>
        </tr>
      `;
      return;
    }

    this.incidentsList = incidents;

    // Filter
    let filtered = incidents;
    if (this.currentFilter === "LANDSLIDE") {
      filtered = incidents.filter(i => (i.incident_type || "").toUpperCase() === "LANDSLIDE");
    } else if (this.currentFilter === "FLOOD") {
      filtered = incidents.filter(i => (i.incident_type || "").toUpperCase() === "FLOOD");
    } else if (this.currentFilter === "VERIFIED") {
      filtered = incidents.filter(i => (i.status || "").toUpperCase() === "VERIFIED");
    }

    if (filtered.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:16px;color:var(--text-muted);">
            No incident reports matching filter "${this.currentFilter}".
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = filtered.map(inc => {
      let badgeClass = "warning";
      if (inc.status === "VERIFIED") badgeClass = "safe";
      if (inc.status === "RESOLVED") badgeClass = "info";

      const typeUpper = (inc.incident_type || "").toUpperCase();
      const typeEmoji = typeUpper === "LANDSLIDE" ? "⛰️" : (typeUpper === "FLOOD" ? "🌊" : (typeUpper === "ROAD_BLOCKED" ? "⛔" : "💥"));
      const lat = Number(inc.latitude);
      const lng = Number(inc.longitude);
      const coordsText = (Number.isFinite(lat) && Number.isFinite(lng))
        ? `(${lat.toFixed(2)}°N, ${lng.toFixed(2)}°E)`
        : "";

      const photoHtml = inc.image_url
        ? `<img src="${inc.image_url}" class="incident-thumb" alt="Evidence" onclick="P6ControlTower.previewPhoto('${inc.image_url}')" title="Click to inspect full photo" />`
        : `<span style="font-size:10.5px;color:var(--text-muted);font-style:italic;">No photo</span>`;

      return `
        <tr>
          <td><b>${inc.incident_id || "—"}</b></td>
          <td><b>${typeEmoji} ${inc.incident_type || "UNKNOWN"}</b></td>
          <td style="text-align:center;">${photoHtml}</td>
          <td><b>${inc.road_id || "N/A"}</b> <span style="font-size:10.5px;color:var(--text-muted);">${coordsText}</span></td>
          <td><span class="status-badge ${badgeClass}">${inc.status || "UNKNOWN"}</span></td>
          <td><b style="color:${(inc.confidence || 0) > 0.9 ? 'var(--status-safe)' : 'var(--status-warning)'}">${inc.confidence != null ? `${Math.round(inc.confidence * 100)}%` : "N/A"}</b></td>
          <td>${inc.description || 'Road hazard report'}</td>
          <td>
            ${inc.status !== 'VERIFIED' ? `
              <button class="btn-primary" style="padding:3px 9px;font-size:10.5px;background:var(--brand-primary);" onclick="P6ControlTower.verifyIncident('${inc.incident_id}')">AI Verify</button>
            ` : `<span style="color:var(--status-safe);font-size:11px;font-weight:700;">✓ Verified</span>`}
          </td>
        </tr>
      `;
    }).join("");
  },

  previewPhoto(url) {
    const modal = document.getElementById("incidentPhotoModal");
    const img = document.getElementById("modalFullPhotoImg");
    if (modal && img) {
      img.src = url;
      modal.style.display = "flex";
    }
  },

  handleUrlInput(url) {
    const thumb = document.getElementById("incidentPhotoThumb");
    const box = document.getElementById("incidentPhotoPreviewBox");
    const status = document.getElementById("incidentPhotoStatus");
    if (thumb && url && url.startsWith("http")) {
      thumb.src = url;
      if (box) box.style.display = "flex";
      if (status) status.textContent = "✓ Photo Evidence Attached";
    }
  },

  handleFileSelect(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      const urlInput = document.getElementById("inputIncidentImageUrl");
      const thumb = document.getElementById("incidentPhotoThumb");
      const box = document.getElementById("incidentPhotoPreviewBox");
      const status = document.getElementById("incidentPhotoStatus");
      if (urlInput) urlInput.value = dataUrl;
      if (thumb) thumb.src = dataUrl;
      if (box) box.style.display = "flex";
      if (status) status.textContent = `✓ Attached: ${file.name}`;
    };
    reader.readAsDataURL(file);
  },

  bindIncidentForm() {
    const form = document.getElementById("formReportIncident");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const lat = parseFloat(fd.get("latitude"));
        const lng = parseFloat(fd.get("longitude"));
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
          App.showToast("Enter valid latitude and longitude before submitting.", "warning");
          return;
        }

        const payload = {
          reported_by: fd.get("reported_by"),
          latitude: lat,
          longitude: lng,
          incident_type: fd.get("incident_type"),
          road_id: fd.get("road_id"),
          description: fd.get("description") || "",
          image_url: fd.get("image_url") || null
        };

        try {
          const res = await PravahAPI.reportIncident(payload);
          App.showToast(`✅ Incident ${res.incident_id || "registered"} into Control Tower!`, "safe");
          form.reset();
        } catch (err) {
          App.showToast(`Failed to register incident: ${err.message}`, "danger");
        }

        await this.renderIncidentsTable();
        await this.renderOverviewStats();
        if (window.PravahMap && PravahMap.renderIncidents) {
          PravahMap.renderIncidents();
        }
      });
    }
  },

  bindAlertForm() {
    const form = document.getElementById("formEvaluateAlert");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const roadId = String(fd.get("road_id") || "").trim();
        const floodProb = parseFloat(fd.get("flood_prob"));
        const landProb = parseFloat(fd.get("landslide_prob"));
        const disruptionProb = parseFloat(fd.get("disruption_prob"));
        const accessibilityScore = parseFloat(fd.get("accessibility_score"));
        const shortageProb = parseFloat(fd.get("shortage_prob"));
        const affectedShipments = parseInt(fd.get("affected_shipments"), 10);
        const criticalShipments = parseInt(fd.get("critical_shipments"), 10);
        if (!roadId || ![floodProb, landProb, disruptionProb, accessibilityScore, shortageProb, affectedShipments, criticalShipments].every(Number.isFinite)) {
          App.showToast("Enter all live risk, accessibility, and shipment values.", "warning");
          return;
        }

        const outBox = document.getElementById("alertEvalResultBox");
        if (outBox) {
          try {
            const result = await PravahAPI.evaluateControlTowerAlert({
              road_id: roadId,
              flood_probability: floodProb,
              landslide_probability: landProb,
              disruption_probability: disruptionProb,
              accessibility_score: accessibilityScore,
              shortage_probability: shortageProb,
              affected_shipments: affectedShipments,
              critical_shipments: criticalShipments
            });
            const sev = result.severity;
            const color = sev === "CRITICAL" ? "var(--status-danger)" : (sev === "HIGH" ? "var(--status-warning)" : "var(--brand-primary)");
            const bg = sev === "CRITICAL" ? "rgba(220,38,38,0.08)" : (sev === "HIGH" ? "rgba(217,119,6,0.08)" : "rgba(2,132,199,0.08)");
            const border = sev === "CRITICAL" ? "rgba(220,38,38,0.3)" : (sev === "HIGH" ? "rgba(217,119,6,0.3)" : "rgba(2,132,199,0.3)");
            outBox.style.display = "block";
            outBox.innerHTML = `
            <div style="background:${bg};border:1.5px solid ${border};border-radius:8px;padding:12px;font-size:12px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <b style="color:${color};font-size:13px;display:flex;align-items:center;gap:6px;">
                  <span>🚨</span> <span>EVALUATED SEVERITY: ${sev}</span>
                </b>
                <span style="font-size:10px;padding:2px 7px;border-radius:10px;font-weight:700;background:${color};color:#fff;">${roadId}</span>
              </div>
              <div style="color:var(--text-primary);line-height:1.45;margin-bottom:6px;">
                <b>Multi-Hazard Risk:</b> Flood ${Math.round(floodProb * 100)}% · Landslide ${Math.round(landProb * 100)}%
              </div>
              <div style="font-size:11px;color:var(--text-secondary);">
                <b>Recommended Command Action:</b> ${result.recommended_action}
              </div>
            </div>
          `;
            await this.renderOverviewStats();
          } catch (error) {
            outBox.style.display = "block";
            outBox.innerHTML = `<div class="error-box">Live alert evaluation unavailable: ${this.escapeHtml(error.message)}</div>`;
          }
        }
      });
    }
  },

  async verifyIncident(incidentId) {
    try {
      const res = await PravahAPI.verifyIncident(incidentId);
      const conf = res.confidence != null ? `${Math.round(res.confidence * 100)}%` : "completed";
      const status = res.status || "UNDER_VERIFICATION";
      const tone = status === "VERIFIED" ? "safe" : (status === "REJECTED" ? "danger" : "warning");
      const prefix = status === "VERIFIED" ? "✅" : (status === "REJECTED" ? "⛔" : "⚠️");
      App.showToast(`${prefix} Incident ${incidentId}: ${status} (${res.detected_type || "no hazard detected"}, ${conf} confidence)`, tone);
    } catch (err) {
      App.showToast(`Verification failed: ${err.message}`, "danger");
    }
    await this.renderIncidentsTable();
    await this.renderOverviewStats();
    if (window.PravahMap && PravahMap.renderIncidents) {
      PravahMap.renderIncidents();
    }
  }
};

window.P6ControlTower = P6ControlTower;
