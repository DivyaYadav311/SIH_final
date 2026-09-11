from typing import List, Dict, Tuple
from p3_src.schemas import RoadSegment, HazardContext, Incident, AnalyzedRoad, Factors

class RiskEngine:
    def __init__(self):
        # We can add model loading here later if needed
        self.model_version = "road-risk-v1-baseline"
        
    def _determine_risk_level(self, probability: float) -> str:
        if probability < 0.25:
            return "low"
        elif probability < 0.50:
            return "moderate"
        elif probability < 0.75:
            return "high"
        else:
            return "critical"
            
    def _determine_recommended_status(self, risk_level: str) -> str:
        if risk_level == "low":
            return "normal"
        elif risk_level == "moderate":
            return "caution"
        elif risk_level == "high":
            return "avoid_if_possible"
        else:
            return "closed_or_severely_disrupted"

    def analyze(self, 
                roads: List[RoadSegment], 
                hazards: List[HazardContext], 
                incidents: List[Incident]) -> List[AnalyzedRoad]:
        
        # Create lookup maps for faster processing
        hazard_map = {h.road_id: h for h in hazards}
        incident_map: Dict[str, List[Incident]] = {}
        for inc in incidents:
            if inc.status == "active":
                if inc.road_id not in incident_map:
                    incident_map[inc.road_id] = []
                incident_map[inc.road_id].append(inc)
                
        analyzed_roads = []
        
        for road in roads:
            hazard = hazard_map.get(road.road_id)
            road_incidents = incident_map.get(road.road_id, [])
            
            # 1. Feature Engineering
            flood_prob = hazard.flood_probability if hazard else 0.0
            landslide_prob = hazard.landslide_probability if hazard else 0.0
            
            active_incident_count = len(road_incidents)
            max_incident_severity = max([inc.severity for inc in road_incidents]) if road_incidents else 0
            
            factors = Factors(
                flood_probability=flood_prob,
                landslide_probability=landslide_prob,
                active_incident_count=active_incident_count,
                max_incident_severity=max_incident_severity
            )
            
            # 2. Rule-based baseline prediction
            # Base disruption from hazards (combining probabilities independent events)
            base_hazard_disruption = 1.0 - ((1.0 - flood_prob) * (1.0 - landslide_prob))
            
            # Impact of incidents
            incident_disruption = min(max_incident_severity * 0.15 + (active_incident_count * 0.05), 1.0)
            
            # Road vulnerability factor (very basic)
            vulnerability = 1.0
            if road.road_class in ["primary", "motorway", "trunk"]:
                vulnerability = 0.8 # Better infrastructure
            elif road.surface in ["unpaved", "dirt", "gravel"]:
                vulnerability = 1.2 # Worse infrastructure
                
            # Combine to get disruption probability
            raw_disruption = (base_hazard_disruption * 0.6 + incident_disruption * 0.4) * vulnerability
            disruption_probability = max(0.0, min(1.0, raw_disruption))
            
            # 3. Accessibility Score
            # Starts at 100, reduces based on disruption and road characteristics
            base_accessibility = 100.0 * (1.0 - disruption_probability)
            
            # Penalty for missing/poor infrastructure
            if road.lanes and road.lanes < 2:
                base_accessibility *= 0.9
            if road.surface in ["unpaved", "dirt"]:
                base_accessibility *= 0.8
                
            accessibility_score = max(0.0, min(100.0, base_accessibility))
            
            # 4. Explanations and Metadata
            risk_level = self._determine_risk_level(disruption_probability)
            recommended_status = self._determine_recommended_status(risk_level)
            
            explanations = []
            if flood_prob > 0.5:
                explanations.append(f"High flood probability ({flood_prob:.2f})")
            if landslide_prob > 0.5:
                explanations.append(f"High landslide probability ({landslide_prob:.2f})")
            if active_incident_count > 0:
                explanations.append(f"{active_incident_count} active incident(s) with max severity {max_incident_severity}")
            if len(explanations) == 0:
                explanations.append("Normal conditions")
                
            analyzed_road = AnalyzedRoad(
                road_id=road.road_id,
                disruption_probability=round(disruption_probability, 4),
                accessibility_score=round(accessibility_score, 1),
                risk_level=risk_level,
                confidence=0.7, # Mock confidence for baseline
                recommended_status=recommended_status,
                factors=factors,
                explanation=explanations
            )
            analyzed_roads.append(analyzed_road)
            
        return analyzed_roads
