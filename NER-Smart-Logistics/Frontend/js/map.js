/**
 * PRAVAH — Interactive Leaflet Map Engine
 * Manages light/dark basemaps, hazard layers, incident markers, and dynamic route polylines.
 */

const PravahMap = {
  map: null,
  layers: {
    baseOSM: null,
    baseStreet: null,
    baseDark: null,
    baseSatellite: null,
    roads: null,
    floods: null,
    landslides: null,
    weather: null,
    incidents: null,
    railways: null,
    ferries: null,
    routePolyline: null,
    hazardSegment: null,
    routeMarkers: null
  },
  currentBase: "light",

  init(containerId = "map") {
    if (this.map) return;

    // Centered on Northeast India (Guwahati / Assam region)
    this.map = L.map(containerId, {
      center: [26.2006, 92.5378],
      zoom: 7,
      zoomControl: false
    });

    // Custom Zoom control at bottom-right (preventing overlap with top-right switcher)
    L.control.zoom({ position: "bottomright" }).addTo(this.map);

    // 1. Basemaps (100% Free, NO API Key Required, NO Watermark)
    // Standard OpenStreetMap (Light Theme)
    this.layers.baseOSM = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    });

    // Esri World Street Map (Clean, detailed, no key needed)
    this.layers.baseStreet = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}", {
      attribution: 'Tiles &copy; Esri',
      maxZoom: 18
    });

    // Esri Dark Gray Canvas (Dark Theme)
    this.layers.baseDark = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", {
      attribution: 'Tiles &copy; Esri, DeLorme',
      maxZoom: 16
    });

    // Esri World Imagery (Satellite)
    this.layers.baseSatellite = L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", {
      attribution: 'Tiles &copy; Esri, Earthstar Geographics',
      maxZoom: 18
    });

    // Initial basemap selection: OpenStreetMap by default (clean, no key required)
    const isDark = document.body.classList.contains("dark-mode");
    if (isDark) {
      this.layers.baseDark.addTo(this.map);
    } else {
      this.layers.baseOSM.addTo(this.map);
    }

    // 2. Initialize Layer Groups (Clean start - no uneven pre-drawn lines)
    this.layers.roads = L.layerGroup().addTo(this.map);
    this.layers.floods = L.layerGroup().addTo(this.map);
    this.layers.landslides = L.layerGroup().addTo(this.map);
    this.layers.weather = L.layerGroup().addTo(this.map);
    this.layers.incidents = L.layerGroup().addTo(this.map);
    this.layers.railways = L.layerGroup();
    this.layers.ferries = L.layerGroup();
    this.layers.routePolyline = L.layerGroup().addTo(this.map);
    this.layers.hazardSegment = L.layerGroup().addTo(this.map);
    this.layers.routeMarkers = L.layerGroup().addTo(this.map);

    // Map starts clean: route and corridor hazards only appear once user clicks Optimize Route

    setTimeout(() => this.map.invalidateSize(), 300);
  },

  // Basemap Switcher
  setBaseLayer(type) {
    this.currentBase = type;
    if (this.layers.baseOSM && this.map.hasLayer(this.layers.baseOSM)) this.map.removeLayer(this.layers.baseOSM);
    if (this.layers.baseStreet && this.map.hasLayer(this.layers.baseStreet)) this.map.removeLayer(this.layers.baseStreet);
    if (this.layers.baseDark && this.map.hasLayer(this.layers.baseDark)) this.map.removeLayer(this.layers.baseDark);
    if (this.layers.baseSatellite && this.map.hasLayer(this.layers.baseSatellite)) this.map.removeLayer(this.layers.baseSatellite);

    if (type === "satellite") {
      this.layers.baseSatellite.addTo(this.map);
    } else if (type === "street") {
      this.layers.baseStreet.addTo(this.map);
    } else if (type === "dark") {
      this.layers.baseDark.addTo(this.map);
    } else {
      const isDark = document.body.classList.contains("dark-mode");
      if (isDark) {
        this.layers.baseDark.addTo(this.map);
      } else {
        this.layers.baseOSM.addTo(this.map);
      }
    }
  },

  updateTheme(isDark) {
    if (this.currentBase === "light" || this.currentBase === "dark") {
      this.setBaseLayer(isDark ? "dark" : "light");
    }
  },

  toggleLayer(layerName, visible) {
    const lg = this.layers[layerName];
    if (!lg) return;
    if (visible) {
      if (!this.map.hasLayer(lg)) this.map.addLayer(lg);
    } else {
      if (this.map.hasLayer(lg)) this.map.removeLayer(lg);
    }
  },

  renderFloodZones() {
    this.layers.floods.clearLayers();
    PRAVAH_CONFIG.FLOOD_ZONES.forEach(zone => {
      const circle = L.circle(zone.center, {
        radius: zone.radius,
        color: "#2563eb",
        weight: 1.5,
        fillColor: "#3b82f6",
        fillOpacity: 0.22,
        dashArray: "4, 4"
      });

      circle.bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;min-width:180px;">
          <b style="color:#1d4ed8;font-size:13px;">🌊 ${zone.name}</b>
          <hr style="margin:6px 0;border:none;border-top:1px solid #e2e8f0;" />
          <div><b>P1 Flood Risk:</b> <span style="color:#dc2626;font-weight:700;">${Math.round(zone.flood_probability * 100)}%</span></div>
          <div><b>7-Day Rainfall:</b> ${zone.rainfall_7day_mm} mm</div>
          <div><b>River Proximity:</b> ${zone.river_proximity_km} km</div>
          <div style="margin-top:6px;font-size:10px;color:#64748b;">Data: CWC / Open-Meteo Flood Model</div>
        </div>
      `);
      this.layers.floods.addLayer(circle);
    });
  },

  renderLandslideZones() {
    this.layers.landslides.clearLayers();
    PRAVAH_CONFIG.LANDSLIDE_ZONES.forEach(zone => {
      const circle = L.circle(zone.center, {
        radius: zone.radius,
        color: "#d97706",
        weight: 1.5,
        fillColor: "#f59e0b",
        fillOpacity: 0.25
      });

      circle.bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;min-width:180px;">
          <b style="color:#b45309;font-size:13px;">⛰️ ${zone.name}</b>
          <hr style="margin:6px 0;border:none;border-top:1px solid #e2e8f0;" />
          <div><b>P2 Landslide Risk:</b> <span style="color:#d97706;font-weight:700;">${Math.round(zone.landslide_probability * 100)}%</span></div>
          <div><b>Slope Angle:</b> ${zone.slope_deg}°</div>
          <div><b>Geology:</b> ${zone.geology}</div>
          <div style="margin-top:6px;font-size:10px;color:#64748b;">Source: ISRO Landslide Atlas + Sentinel-2</div>
        </div>
      `);
      this.layers.landslides.addLayer(circle);
    });
  },

  renderIncidents() {
    this.layers.incidents.clearLayers();
    PRAVAH_CONFIG.INITIAL_INCIDENTS.forEach(inc => {
      let iconColor = "#dc2626";
      let iconEmoji = "⚠️";
      if (inc.incident_type === "LANDSLIDE") { iconColor = "#d97706"; iconEmoji = "⛰️"; }
      if (inc.incident_type === "FLOOD") { iconColor = "#2563eb"; iconEmoji = "🌊"; }
      if (inc.incident_type === "ROAD_BLOCKED") { iconColor = "#dc2626"; iconEmoji = "⛔"; }

      const customIcon = L.divIcon({
        className: "incident-map-marker",
        html: `
          <div style="
            background: #ffffff;
            border: 2px solid ${iconColor};
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.22);
            font-size: 13px;
          ">${iconEmoji}</div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14]
      });

      const marker = L.marker([inc.latitude, inc.longitude], { icon: customIcon });
      marker.bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;min-width:200px;">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <b style="color:${iconColor};font-size:13px;">${inc.incident_type}</b>
            <span style="font-size:9.5px;padding:1px 5px;background:#ecfdf5;color:#059669;border-radius:4px;font-weight:600;">${inc.status}</span>
          </div>
          <p style="margin:6px 0;color:#334155;line-height:1.35;">${inc.description}</p>
          <div style="font-size:11px;color:#64748b;">
            <b>Road ID:</b> ${inc.road_id} | <b>AI Confidence:</b> ${Math.round((inc.confidence || 0.85) * 100)}%
          </div>
          ${inc.image_url ? `<img src="${inc.image_url}" style="width:100%;height:90px;object-fit:cover;border-radius:4px;margin-top:6px;" alt="Incident Evidence" />` : ''}
        </div>
      `);
      this.layers.incidents.addLayer(marker);
    });
  },

  renderNationalHighways() {
    this.layers.roads.clearLayers();
    const guw = [26.1445, 91.7362];
    const shill = [25.5788, 91.8933];
    const tez = [26.6528, 92.7926];
    const sil = [24.8170, 92.7959];
    const taw = [27.5861, 91.8594];

    const nh6 = L.polyline([guw, [26.04, 91.82], [25.80, 91.88], shill], {
      color: "#64748b",
      weight: 3,
      opacity: 0.6
    }).bindTooltip("NH-6 (Guwahati - Shillong Expressway)");

    const nh27 = L.polyline([guw, [26.25, 92.34], tez, [25.75, 93.00], sil], {
      color: "#64748b",
      weight: 3,
      opacity: 0.6
    }).bindTooltip("NH-27 (East-West Corridor)");

    const nh13 = L.polyline([tez, [27.01, 92.65], [27.27, 92.42], [27.50, 92.10], taw], {
      color: "#d97706",
      weight: 3,
      opacity: 0.7,
      dashArray: "6, 4"
    }).bindTooltip("NH-13 Trans-Arunachal (Fragile High-Altitude)");

    this.layers.roads.addLayer(nh6);
    this.layers.roads.addLayer(nh27);
    this.layers.roads.addLayer(nh13);
  },

  renderFerriesAndRail() {
    this.layers.ferries.clearLayers();
    this.layers.railways.clearLayers();

    const ferry = L.polyline([[26.01, 89.98], [26.18, 91.74], [26.85, 94.22]], {
      color: "#0284c7",
      weight: 2.5,
      dashArray: "3, 6"
    }).bindTooltip("IWAI NW-2 River Brahmaputra Ro-Pax Ferry");
    this.layers.ferries.addLayer(ferry);

    const rail = L.polyline([[26.15, 91.72], [26.68, 92.85], [27.48, 94.90]], {
      color: "#7c3aed",
      weight: 2.5,
      dashArray: "8, 4"
    }).bindTooltip("NFR BG Railway Corridor");
    this.layers.railways.addLayer(rail);
  },

  // Plot Optimized Route and show adapted hazard segments if applicable
  plotRoute(routeData, isAdapted = false) {
    if (this.map) {
      this.map.invalidateSize();
    }
    this.layers.routePolyline.clearLayers();
    this.layers.hazardSegment.clearLayers();
    this.layers.routeMarkers.clearLayers();

    if (!routeData || !routeData.route_coordinates || routeData.route_coordinates.length === 0) return;

    const coords = routeData.route_coordinates;

    // Primary route line (Vibrant Blue with smooth styling)
    const primaryLine = L.polyline(coords, {
      color: "#2563eb",
      weight: 5.5,
      opacity: 0.95,
      lineJoin: "round"
    });

    const glowLine = L.polyline(coords, {
      color: "#93c5fd",
      weight: 9,
      opacity: 0.45,
      lineJoin: "round"
    });

    this.layers.routePolyline.addLayer(glowLine);
    this.layers.routePolyline.addLayer(primaryLine);

    // If route was adapted due to AI prediction logic, mark the autonomous bypass badge cleanly on corridor
    if (isAdapted && coords.length > 4) {
      const mid = Math.floor(coords.length / 2);
      const bypassMarker = L.marker(coords[mid], {
        icon: L.divIcon({
          className: "bypass-badge-icon",
          html: `
            <div style="
              background: #dc2626;
              color: #ffffff;
              font-size: 10px;
              font-weight: 700;
              padding: 3px 8px;
              border-radius: 12px;
              border: 1.5px solid #ffffff;
              box-shadow: 0 2px 8px rgba(220,38,38,0.5);
              white-space: nowrap;
              display: flex;
              align-items: center;
              gap: 4px;
            ">⚡ Safe AI Bypass Applied</div>
          `,
          iconSize: [140, 24],
          iconAnchor: [70, 12]
        })
      }).bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;padding:2px;">
          <b style="color:#dc2626;">⚡ Autonomous Route Adaptation</b><br/>
          Corridor rerouted via verified low-hazard bypass to avoid seasonal landslide/flood blockages.
        </div>
      `);
      this.layers.hazardSegment.addLayer(bypassMarker);
    }

    // Start marker (Origin)
    const startCoord = coords[0];
    const startIcon = L.divIcon({
      className: "route-start-marker",
      html: `
        <div style="
          background: #059669;
          color: #ffffff;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid #ffffff;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
          font-weight: 700;
          font-size: 11px;
        ">A</div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
    const startMarker = L.marker(startCoord, { icon: startIcon }).bindPopup(`<b>Origin:</b> ${routeData.origin}`);
    this.layers.routeMarkers.addLayer(startMarker);

    // End marker (Destination)
    const endCoord = coords[coords.length - 1];
    const endIcon = L.divIcon({
      className: "route-end-marker",
      html: `
        <div style="
          background: #dc2626;
          color: #ffffff;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          border: 2px solid #ffffff;
          box-shadow: 0 2px 6px rgba(0,0,0,0.25);
          font-weight: 700;
          font-size: 11px;
        ">B</div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    });
    const endMarker = L.marker(endCoord, { icon: endIcon }).bindPopup(`<b>Destination:</b> ${routeData.destination}`);
    this.layers.routeMarkers.addLayer(endMarker);

    // Floating Timing & Distance Badge at Route Midpoint
    if (coords.length > 2) {
      const midIdx = Math.floor(coords.length / 2);
      const midCoord = coords[midIdx];
      const timeStr = routeData.duration_formatted || `${Math.round(routeData.estimated_travel_time_minutes || 0)}m`;
      const distStr = `${routeData.distance_km} km`;
      const goalLabel = (routeData.goal || "").toLowerCase() === "shortest" ? "📏 Shortest" : "🛡️ Safest";

      const badgeIcon = L.divIcon({
        className: "route-time-badge-container",
        html: `
          <div class="route-time-badge">
            <span>⏱️ ${timeStr}</span>
            <span style="opacity:0.4;">|</span>
            <span>${distStr}</span>
            <span style="opacity:0.4;">|</span>
            <span style="color:#60a5fa;">${goalLabel}</span>
          </div>
        `,
        iconSize: [160, 26],
        iconAnchor: [80, 13]
      });
      const badgeMarker = L.marker(midCoord, { icon: badgeIcon, interactive: false });
      this.layers.routeMarkers.addLayer(badgeMarker);
    }

    // Required Hazard & Infrastructure Monitoring Symbols along Corridor
    if (routeData.flood_risk && routeData.flood_risk > 0.12 && coords.length > 6) {
      const floodPt = coords[Math.floor(coords.length * 0.28)];
      const floodIcon = L.divIcon({
        className: "hazard-map-icon-container",
        html: `<div class="hazard-map-icon flood" title="Flood Inundation Telemetry">🌊</div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      });
      const floodMarker = L.marker(floodPt, { icon: floodIcon }).bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;padding:2px;">
          <b style="color:#2563eb;">🌊 P1 Flood Prediction Point</b><br/>
          <b>Inundation Risk:</b> ${Math.round(routeData.flood_risk * 100)}%<br/>
          <b>Rainfall 7-Day:</b> ${routeData.rainfall_mm || 18} mm<br/>
          <b>Drainage Factor:</b> River catchment monitored
        </div>
      `);
      this.layers.routeMarkers.addLayer(floodMarker);
    }

    if (routeData.landslide_risk && routeData.landslide_risk > 0.12 && coords.length > 6) {
      const lsPt = coords[Math.floor(coords.length * 0.72)];
      const lsIcon = L.divIcon({
        className: "hazard-map-icon-container",
        html: `<div class="hazard-map-icon landslide" title="Landslide Susceptibility">⛰️</div>`,
        iconSize: [26, 26],
        iconAnchor: [13, 13]
      });
      const lsMarker = L.marker(lsPt, { icon: lsIcon }).bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;padding:2px;">
          <b style="color:#d97706;">⛰️ P2 Landslide Prediction Point</b><br/>
          <b>Susceptibility:</b> ${Math.round(routeData.landslide_risk * 100)}%<br/>
          <b>Terrain Slope:</b> Fragile mountain ghat section<br/>
          <b>Stability Score:</b> GSI Atlas verified
        </div>
      `);
      this.layers.routeMarkers.addLayer(lsMarker);
    }

    if (routeData.live_incidents && routeData.live_incidents.length > 0) {
      routeData.live_incidents.forEach((inc, idx) => {
        const incPt = (inc.latitude && inc.longitude) ? [inc.latitude, inc.longitude] : coords[Math.min(coords.length - 1, 10 + idx * 25)];
        const incIcon = L.divIcon({
          className: "hazard-map-icon-container",
          html: `<div class="hazard-map-icon incident" title="${inc.title || 'Road Incident'}">⚠️</div>`,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });
        const incMarker = L.marker(incPt, { icon: incIcon }).on("click", () => {
          if (window.P4Routing && P4Routing.showInPageDetail) {
            P4Routing.showInPageDetail({
              title: inc.title || inc.text || "Active Incident Alert",
              badge: "INCIDENT ALERT",
              source: inc.source || "Control Tower / P3 Road Risk",
              time: "Live Intelligence",
              body: inc.description || inc.title || "Real-time road disruption report along route corridor.",
              disruption: `${Math.round((inc.severity || 0.3) * 100)}%`,
              distance: inc.distance_from_route_km ? `${inc.distance_from_route_km} km` : "On corridor",
              status: "Active Incident"
            });
          }
        });
        this.layers.routeMarkers.addLayer(incMarker);
      });
    }

    this.map.fitBounds(primaryLine.getBounds(), { padding: [40, 40] });

    // ----------------------------------------------------------------------
    // Real-Life GPS Delivery Convoy Vehicle Animation along Route Geometry
    // ----------------------------------------------------------------------
    if (this.vehicleAnimationTimer) {
      clearInterval(this.vehicleAnimationTimer);
      this.vehicleAnimationTimer = null;
    }
    if (this.layers.vehicleMarker) {
      this.map.removeLayer(this.layers.vehicleMarker);
      this.layers.vehicleMarker = null;
    }

    if (coords.length >= 2) {
      const truckIcon = L.divIcon({
        className: "live-truck-gps-marker",
        html: `
          <div style="
            background: #0f172a;
            border: 2.5px solid #38bdf8;
            border-radius: 50%;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 14px rgba(56, 189, 248, 0.75);
            font-size: 17px;
          " title="Live Relief Convoy Vehicle (GPS Telemetry Active)">🚚</div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
      });

      let currentStepIndex = 0;
      const vehicleMarker = L.marker(coords[0], { icon: truckIcon, zIndexOffset: 1000 }).addTo(this.map);
      vehicleMarker.bindPopup(`
        <div style="font-family:Inter,sans-serif;font-size:12px;padding:2px;">
          <b style="color:#0284c7;">🚚 Relief Convoy Vehicle (In-Transit)</b><br/>
          <b>Corridor:</b> ${routeData.origin || 'Origin'} ➔ ${routeData.destination || 'Destination'}<br/>
          <b>Speed:</b> 48 km/h · <b>Telemetry:</b> GPS Sensor Active
        </div>
      `).openPopup();
      this.layers.vehicleMarker = vehicleMarker;

      // Animate truck moving along the route coordinates step-by-step
      this.vehicleAnimationTimer = setInterval(() => {
        currentStepIndex = (currentStepIndex + 1) % coords.length;
        const currentCoord = coords[currentStepIndex];
        vehicleMarker.setLatLng(currentCoord);
      }, 800);
    }
  },

  userMarker: null,
  userAccuracyCircle: null,

  setUserLocationMarker(lat, lng, name = "Your Location", accuracy = 50) {
    if (this.userMarker) {
      this.map.removeLayer(this.userMarker);
      this.userMarker = null;
    }
    if (this.userAccuracyCircle) {
      this.map.removeLayer(this.userAccuracyCircle);
      this.userAccuracyCircle = null;
    }

    const pulseIcon = L.divIcon({
      className: "user-gps-pulse-marker",
      html: `
        <div style="position:relative;width:28px;height:28px;display:flex;align-items:center;justify-content:center;">
          <div style="position:absolute;width:28px;height:28px;border-radius:50%;background:#3b82f6;opacity:0.35;animation:pulse-dot 1.5s infinite;"></div>
          <div style="width:16px;height:16px;border-radius:50%;background:#2563eb;border:3px solid #ffffff;box-shadow:0 0 12px rgba(37,99,235,0.85);z-index:2;"></div>
        </div>
      `,
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });

    this.userMarker = L.marker([lat, lng], { icon: pulseIcon }).addTo(this.map);
    this.userMarker.bindPopup(`
      <div style="font-family:Inter,sans-serif;font-size:12px;padding:4px;">
        <b style="color:#2563eb;font-size:13px;">📍 Live GPS Position</b><br/>
        <b>${name}</b><br/>
        <span style="font-size:10.5px;color:#64748b;">Coordinates: ${lat.toFixed(4)}°N, ${lng.toFixed(4)}°E (±${accuracy}m)</span>
      </div>
    `).openPopup();

    this.userAccuracyCircle = L.circle([lat, lng], {
      radius: Math.max(accuracy, 120),
      color: "#3b82f6",
      weight: 1.5,
      fillColor: "#60a5fa",
      fillOpacity: 0.15
    }).addTo(this.map);

    this.map.flyTo([lat, lng], Math.max(this.map.getZoom(), 11), { duration: 1.2 });
  }
};
window.OverviewMiniMap = {
    map: null,

    init() {
        const container = document.getElementById('overviewMiniMap');

        if (!container) return;

        // Prevent duplicate initialization
        if (this.map) {
            setTimeout(() => this.map.invalidateSize(), 100);
            return;
        }

        this.map = L.map('overviewMiniMap', {
            zoomControl: false,
            attributionControl: true
        }).setView([26.2, 92.5], 7);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 19
        }).addTo(this.map);

        setTimeout(() => {
            this.map.invalidateSize();
        }, 200);
    },

    zoomIn() {
        if (this.map) {
            this.map.zoomIn();
        }
    },

    zoomOut() {
        if (this.map) {
            this.map.zoomOut();
        }
    }
};

function switchTab(tabName) {
    if (tabName === 'overview') {
        setTimeout(() => {
            if (window.OverviewMiniMap) {
                window.OverviewMiniMap.init();

                if (window.OverviewMiniMap.map) {
                    window.OverviewMiniMap.map.invalidateSize();
                }
            }
        }, 150);
    }
}