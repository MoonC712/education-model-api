from __future__ import annotations

import json
from urllib.request import urlopen


BASE = "http://127.0.0.1:8000"
for endpoint in ["/health", "/api/summary", "/api/interventions"]:
    with urlopen(BASE + endpoint, timeout=10) as response:
        payload = json.load(response)
    print(endpoint, "OK", str(payload)[:180])
