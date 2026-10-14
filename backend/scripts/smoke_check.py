"""Smoke-test every endpoint of a running RulePilot server (no Gemini key needed).

Usage: python scripts/smoke_check.py [BASE_URL] [--review]

--review approves and then rejects a recorded run to exercise the governance flow.
It writes review and audit records, so do not use it against the demo deployment.
"""
import json
import sys
import urllib.error
import urllib.request

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
REVIEW = "--review" in sys.argv
BASE = (ARGS[0] if ARGS else "http://127.0.0.1:8080").rstrip("/")
results = []


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            ctype = r.headers.get("content-type", "")
            return r.status, (json.loads(raw) if "json" in ctype else raw.decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""))


s, b = call("GET", "/health"); check("GET /health", s == 200 and b.get("status") == "ok", str(b))
s, b = call("GET", "/api/v1/info"); check("GET /api/v1/info", s == 200, str(b)[:120])
s, b = call("GET", "/"); check("GET / serves dashboard", s == 200 and "<div id=\"root\"" in b)
s, b = call("GET", "/investigations/some/deep/link"); check("SPA fallback", s == 200 and "<div id=\"root\"" in b)
s, b = call("GET", "/../../etc/passwd"); check("No path traversal", s in (200, 404) and "root:" not in str(b))
s, b = call("GET", "/docs"); check("GET /docs", s == 200)
s, b = call("GET", "/api/v1/datasets"); check("GET datasets", s == 200, str([d.get("dataset_id") for d in b.get("items", b if isinstance(b, list) else [])]) if s == 200 else str(b))
s, b = call("GET", "/api/v1/rules"); check("GET rules", s == 200)
baseline = b["items"][0] if s == 200 and "items" in b else None

cand = {"rule_id": "TEAM-AMOUNT-001", "name": "High amount review", "description": "Flags high amounts.",
        "rationale": "Example.", "conditions": [{"field": "amount", "operator": "greater_than", "value": 1250}],
        "logical_operator": "and", "status": "draft", "version": 1, "created_by": "analyst"}
s, b = call("POST", "/api/v1/rules/evaluate", {"rule": cand}); check("POST rules/evaluate", s == 200, str(b)[:150] if s != 200 else "")
s, b = call("POST", "/api/v1/backtests/run", {"candidate_rule": cand, "seed": 41}); check("POST backtests/run", s == 200, str(b)[:150] if s != 200 else "")
s, b = call("POST", "/api/v1/rules/discover", {"seed": 41}); check("POST rules/discover", s == 200, str(b)[:150] if s != 200 else "")
bad = dict(cand, conditions=[{"field": "__import__", "operator": "greater_than", "value": 1}])
s, b = call("POST", "/api/v1/backtests/run", {"candidate_rule": bad, "seed": 41}); check("Malformed rule rejected (422)", s == 422)

s, b = call("GET", "/api/v1/advisories"); check("GET advisories", s == 200, str([i["advisory_id"] for i in b["items"]]))
s, b = call("GET", "/api/v1/agent/status"); check("GET agent/status (no key)", s == 200 and b["configured"] is False, str(b))
s, b = call("POST", "/api/v1/investigations", {"advisory_id": "jpm-card-testing"}); check("POST investigation without key -> 503", s == 503, str(b))
s, b = call("POST", "/api/v1/investigations", {"advisory_id": "nope"}); check("Unknown advisory -> 404", s == 404)

s, invs = call("GET", "/api/v1/investigations"); check("GET investigations (recorded)", s == 200 and len(invs) >= 3,
                                                     str([(i.get("investigation_id"), i.get("status")) for i in invs]))
for inv in invs:
    s, b = call("GET", f"/api/v1/investigations/{inv['investigation_id']}")
    check(f"GET investigation {inv['investigation_id'][:30]}", s == 200)
s, b = call("GET", "/api/v1/investigations/does-not-exist"); check("Missing investigation -> 404", s == 404)

s, cat0 = call("GET", "/api/v1/rule-catalog"); check("GET rule-catalog", s == 200,
                                                   f"active={len(cat0['active'])} approved={len(cat0['approved_not_active'])}")
pending = [i for i in invs if i.get("status") == "pending_human_review"]
if not REVIEW:
    print("SKIP governance write flow (pass --review to run it)")
elif pending:
    iid = pending[0]["investigation_id"]
    s, b = call("POST", f"/api/v1/investigations/{iid}/review",
                {"decision": "approve", "reviewer": "smoke-test", "comment": "Keep rule-set FPR under 1%"})
    check("Approve pending investigation", s == 200 and b.get("activation") == "not_activated", str(b)[:200])
    s, cat1 = call("GET", "/api/v1/rule-catalog")
    check("Approved rule joins catalog, not active", len(cat1["approved_not_active"]) == len(cat0["approved_not_active"]) + 1
          and len(cat1["active"]) == len(cat0["active"]))
    s, aud = call("GET", f"/api/v1/audit?investigation_id={iid}"); check("Audit records the review", s == 200 and len(aud) >= 1, f"{len(aud)} events")
    s, b = call("POST", f"/api/v1/investigations/{iid}/review",
                {"decision": "reject", "reviewer": "smoke-test", "comment": "reset"})
    check("Reject after approval", s in (200, 409), f"{s} {str(b)[:150]}")
    s, cat2 = call("GET", "/api/v1/rule-catalog")
    check("Catalog after reject", s == 200, f"approved={len(cat2['approved_not_active'])}")
else:
    check("Found a pending_human_review investigation to review", False)
s, b = call("POST", "/api/v1/investigations/x/review", {"decision": "approved", "reviewer": "a", "comment": "b", "extra": 1})
check("Review with extra field rejected (422)", s == 422)
s, b = call("GET", "/api/v1/audit"); check("GET audit (all)", s == 200, f"{len(b)} events")

print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
