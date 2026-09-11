import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "p4-path-optimization"))

from p4_src.news_intelligence import fetch_live_disaster_news

print("=== FETCHING LIVE NEWS FOR Guwahati -> Shillong ===")
events1 = fetch_live_disaster_news("Guwahati", "Shillong", (26.1445, 91.7362), (25.5788, 91.8933))
print(f"Total events found: {len(events1)}")
for ev in events1[:5]:
    title = str(ev.get('title')).encode('ascii', 'ignore').decode('ascii')
    url = ev.get('url')
    print(f"- Title: {title}")
    print(f"  URL: {url}")
    print(f"  Source: {ev.get('source')} | Provider: {ev.get('provider')}")

print("\n=== FETCHING LIVE NEWS FOR Dehradun -> Nainital ===")
events2 = fetch_live_disaster_news("Dehradun", "Nainital", (30.3165, 78.0322), (29.3919, 79.4542))
print(f"Total events found: {len(events2)}")
for ev in events2[:5]:
    title = str(ev.get('title')).encode('ascii', 'ignore').decode('ascii')
    url = ev.get('url')
    print(f"- Title: {title}")
    print(f"  URL: {url}")
    print(f"  Source: {ev.get('source')} | Provider: {ev.get('provider')}")
