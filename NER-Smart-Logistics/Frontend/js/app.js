/**
 * PRAVAH — Core Application Coordinator
 * Coordinates tabs, Light/Dark Theme toggle, Disaster Mode, IST clock, search, and prediction popups.
 */

const App = {
  activeTab: "path-optimization",
  disasterMode: false,
  isDarkMode: false,

  init() {
    this.initTheme();
    this.startClock();
    this.bindTabNavigation();
    this.bindDisasterToggle();
    this.bindSearch();
    this.bindSettingsModal();
    this.bindNotificationDrawer();
    this.bindProfileMenu();
    this.bindPredictionPopupModal();
    this.bindMapControls();
    this.initRiskIntelligence();

    this.updateBackendHealth();
    setInterval(() => this.updateBackendHealth(), 15000);

    window.addEventListener("resize", () => {
      if (PravahMap && PravahMap.map) {
        PravahMap.map.invalidateSize();
      }
    });
  },

  // --------------------------------------------------------------------------
  // LIGHT / DARK MODE TOGGLE
  // --------------------------------------------------------------------------
  initTheme() {
    const savedTheme = localStorage.getItem("pravah_theme");
    // Default to light as instructed by user, but respect saved preference
    this.isDarkMode = (savedTheme === "dark");
    this.applyTheme(this.isDarkMode);

    const btnTheme = document.getElementById("btnThemeToggle");
    if (btnTheme) {
      btnTheme.addEventListener("click", () => {
        this.isDarkMode = !this.isDarkMode;
        localStorage.setItem("pravah_theme", this.isDarkMode ? "dark" : "light");
        this.applyTheme(this.isDarkMode);
        this.showToast(this.isDarkMode ? "Switched to Dark Theme" : "Switched to Light Theme", "info");
      });
    }
  },

  applyTheme(isDark) {
    document.body.classList.toggle("dark-mode", isDark);
    const btnTheme = document.getElementById("btnThemeToggle");
    if (btnTheme) {
      btnTheme.innerHTML = isDark ? `
        <svg viewBox="0 0 24 24" fill="currentColor">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3" stroke="currentColor" stroke-width="2"></line>
          <line x1="12" y1="21" x2="12" y2="23" stroke="currentColor" stroke-width="2"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" stroke="currentColor" stroke-width="2"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" stroke="currentColor" stroke-width="2"></line>
          <line x1="1" y1="12" x2="3" y2="12" stroke="currentColor" stroke-width="2"></line>
          <line x1="21" y1="12" x2="23" y2="12" stroke="currentColor" stroke-width="2"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" stroke="currentColor" stroke-width="2"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" stroke="currentColor" stroke-width="2"></line>
        </svg>
      ` : `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      `;
      btnTheme.title = isDark ? "Switch to Light Mode" : "Switch to Dark Mode";
    }

    if (PravahMap && PravahMap.map) {
      PravahMap.updateTheme(isDark);
    }
  },

  // --------------------------------------------------------------------------
  // REAL-TIME IST CLOCK
  // --------------------------------------------------------------------------
  startClock() {
    const updateTime = () => {
      const now = new Date();
      const options = {
        timeZone: "Asia/Kolkata",
        weekday: "short",
        month: "short",
        day: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: true
      };
      const formatted = new Intl.DateTimeFormat("en-IN", options).format(now);
      const clockEl = document.getElementById("headerLiveClock");
      if (clockEl) {
        clockEl.innerHTML = `<b>${formatted}</b><span>IST (North East Command)</span>`;
      }
    };
    updateTime();
    setInterval(updateTime, 1000);
  },

  // --------------------------------------------------------------------------
  // TAB NAVIGATION
  // --------------------------------------------------------------------------
  bindTabNavigation() {
    document.querySelectorAll(".nav-tab").forEach(tab => {
      tab.addEventListener("click", (e) => {
        const targetTab = e.currentTarget.dataset.tab;
        this.switchTab(targetTab);
      });
    });
  },

  switchTab(tabId) {
    this.activeTab = tabId;
    document.querySelectorAll(".nav-tab").forEach(t => {
      t.classList.toggle("active", t.dataset.tab === tabId);
    });
    document.querySelectorAll(".tab-pane").forEach(p => {
      p.classList.toggle("active", p.id === `tab-${tabId}`);
    });

    if (tabId === "path-optimization" && PravahMap.map) {
      setTimeout(() => PravahMap.map.invalidateSize(), 200);
    }
    if (tabId === "risk-intelligence") {
      if (window.RiskIntelligence) {
        if (!this._riskIntelInit) {
          this._riskIntelInit = true;
          RiskIntelligence.init();
        } else if (RiskIntelligence.riskMap) {
          setTimeout(() => RiskIntelligence.riskMap.invalidateSize(), 200);
        }
      }
    }
  if (tabId === "overview") {
  P6ControlTower.renderOverviewStats();

  setTimeout(() => {
    if (window.OverviewMiniMap) {
      window.OverviewMiniMap.init();

      if (window.OverviewMiniMap.map) {
        window.OverviewMiniMap.map.invalidateSize();
      }
    }
  }, 150);
}
    if (tabId === "logistics") {
      P5Logistics.renderShipmentsTable();
    }
    if (tabId === "incidents") {
      P6ControlTower.renderIncidentsTable();
    }
  },

  // --------------------------------------------------------------------------
  // DISASTER MODE
  // --------------------------------------------------------------------------
  bindDisasterToggle() {
    const toggle = document.getElementById("disasterModeToggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        this.disasterMode = !this.disasterMode;
        document.body.classList.toggle("disaster-mode-active", this.disasterMode);
        const label = document.getElementById("disasterModeLabel");
        if (label) label.textContent = this.disasterMode ? "DISASTER ACTIVE" : "Disaster Mode";

        if (this.disasterMode) {
          this.showToast("🚨 DISASTER MODE ACTIVATED: High-alert relief corridors prioritized", "danger");
          ["floods", "landslides", "incidents"].forEach(l => {
            const cb = document.getElementById(`layer-${l}`);
            if (cb) { cb.checked = true; PravahMap.toggleLayer(l, true); }
          });
        } else {
          this.showToast("Standard operational monitoring restored", "safe");
        }
      });
    }
  },

  // --------------------------------------------------------------------------
  // UNIVERSAL SEARCH
  // --------------------------------------------------------------------------
  bindSearch() {
    const searchInput = document.getElementById("headerSearchInput");
    if (searchInput) {
      searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          const val = searchInput.value.trim();
          if (!val) return;
          this.switchTab("path-optimization");
          const destInput = document.getElementById("inputDestLocation");
          if (destInput) {
            destInput.value = val;
            P4Routing.handleOptimizeClick();
          }
        }
      });
    }
  },

  // --------------------------------------------------------------------------
  // MAP BASEMAP & OVERLAY CONTROLS
  // --------------------------------------------------------------------------
  bindMapControls() {
    document.querySelectorAll(".map-base-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        document.querySelectorAll(".map-base-btn").forEach(b => b.classList.remove("active"));
        e.currentTarget.classList.add("active");
        PravahMap.setBaseLayer(e.currentTarget.dataset.base);
      });
    });

    const layerIds = ["roads", "floods", "landslides", "weather", "incidents", "railways", "ferries"];
    layerIds.forEach(id => {
      const cb = document.getElementById(`layer-${id}`);
      if (cb) {
        cb.addEventListener("change", () => {
          PravahMap.toggleLayer(id, cb.checked);
        });
      }
    });
  },

  // --------------------------------------------------------------------------
  // AUTOMATED RISK INTELLIGENCE TAB (NO MANUAL FORM FIELDS)
  // --------------------------------------------------------------------------
  initRiskIntelligence() {
    const corridorButtons = document.querySelectorAll(".corridor-select-btn");
    corridorButtons.forEach(btn => {
      btn.addEventListener("click", async (e) => {
        corridorButtons.forEach(b => b.classList.remove("active"));
        e.currentTarget.classList.add("active");
        const orig = e.currentTarget.dataset.origin;
        const dest = e.currentTarget.dataset.dest;
        this.runCorridorScan(orig, dest);
      });
    });

    // Do not scan on app load — P1–P4 ribbon stays idle until Optimize Route
  },

  async runCorridorScan(origin, destination) {
    const statusEl = document.getElementById("corridorScanStatus");
    if (statusEl) statusEl.textContent = "Scanning corridor satellite & weather telemetry…";

    const res = await PredictionPipeline.runFullPipeline({ origin, destination }, { updateRibbon: false });

    if (statusEl) statusEl.textContent = `Completed: ${origin} ➔ ${destination} (${res.corridor})`;

    const cardP1 = document.getElementById("inspP1Val");
    const cardP2 = document.getElementById("inspP2Val");
    const cardP3 = document.getElementById("inspP3Val");
    const cardP4 = document.getElementById("inspP4Val");

    if (cardP1) cardP1.textContent = `${Math.round(res.p1.flood_probability * 100)}%`;
    if (cardP2) cardP2.textContent = `${Math.round(res.p2.landslide_probability * 100)}%`;
    if (cardP3) cardP3.textContent = `${Math.round(res.p3.disruption_probability * 100)}%`;
    if (cardP4) cardP4.textContent = `${Math.round(res.p3.accessibility_score * 100)}%`;

    const decisionBox = document.getElementById("inspDecisionSummary");
    if (decisionBox) {
      decisionBox.innerHTML = `
        <div style="background:${res.is_adapted ? 'var(--status-danger-light)' : 'var(--status-safe-light)'};border:1px solid ${res.is_adapted ? 'var(--status-danger-border)' : 'var(--status-safe-border)'};border-radius:8px;padding:12px;">
          <b style="color:${res.is_adapted ? 'var(--status-danger)' : 'var(--status-safe)'};font-size:13px;">
            ${res.is_adapted ? '⚡ Autonomous Route Adaptation Triggered' : '✅ Direct Corridor Cleared'}
          </b>
          <p style="margin-top:4px;font-size:12px;color:var(--text-primary);line-height:1.4;">
            ${res.adaptation_summary}
          </p>
          <div style="margin-top:8px;">
            <button class="btn-primary" style="padding:6px 14px;font-size:11.5px;" onclick="App.inspectOnMap('${origin}', '${destination}')">
              Plot on Map & View Detour
            </button>
          </div>
        </div>
      `;
    }
  },

  inspectOnMap(origin, destination) {
    this.switchTab("path-optimization");
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (window.PravahMap && PravahMap.map) {
      PravahMap.map.invalidateSize();
    }
    const srcInput = document.getElementById("inputSourceLocation");
    const destInput = document.getElementById("inputDestLocation");
    if (srcInput) srcInput.value = origin.includes(",") ? origin : `${origin}, Assam`;
    if (destInput) destInput.value = destination.includes(",") ? destination : `${destination}, Arunachal Pradesh`;
    P4Routing.handleOptimizeClick();
  },

  // --------------------------------------------------------------------------
  // PREDICTION LOGIC POPUP MODAL
  // --------------------------------------------------------------------------
  bindPredictionPopupModal() {
    const modal = document.getElementById("predictionPopupModal");
    const closeBtn = document.getElementById("btnClosePredictionPopup");
    const okBtn = document.getElementById("btnAckPredictionPopup");

    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    }
    if (okBtn && modal) {
      okBtn.addEventListener("click", () => modal.classList.remove("active"));
    }
  },

  // --------------------------------------------------------------------------
  // BACKEND HEALTH STATUS MONITOR
  // --------------------------------------------------------------------------
  async updateBackendHealth() {
    const health = await PravahAPI.checkHealth();
    const pill = document.getElementById("backendHealthPill");
    const label = document.getElementById("backendHealthText");
    if (pill && label) {
      const liveCount = Object.values(health).filter(v => v).length;
      const totalCount = Object.keys(health).length;
      if (liveCount >= 3) {
        pill.style.background = "var(--status-safe-light)";
        pill.style.color = "var(--status-safe)";
        pill.style.borderColor = "var(--status-safe-border)";
        label.textContent = `Backends Live (${liveCount}/${totalCount})`;
      } else if (liveCount > 0) {
        pill.style.background = "var(--status-warning-light)";
        pill.style.color = "var(--status-warning)";
        pill.style.borderColor = "var(--status-warning-border)";
        label.textContent = `Partial (${liveCount}/${totalCount})`;
      } else {
        pill.style.background = "var(--brand-cyan-light)";
        pill.style.color = "var(--brand-cyan)";
        pill.style.borderColor = "#bae6fd";
        label.textContent = "AI Engine Active";
      }
    }
  },

  // --------------------------------------------------------------------------
  // SETTINGS & NOTIFICATIONS MODALS
  // --------------------------------------------------------------------------
  bindSettingsModal() {
    const pill = document.getElementById("backendHealthPill");
    const modal = document.getElementById("settingsModal");
    const closeBtn = document.getElementById("btnCloseSettings");
    const saveBtn = document.getElementById("btnSaveSettings");

    if (pill && modal) {
      pill.addEventListener("click", () => {
        modal.classList.add("active");
        document.getElementById("setEndpointP1").value = PRAVAH_CONFIG.API_ENDPOINTS.p1_flood;
        document.getElementById("setEndpointP2").value = PRAVAH_CONFIG.API_ENDPOINTS.p2_landslide;
        document.getElementById("setEndpointP3").value = PRAVAH_CONFIG.API_ENDPOINTS.p3_road_risk;
        document.getElementById("setEndpointP4").value = PRAVAH_CONFIG.API_ENDPOINTS.p4_routing;
        document.getElementById("setEndpointP5").value = PRAVAH_CONFIG.API_ENDPOINTS.p5_logistics;
        document.getElementById("setEndpointP6").value = PRAVAH_CONFIG.API_ENDPOINTS.p6_control_tower;
      });
    }
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    }
    if (saveBtn && modal) {
      saveBtn.addEventListener("click", () => {
        PRAVAH_CONFIG.API_ENDPOINTS.p1_flood = document.getElementById("setEndpointP1").value;
        PRAVAH_CONFIG.API_ENDPOINTS.p2_landslide = document.getElementById("setEndpointP2").value;
        PRAVAH_CONFIG.API_ENDPOINTS.p3_road_risk = document.getElementById("setEndpointP3").value;
        PRAVAH_CONFIG.API_ENDPOINTS.p4_routing = document.getElementById("setEndpointP4").value;
        PRAVAH_CONFIG.API_ENDPOINTS.p5_logistics = document.getElementById("setEndpointP5").value;
        PRAVAH_CONFIG.API_ENDPOINTS.p6_control_tower = document.getElementById("setEndpointP6").value;
        localStorage.setItem("pravah_p1_url", PRAVAH_CONFIG.API_ENDPOINTS.p1_flood);
        localStorage.setItem("pravah_p2_url", PRAVAH_CONFIG.API_ENDPOINTS.p2_landslide);
        localStorage.setItem("pravah_p3_url", PRAVAH_CONFIG.API_ENDPOINTS.p3_road_risk);
        localStorage.setItem("pravah_p4_url", PRAVAH_CONFIG.API_ENDPOINTS.p4_routing);
        localStorage.setItem("pravah_p5_url", PRAVAH_CONFIG.API_ENDPOINTS.p5_logistics);
        localStorage.setItem("pravah_p6_url", PRAVAH_CONFIG.API_ENDPOINTS.p6_control_tower);
        modal.classList.remove("active");
        this.updateBackendHealth();
        this.showToast("API Endpoint settings updated", "safe");
      });
    }
  },

  bindNotificationDrawer() {
    const btnBell = document.getElementById("btnNotificationBell");
    const modal = document.getElementById("notificationsModal");
    const closeBtn = document.getElementById("btnCloseNotifications");

    if (btnBell && modal) {
      btnBell.addEventListener("click", () => modal.classList.add("active"));
    }
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => modal.classList.remove("active"));
    }
  },

  bindProfileMenu() {
    const avatarBadge = document.getElementById("userAvatarBadge");
    const dropdown = document.getElementById("profileDropdown");
    const profileModal = document.getElementById("profileModal");
    const dashModal = document.getElementById("dashboardOptionsModal");

    if (avatarBadge && dropdown) {
      avatarBadge.addEventListener("click", (e) => {
        e.stopPropagation();
        const isOpen = dropdown.style.display === "block";
        dropdown.style.display = isOpen ? "none" : "block";
      });
    }

    // Close dropdown on outside click
    document.addEventListener("click", (e) => {
      if (dropdown && !e.target.closest(".profile-menu-container")) {
        dropdown.style.display = "none";
      }
    });

    // Profile & Clearance button
    const btnProfile = document.getElementById("btnMenuProfile");
    if (btnProfile && profileModal) {
      btnProfile.addEventListener("click", () => {
        if (dropdown) dropdown.style.display = "none";
        profileModal.style.display = "flex";
      });
    }

    const btnCloseProfile = document.getElementById("btnCloseProfileModal");
    const btnDoneProfile = document.getElementById("btnProfileDone");
    const closeProfile = () => { if (profileModal) profileModal.style.display = "none"; };
    if (btnCloseProfile) btnCloseProfile.onclick = closeProfile;
    if (btnDoneProfile) btnDoneProfile.onclick = closeProfile;
    if (profileModal) {
      profileModal.onclick = (e) => { if (e.target === profileModal) closeProfile(); };
    }

    // Dashboard preferences button
    const btnDash = document.getElementById("btnMenuDashboard");
    if (btnDash && dashModal) {
      btnDash.addEventListener("click", () => {
        if (dropdown) dropdown.style.display = "none";
        // Load stored preferences
        const savedGoal = localStorage.getItem("pravah_default_goal") || "safest";
        const savedHub = localStorage.getItem("pravah_default_hub") || "Guwahati, Assam";
        const elGoal = document.getElementById("prefDefaultGoal");
        const elHub = document.getElementById("prefDefaultHub");
        if (elGoal) elGoal.value = savedGoal;
        if (elHub) elHub.value = savedHub;

        dashModal.style.display = "flex";
      });
    }

    const btnCloseDash = document.getElementById("btnCloseDashboardModal");
    const btnCancelDash = document.getElementById("btnCancelDashboardModal");
    const btnSaveDash = document.getElementById("btnSaveDashboardModal");
    const closeDash = () => { if (dashModal) dashModal.style.display = "none"; };
    if (btnCloseDash) btnCloseDash.onclick = closeDash;
    if (btnCancelDash) btnCancelDash.onclick = closeDash;
    if (dashModal) {
      dashModal.onclick = (e) => { if (e.target === dashModal) closeDash(); };
    }

    if (btnSaveDash) {
      btnSaveDash.addEventListener("click", () => {
        const selGoal = document.getElementById("prefDefaultGoal")?.value || "safest";
        const selHub = document.getElementById("prefDefaultHub")?.value || "Guwahati, Assam";
        localStorage.setItem("pravah_default_goal", selGoal);
        localStorage.setItem("pravah_default_hub", selHub);

        // Apply chosen goal
        if (window.P4Routing) {
          P4Routing.optimizeGoal = selGoal;
          document.querySelectorAll(".pill-select-group.optimize-group .pill-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.goal === selGoal);
          });
        }

        closeDash();
        this.showToast(`Preferences saved! Default goal: ${selGoal.toUpperCase()}, Hub: ${selHub}`, "safe");
      });
    }

    // Dispatch Hubs button
    const btnHubs = document.getElementById("btnMenuSwitchZone");
    if (btnHubs) {
      btnHubs.addEventListener("click", () => {
        if (dropdown) dropdown.style.display = "none";
        this.switchTab("path-optimization");
        const hubs = ["Tezpur, Assam", "Shillong, Meghalaya", "Silchar, Assam", "Guwahati, Assam"];
        const currentSrc = document.getElementById("inputSourceLocation")?.value || "";
        const nextHub = hubs.find(h => !currentSrc.includes(h.split(",")[0])) || hubs[0];
        if (window.P4Routing) {
          P4Routing.setOriginAndOptimize(nextHub);
        }
        this.showToast(`Switched active dispatch hub to ${nextHub}`, "info");
      });
    }

    // Switch Officer / Sign In buttons (from dropdown or profile modal)
    const loginModal = document.getElementById("loginModal");
    const btnMenuLogin = document.getElementById("btnMenuLogin");
    const btnProfileSwitch = document.getElementById("btnProfileSwitchAccount");
    const btnCloseLogin = document.getElementById("btnCloseLoginModal");
    const btnCancelLogin = document.getElementById("btnCancelLogin");

    const openLogin = () => {
      if (dropdown) dropdown.style.display = "none";
      if (profileModal) profileModal.style.display = "none";
      if (loginModal) loginModal.style.display = "flex";
    };

    const closeLogin = () => {
      if (loginModal) loginModal.style.display = "none";
    };

    if (btnMenuLogin) btnMenuLogin.onclick = openLogin;
    if (btnProfileSwitch) btnProfileSwitch.onclick = openLogin;
    if (btnCloseLogin) btnCloseLogin.onclick = closeLogin;
    if (btnCancelLogin) btnCancelLogin.onclick = closeLogin;
    if (loginModal) {
      loginModal.onclick = (e) => { if (e.target === loginModal) closeLogin(); };
    }

    // Quick Select Officer Profile Chips in Login Modal
    let selectedOfficer = {
      name: "Aditya Sharma",
      role: "Logistics Command Officer",
      id: "NER-CMD-26002-AS",
      init: "AS",
      station: "Guwahati Central Hub"
    };

    document.querySelectorAll(".quick-login-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".quick-login-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        selectedOfficer = {
          name: chip.dataset.name,
          role: chip.dataset.role,
          id: chip.dataset.id,
          init: chip.dataset.init,
          station: chip.dataset.station
        };
        const idInput = document.getElementById("loginOfficerId");
        if (idInput) idInput.value = chip.dataset.id;
      });
    });

    // Handle Officer Login Form Submit
    const loginForm = document.getElementById("officerLoginForm");
    if (loginForm) {
      loginForm.addEventListener("submit", (e) => {
        e.preventDefault();
        closeLogin();

        // Update Avatar Badge & Chip
        const navInitials = document.getElementById("navAvatarInitials");
        const navName = document.getElementById("navOfficerName");
        if (navInitials) navInitials.textContent = selectedOfficer.init;
        if (navName) navName.textContent = selectedOfficer.name;
        if (avatarBadge) {
          avatarBadge.title = `Signed in: ${selectedOfficer.name} (${selectedOfficer.role})`;
        }

        // Update Dropdown Header Info
        const nameEl = document.getElementById("menuOfficerName") || document.querySelector(".profile-name");
        const roleEl = document.getElementById("menuOfficerRole") || document.querySelector(".profile-role");
        const avatarLg = document.getElementById("menuAvatarInitials") || document.querySelector(".profile-avatar-lg");
        if (nameEl) nameEl.textContent = selectedOfficer.name;
        if (roleEl) roleEl.textContent = `${selectedOfficer.role} · NER`;
        if (avatarLg) avatarLg.textContent = selectedOfficer.init;

        this.showToast(`✅ Command Clearance Verified: Welcome, ${selectedOfficer.name}!`, "safe");
      });
    }

    // Sign out button
    const btnLogout = document.getElementById("btnMenuLogout");
    if (btnLogout) {
      btnLogout.addEventListener("click", () => {
        if (dropdown) dropdown.style.display = "none";
        this.showToast(`🔒 Command session locked. Please re-authenticate.`, "warning");
        const navInitials = document.getElementById("navAvatarInitials");
        const navName = document.getElementById("navOfficerName");
        if (navInitials) navInitials.textContent = "🔒";
        if (navName) navName.textContent = "Locked";
        if (avatarBadge) {
          avatarBadge.title = "Session Locked. Click to Sign In";
        }
        openLogin();
      });
    }
  },

  showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    let icon = "ℹ️";
    if (type === "safe") icon = "✅";
    if (type === "warning") icon = "⚠️";
    if (type === "danger") icon = "🚨";

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }
};

document.addEventListener("DOMContentLoaded", () => {
  PravahMap.init();
  P4Routing.init();
  P5Logistics.init();
  P6ControlTower.init();
  WhatIfSimulation.init();
  App.init();
});
