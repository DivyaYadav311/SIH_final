import httpx
import json

url = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": "29.3919,26.1445",
    "longitude": "79.4542,91.7362",
    "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m"
}

r = httpx.get(url, params=params)
print("LIVE OPEN-METEO WEATHER RESPONSE:")
print(json.dumps(r.json(), indent=2))
