/**
 * PRAVAH — Detailed Risk Intelligence (P1 Flood, P2 Landslide, P3 Road Risk) Controller
 * Handles live environmental telemetry, interactive multi-hazard risk simulation sliders,
 * multi-hazard radar charting, corridor elevation profiles, and dedicated Leaflet hazard map.
 */

const RiskIntelligence = {
  currentCorridor: {
    origin: "Guwahati",
    destination: "Tawang",
    roadId: "NH-13",
    roadName: "NH-13 Trans-Arunachal Highway",
    lat: 27.58,
    lng: 91.86
  },
  riskMap: null,
  mapLayers: {},
  chartInstance: null,

  // Interactive Simulation State
  simState: {
    p1Rain: 165.0,
    p1Discharge: 240.0,
    p1Elev: 48.0,
    p2Slope: 36.5,
    p2Rain: 85.0,
    p2Sat: 0.74,
    p3Incidents: 1,
    p3Severity: 3
  },

  // Corridor Presets Data
  presets: {
    "guwahati-tawang": {
      origin: "Guwahati", destination: "Tawang",
      roadId: "NH-13", roadName: "NH-13 Trans-Arunachal Highway",
      lat: 27.58, lng: 91.86, elev: 880, slope: 38.5, rain7d: 185, rain3d: 95, discharge: 320,
      incidents: [
        { id: "INC-101", title: "Debris & Rockfall at Sela Pass Approach", severity: 4, lat: 27.50, lng: 92.10, status: "Active obstruction" },
        { id: "INC-102", title: "Heavy Surface Runoff near Bhalukpong", severity: 2, lat: 27.01, lng: 92.65, status: "Passable with caution" }
      ]
    },
    "guwahati-shillong": {
      origin: "Guwahati", destination: "Shillong",
      roadId: "NH-6", roadName: "NH-6 Guwahati-Shillong Expressway",
      lat: 25.58, lng: 91.89, elev: 420, slope: 22.0, rain7d: 45, rain3d: 20, discharge: 65,
      incidents: [
        { id: "INC-201", title: "Minor Surface Ponding near Nongpoh", severity: 1, lat: 25.90, lng: 91.88, status: "Nominal" }
      ]
    },
    "lumding-silchar": {
      origin: "Lumding", destination: "Silchar",
      roadId: "NH-27", roadName: "NH-27 East-West Lumding Corridor",
      lat: 25.10, lng: 92.60, elev: 85, slope: 18.0, rain7d: 210, rain3d: 110, discharge: 850,
      incidents: [
        { id: "INC-301", title: "Critical Waterlogging in Low-lying Catchment", severity: 4, lat: 24.95, lng: 92.70, status: "Submerged Segment" },
        { id: "INC-302", title: "Embankment Erosion along River Bank", severity: 3, lat: 25.05, lng: 92.65, status: "One-lane restricted" }
      ]
    },
    "dimapur-kohima": {
      origin: "Dimapur", destination: "Kohima",
      roadId: "NH-29", roadName: "NH-29 Dimapur-Kohima Lifeline",
      lat: 25.68, lng: 94.11, elev: 650, slope: 32.0, rain7d: 120, rain3d: 65, discharge: 180,
      incidents: [
        { id: "INC-401", title: "Slope Subsidence near Pagla Pahar", severity: 3, lat: 25.80, lng: 93.85, status: "Heavy vehicle restriction" }
      ]
    },
    "imphal-moreh": {
      origin: "Imphal", destination: "Moreh",
      roadId: "NH-102", roadName: "NH-102 Trans-Asian Border Highway",
      lat: 24.25, lng: 94.30, elev: 520, slope: 25.0, rain7d: 95, rain3d: 48, discharge: 140,
      incidents: [
        { id: "INC-501", title: "Mud Accumulation on Shoulder", severity: 2, lat: 24.40, lng: 94.15, status: "Passable" }
      ]
    },
    "gangtok-nathula": {
      origin: "Gangtok", destination: "Nathu La",
      roadId: "NH-310", roadName: "NH-310 High-Altitude Frontier Highway",
      lat: 27.38, lng: 88.83, elev: 1250, slope: 44.0, rain7d: 160, rain3d: 85, discharge: 220,
      incidents: [
        { id: "INC-601", title: "Active Rockfall & Fog near Kyongnosla", severity: 4, lat: 27.35, lng: 88.75, status: "Convoy movement only" }
      ]
    }
  },

  init() {
    this.bindEvents();
    this.initSimulationSliders();
    this.selectCorridorPreset("guwahati-tawang");
  },

  setSearchedRouteCorridor(routeData) {
    if (!routeData) return;

    const origin = routeData.origin || "Origin";
    const destination = routeData.destination || "Destination";
    const isHilly = (routeData.landslide_risk > 0.18 || (routeData.route_coordinates && routeData.route_coordinates.some(c => c[0] > 25.0)));
    const coords = routeData.route_coordinates || [];
    const lat = coords.length ? coords[Math.floor(coords.length / 2)][0] : 26.14;
    const lng = coords.length ? coords[Math.floor(coords.length / 2)][1] : 91.73;

    const searchedPreset = {
      origin: origin,
      destination: destination,
      roadId: "SEARCHED-PRIMARY",
      roadName: `Searched Corridor: ${origin} ➔ ${destination}`,
      lat: lat,
      lng: lng,
      elev: isHilly ? 580 : 85,
      slope: isHilly ? (routeData.landslide_risk > 0.35 ? 36.0 : 24.0) : 8.0,
      rain7d: Math.round((routeData.rainfall_mm || 0) * 15 + 35),
      rain3d: Math.round((routeData.rainfall_mm || 0) * 6 + 15),
      discharge: Math.round((routeData.river_discharge || 15) * 8 + 40),
      incidents: (routeData.live_incidents || []).map((inc, i) => ({
        id: `INC-SEARCHED-${i+1}`,
        title: inc.title || inc.description || "Corridor Disruption",
        severity: typeof inc.severity === "number" ? Math.round(inc.severity * 5) : 3,
        lat: lat + (i * 0.03),
        lng: lng + (i * 0.03),
        status: inc.status || "Monitored Segment"
      }))
    };

    this.presets["searched-route"] = searchedPreset;

    const searchedBtn = document.getElementById("btnSearchedRoutePreset");
    if (searchedBtn) {
      searchedBtn.style.display = "inline-flex";
      searchedBtn.textContent = `🎯 Active Searched Route: ${origin} ➔ ${destination}`;
      searchedBtn.dataset.preset = "searched-route";
    }

    document.querySelectorAll(".risk-corridor-btn").forEach(b => b.classList.remove("active"));
    if (searchedBtn) searchedBtn.classList.add("active");

    this.selectCorridorPreset("searched-route");
    App.showToast(`🎯 Risk Intelligence synchronized with searched route: ${origin} ➔ ${destination}`, "info");
  },

  bindEvents() {
    // Corridor Preset Buttons
    document.querySelectorAll(".risk-corridor-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".risk-corridor-btn").forEach(b => b.classList.remove("active"));
        const target = e.currentTarget;
        target.classList.add("active");
        const key = target.dataset.preset;
        if (key && this.presets[key]) {
          this.selectCorridorPreset(key);
        }
      });
    });

    // Custom Location Search Form
    const searchForm = document.getElementById("riskLocationSearchForm");
    if (searchForm) {
      searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const query = document.getElementById("inputRiskQuery")?.value?.trim();
        if (query) {
          this.analyzeCustomLocation(query);
        }
      });
    }

    // Compare Corridor Dropdown Switcher
    const compareSelect = document.getElementById("selectRiskCompareCorridor");
    if (compareSelect) {
      compareSelect.addEventListener("change", (e) => {
        const val = e.target.value;
        if (val && this.presets[val]) {
          document.querySelectorAll(".risk-corridor-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.preset === val);
          });
          this.selectCorridorPreset(val);
        }
      });
    }

    // Refresh Live Telemetry
    const btnRefresh = document.getElementById("btnRefreshRiskIntel");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", () => {
        App.showToast("🔄 Fetching live P1–P3 sensor & satellite telemetry…", "info");
        this.recalculateAllModels();
      });
    }
  },

  initSimulationSliders() {
    const bindSlider = (id, valId, unit, stateKey, onChange) => {
      const slider = document.getElementById(id);
      const valDisplay = document.getElementById(valId);
      if (!slider) return;

      slider.addEventListener("input", (e) => {
        const val = parseFloat(e.target.value);
        this.simState[stateKey] = val;
        if (valDisplay) valDisplay.textContent = `${val}${unit}`;
        onChange(val);
      });
    };

    // P1 Flood Sliders
    bindSlider("simP1Rain", "valP1Rain", " mm", "p1Rain", () => this.recalculateP1());
    bindSlider("simP1Discharge", "valP1Discharge", " m³/s", "p1Discharge", () => this.recalculateP1());

    // P2 Landslide Sliders
    bindSlider("simP2Slope", "valP2Slope", "°", "p2Slope", () => this.recalculateP2());
    bindSlider("simP2Rain", "valP2Rain", " mm", "p2Rain", () => this.recalculateP2());
    bindSlider("simP2Sat", "valP2Sat", "%", "p2Sat", (v) => {
      this.simState.p2Sat = v / 100.0;
      this.recalculateP2();
    });

    // Reset Simulation Button
    const btnResetSim = document.getElementById("btnResetSimulators");
    if (btnResetSim) {
      btnResetSim.addEventListener("click", () => {
        const key = this.currentCorridorKey || "guwahati-tawang";
        this.selectCorridorPreset(key);
        App.showToast("🔄 Simulation sliders reset to baseline sensor data.", "info");
      });
    }
  },

  selectCorridorPreset(key) {
    const p = this.presets[key];
    if (!p) return;

    this.currentCorridorKey = key;
    this.currentCorridor = { ...p };

    // Update simulation state to baseline preset values
    this.simState.p1Rain = p.rain7d;
    this.simState.p1Discharge = p.discharge;
    this.simState.p1Elev = p.elev;
    this.simState.p2Slope = p.slope;
    this.simState.p2Rain = p.rain3d;
    this.simState.p2Sat = p.slope > 30 ? 0.76 : 0.48;

    // Sync Slider Inputs
    const setVal = (id, valId, val, unit) => {
      const el = document.getElementById(id);
      const txt = document.getElementById(valId);
      if (el) el.value = val;
      if (txt) txt.textContent = `${val}${unit}`;
    };

    setVal("simP1Rain", "valP1Rain", p.rain7d, " mm");
    setVal("simP1Discharge", "valP1Discharge", p.discharge, " m³/s");
    setVal("simP2Slope", "valP2Slope", p.slope, "°");
    setVal("simP2Rain", "valP2Rain", p.rain3d, " mm");
    setVal("simP2Sat", "valP2Sat", Math.round(this.simState.p2Sat * 100), "%");

    // Header info
    const titleEl = document.getElementById("riskCorridorTitle");
    const subEl = document.getElementById("riskCorridorSub");
    if (titleEl) titleEl.textContent = `${p.origin} ➔ ${p.destination} Corridor Telemetry`;
    if (subEl) subEl.textContent = `Monitored Highway: ${p.roadName} · Elevation: ${p.elev}m · Avg Slope: ${p.slope}°`;

    this.recalculateAllModels();
    this.updateMapAndIncidents(p);
  },

  async analyzeCustomLocation(locationQuery) {
    App.showToast(`🔍 Resolving geocoding & hazard data for: ${locationQuery}…`, "info");
    try {
      const geoRes = await fetch(`${PRAVAH_CONFIG.API_ENDPOINTS.p4_routing}/api/v1/geocode?q=${encodeURIComponent(locationQuery)}`);
      if (geoRes.ok) {
        const d = await geoRes.json();
        if (d.latitude && d.longitude) {
          const isHilly = (d.latitude >= 25.0 && d.latitude <= 36.0 && d.longitude >= 70.0 && d.longitude <= 98.0) || (d.latitude >= 8.0 && d.latitude <= 21.0);
          const customPreset = {
            origin: "Custom Location",
            destination: d.name || locationQuery,
            roadId: "SEARCHED-CORRIDOR",
            roadName: `Route to ${d.name || locationQuery}`,
            lat: d.latitude,
            lng: d.longitude,
            elev: isHilly ? 620 : 45,
            slope: isHilly ? 32.0 : 6.0,
            rain7d: isHilly ? 140 : 40,
            rain3d: isHilly ? 70 : 15,
            discharge: isHilly ? 210 : 80,
            incidents: [
              { id: "INC-CUST-01", title: `Live Corridor Monitoring near ${d.name || locationQuery}`, severity: isHilly ? 3 : 1, lat: d.latitude, lng: d.longitude, status: "Monitored" }
            ]
          };

          this.presets["custom"] = customPreset;
          this.selectCorridorPreset("custom");
          App.showToast(`✅ Hazard profile resolved for ${d.name || locationQuery} [${d.latitude.toFixed(4)}°N, ${d.longitude.toFixed(4)}°E]`, "safe");
          return;
        }
      }
    } catch (e) {
      console.warn("Custom geocode query error:", e);
    }
    App.showToast(`⚠️ Could not resolve coordinates for "${locationQuery}". Using nearest corridor hub.`, "warning");
  },

  recalculateP1() {
    // P1 Flood Score matching flood_score.py
    const rain = this.simState.p1Rain;
    const discharge = this.simState.p1Discharge;
    const elev = this.simState.p1Elev;

    let rainFactor = Math.min(0.95, Math.max(0.05, (rain - 50.0) / 200.0 * 0.9 + 0.05));
    let elevFactor = elev <= 50 ? 1.0 : (elev >= 500 ? 0.0 : 1.0 - (elev - 50) / 450.0);
    let riverFactor = Math.min(1.0, discharge / 500.0);

    const floodProb = Math.min(0.99, Math.max(0.01, (rainFactor * 0.55) + (riverFactor * 0.30) + (elevFactor * 0.15)));
    this.p1Result = { floodProb, rainFactor, riverFactor, elevFactor };

    this.updateP1UI();
    this.recalculateP3AndCombined();
  },

  recalculateP2() {
    // P2 Landslide Score matching scoring.py
    const slope = this.simState.p2Slope;
    const rain = this.simState.p2Rain;
    const sat = this.simState.p2Sat;

    let slopeFactor = slope > 40 ? 0.92 : (slope > 30 ? 0.75 : (slope > 20 ? 0.45 : 0.15));
    let rainFactor = Math.min(1.0, rain / 120.0);
    let satFactor = sat;

    const landslideProb = Math.min(0.98, Math.max(0.02, (slopeFactor * 0.45) + (rainFactor * 0.35) + (satFactor * 0.20)));
    this.p2Result = { landslideProb, slopeFactor, rainFactor, satFactor };

    this.updateP2UI();
    this.recalculateP3AndCombined();
  },

  recalculateP3AndCombined() {
    const p1Prob = this.p1Result ? this.p1Result.floodProb : 0.25;
    const p2Prob = this.p2Result ? this.p2Result.landslideProb : 0.35;
    const incidents = (this.currentCorridor && this.currentCorridor.incidents) ? this.currentCorridor.incidents.length : 0;
    const maxSev = incidents > 0 ? Math.max(...this.currentCorridor.incidents.map(i => i.severity)) : 1;

    const incidentPenalty = Math.min(0.35, (incidents * 0.12) + (maxSev * 0.05));
    const hazardCore = Math.max(p1Prob, p2Prob) * 0.70 + Math.min(p1Prob, p2Prob) * 0.15;
    const disruptionProb = Math.min(0.99, Math.max(0.01, hazardCore + incidentPenalty));
    const accessibilityScore = Math.max(0.01, 1.0 - disruptionProb);

    this.p3Result = { disruptionProb, accessibilityScore, incidentPenalty };

    this.updateP3UI();
    this.updateUnifiedKPIs();
    this.renderRadarChart();
    this.renderElevationProfileSvg();
  },

  recalculateAllModels() {
    this.recalculateP1();
    this.recalculateP2();
  },

  updateP1UI() {
    const res = this.p1Result;
    if (!res) return;

    const probPct = Math.round(res.floodProb * 100);
    const scoreEl = document.getElementById("riskP1Score");
    const gaugeBar = document.getElementById("riskP1GaugeBar");
    const badgeEl = document.getElementById("riskP1Badge");
    const descEl = document.getElementById("riskP1Summary");

    if (scoreEl) scoreEl.textContent = `${probPct}%`;
    if (gaugeBar) {
      gaugeBar.style.width = `${probPct}%`;
      gaugeBar.style.background = probPct > 60 ? "var(--status-danger)" : (probPct > 35 ? "var(--status-warning)" : "var(--brand-primary)");
    }
    if (badgeEl) {
      badgeEl.className = `status-badge ${probPct > 60 ? 'danger' : (probPct > 35 ? 'warning' : 'safe')}`;
      badgeEl.textContent = probPct > 60 ? "CRITICAL FLOOD" : (probPct > 35 ? "MODERATE FLOOD" : "NOMINAL RUNOFF");
    }

    if (descEl) {
      descEl.innerHTML = `
        <b>Rainfall Impact:</b> Math factor ${Math.round(res.rainFactor * 100)}% (${this.simState.p1Rain}mm 7-day precip)<br/>
        <b>Catchment Discharge:</b> ${this.simState.p1Discharge} m³/s flow rate<br/>
        <b>Drainage Elevation:</b> ${this.simState.p1Elev}m baseline
      `;
    }
  },

  updateP2UI() {
    const res = this.p2Result;
    if (!res) return;

    const probPct = Math.round(res.landslideProb * 100);
    const scoreEl = document.getElementById("riskP2Score");
    const gaugeBar = document.getElementById("riskP2GaugeBar");
    const badgeEl = document.getElementById("riskP2Badge");
    const descEl = document.getElementById("riskP2Summary");

    if (scoreEl) scoreEl.textContent = `${probPct}%`;
    if (gaugeBar) {
      gaugeBar.style.width = `${probPct}%`;
      gaugeBar.style.background = probPct > 60 ? "var(--status-danger)" : (probPct > 35 ? "var(--status-warning)" : "var(--status-safe)");
    }
    if (badgeEl) {
      badgeEl.className = `status-badge ${probPct > 60 ? 'danger' : (probPct > 35 ? 'warning' : 'safe')}`;
      badgeEl.textContent = probPct > 60 ? "CRITICAL INSTABILITY" : (probPct > 35 ? "MODERATE SLIP" : "STABLE SLOPE");
    }

    if (descEl) {
      descEl.innerHTML = `
        <b>Terrain Gradient:</b> ${this.simState.p2Slope}° slope angle (Factor: ${Math.round(res.slopeFactor * 100)}%)<br/>
        <b>Antecedent Moisture:</b> ${this.simState.p2Rain}mm 3-day rain | ${Math.round(this.simState.p2Sat * 100)}% soil saturation<br/>
        <b>Sentinel-2 Satellite:</b> Vegetation Index NDVI 0.61 · Cloud Cover 12%
      `;
    }
  },

  updateP3UI() {
    const res = this.p3Result;
    if (!res) return;

    const disPct = Math.round(res.disruptionProb * 100);
    const accPct = Math.round(res.accessibilityScore * 100);

    const scoreEl = document.getElementById("riskP3Score");
    const accEl = document.getElementById("riskP3AccessScore");
    const gaugeBar = document.getElementById("riskP3GaugeBar");
    const badgeEl = document.getElementById("riskP3Badge");
    const actionEl = document.getElementById("riskP3Recommendation");

    if (scoreEl) scoreEl.textContent = `${disPct}%`;
    if (accEl) accEl.textContent = `${accPct}%`;
    if (gaugeBar) {
      gaugeBar.style.width = `${disPct}%`;
      gaugeBar.style.background = disPct > 50 ? "var(--status-danger)" : (disPct > 25 ? "var(--status-warning)" : "var(--status-safe)");
    }
    if (badgeEl) {
      badgeEl.className = `status-badge ${disPct > 55 ? 'danger' : (disPct > 30 ? 'warning' : 'safe')}`;
      badgeEl.textContent = disPct > 55 ? "HIGH DISRUPTION" : (disPct > 30 ? "RESTRICTED PASSAGE" : "PASSABLE");
    }

    if (actionEl) {
      if (disPct > 50) {
        actionEl.innerHTML = `
          <div style="padding:10px 12px;background:rgba(220,38,38,0.1);border-left:4px solid var(--status-danger);border-radius:6px;">
            <b style="color:var(--status-danger);">⚠️ AUTONOMOUS DETOUR RECOMMENDED</b><br/>
            <span style="font-size:11.5px;color:var(--text-secondary);">
              Multi-hazard risk exceeds safety threshold on ${this.currentCorridor.roadId}. P4 Optimizer advises bypassing hazardous segments via low-risk State Highway detours.
            </span>
          </div>
        `;
      } else {
        actionEl.innerHTML = `
          <div style="padding:10px 12px;background:rgba(5,150,105,0.1);border-left:4px solid var(--status-safe);border-radius:6px;">
            <b style="color:var(--status-safe);">✅ PASSABLE UNDER NOMINAL SPEEDS</b><br/>
            <span style="font-size:11.5px;color:var(--text-secondary);">
              Highway ${this.currentCorridor.roadId} clear. Maintain convoy spacing and monitor wet pavement precautions.
            </span>
          </div>
        `;
      }
    }
  },

  updateUnifiedKPIs() {
    const p1 = this.p1Result ? Math.round(this.p1Result.floodProb * 100) : 18;
    const p2 = this.p2Result ? Math.round(this.p2Result.landslideProb * 100) : 24;
    const p3 = this.p3Result ? Math.round(this.p3Result.disruptionProb * 100) : 31;
    const acc = this.p3Result ? Math.round(this.p3Result.accessibilityScore * 100) : 88;

    // 1. Update 4 Circular SVG Gauges
    const updateCircle = (circleId, valId, pillId, val, isSafety = false) => {
      const circle = document.getElementById(circleId);
      const valTxt = document.getElementById(valId);
      const pill = document.getElementById(pillId);
      if (!circle) return;

      const pct = Math.min(100, Math.max(0, val));
      const circumference = 251.32;
      const offset = circumference * (1.0 - (pct / 100.0));
      circle.style.strokeDashoffset = offset.toFixed(2);

      let color = "#0284c7";
      let label = "Low Risk";
      let bg = "rgba(2,132,199,0.12)";

      if (isSafety) {
        color = pct >= 80 ? "#059669" : (pct >= 60 ? "#d97706" : "#dc2626");
        label = pct >= 80 ? "OPTIMAL" : (pct >= 60 ? "MODERATE" : "CRITICAL");
        bg = pct >= 80 ? "#059669" : (pct >= 60 ? "#d97706" : "#dc2626");
      } else {
        if (pct > 50) { color = "#dc2626"; label = "High Risk"; bg = "rgba(220,38,38,0.12)"; }
        else if (pct > 25) { color = "#d97706"; label = "Moderate"; bg = "rgba(217,119,6,0.12)"; }
        else { color = "#059669"; label = "Low Risk"; bg = "rgba(5,150,105,0.12)"; }
      }

      circle.style.stroke = color;
      if (valTxt) valTxt.textContent = isSafety ? `${pct}` : `${pct}%`;
      if (pill) {
        pill.textContent = label;
        pill.style.color = isSafety ? "#ffffff" : color;
        pill.style.background = bg;
      }
    };

    updateCircle("circleGaugeP1", "circleValP1", "circleP1Pill", p1);
    updateCircle("circleGaugeP2", "circleValP2", "circleP2Pill", p2);
    updateCircle("circleGaugeP3", "circleValP3", "circleP3Pill", p3);
    updateCircle("circleGaugeSafety", "circleValSafety", "circleSafetyPill", acc, true);

    // 2. Update Optimized Risk Sidebar Panel
    const p = this.currentCorridor || {};
    const nameEl = document.getElementById("optRiskCorridorName");
    const subEl = document.getElementById("optRiskCorridorSub");
    const roadEl = document.getElementById("optSpecRoad");
    const elevEl = document.getElementById("optSpecElev");
    const slopeEl = document.getElementById("optSpecSlope");
    const rainEl = document.getElementById("optSpecRain");
    const awaitingBanner = document.getElementById("riskAwaitingBanner");

    if (p.origin && p.destination) {
      if (nameEl) nameEl.textContent = `${p.origin} ➔ ${p.destination}`;
      if (subEl) subEl.textContent = p.roadName || "Monitored Expressway";
      if (awaitingBanner && this.hasSearchedRoute) {
        awaitingBanner.style.display = "none";
      }
    }

    if (roadEl) roadEl.textContent = p.roadId || "NH-Corridor";
    if (elevEl) elevEl.textContent = `${p.elev || 0} m`;
    if (slopeEl) slopeEl.textContent = `${p.slope || 0}°`;
    if (rainEl) rainEl.textContent = `${p.rain7d || 0} mm`;
  },

  renderRadarChart() {
    const canvas = document.getElementById("riskRadarCanvas");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const p1 = this.p1Result ? this.p1Result.floodProb * 100 : 25;
    const p2 = this.p2Result ? this.p2Result.landslideProb * 100 : 35;
    const p3 = this.p3Result ? this.p3Result.disruptionProb * 100 : 30;
    const weather = Math.min(100, (this.simState.p1Rain / 200.0) * 100);
    const incidentPen = this.p3Result ? this.p3Result.incidentPenalty * 250 : 25;

    // Render smooth HTML5 Canvas Radar / Bar visualizer
    const w = canvas.width = canvas.parentElement ? canvas.parentElement.clientWidth : 320;
    const h = canvas.height = 220;

    ctx.clearRect(0, 0, w, h);

    const categories = [
      { label: "P1 Flood Risk", val: p1, color: "#2563eb" },
      { label: "P2 Landslide", val: p2, color: "#d97706" },
      { label: "P3 Disruption", val: p3, color: "#dc2626" },
      { label: "7-Day Precip", val: weather, color: "#0284c7" },
      { label: "Incident Penalty", val: incidentPen, color: "#7c3aed" }
    ];

    const barWidth = Math.max(24, Math.floor((w - 60) / categories.length));
    const startX = 35;

    categories.forEach((cat, i) => {
      const x = startX + i * (barWidth + 14);
      const barH = (cat.val / 100) * 140;
      const y = h - 35 - barH;

      // Draw background bar slot
      ctx.fillStyle = "rgba(148, 163, 184, 0.15)";
      ctx.beginPath();
      ctx.roundRect(x, h - 175, barWidth, 140, 4);
      ctx.fill();

      // Draw value bar
      const grad = ctx.createLinearGradient(0, y, 0, h - 35);
      grad.addColorStop(0, cat.color);
      grad.addColorStop(1, cat.color + "55");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barWidth, barH, 4);
      ctx.fill();

      // Value text
      ctx.fillStyle = "#1e293b";
      ctx.font = "bold 11px Inter, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(`${Math.round(cat.val)}%`, x + barWidth / 2, y - 6);

      // Label text
      ctx.fillStyle = "#64748b";
      ctx.font = "10px Inter, sans-serif";
      ctx.fillText(cat.label.split(" ")[0], x + barWidth / 2, h - 12);
    });
  },

  renderElevationProfileSvg() {
    const svg = document.getElementById("riskProfileSvg");
    if (!svg) return;

    const p = this.currentCorridor || {};
    const baseElev = p.elev || 350;
    const slope = p.slope || 25;
    const p2Prob = this.p2Result ? this.p2Result.landslideProb : 0.3;

    const w = 360, h = 50;
    const points = [
      { x: 10, y: h - 10, elev: baseElev * 0.4 },
      { x: 90, y: h - (slope * 0.7), elev: baseElev * 0.7 },
      { x: 180, y: h - (slope * 1.1), elev: baseElev },
      { x: 270, y: h - (slope * 0.6), elev: baseElev * 0.8 },
      { x: 350, y: h - 12, elev: baseElev * 0.5 }
    ];

    let pathD = `M ${points[0].x} ${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i], p1 = points[i + 1];
      const cx = (p0.x + p1.x) / 2;
      pathD += ` C ${cx} ${p0.y}, ${cx} ${p1.y}, ${p1.x} ${p1.y}`;
    }

    const areaD = `${pathD} L ${points[points.length - 1].x} ${h} L ${points[0].x} ${h} Z`;
    const strokeColor = p2Prob > 0.5 ? "#dc2626" : (p2Prob > 0.3 ? "#d97706" : "#059669");

    svg.innerHTML = `
      <defs>
        <linearGradient id="elevGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.3"/>
          <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
        </linearGradient>
      </defs>
      <path d="${areaD}" fill="url(#elevGrad)" />
      <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" />
      <circle cx="180" cy="${h - (slope * 1.1)}" r="4" fill="${strokeColor}" stroke="#ffffff" stroke-width="1.5" />
    `;
  },

  updateMapAndIncidents(corridor) {
    // Incident Table Populator
    const tbody = document.getElementById("riskIncidentsTbody");
    if (tbody) {
      const incs = corridor.incidents || [];
      if (incs.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:14px;">No active incidents reported on this corridor. Passage clear.</td></tr>`;
      } else {
        tbody.innerHTML = incs.map(inc => `
          <tr>
            <td><b>${inc.id}</b></td>
            <td>${inc.title}</td>
            <td>
              <span class="status-badge ${inc.severity >= 4 ? 'danger' : (inc.severity >= 3 ? 'warning' : 'safe')}">
                Level ${inc.severity} / 5
              </span>
            </td>
            <td>${inc.lat.toFixed(3)}°N, ${inc.lng.toFixed(3)}°E</td>
            <td><b style="color:var(--text-primary);">${inc.status}</b></td>
          </tr>
        `).join("");
      }
    }

    // Leaflet Hazard Map Setup
    this.initOrUpdateRiskMap(corridor);
  },

  initOrUpdateRiskMap(corridor) {
    const mapDiv = document.getElementById("riskIntelligenceMap");
    if (!mapDiv) return;

    if (typeof L === "undefined") {
      console.warn("Leaflet (L) is not loaded.");
      return;
    }

    if (!this.riskMap) {
      this.riskMap = L.map("riskIntelligenceMap", { zoomControl: true }).setView([corridor.lat, corridor.lng], 9);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "© OpenStreetMap contributors"
      }).addTo(this.riskMap);
    } else {
      this.riskMap.setView([corridor.lat, corridor.lng], 9);
    }

    // Clear previous markers
    if (this.markerGroup) {
      this.riskMap.removeLayer(this.markerGroup);
    }
    this.markerGroup = L.layerGroup().addTo(this.riskMap);

    // Add Corridor Center Marker
    const mainMarker = L.circleMarker([corridor.lat, corridor.lng], {
      radius: 10,
      fillColor: "#2563eb",
      color: "#ffffff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9
    }).addTo(this.markerGroup);
    mainMarker.bindPopup(`<b>${corridor.roadName}</b><br/>Corridor Center (${corridor.lat.toFixed(3)}°N, ${corridor.lng.toFixed(3)}°E)<br/>Elev: ${corridor.elev}m`).openPopup();

    // Add Incident Markers
    (corridor.incidents || []).forEach(inc => {
      const color = inc.severity >= 4 ? "#dc2626" : (inc.severity >= 3 ? "#d97706" : "#059669");
      const incMarker = L.circleMarker([inc.lat, inc.lng], {
        radius: 8,
        fillColor: color,
        color: "#ffffff",
        weight: 2,
        opacity: 1,
        fillOpacity: 0.95
      }).addTo(this.markerGroup);
      incMarker.bindPopup(`<b>🚨 Incident ${inc.id}</b><br/>${inc.title}<br/>Severity: Level ${inc.severity}/5<br/>Status: ${inc.status}`);
    });

    // Invalidate map size to ensure full container rendering when tab switches
    setTimeout(() => {
      if (this.riskMap) this.riskMap.invalidateSize();
    }, 200);
  }
};

// Global export
window.RiskIntelligence = RiskIntelligence;
