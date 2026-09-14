/**
 * PRAVAH — Configuration, Constants & Northeast Regional Data
 * All services point to the unified backend at port 8002.
 */

// Clean up any stale legacy port URLs in localStorage
if (typeof localStorage !== "undefined") {
  ['pravah_p4_url', 'pravah_api_base', 'pravah_p1_url', 'pravah_p2_url', 'pravah_p3_url', 'pravah_p5_url', 'pravah_p6_url'].forEach(k => {
    localStorage.removeItem(k);
  });
}

const _host = (typeof window !== "undefined" && window.location && window.location.hostname)
  ? window.location.hostname
  : "127.0.0.1";
const _protocol = (typeof window !== "undefined" && window.location && window.location.protocol)
  ? window.location.protocol
  : "http:";

const _backendPort = "8002";
const _defaultBackend = `${_protocol}//${_host}:${_backendPort}`;

const _p4Url = (typeof localStorage !== "undefined" && localStorage.getItem("pravah_p4_url")) || _defaultBackend;
const _p5Url = (typeof localStorage !== "undefined" && localStorage.getItem("pravah_p5_url")) || _defaultBackend;
const _p6Url = (typeof localStorage !== "undefined" && localStorage.getItem("pravah_p6_url")) || _defaultBackend;
const _p2Url = (typeof localStorage !== "undefined" && localStorage.getItem("pravah_p2_url")) || _defaultBackend;

const PRAVAH_CONFIG = {
  APP_NAME: "Pravah",
  TAGLINE: "Safer Journeys. Stronger North East.",
  VERSION: "3.0.0",

  // Unified Backend Endpoint (All P1–P6 on port 8002)
  API_BASE: _defaultBackend,

  // Modular endpoints (all unified on port 8002 with individual microservice fallback support)
  API_ENDPOINTS: {
    p4_routing: _p4Url,
    p6_control_tower: _p6Url,
    p5_logistics: _p5Url,
    p2_landslide: _p2Url,
    p3_road_risk: _p2Url,
    p1_flood: _p2Url,
    gemini_ai: _defaultBackend,
  },

  // Northeast Transit Hubs & Coordinates
  LOCATIONS: {
    "Delhi": { lat: 28.6139, lng: 77.2090, district: "Central Delhi", state: "Delhi" },
    "New Delhi": { lat: 28.6139, lng: 77.2090, district: "New Delhi", state: "Delhi" },
    "Kolkata, West Bengal": { lat: 22.5726, lng: 88.3639, district: "Kolkata", state: "West Bengal" },
    "Siliguri, West Bengal": { lat: 26.7271, lng: 88.3953, district: "Darjeeling", state: "West Bengal" },
    "Patna, Bihar": { lat: 25.5941, lng: 85.1376, district: "Patna", state: "Bihar" },
    "Dispur, Assam": { lat: 26.1408, lng: 91.7898, district: "Kamrup Metropolitan", state: "Assam" },
    "Guwahati, Assam": { lat: 26.1445, lng: 91.7362, district: "Kamrup Metropolitan", state: "Assam" },
    "Shillong, Meghalaya": { lat: 25.5788, lng: 91.8933, district: "East Khasi Hills", state: "Meghalaya" },
    "Tawang, Arunachal Pradesh": { lat: 27.5861, lng: 91.8594, district: "Tawang", state: "Arunachal Pradesh" },
    "Tezpur, Assam": { lat: 26.6528, lng: 92.7926, district: "Sonitpur", state: "Assam" },
    "Silchar, Assam": { lat: 24.8170, lng: 92.7959, district: "Cachar", state: "Assam" },
    "Dibrugarh, Assam": { lat: 27.4728, lng: 94.9120, district: "Dibrugarh", state: "Assam" },
    "Jorhat, Assam": { lat: 26.7509, lng: 94.2037, district: "Jorhat", state: "Assam" },
    "Agartala, Tripura": { lat: 23.8315, lng: 91.2868, district: "West Tripura", state: "Tripura" },
    "Gangtok, Sikkim": { lat: 27.3389, lng: 88.6065, district: "East Sikkim", state: "Sikkim" },
    "Kohima, Nagaland": { lat: 25.6751, lng: 94.1086, district: "Kohima", state: "Nagaland" },
    "Imphal, Manipur": { lat: 24.8170, lng: 93.9368, district: "Imphal West", state: "Manipur" },
    "Aizawl, Mizoram": { lat: 23.7271, lng: 92.7176, district: "Aizawl", state: "Mizoram" },
    "Itanagar, Arunachal Pradesh": { lat: 27.0844, lng: 93.6053, district: "Papum Pare", state: "Arunachal Pradesh" },
    "Nainital": { lat: 29.3919, lng: 79.4542, district: "Nainital", state: "Uttarakhand" },
    "Bhimtal": { lat: 29.3500, lng: 79.5667, district: "Nainital", state: "Uttarakhand" },
    "Nainital, Uttarakhand": { lat: 29.3919, lng: 79.4542, district: "Nainital", state: "Uttarakhand" },
    "Bhimtal, Uttarakhand": { lat: 29.3500, lng: 79.5667, district: "Nainital", state: "Uttarakhand" },
    "Kochi": { lat: 9.9312, lng: 76.2673, district: "Ernakulam", state: "Kerala" },
    "Cochin": { lat: 9.9312, lng: 76.2673, district: "Ernakulam", state: "Kerala" },
    "Leh": { lat: 34.1526, lng: 77.5771, district: "Leh", state: "Ladakh" },
    "Ladakh": { lat: 34.1526, lng: 77.5771, district: "Leh", state: "Ladakh" },
    "Mumbai": { lat: 19.0760, lng: 72.8777, district: "Mumbai", state: "Maharashtra" },
    "Pune": { lat: 18.5204, lng: 73.8567, district: "Pune", state: "Maharashtra" },
    "Bengaluru": { lat: 12.9716, lng: 77.5946, district: "Bengaluru", state: "Karnataka" },
    "Bangalore": { lat: 12.9716, lng: 77.5946, district: "Bengaluru", state: "Karnataka" },
    "Chennai": { lat: 13.0827, lng: 80.2707, district: "Chennai", state: "Tamil Nadu" },
    "Hyderabad": { lat: 17.3850, lng: 78.4867, district: "Hyderabad", state: "Telangana" },
    "Ahmedabad": { lat: 23.0225, lng: 72.5714, district: "Ahmedabad", state: "Gujarat" },
    "Surat": { lat: 21.1702, lng: 72.8311, district: "Surat", state: "Gujarat" },
    "Jaipur": { lat: 26.9124, lng: 75.7873, district: "Jaipur", state: "Rajasthan" },
    "Bhopal": { lat: 23.2599, lng: 77.4126, district: "Bhopal", state: "Madhya Pradesh" },
    "Indore": { lat: 22.7196, lng: 75.8577, district: "Indore", state: "Madhya Pradesh" },
    "Raipur": { lat: 21.2514, lng: 81.6296, district: "Raipur", state: "Chhattisgarh" },
    "Bhubaneswar": { lat: 20.2961, lng: 85.8245, district: "Khurda", state: "Odisha" },
    "Srinagar": { lat: 34.0837, lng: 74.7973, district: "Srinagar", state: "Jammu and Kashmir" },
    "Shimla": { lat: 31.1048, lng: 77.1734, district: "Shimla", state: "Himachal Pradesh" },
    "Manali": { lat: 32.2396, lng: 77.1887, district: "Kullu", state: "Himachal Pradesh" },
    "Dehradun": { lat: 30.3165, lng: 78.0322, district: "Dehradun", state: "Uttarakhand" }
  },

  // Key National Highways & Corridors in Northeast
  HIGHWAYS: [
    { id: "NH-27", name: "NH-27 East-West Corridor (Silchar - Guwahati)", risk: 0.18, status: "Open" },
    { id: "NH-6", name: "NH-6 (Guwahati - Jorabat - Shillong - Silchar)", risk: 0.28, status: "Open" },
    { id: "NH-13", name: "NH-13 Trans-Arunachal Highway (Bhalukpong - Tawang)", risk: 0.65, status: "Caution" },
    { id: "NH-15", name: "NH-15 North Bank Highway (Baihat - Tezpur - Dibrugarh)", risk: 0.22, status: "Open" },
    { id: "NH-29", name: "NH-29 (Dimapur - Kohima Bypass)", risk: 0.45, status: "Caution" },
    { id: "NH-306", name: "NH-306 (Silchar - Vairengte - Aizawl Lifeline)", risk: 0.52, status: "Caution" }
  ],

  // Flood Inundation Hotspots (Brahmaputra & Barak River Basins)
  FLOOD_ZONES: [
    {
      name: "Kaziranga - Brahmaputra Flood Basin",
      center: [26.58, 93.17],
      radius: 22000,
      flood_probability: 0.76,
      rainfall_7day_mm: 240.5,
      river_proximity_km: 0.8
    },
    {
      name: "Morigaon Lowland Corridor",
      center: [26.25, 92.34],
      radius: 15000,
      flood_probability: 0.58,
      rainfall_7day_mm: 175.0,
      river_proximity_km: 1.4
    },
    {
      name: "Silchar - Barak Valley Plains",
      center: [24.82, 92.80],
      radius: 18000,
      flood_probability: 0.62,
      rainfall_7day_mm: 195.2,
      river_proximity_km: 0.9
    }
  ],

  // Landslide Susceptibility Zones (ISRO Landslide Atlas + Terrain Slope)
  LANDSLIDE_ZONES: [
    {
      name: "Sela Pass - Dirang Fragile Slope",
      center: [27.50, 92.10],
      radius: 12000,
      landslide_probability: 0.78,
      slope_deg: 38.5,
      geology: "Weathered Schist & Gneiss",
      risk_level: "High"
    },
    {
      name: "Barapani - Nongpoh Hill Cut (NH-6)",
      center: [25.75, 91.88],
      radius: 8000,
      landslide_probability: 0.38,
      slope_deg: 26.0,
      geology: "Shillong Plateau Sediments",
      risk_level: "Moderate"
    },
    {
      name: "Paglajhora Hill Section (NH-55 corridor)",
      center: [26.85, 88.35],
      radius: 7000,
      landslide_probability: 0.72,
      slope_deg: 41.0,
      geology: "Active debris slide zone",
      risk_level: "High"
    }
  ],

  // Initial Seed Incidents (for P6 Control Tower)
  INITIAL_INCIDENTS: [
    {
      incident_id: "INC_2026_0901",
      reported_by: "DRIVER_NER_442",
      latitude: 27.52,
      longitude: 92.05,
      incident_type: "LANDSLIDE",
      detected_type: "LANDSLIDE",
      confidence: 0.89,
      status: "VERIFIED",
      road_id: "NH-13",
      description: "Mud and boulder blockage 4km north of Dirang. Single lane traffic.",
      image_url: "https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?w=600&q=80",
      reported_at: "2026-09-08T14:22:00Z"
    },
    {
      incident_id: "INC_2026_0902",
      reported_by: "CITIZEN_APP_91",
      latitude: 26.29,
      longitude: 92.45,
      incident_type: "FLOOD",
      detected_type: "FLOOD",
      confidence: 0.94,
      status: "VERIFIED",
      road_id: "NH-27",
      description: "Water overflowing road surface (approx 1.5 ft) near Jagiroad culvert.",
      image_url: "https://images.unsplash.com/photo-1547683905-f686c993aae5?w=600&q=80",
      reported_at: "2026-09-08T16:45:00Z"
    },
    {
      incident_id: "INC_2026_0903",
      reported_by: "PATROL_OFFICER_07",
      latitude: 25.68,
      longitude: 91.90,
      incident_type: "ROAD_BLOCKED",
      detected_type: "ROAD_BLOCKED",
      confidence: 0.82,
      status: "UNDER_VERIFICATION",
      road_id: "NH-6",
      description: "Overturned goods carrier blocking uphill carriageway near Umsning.",
      image_url: "",
      reported_at: "2026-09-09T08:10:00Z"
    }
  ],

  // Warehouses (P5 Module)
  WAREHOUSES: [
    { warehouse_id: "WH_GUW_01", name: "Guwahati Central Depot", location: "Guwahati", capacity: 10000, current_utilization: 6850, product_type: "MEDICINE" },
    { warehouse_id: "WH_TEZ_02", name: "Tezpur Forward Supply Base", location: "Tezpur", capacity: 5000, current_utilization: 3200, product_type: "FOOD_RATIONS" },
    { warehouse_id: "WH_SIL_03", name: "Silchar Relief Warehouse", location: "Silchar", capacity: 4500, current_utilization: 3950, product_type: "MEDICINE" },
    { warehouse_id: "WH_DIM_04", name: "Dimapur Transit Logistics Hub", location: "Dimapur", capacity: 6000, current_utilization: 2400, product_type: "FUEL" }
  ],

  // Shipments (P5 Module)
  SHIPMENTS: [
    {
      shipment_id: "SHIP_MED_101",
      origin: "Guwahati",
      destination: "Tawang",
      cargo_type: "MEDICINE",
      quantity: 500,
      unit: "BOXES",
      priority: "CRITICAL",
      status: "ON_ROUTE",
      route_id: "ROUTE_OPT_402",
      travel_time_minutes: 420,
      route_risk: 0.28,
      eta: "2026-09-09T22:30:00Z"
    },
    {
      shipment_id: "SHIP_FOOD_102",
      origin: "Guwahati",
      destination: "Shillong",
      cargo_type: "FOOD_RATIONS",
      quantity: 1200,
      unit: "BAGS",
      priority: "HIGH",
      status: "ON_ROUTE",
      route_id: "ROUTE_OPT_108",
      travel_time_minutes: 169,
      route_risk: 0.12,
      eta: "2026-09-09T18:45:00Z"
    },
    {
      shipment_id: "SHIP_FUEL_103",
      origin: "Tezpur",
      destination: "Itanagar",
      cargo_type: "FUEL",
      quantity: 8000,
      unit: "LITERS",
      priority: "CRITICAL",
      status: "PENDING",
      route_id: "ROUTE_OPT_311",
      travel_time_minutes: 240,
      route_risk: 0.21,
      eta: "2026-09-10T11:00:00Z"
    }
  ]
};
