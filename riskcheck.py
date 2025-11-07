#!/usr/bin/env python3
"""
RiskCheck: quick URL/domain/email risk triage
- Aggregates signals from VirusTotal, Google Safe Browsing, and Have I Been Pwned (optional - keys required)
- Performs DNS checks for SPF/DMARC (no key required)
- Produces a simple risk score and a JSON/CSV report

USAGE
  python riskcheck.py --input example_inputs.csv --out report.json --csv report.csv
  python riskcheck.py --url https://suspicious.example --email ceo@contoso.com --domain contoso.com

ENV VARS
  VT_API_KEY            VirusTotal API key (optional but recommended)
  GSB_API_KEY           Google Safe Browsing API key (optional)
  HIBP_API_KEY          Have I Been Pwned API key (optional)
  HIBP_TRUSTED_QUERY    "1" to enable elevated HIBP email search (if your key allows)

DEPENDENCIES
  pip install -r requirements.txt
"""
import argparse, os, sys, json, csv, time, re
import requests
import tldextract
import dns.resolver

RISK_THRESHOLDS = {
    "high": 8,
    "medium": 4
}

def safe_getenv(name, default=None):
    v = os.getenv(name, default)
    return v if v not in ("", None) else default

VT_API_KEY  = safe_getenv("VT_API_KEY")
GSB_API_KEY = safe_getenv("GSB_API_KEY")
HIBP_API_KEY = safe_getenv("HIBP_API_KEY")
HIBP_TRUSTED = safe_getenv("HIBP_TRUSTED_QUERY") == "1"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def extract_domain(value:str):
    if not value:
        return None
    ext = tldextract.extract(value)
    if not ext.registered_domain:
        return None
    return ext.registered_domain

def dns_txt_records(name):
    try:
        answers = dns.resolver.resolve(name, 'TXT', lifetime=5)
        return [b"".join(r.strings).decode("utf-8", errors="ignore") for r in answers]
    except Exception:
        return []

def has_spf(domain):
    for txt in dns_txt_records(domain):
        if txt.lower().startswith("v=spf1"):
            return True, txt
    return False, None

def get_dmarc(domain):
    dmarc_domain = f"_dmarc.{domain}"
    for txt in dns_txt_records(dmarc_domain):
        if txt.lower().startswith("v=dmarc1"):
            return txt
    return None

def vt_domain_report(domain):
    if not VT_API_KEY:
        return {"available": False, "score": 0, "detail": "no VT_API_KEY set"}
    try:
        url = f"https://www.virustotal.com/api/v3/domains/{domain}"
        r = requests.get(url, headers={"x-apikey": VT_API_KEY}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            cats = data.get("data",{}).get("attributes",{}).get("last_analysis_stats",{})
            # count engines that marked malicious/suspicious
            bad = int(cats.get("malicious",0)) + int(cats.get("suspicious",0))
            score = 0
            if bad >= 10:
                score = 6
            elif bad >= 5:
                score = 4
            elif bad >= 1:
                score = 2
            return {"available": True, "score": score, "detail": {"bad_engines": bad, "stats": cats}}
        return {"available": True, "score": 0, "detail": f"http {r.status_code}"}
    except Exception as e:
        return {"available": True, "score": 0, "detail": f"error {e}"}

def vt_url_report(url):
    if not VT_API_KEY:
        return {"available": False, "score": 0, "detail": "no VT_API_KEY set"}
    try:
        # VT requires URL to be base64-url-safe; using v3 analyze via re-scan shortcut:
        resp = requests.post("https://www.virustotal.com/api/v3/urls",
                             headers={"x-apikey": VT_API_KEY},
                             data={"url": url},
                             timeout=15)
        if resp.status_code in (200, 201):
            rid = resp.json()["data"]["id"]
            r = requests.get(f"https://www.virustotal.com/api/v3/analyses/{rid}",
                             headers={"x-apikey": VT_API_KEY}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                stats = data.get("data",{}).get("attributes",{}).get("stats",{})
                bad = int(stats.get("malicious",0)) + int(stats.get("suspicious",0))
                score = 0
                if bad >= 10:
                    score = 6
                elif bad >= 5:
                    score = 4
                elif bad >= 1:
                    score = 2
                return {"available": True, "score": score, "detail": {"bad_engines": bad, "stats": stats}}
        return {"available": True, "score": 0, "detail": f"http {resp.status_code}"}
    except Exception as e:
        return {"available": True, "score": 0, "detail": f"error {e}"}

def gsb_check_url(url):
    if not GSB_API_KEY:
        return {"available": False, "score": 0, "detail": "no GSB_API_KEY set"}
    try:
        endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GSB_API_KEY}"
        payload = {
            "client": {"clientId": "riskcheck", "clientVersion": "1.0"},
            "threatInfo": {
                "threatTypes": ["MALWARE","SOCIAL_ENGINEERING","UNWANTED_SOFTWARE","POTENTIALLY_HARMFUL_APPLICATION"],
                "platformTypes": ["ANY_PLATFORM"],
                "threatEntryTypes": ["URL"],
                "threatEntries": [{"url": url}]
            }
        }
        r = requests.post(endpoint, json=payload, timeout=15)
        if r.status_code == 200:
            matches = r.json().get("matches", [])
            score = 4 if matches else 0
            return {"available": True, "score": score, "detail": matches}
        return {"available": True, "score": 0, "detail": f"http {r.status_code}"}
    except Exception as e:
        return {"available": True, "score": 0, "detail": f"error {e}"}

def hibp_email(email):
    if not HIBP_API_KEY:
        return {"available": False, "score": 0, "detail": "no HIBP_API_KEY set"}
    headers = {"hibp-api-key": HIBP_API_KEY, "user-agent": "riskcheck/1.0"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    params = {"truncateResponse": "true"}
    if HIBP_TRUSTED:
        params["includeUnverified"] = "true"
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            breaches = r.json()
            # score modestly for breach exposure
            score = 3 if breaches else 0
            return {"available": True, "score": score, "detail": breaches}
        elif r.status_code == 404:
            return {"available": True, "score": 0, "detail": []}
        else:
            return {"available": True, "score": 0, "detail": f"http {r.status_code}"}
    except Exception as e:
        return {"available": True, "score": 0, "detail": f"error {e}"}

def score_email_auth(domain):
    spf_ok, spf_txt = has_spf(domain)
    dmarc_txt = get_dmarc(domain)
    score = 0
    notes = []
    if not spf_ok:
        score += 2
        notes.append("SPF missing")
    if not dmarc_txt:
        score += 3
        notes.append("DMARC missing")
    else:
        # Light heuristic: reject/quarantine policies are safer than none
        pol = None
        for part in dmarc_txt.split(";"):
            part = part.strip().lower()
            if part.startswith("p="):
                pol = part.split("=",1)[1]
                break
        if pol in ("reject","quarantine"):
            score += 0
            notes.append(f"DMARC policy {pol}")
        else:
            score += 1
            notes.append(f"DMARC policy {pol or 'none'}")
    return score, {"spf": spf_txt or "none", "dmarc": dmarc_txt or "none", "notes": notes}

def compute_overall_score(signals):
    # Sum with cap to keep sane ranges
    total = 0
    for s in signals:
        total += max(0, int(s))
    return min(20, total)

def risk_level(score):
    if score >= RISK_THRESHOLDS["high"]:
        return "high"
    if score >= RISK_THRESHOLDS["medium"]:
        return "medium"
    return "low"

def analyze_item(item):
    """
    item: dict with optional keys: url, domain, email
    """
    result = {"input": item, "signals": {}, "score": 0, "level": "low"}

    # Normalize domain
    dom = item.get("domain")
    if not dom:
        if item.get("url"):
            dom = extract_domain(item["url"])
        elif item.get("email"):
            dom = extract_domain(item["email"].split("@")[-1])
    if dom:
        result["signals"]["domain"] = {"value": dom}

    # VirusTotal (domain or url)
    vt_score = 0
    if item.get("url"):
        vt = vt_url_report(item["url"])
        result["signals"]["vt_url"] = vt
        vt_score += vt["score"]
    if dom:
        vt_d = vt_domain_report(dom)
        result["signals"]["vt_domain"] = vt_d
        vt_score += vt_d["score"]

    # Google Safe Browsing
    gsb_score = 0
    if item.get("url"):
        gsb = gsb_check_url(item["url"])
        result["signals"]["gsb"] = gsb
        gsb_score += gsb["score"]

    # Email auth & HIBP (if email present or deduced domain)
    auth_score = 0
    if dom:
        a_score, a_detail = score_email_auth(dom)
        result["signals"]["email_auth"] = {"score": a_score, "detail": a_detail}
        auth_score += a_score

    hibp_score = 0
    if item.get("email") and EMAIL_RE.match(item["email"]):
        hibp = hibp_email(item["email"])
        result["signals"]["hibp"] = hibp
        hibp_score += hibp["score"]
    elif item.get("email"):
        result["signals"]["hibp"] = {"available": True, "score": 0, "detail": "invalid email format"}

    # Overall
    score = compute_overall_score([vt_score, gsb_score, auth_score, hibp_score])
    result["score"] = score
    result["level"] = risk_level(score)
    return result

def load_input(args):
    items = []
    if args.input:
        with open(args.input, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                items.append({"url": row.get("url","") or None,
                              "domain": row.get("domain","") or None,
                              "email": row.get("email","") or None})
    # CLI flags
    if args.url or args.domain or args.email:
        items.append({"url": args.url, "domain": args.domain, "email": args.email})
    return items

def main():
    p = argparse.ArgumentParser(description="RiskCheck: quick spoof/scam/security triage for domains, URLs, and email addresses.")
    p.add_argument("--input", help="CSV with columns: url,domain,email")
    p.add_argument("--url")
    p.add_argument("--domain")
    p.add_argument("--email")
    p.add_argument("--out", help="Write JSON report to this file")
    p.add_argument("--csv", help="Write flat CSV summary to this file")
    args = p.parse_args()

    items = load_input(args)
    if not items:
        print("No inputs. Provide --input CSV or flags --url/--domain/--email")
        sys.exit(2)

    results = []
    for it in items:
        res = analyze_item(it)
        results.append(res)

    # Print concise console output
    for r in results:
        label = r["input"]
        print("="*60)
        print(f"INPUT: {label}")
        print(f"SCORE: {r['score']}  LEVEL: {r['level']}")
        if "email_auth" in r["signals"]:
            notes = r["signals"]["email_auth"]["detail"]["notes"]
            print(f"Email auth notes: {', '.join(notes) if notes else 'n/a'}")
        vt_dom = r["signals"].get("vt_domain", {})
        if vt_dom:
            bd = (vt_dom.get("detail") or {})
            bad_eng = bd.get("bad_engines") if isinstance(bd, dict) else None
            if bad_eng is not None:
                print(f"VirusTotal domain bad engines: {bad_eng}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"generated_at": datetime.utcnow().isoformat()+"Z", "results": results}, f, indent=2)

    if args.csv:
        # flatten to simple rows
        rows = []
        for r in results:
            dom = r["signals"].get("domain",{}).get("value","")
            email_auth = r["signals"].get("email_auth",{})
            notes = ",".join(email_auth.get("detail",{}).get("notes",[])) if email_auth else ""
            vt_dom = r["signals"].get("vt_domain",{})
            vt_bad = vt_dom.get("detail",{}).get("bad_engines") if isinstance(vt_dom.get("detail",{}), dict) else ""
            rows.append({
                "input_url": r["input"].get("url",""),
                "input_domain": r["input"].get("domain","") or dom,
                "input_email": r["input"].get("email",""),
                "score": r["score"],
                "level": r["level"],
                "spf": email_auth.get("detail",{}).get("spf",""),
                "dmarc": email_auth.get("detail",{}).get("dmarc",""),
                "email_auth_notes": notes,
                "vt_domain_bad_engines": vt_bad
            })
        import pandas as pd
        df = pd.DataFrame(rows)
        df.to_csv(args.csv, index=False)

if __name__ == "__main__":
    main()
