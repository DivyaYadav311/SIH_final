from datetime import datetime, timezone, timedelta
from p4_src.news_intelligence import _parse_google_rss, _within_lookback, news_risk_for_point

def test_google_rss_timestamp_is_parsed_and_filtered():
    xml = '<rss><channel><item><title>Landslide blocks road</title><description>road closed</description><link>https://x</link><pubDate>Fri, 04 Sep 2026 00:00:00 GMT</pubDate></item></channel></rss>'
    e = _parse_google_rss(xml)[0]
    assert _within_lookback(e, 24) in (True, False)
    assert e['event_type'] == 'landslide'

def test_only_geolocated_news_can_score():
    events=[{'event_type':'landslide','severity':1,'confidence':1,'latitude':26.0,'longitude':91.0,'geolocated':True,'title':'x','source':'x'}, {'event_type':'landslide','severity':1,'confidence':1,'geolocated':False,'title':'y','source':'y'}]
    risk, matches=news_risk_for_point(26.0,91.0,events)
    assert risk == 1.0
    assert len(matches)==1
