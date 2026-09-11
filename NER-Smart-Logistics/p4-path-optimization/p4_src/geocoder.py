"""
Geocoder — resolve place names ↔ (latitude, longitude).

Uses a built-in lookup table for NE India towns (instant, no network)
and falls back to Nominatim (OpenStreetMap) for unknown places.
"""

from __future__ import annotations

import functools
import logging
import math
import re
from typing import Tuple

try:
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GeocoderServiceError = Exception
    GeocoderTimedOut = Exception
    Nominatim = None
    GEOPY_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Well-known places in Northeast India (instant lookup) ───────────────
KNOWN_PLACES: dict[str, Tuple[float, float]] = {
    # ── Major National Gateway Hubs ──
    "delhi":          (28.6139, 77.2090),
    "new delhi":      (28.6139, 77.2090),
    "kolkata":        (22.5726, 88.3639),
    "siliguri":       (26.7271, 88.3953),
    "patna":          (25.5941, 85.1376),
    "lucknow":        (26.8467, 80.9462),
    "mumbai":         (19.0760, 72.8777),
    "dispur":         (26.1408, 91.7898),

    # ── Assam ──
    "guwahati":       (26.1445, 91.7362),
    "silchar":        (24.8333, 92.7789),
    "dibrugarh":      (27.4728, 94.9120),
    "jorhat":         (26.7509, 94.2037),
    "nagaon":         (26.3500, 92.6900),
    "tinsukia":       (27.5000, 95.3667),
    "tezpur":         (26.6338, 92.8006),
    "bongaigaon":     (26.5000, 90.5500),
    "dhubri":         (26.0200, 89.9800),
    "goalpara":       (26.1700, 90.6200),
    "barpeta":        (26.3200, 91.0000),
    "nalbari":        (26.4500, 91.4400),
    "rangiya":        (26.4500, 91.6100),
    "rangia":         (26.4500, 91.6100),
    "mangaldoi":      (26.4400, 92.0300),
    "udalguri":       (26.7500, 92.1000),
    "orang":          (26.8800, 92.7800),
    "rangapara":      (26.8400, 92.7400),
    "kaziranga":      (26.5775, 93.1711),
    "diphu":          (25.8400, 93.4300),
    "haflong":        (25.1800, 93.0300),
    "north lakhimpur":(27.2300, 94.1000),
    "sivasagar":      (26.9800, 94.6300),
    "karimganj":      (24.8700, 92.3500),

    # ── Arunachal Pradesh ──
    "itanagar":       (27.0844, 93.6053),
    "naharlagun":     (27.1000, 93.6900),
    "pasighat":       (28.0667, 95.3333),
    "tawang":         (27.5860, 91.8590),
    "bomdila":        (27.2645, 92.4003),
    "ziro":           (27.5300, 93.8300),
    "aalo":           (28.1700, 94.8000),
    "along":          (28.1700, 94.8000),
    "tezu":           (27.9200, 96.1700),
    "namsai":         (27.6700, 95.8700),
    "roing":          (28.1400, 95.8300),
    "bhalukpong":     (27.0135, 92.6498),
    "dirang":         (27.3566, 92.2374),
    "sela pass":      (27.5000, 92.1000),
    "jang":           (27.5200, 91.9500),
    "tenga":          (27.1200, 92.4200),
    "kalaktang":      (27.1200, 92.2000),
    "rupa":           (27.2000, 92.3800),

    # ── Meghalaya ──
    "shillong":       (25.5788, 91.8933),
    "cherrapunji":    (25.2986, 91.7317),
    "sohra":          (25.2986, 91.7317),
    "tura":           (25.5100, 90.2200),
    "jowai":          (25.4400, 92.2000),
    "nongpoh":        (25.9000, 91.8800),
    "baghmara":       (25.2000, 90.6300),
    "williamnagar":   (25.6000, 90.6000),

    # ── Nagaland ──
    "dimapur":        (25.9068, 93.7271),
    "kohima":         (25.6751, 94.1086),
    "mokokchung":     (26.3300, 94.5200),
    "tuensang":       (26.2800, 94.8300),
    "wokha":          (26.1000, 94.2700),
    "zunheboto":      (26.0100, 94.5200),
    "mon":            (26.7500, 95.0500),

    # ── Manipur ──
    "imphal":         (24.8170, 93.9368),
    "churachandpur":  (24.3300, 93.6800),
    "thoubal":        (24.6400, 94.0100),
    "bishnupur":      (24.6300, 93.7600),
    "ukhrul":         (25.1200, 94.3600),
    "senapati":       (25.2700, 94.0200),

    # ── Mizoram ──
    "aizawl":         (23.7271, 92.7176),
    "lunglei":        (22.8800, 92.7300),
    "champhai":       (23.4700, 93.3300),
    "kolasib":        (24.2200, 92.6800),
    "serchhip":       (23.3400, 92.8500),

    # ── Tripura ──
    "agartala":       (23.8315, 91.2868),
    "dharmanagar":    (24.3800, 92.1700),
    "udaipur":        (23.5300, 91.4800),
    "kailashahar":    (24.3300, 92.0000),
    "belonia":        (23.2500, 91.4500),

    # ── Sikkim ──
    "gangtok":        (27.3389, 88.6065),
    "namchi":         (27.1700, 88.3500),
    "geyzing":        (27.2800, 88.2500),
    "mangan":         (27.5000, 88.5300),
    "pelling":        (27.3000, 88.2300),

    # ── Major Logistics Gateways & Indian Metros ──
    "siliguri":       (26.7271, 88.3953),
    "jalpaiguri":     (26.5400, 88.7200),
    "alipurduar":     (26.4900, 89.5300),
    "cooch behar":    (26.3200, 89.4500),
    "kolkata":        (22.5726, 88.3639),
    "patna":          (25.5941, 85.1376),
    "delhi":          (28.6139, 77.2090),
    "mumbai":         (19.0760, 72.8777),
    "chennai":        (13.0827, 80.2707),
    "bengaluru":      (12.9716, 77.5946),
    "bangalore":      (12.9716, 77.5946),
    "hyderabad":      (17.3850, 78.4867),
    "lucknow":        (26.8467, 80.9462),
    "kanpur":         (26.4499, 80.3319),
    "varanasi":       (25.3176, 82.9739),
    "ranchi":         (23.3441, 85.3096),
    "bhubaneswar":    (20.2961, 85.8245),
    "jaipur":         (26.9124, 75.7873),
    "ahmedabad":      (23.0225, 72.5714),
    "chandigarh":     (30.7333, 76.7794),

    # ── All 28 Indian States & UTs (direct lookup) ──
    "bihar":             (25.5941, 85.1376),
    "west bengal":       (22.5726, 88.3639),
    "bengal":            (22.5726, 88.3639),
    "uttar pradesh":     (26.8467, 80.9462),
    "up":                (26.8467, 80.9462),
    "jharkhand":         (23.3441, 85.3096),
    "odisha":            (20.2961, 85.8245),
    "orissa":            (20.2961, 85.8245),
    "maharashtra":       (19.0760, 72.8777),
    "karnataka":         (12.9716, 77.5946),
    "tamil nadu":        (13.0827, 80.2707),
    "telangana":         (17.3850, 78.4867),
    "andhra pradesh":    (16.5062, 80.6480),
    "madhya pradesh":    (23.2599, 77.4126),
    "mp":                (23.2599, 77.4126),
    "rajasthan":         (26.9124, 75.7873),
    "punjab":            (30.7333, 76.7794),
    "haryana":           (28.4595, 77.0266),
    "gujarat":           (23.0225, 72.5714),
    "kerala":            (9.9312, 76.2673),
    "chhattisgarh":      (21.2514, 81.6296),
    "uttarakhand":       (30.3165, 78.0322),
    "himachal pradesh":  (31.1048, 77.1734),
    "jammu and kashmir": (34.0837, 74.7973),
    "kashmir":           (34.0837, 74.7973),
    "goa":               (15.4909, 73.8278),
    "assam":             (26.1445, 91.7362),
    "arunachal pradesh": (27.0844, 93.6053),
    "arunachal":         (27.0844, 93.6053),
    "meghalaya":         (25.5788, 91.8933),
    "nagaland":          (25.6751, 94.1086),
    "manipur":           (24.8170, 93.9368),
    "mizoram":           (23.7271, 92.7176),
    "tripura":           (23.8315, 91.2868),
    "sikkim":            (27.3389, 88.6065),
    "delhi ncr":         (28.6139, 77.2090),
    "new delhi":         (28.6139, 77.2090),
    "pune":              (18.5204, 73.8567),
    "surat":             (21.1702, 72.8311),
    "indore":            (22.7196, 75.8577),
    "bhopal":            (23.2599, 77.4126),
    "nagpur":            (21.1458, 79.0882),
    "visakhapatnam":     (17.6868, 83.2185),
    "vizag":             (17.6868, 83.2185),
    "vadodara":          (22.3072, 73.1812),
    "ludhiana":          (30.9010, 75.8573),
    "agra":              (27.1767, 78.0081),
    "nashik":            (19.9975, 73.7898),
    "meerut":            (28.9845, 77.7064),
    "rajkot":            (22.3039, 70.8022),
    "srinagar":          (34.0837, 74.7973),
    "amritsar":          (31.6340, 74.8723),
    "allahabad":         (25.4358, 81.8463),
    "prayagraj":         (25.4358, 81.8463),
    "howrah":            (22.5958, 88.2636),
    "coimbatore":        (11.0168, 76.9558),
    "jabalpur":          (23.1815, 79.9864),
    "gwalior":           (26.2183, 78.1828),
    "vijayawada":        (16.5062, 80.6480),
    "jodhpur":           (26.2389, 73.0243),
    "madurai":           (9.9252, 78.1198),
    "raipur":            (21.2514, 81.6296),
    "kota":              (25.2138, 75.8648),
    "dehradun":          (30.3165, 78.0322),
    "shimla":            (31.1048, 77.1734),
    "haridwar":          (29.9457, 78.1642),
    "rishikesh":         (30.0869, 78.2676),
    "nainital":          (29.3919, 79.4542),
    "bhimtal":           (29.3500, 79.5667),
    "bhowali":           (29.3833, 79.5167),
    "haldwani":          (29.2183, 79.5130),
    "kathgodam":         (29.2700, 79.5500),
    "almora":            (29.5971, 79.6591),
    "ranikhet":          (29.6434, 79.4322),
    "ramnagar":          (29.3970, 79.1250),
    "pantnagar":         (29.0200, 79.4800),
    "rudrapur":          (28.9800, 79.4000),
    "mussoorie":         (30.4598, 78.0664),
    "manali":            (32.2396, 77.1887),
    "dharamshala":       (32.2190, 76.3234),
    "dhanbad":           (23.7957, 86.4304),
    "jamshedpur":        (22.8046, 86.2029),

    # ── Kerala & South India Hubs ──
    "kochi":             (9.9312, 76.2673),
    "cochin":            (9.9312, 76.2673),
    "trivandrum":        (8.5241, 76.9366),
    "thiruvananthapuram":(8.5241, 76.9366),
    "kozhikode":         (11.2588, 75.7804),
    "calicut":           (11.2588, 75.7804),
    "thrissur":          (10.5276, 76.2144),
    "kannur":            (11.8745, 75.3704),
    "kottayam":          (9.5916, 76.5222),
    "alappuzha":         (9.4981, 76.3388),
    "palakkad":          (10.7867, 76.6548),

    # ── Jammu & Kashmir, Ladakh ──
    "leh":               (34.1526, 77.5771),
    "ladakh":            (34.1526, 77.5771),
    "kargil":            (34.5539, 76.1349),
    "drass":             (34.4286, 75.7725),
    "nubra":             (34.6863, 77.5673),
    "gulmarg":           (34.0484, 74.3805),
    "pahalgam":          (34.0163, 75.3150),
    "anantnag":          (33.7311, 75.1485),

    # ── Karnataka ──
    "mysuru":            (12.2958, 76.6394),
    "mysore":            (12.2958, 76.6394),
    "mangaluru":         (12.9141, 74.8560),
    "mangalore":         (12.9141, 74.8560),
    "hubballi":          (15.3647, 75.1240),
    "hubli":             (15.3647, 75.1240),
    "belagavi":          (15.8497, 74.4977),
    "belgaum":           (15.8497, 74.4977),
    "shivamogga":        (13.9299, 75.5681),
    "shimoga":           (13.9299, 75.5681),
    "tumakuru":          (13.3379, 77.1173),
    "ballari":           (15.1394, 76.9214),

    # ── Andhra Pradesh & Telangana ──
    "tirupati":          (13.6288, 79.4192),
    "kakinada":          (16.9891, 82.2475),
    "nellore":           (14.4426, 79.9865),
    "kurnool":           (15.8281, 78.0373),
    "guntur":            (16.3067, 80.4365),
    "rajahmundry":       (17.0005, 81.8040),
    "warangal":          (17.9689, 79.5941),
    "nizamabad":         (18.6725, 78.0941),

    # ── Tamil Nadu ──
    "salem":             (11.6643, 78.1460),
    "tiruchirappalli":   (10.7905, 78.7047),
    "trichy":            (10.7905, 78.7047),
    "tirunelveli":       (8.7139, 77.7567),
    "vellore":           (12.9165, 79.1325),
    "erode":             (11.3410, 77.7172),
    "thanjavur":         (10.7870, 79.1378),
    "thoothukudi":       (8.7642, 78.1348),

    # ── Rajasthan ──
    "udaipur":           (24.5854, 73.7125),
    "bikaner":           (28.0229, 73.3119),
    "jaisalmer":         (26.9157, 70.9083),
    "ajmer":             (26.4499, 74.6399),
    "alwar":             (27.5530, 76.6346),
    "bhilwara":          (25.3463, 74.6364),

    # ── Punjab & Haryana ──
    "jalandhar":         (31.3260, 75.5762),
    "patiala":           (30.3398, 76.3869),
    "bathinda":          (30.2110, 74.9455),
    "pathankot":         (32.2643, 75.6421),
    "gurugram":          (28.4595, 77.0266),
    "gurgaon":           (28.4595, 77.0266),
    "faridabad":         (28.4089, 77.3178),
    "panipat":           (29.3909, 76.9635),
    "ambala":            (30.3782, 76.7767),
    "rohtak":            (28.8955, 76.6066),
    "hisar":             (29.1492, 75.7217),
    "karnal":            (29.6857, 76.9905),

    # ── Uttar Pradesh & Bihar ──
    "noida":             (28.5355, 77.3910),
    "greater noida":     (28.4744, 77.5040),
    "ghaziabad":         (28.6692, 77.4538),
    "bareilly":          (28.3670, 79.4304),
    "aligarh":           (27.8974, 78.0880),
    "moradabad":         (28.8386, 78.7733),
    "gorakhpur":         (26.7606, 83.3732),
    "mathura":           (27.4924, 77.6737),
    "jhansi":            (25.4484, 78.5685),
    "gaya":              (24.7955, 85.0002),
    "muzaffarpur":       (26.1209, 85.3647),
    "bhagalpur":         (25.2425, 86.9842),
    "darbhanga":         (26.1542, 85.8918),
    "purnia":            (25.7771, 87.4753),

    # ── Odisha, Jharkhand & Chhattisgarh ──
    "cuttack":           (20.4625, 85.8828),
    "puri":              (19.8135, 85.8312),
    "rourkela":          (22.2604, 84.8536),
    "sambalpur":         (21.4669, 83.9812),
    "balasore":          (21.4934, 86.9135),
    "bokaro":            (23.6693, 86.1511),
    "hazaribagh":        (23.9961, 85.3637),
    "deoghar":           (24.4826, 86.6977),
    "bilaspur":          (22.0797, 82.1391),
    "durg":              (21.1904, 81.2849),
    "bhilai":            (21.2167, 81.4333),
    "korba":             (22.3595, 82.7501),

    # ── Madhya Pradesh & Gujarat ──
    "ujjain":            (23.1765, 75.7885),
    "sagar":             (23.8388, 78.7378),
    "satna":             (24.6005, 80.8322),
    "rewar":             (24.5362, 81.3037),
    "gwalior":           (26.2183, 78.1828),
    "junagadh":          (21.5222, 70.4579),
    "gandhinagar":       (23.2156, 72.6369),
    "jamnagar":          (22.4707, 70.0577),
    "bhavnagar":         (21.7645, 72.1519),

    # ── Maharashtra ──
    "aurangabad":        (19.8762, 75.3433),
    "chhatrapati sambhajinagar": (19.8762, 75.3433),
    "solapur":           (17.6599, 75.9064),
    "kolhapur":          (16.7050, 74.2433),
    "amravati":          (20.9374, 77.7796),
    "nanded":            (19.1383, 77.3210),
    "latur":             (18.4088, 76.5604),
    "ratnagiri":         (16.9902, 73.3120),

    # ── UTs & Islands ──
    "port blair":        (11.6234, 92.7265),
    "andaman":           (11.6234, 92.7265),
    "silvassa":          (20.2763, 73.0083),
    "daman":             (20.3974, 72.8328),
    "diu":               (20.7144, 70.9874),
    "kavaratti":         (10.5669, 72.6420),
    "lakshadweep":       (10.5669, 72.6420),
    "puducherry":        (11.9416, 79.8083),
    "pondicherry":       (11.9416, 79.8083),

    "silchar, assam":    (24.8333, 92.7789),
    "guwahati, assam":   (26.1445, 91.7362),
    "shillong, meghalaya":(25.5788, 91.8933),
    "imphal, manipur":   (24.8170, 93.9368),
    "kohima, nagaland":  (25.6751, 94.1086),
    "aizawl, mizoram":   (23.7271, 92.7176),
    "agartala, tripura": (23.8315, 91.2868),
    "gangtok, sikkim":   (27.3389, 88.6065),
    "itanagar, arunachal pradesh": (27.0844, 93.6053),
}


_geolocator: Nominatim | None = None


def _get_geolocator() -> Nominatim:
    global _geolocator
    if _geolocator is None:
        _geolocator = Nominatim(user_agent="ner-smart-logistics-p4-routing")
    return _geolocator


def _photon_geocode(query: str) -> Tuple[float, float] | None:
    """Free, fast fallback geocoding using OSM-backed Photon API."""
    import urllib.parse
    import httpx
    try:
        url = f"https://photon.komoot.io/api/?q={urllib.parse.quote(query)}&limit=1"
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                if features:
                    coords = features[0].get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        lon, lat = float(coords[0]), float(coords[1])
                        logger.info("Geocoded '%s' via Photon: (%s, %s)", query, lat, lon)
                        return (lat, lon)
    except Exception as exc:
        logger.warning("Photon geocode failed for '%s': %s", query, exc)
    return None


@functools.lru_cache(maxsize=400)
def geocode(place_name: str) -> Tuple[float, float]:
    """
    Resolve *place_name* → ``(latitude, longitude)``.
    Works for any city, town, district, or state across Northeast India and all of India.
    Handles 'City, State' formats, local caches, Nominatim, and Photon API.
    """
    cleaned = place_name.strip()
    key = cleaned.lower()

    # 1. Direct local cache match
    if key in KNOWN_PLACES:
        logger.info("Geocoded '%s' from local cache: %s", place_name, KNOWN_PLACES[key])
        return KNOWN_PLACES[key]

    # 2. Extract city/state parts for 'City, State' or 'City - State' patterns
    parts = [p.strip().lower() for p in re.split(r"[,/–—\-]+", cleaned) if p.strip()]
    if parts:
        # Check first part (city/town name)
        first_part = parts[0]
        if first_part in KNOWN_PLACES:
            logger.info("Geocoded '%s' via prefix '%s' from local cache: %s", place_name, first_part, KNOWN_PLACES[first_part])
            return KNOWN_PLACES[first_part]
        # Check last part (state name) if user entered only state or reverse
        if len(parts) > 1 and parts[-1] in KNOWN_PLACES and parts[-1] != "india":
            # If the first part is unknown but state is known, we still prefer accurate city lookup via geocoders first
            pass

    # 3. Nominatim lookup across India
    search_queries = [
        f"{cleaned}, India" if "india" not in key else cleaned,
        cleaned,
    ]
    if len(parts) > 1:
        # Also try "City State, India"
        search_queries.append(f"{parts[0]} {parts[1]}, India")

    if GEOPY_AVAILABLE and _get_geolocator() is not None:
        for query in search_queries:
            try:
                loc = _get_geolocator().geocode(query, timeout=6)
                if loc:
                    coords = (loc.latitude, loc.longitude)
                    logger.info("Geocoded '%s' via Nominatim (%s): %s", place_name, query, coords)
                    return coords
            except (GeocoderTimedOut, GeocoderServiceError) as exc:
                logger.warning("Nominatim error for '%s' (%s): %s", place_name, query, exc)

    # 4. Photon API fallback (OpenStreetMap global search)
    for query in search_queries:
        coords = _photon_geocode(query)
        if coords:
            return coords

    # 5. Last resort fallback: if a state component is recognized in KNOWN_PLACES
    for p in parts:
        if p in KNOWN_PLACES:
            logger.warning("Falling back to state/region center for '%s' -> '%s'", place_name, p)
            return KNOWN_PLACES[p]

    raise ValueError(
        f"Could not geocode '{place_name}'. "
        "Please specify a valid city, state, or location name in India."
    )


KNOWN_STATES: dict[str, str] = {
    "guwahati": "Assam", "silchar": "Assam", "dibrugarh": "Assam", "jorhat": "Assam", "nagaon": "Assam", "tezpur": "Assam", "bongaigaon": "Assam", "dispur": "Assam", "barpeta": "Assam", "dhubri": "Assam", "goalpara": "Assam", "nalbari": "Assam", "rangiya": "Assam", "rangia": "Assam", "mangaldoi": "Assam", "udalguri": "Assam", "kaziranga": "Assam", "diphu": "Assam", "haflong": "Assam", "north lakhimpur": "Assam", "sivasagar": "Assam", "karimganj": "Assam", "tinsukia": "Assam",
    "itanagar": "Arunachal Pradesh", "naharlagun": "Arunachal Pradesh", "pasighat": "Arunachal Pradesh", "tawang": "Arunachal Pradesh", "bomdila": "Arunachal Pradesh", "ziro": "Arunachal Pradesh", "aalo": "Arunachal Pradesh", "along": "Arunachal Pradesh", "tezu": "Arunachal Pradesh", "namsai": "Arunachal Pradesh", "roing": "Arunachal Pradesh", "bhalukpong": "Arunachal Pradesh", "dirang": "Arunachal Pradesh", "sela pass": "Arunachal Pradesh", "jang": "Arunachal Pradesh", "tenga": "Arunachal Pradesh",
    "shillong": "Meghalaya", "cherrapunji": "Meghalaya", "sohra": "Meghalaya", "tura": "Meghalaya", "jowai": "Meghalaya", "nongpoh": "Meghalaya", "baghmara": "Meghalaya", "williamnagar": "Meghalaya",
    "dimapur": "Nagaland", "kohima": "Nagaland", "mokokchung": "Nagaland", "tuensang": "Nagaland",
    "imphal": "Manipur", "churachandpur": "Manipur", "moreh": "Manipur", "ukhrul": "Manipur",
    "gangtok": "Sikkim", "pelling": "Sikkim", "namchi": "Sikkim", "nathu la": "Sikkim",
    "agartala": "Tripura", "dharmanagar": "Tripura", "udaipur": "Tripura",
    "aizawl": "Mizoram", "lunglei": "Mizoram", "champhai": "Mizoram",
    "delhi": "Delhi", "new delhi": "Delhi", "kolkata": "West Bengal", "siliguri": "West Bengal", "patna": "Bihar", "lucknow": "Uttar Pradesh", "mumbai": "Maharashtra", "dehradun": "Uttarakhand", "agra": "Uttar Pradesh"
}


def reverse_geocode(lat: float, lng: float) -> str:
    """Return the name of the place at *(lat, lng)* with clean English names."""
    best_known = None
    best_raw_key = None
    best_dist = float("inf")
    for name, (plat, plng) in KNOWN_PLACES.items():
        d = math.sqrt((lat - plat) ** 2 + (lng - plng) ** 2)
        if d < best_dist:
            best_dist = d
            best_raw_key = name
            best_known = name.replace("_", " ").title()

    if best_known and best_dist < 0.16:
        state = KNOWN_STATES.get(best_raw_key, "")
        if state:
            return f"{best_known}, {state}"
        return best_known

    if GEOPY_AVAILABLE and _get_geolocator() is not None:
        try:
            geo = _get_geolocator()
            location = geo.reverse((lat, lng), exactly_one=True, timeout=3, language="en")
            if location and location.raw and "address" in location.raw:
                addr = location.raw["address"]
                city = (
                    addr.get("city")
                    or addr.get("town")
                    or addr.get("village")
                    or addr.get("municipality")
                    or addr.get("suburb")
                    or addr.get("county")
                    or addr.get("state_district")
                )
                state = addr.get("state")
                if city and state:
                    return f"{city}, {state}"
                elif city:
                    return city
                elif state:
                    return state
        except Exception as exc:
            logger.debug("Nominatim reverse geocode error: %s", exc)

    if best_known:
        state = KNOWN_STATES.get(best_raw_key, "")
        if state:
            return f"{best_known}, {state}"
        return best_known
    return f"{lat:.4f}°N, {lng:.4f}°E"

