/**
 * PRAVAH — What-If Simulation Engine
 * Multi-hazard disruption modeler using P6 simulation results (P5 shipments + P4 routes).
 */

const WhatIfSimulation = {
  map: null,

  init() {
    this.bindEvents();
    this.renderInitialDashboard();
  },

  bindEvents() {
    const form = document.getElementById("formWhatIfSim");
    if (form) {
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const fd = new FormData(form);
        const scenarioType = fd.get("scenario_type") || "LANDSLIDE_BLOCK";
        const roadId = fd.get("road_id") || "NH-13";

        const btn = form.querySelector("button[type='submit']");
        if (btn) {
          btn.disabled = true;
          btn.innerHTML = `<span>⏳</span> <span>Simulating Real-Time Cascade Disruptions…</span>`;
        }

        let res;
        try {
          res = await PravahAPI.runWhatIfSimulation({ scenario_type: scenarioType, road_id: roadId });
        } catch (err) {
          // What-If simulation unavailable
        }

        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<span>⚡</span> <span>Run Scenario Simulation</span>`;
        }

        if (res) {
          const serviceError = Array.isArray(res.errors) && res.errors.length
            ? res.errors.join(" ")
            : "";
          this.setServiceStatus(serviceError);
          this.renderSimulationResults(res, scenarioType, roadId);
          App.showToast(`Simulation scenario complete: ${res.scenario_id || "completed"}`, "safe");
        } else {
          this.setServiceStatus("Unable to retrieve simulation results. Please check the P6 service.");
          App.showToast("Unable to retrieve simulation results. Please check the P6 service.", "warning");
        }
      });

      form.addEventListener("reset", () => {
        this.setServiceStatus();
        this.destroyMap();
        this.renderInitialDashboard();
      });
    }
  },

  setServiceStatus(message = "") {
    const status = document.getElementById("simulationServiceStatus");
    if (!status) return;
    status.hidden = !message;
    status.textContent = message;
  },

  destroyMap() {
    if (this.map) {
      this.map.remove();
      this.map = null;
    }
  },

  renderRouteMap(coordinates) {
    const el = document.getElementById("whatIfScenarioMap");
    if (!el || !window.L) return false;
    this.destroyMap();
    this.map = L.map(el, { zoomControl: false });
    L.control.zoom({ position: "bottomright" }).addTo(this.map);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }).addTo(this.map);
    const line = L.polyline(coordinates, {
      color: "#2563eb",
      weight: 5.5,
      opacity: 0.95,
      lineJoin: "round"
    });
    const glow = L.polyline(coordinates, {
      color: "#93c5fd",
      weight: 9,
      opacity: 0.45,
      lineJoin: "round"
    });
    glow.addTo(this.map);
    line.addTo(this.map);
    this.map.fitBounds(line.getBounds(), { padding: [24, 24] });
    setTimeout(() => this.map && this.map.invalidateSize(), 80);
    return true;
  },

  renderInitialDashboard() {
    const container = document.getElementById("simulationResultContainer");
    if (!container) return;
    this.destroyMap();
    container.style.display = "block";
    container.innerHTML = `
      <div class="whatif-results-shell whatif-awaiting-dashboard">
        <div class="whatif-metric-grid">
          <div class="whatif-metric-card roads"><span>▥</span><div><b>—</b><strong>Affected road segments</strong><small>Run a scenario to view results.</small></div></div>
          <div class="whatif-metric-card detour"><span>⌁</span><div><b>—</b><strong>Estimated detour</strong><small>Run a scenario to view results.</small></div></div>
          <div class="whatif-metric-card delay"><span>◷</span><div><b>—</b><strong>Additional travel time</strong><small>Run a scenario to view results.</small></div></div>
          <div class="whatif-metric-card shipments"><span>♟</span><div><b>—</b><strong>Shipments impacted</strong><small>Run a scenario to view results.</small></div></div>
        </div>
        <div class="whatif-dashboard-grid">
          <section class="whatif-panel whatif-parameters-card"><h3><span aria-hidden="true">⚙</span> Hazard Parameters</h3><p class="whatif-panel-subtitle">Controls are available above; impact values appear after a run.</p><div class="whatif-inline-empty">Run a scenario to view results.</div></section>
          <section class="whatif-panel whatif-map-card"><div class="whatif-panel-heading"><div><h3><span aria-hidden="true">⌖</span> Scenario Impact Map</h3><p>Route geometry is shown when supplied by the simulation.</p></div><span class="whatif-map-status">AWAITING RUN</span></div><div class="whatif-map-empty"><span aria-hidden="true">⌖</span><strong>Impact geometry unavailable</strong><p>Run a scenario to view results.</p></div></section>
          <aside class="whatif-panel whatif-decision-card"><h3><span aria-hidden="true">▤</span> Simulation Results</h3><p class="whatif-panel-subtitle">Decision support from the completed run</p><div class="whatif-inline-empty">Run a scenario to view results.</div></aside>
        </div>
        <div class="whatif-bottom-grid">
          <section class="whatif-panel whatif-shipments-card"><h3><span aria-hidden="true">♟</span> Potentially Impacted Shipments</h3><div class="whatif-inline-empty">Run a scenario to view results.</div></section>
          <aside class="whatif-panel whatif-insights-card"><h3><span aria-hidden="true">✦</span> Key Insights</h3><div class="whatif-inline-empty">Run a scenario to view results.</div></aside>
        </div>
      </div>
    `;
  },

  renderSimulationResults(res, scenarioType, roadId) {
    const container = document.getElementById("simulationResultContainer");
    if (!container) return;

    const escapeHtml = (value) => String(value ?? "N/A").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
    const unavailable = (label = "Data unavailable") => `<span title="${escapeHtml(label)}">N/A</span>`;
    const scenario = String(res.scenario_type || scenarioType || "").replaceAll("_", " ");
    const roads = Array.isArray(res.affected_roads) ? res.affected_roads : [];
    const delayMinutes = (typeof res.additional_delay_minutes === "number" && Number.isFinite(res.additional_delay_minutes))
      ? res.additional_delay_minutes
      : null;
    const delayText = delayMinutes !== null
      ? `${Math.floor(delayMinutes / 60)} h ${delayMinutes % 60} m`
      : unavailable("Average delay cannot be calculated from available P4/P5 data.");
    const risk = (typeof res.shortage_risk_change === "number" && Number.isFinite(res.shortage_risk_change))
      ? `${Math.round(res.shortage_risk_change * 100)}%`
      : unavailable("Shortage risk cannot be calculated from available backend data.");
    const metricValue = (value) => (typeof value === "number" && Number.isFinite(value)) ? value : unavailable();
    const reroute = res.alternative_route || (Array.isArray(res.recommended_reroutes) ? res.recommended_reroutes.find(Boolean) : null);
    const detourDistance = (typeof reroute?.additional_distance_km === "number" && Number.isFinite(reroute.additional_distance_km))
      ? reroute.additional_distance_km
      : null;
    const detourText = detourDistance !== null
      ? `${detourDistance} km`
      : unavailable("No P4 additional distance was returned.");
    const shipmentRows = Array.isArray(res.affected_shipments_detail) ? res.affected_shipments_detail : [];
    const coordinates = Array.isArray(res.route_coordinates) && res.route_coordinates.length >= 2
      ? res.route_coordinates
      : (Array.isArray(res.route_geometry) && res.route_geometry.length >= 2
        ? res.route_geometry
        : (Array.isArray(reroute?.route_coordinates) && reroute.route_coordinates.length >= 2
          ? reroute.route_coordinates
          : (Array.isArray(reroute?.route_geometry) && reroute.route_geometry.length >= 2
            ? reroute.route_geometry
            : [])));
    const hasGeometry = coordinates.length >= 2;
    const insights = [];
    const shipmentDataAvailable = res.data_provenance?.shipments !== "unavailable"
      && !res.unavailable_metrics?.includes("shipments");
    const affectedShipmentCount = shipmentDataAvailable
      && typeof res.affected_shipments === "number"
      && Number.isFinite(res.affected_shipments)
      ? res.affected_shipments
      : null;

    // Network-level insight
    if (roads.length > 0) {
      insights.push(`Network scenario: ${roads.join(", ")} corridor disruption modeled.`);
    }
    if (reroute?.route_id || reroute?.corridor || res.recommended_route_id) {
      const recName = reroute?.corridor || reroute?.route_id || res.recommended_route_id;
      insights.push(`P4 alternative route computed: ${recName}${detourDistance !== null ? ` (${detourDistance} km detour)` : ""}.`);
    } else if (res.unavailable_metrics?.includes("recommended_route")) {
      insights.push("P4 alternative route is currently unavailable for this corridor.");
    }

    if (delayMinutes !== null) {
      insights.push(`Average additional travel time: ${Math.floor(delayMinutes / 60)} h ${delayMinutes % 60} m.`);
    }

    // Logistics/Shipment-level insight
    if (affectedShipmentCount === null) {
      insights.push("Live P5 shipment data is unavailable, so shipment impact cannot be calculated.");
    } else if (affectedShipmentCount > 0) {
      insights.push(`Logistics impact: ${affectedShipmentCount} live shipment${affectedShipmentCount === 1 ? " is" : "s are"} affected by this disruption.`);
    } else {
      insights.push("Logistics impact: 0 live shipments affected on this corridor.");
    }

    if (typeof res.shortage_risk_change === "number" && Number.isFinite(res.shortage_risk_change)) {
      insights.push(`The reported shortage-risk change is ${Math.round(res.shortage_risk_change * 100)}%.`);
    }
    const formatDate = (value) => {
      if (!value) return "N/A";
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    };
    const displayField = (value) => (value === undefined || value === null || value === "") ? "N/A" : escapeHtml(value);
    const shipmentTable = shipmentRows.length ? `
      <div class="whatif-shipments-table-wrap">
        <table class="whatif-shipments-table">
          <thead><tr><th>Shipment ID</th><th>Origin</th><th>Destination</th><th>Current ETA</th><th>Simulated ETA</th><th>Delay</th><th>Status</th></tr></thead>
          <tbody>${shipmentRows.map((shipment) => {
            const delay = (typeof shipment.delay_hours === "number" && Number.isFinite(shipment.delay_hours))
              ? shipment.delay_hours
              : (typeof shipment.delay_minutes === "number" && Number.isFinite(shipment.delay_minutes) ? round(shipment.delay_minutes / 60.0, 1) : null);
            const delayLabel = delay !== null ? `${delay} h` : "N/A";
            return `<tr><td><strong>${displayField(shipment.shipment_id)}</strong></td><td>${displayField(shipment.origin)}</td><td>${displayField(shipment.destination)}</td><td>${escapeHtml(formatDate(shipment.current_eta))}</td><td>${escapeHtml(formatDate(shipment.revised_eta))}</td><td class="whatif-delay-cell">${escapeHtml(delayLabel)}</td><td>${shipment.status || shipment.priority ? `<span class="status-badge ${String(shipment.priority || shipment.status).toUpperCase() === "CRITICAL" ? "danger" : "warning"}">${escapeHtml(shipment.status || shipment.priority)}</span>` : "N/A"}</td></tr>`;
          }).join("")}</tbody>
        </table>
      </div>` : affectedShipmentCount === null
        ? `<div class="whatif-inline-empty">Live P5 shipment data is unavailable; no shipment impact is shown.</div>`
        : `<div class="whatif-inline-empty">0 live shipments impacted by this corridor scenario.</div>`;
    const routeRisk = typeof reroute?.route_risk === "number" ? `${Math.round(reroute.route_risk * 100)}%` : (reroute?.risk_level ? escapeHtml(reroute.risk_level) : unavailable("No P4 risk value was returned."));
    const mapBody = hasGeometry
      ? `<div id="whatIfScenarioMap" style="flex:1;min-height:266px;margin-top:10px;border-radius:9px;"></div>`
      : `<div class="whatif-map-empty"><span aria-hidden="true">⌖</span><strong>Route geometry unavailable for this scenario.</strong><p>The P4 routing response did not include route_coordinates for this run.</p></div>`;

    container.style.display = "block";
    container.innerHTML = `
      <div class="whatif-results-shell">
        <div class="whatif-metric-grid">
          <div class="whatif-metric-card roads"><span>▥</span><div><b>${roads.length}</b><strong>Selected Road (Scenario)</strong><small>${escapeHtml(roads[0] || res.road_id || roadId)}</small></div></div>
          <div class="whatif-metric-card detour"><span>⌁</span><div><b>${detourText}</b><strong>Alternative Detour</strong><small>P4 Route Distance</small></div></div>
          <div class="whatif-metric-card delay"><span>◷</span><div><b>${delayText}</b><strong>Additional Travel Time</strong><small>P4 Route Comparison</small></div></div>
          <div class="whatif-metric-card shipments"><span>♟</span><div><b>${affectedShipmentCount ?? unavailable("Live P5 shipment data is unavailable.")}</b><strong>Shipments Impacted</strong><small>Live P5 Fleet</small></div></div>
        </div>
        <div class="whatif-dashboard-grid">
          <section class="whatif-panel whatif-parameters-card">
            <h3><span aria-hidden="true">⚙</span> Scenario Parameters & Impact</h3>
            <p class="whatif-panel-subtitle">Network disruption vs logistics fleet state</p>
            <dl class="whatif-detail-list">
              <div><dt>Disruption scenario</dt><dd>${escapeHtml(scenario || "N/A")}</dd></div>
              <div><dt>Disrupted corridor</dt><dd>${escapeHtml(res.road_id || roadId)}</dd></div>
              <div><dt>P4 alternative route</dt><dd>${reroute ? "Available" : "Unavailable"}</dd></div>
              <div><dt>Affected districts</dt><dd>${metricValue(res.affected_districts)}</dd></div>
              <div><dt>Impacted shipments (P5)</dt><dd>${affectedShipmentCount ?? unavailable("Live P5 shipment data is unavailable.")}</dd></div>
              <div><dt>Delayed shipments (P5)</dt><dd>${shipmentDataAvailable ? metricValue(res.delayed_shipments) : unavailable("Live P5 shipment data is unavailable.")}</dd></div>
              <div><dt>Shortage risk change</dt><dd>${risk}</dd></div>
            </dl>
          </section>
          <section class="whatif-panel whatif-map-card">
            <div class="whatif-panel-heading">
              <div>
                <h3><span aria-hidden="true">⌖</span> Scenario Impact Map</h3>
                <p>Real OpenStreetMap route geometry from P4.</p>
              </div>
              <span class="whatif-map-status">${hasGeometry ? "P4 GEOMETRY" : "NO GEOMETRY"}</span>
            </div>
            ${mapBody}
          </section>
          <aside class="whatif-panel whatif-decision-card">
            <h3><span aria-hidden="true">▤</span> Simulation Results</h3>
            <p class="whatif-panel-subtitle">Network routing decision support</p>
            ${reroute ? `<div class="whatif-decision-callout"><span aria-hidden="true">↗</span><div><strong>Recommended alternative</strong><p>${escapeHtml(reroute.corridor || reroute.route_id || res.recommended_route_id)}</p></div></div>` : `<div class="whatif-inline-empty">No P4 routing recommendation was returned.</div>`}
            <dl class="whatif-detail-list">
              <div><dt>Detour distance</dt><dd>${detourText}</dd></div>
              <div><dt>Additional travel time</dt><dd>${delayText}</dd></div>
              <div><dt>Alternative route risk</dt><dd>${routeRisk}</dd></div>
            </dl>
            ${res.scenario_id ? `<p class="whatif-provenance">Run ID: ${escapeHtml(res.scenario_id)}</p>` : ""}
          </aside>
        </div>
        <div class="whatif-bottom-grid">
          <section class="whatif-panel whatif-shipments-card">
            <h3><span aria-hidden="true">♟</span> Potentially Impacted Shipments (P5)</h3>
            ${shipmentTable}
          </section>
          <aside class="whatif-panel whatif-insights-card">
            <h3><span aria-hidden="true">✦</span> Key Insights</h3>
            ${insights.length ? `<ul class="whatif-insights-list">${insights.map((insight) => `<li>${escapeHtml(insight)}</li>`).join("")}</ul>` : `<div class="whatif-inline-empty">No disruption impact or rerouting was required for the current simulation result.</div>`}
            ${res.data_provenance?.shipments ? `<p class="whatif-provenance">Shipment source: ${escapeHtml(res.data_provenance.shipments)} · Routes: ${escapeHtml(res.data_provenance.routes || "unavailable")}</p>` : ""}
          </aside>
        </div>
      </div>
    `;

    if (hasGeometry) {
      this.renderRouteMap(coordinates);
    } else {
      this.destroyMap();
    }
  }
};

window.WhatIfSimulation = WhatIfSimulation;
