import json
import ipaddress
import platform
import re
import subprocess
import telnetlib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ACTIVITY_LOG = Path(__file__).resolve().parent.parent / "activity_log.json"
MAC_CACHE = Path(__file__).resolve().parent.parent / "mac_cache.json"
USER_COLORS = ["#ff8a1f", "#42c77b", "#d9ad35", "#5ab0ff", "#e85b5b", "#b98cff", "#00c2a8", "#f06bb4"]
TFTP_IOS_URL = "http://10.101.11.48/TFTP/"
IOS_UPLOAD_JOBS = {}
LIVE_TOOL_JOBS = {}
SUPPORTED_IOS_MODEL_MESSAGE = "Only Catalyst 3560, 3750, and 4948 are supported currently."
MAC_MODEL_CAPACITY = {
    "9372": 98300,
    "6001": 128000,
    "3064": 128000,
    "93180": 90000,
    "3232C": 40000,
}
LIVE_ACTION_ACTIVITY = {
    "span_vlan": ("corporate-deployment", "Corporate Deployment", "VLAN Span"),
    "apply_lastmile": ("corporate-deployment", "Corporate Deployment", "Last-Mile Port"),
    "p2p_test": ("p2p-testing", "P2P Testing", "P2P Switch Test"),
    "single_switch_test": ("p2p-testing", "P2P Testing", "Single Switch Test"),
    "ios_phase1": ("cisco-ios-uploader", "Cisco IOS Uploader", "Cisco IOS Phase 1"),
}

ROOT_SWITCHES = [
    {"name": "Korangi", "ip": "10.101.88.56"},
    {"name": "Ikhlaq", "ip": "10.101.89.200"},
    {"name": "Nagan", "ip": "10.101.90.101"},
    {"name": "DHA", "ip": "10.101.91.61"},
    {"name": "Saddar", "ip": "10.101.92.62"},
    {"name": "PAF-202", "ip": "10.101.93.202"},
    {"name": "PAF-170", "ip": "10.101.93.170"},
    {"name": "Kboard", "ip": "10.101.94.230"},
    {"name": "Site", "ip": "10.101.96.180"},
    {"name": "Highway", "ip": "10.101.97.7"},
    {"name": "Karimabad", "ip": "10.101.98.112"},
    {"name": "MAS", "ip": "10.101.99.55"},
]
DC_OC_SWITCHES = [
    {"name": "DC/OC-95.251", "ip": "10.101.95.251"},
    {"name": "DC/OC-95.252", "ip": "10.101.95.252"},
    {"name": "DC/OC-95.100", "ip": "10.101.95.100"},
    {"name": "DC/OC-95.101", "ip": "10.101.95.101"},
    {"name": "DC/OC-150.36", "ip": "172.16.150.36"},
]


def user_color(username, index=0):
    return USER_COLORS[index % len(USER_COLORS)]

REGION_SUBNETS = {
    "Korangi-88(REGION)": "10.101.88.0/24",
    "Ikhlaq-89(REGION)": "10.101.89.0/24",
    "Nagan-90(REGION)": "10.101.90.0/24",
    "DHA-91(REGION)": "10.101.91.0/24",
    "Saddar-92(REGION)": "10.101.92.0/24",
    "PAF-93(REGION)": "10.101.93.0/24",
    "Kboard-94(REGION)": "10.101.94.0/24",
    "Site-96(REGION)": "10.101.96.0/24",
    "Highway-97(REGION)": "10.101.97.0/24",
    "Karimabad-98(REGION)": "10.101.98.0/24",
    "MAS-99(REGION)": "10.101.99.0/24",
    "NOC-125(SINGLE)": "10.101.95.125/32",
    "OC-100(SINGLE)": "10.101.95.100/32",
    "OC-101(SINGLE)": "10.101.95.101/32",
    "OC-131(SINGLE)": "10.101.95.131/32",
    "OC-31(SINGLE)": "10.101.95.31/32",
    "NOC-89(SINGLE)": "10.101.95.89/32",
    "NOC-112(SINGLE)": "10.101.95.112/32",
    "NOC-103(SINGLE)": "10.101.95.103/32",
    "NOC-177(SINGLE)": "10.101.95.177/32",
    "NOC-205(SINGLE)": "10.101.95.205/32",
    "NOC-75(SINGLE)": "10.101.95.75/32",
    "IPNOC-30(SINGLE)": "10.101.95.30/32",
    "NOC-38(SINGLE)": "10.101.95.38/32",
    "NOC-54(SINGLE)": "10.101.95.54/32",
    "NOC-95(SINGLE)": "10.101.95.95/32",
}

REGION_EXCLUDE_IPS = {
    "Korangi-88(REGION)": ["10.101.88.41", "10.101.88.125", "10.101.88.78", "10.101.88.39", "10.101.88.122", "10.101.88.70"],
    "Ikhlaq-89(REGION)": ["10.101.89.125", "10.101.89.53", "10.101.89.215"],
    "Nagan-90(REGION)": ["10.101.90.169", "10.101.90.125", "10.101.90.224", "10.101.90.122", "10.101.90.123"],
    "DHA-91(REGION)": ["10.101.91.160", "10.101.91.125", "10.101.91.6", "10.101.91.79"],
    "Saddar-92(REGION)": ["10.101.92.161", "10.101.92.114", "10.101.92.170", "10.101.92.125", "10.101.92.171", "10.101.92.229", "10.101.92.178", "10.101.92.212", "10.101.92.132", "10.101.92.135"],
    "PAF-93(REGION)": ["10.101.93.161", "10.101.93.125", "10.101.93.170", "10.101.93.192", "10.101.93.62", "10.101.93.16", "10.101.93.150", "10.101.93.60", "10.101.93.159"],
    "Kboard-94(REGION)": ["10.101.94.80", "10.101.94.95", "10.101.94.97", "10.101.94.89", "10.101.94.125", "10.101.94.1", "10.101.94.213", "10.101.94.162", "10.101.94.145", "10.101.94.65"],
    "Site-96(REGION)": ["10.101.96.160", "10.101.96.159", "10.101.96.36", "10.101.96.162", "10.101.96.125", "10.101.96.170", "10.101.96.17", "10.101.96.99"],
    "Highway-97(REGION)": ["10.101.97.155", "10.101.97.160", "10.101.97.125", "10.101.97.166", "10.101.97.199", "10.101.97.111", "10.101.97.18"],
    "Karimabad-98(REGION)": ["10.101.98.159", "10.101.98.161", "10.101.98.125", "10.101.98.194", "10.101.98.182", "10.101.98.40", "10.101.98.42"],
    "MAS-99(REGION)": ["10.101.99.125", "10.101.99.1", "10.101.99.25", "10.101.99.175", "10.101.99.98", "10.101.99.48"],
}

RESERVED_VLANS = {7, 8, 9, 11, 13, 15, 21, 23, 28, 36, 100, 101, 900, 910, 1000, 1900, 1901, 1902, 1903, 1904, 1905, 1906, 1907, 2300, 2500, 2520}
RESERVED_NETWORKS = [
    ipaddress.ip_network("10.101.8.0/22"),
    ipaddress.ip_network("10.101.88.0/21"),
    ipaddress.ip_network("10.101.96.0/22"),
    ipaddress.ip_network("10.10.20.0/22"),
    ipaddress.ip_network("192.168.16.136/32"),
]


def message(kind, text, details=None):
    return {"kind": kind, "message": text, "details": details or [], "raw": ""}


def _post_copy(post):
    data = {key: post.get(key, "") for key in post.keys()}
    region_values = post.getlist("regions") if hasattr(post, "getlist") else []

    class LivePost(dict):
        def getlist(self, key):
            return region_values if key == "regions" else []

    return LivePost(data)


def start_live_tool_job(action, post):
    job_id = uuid.uuid4().hex
    LIVE_TOOL_JOBS[job_id] = {
        "id": job_id,
        "action": action,
        "kind": "info",
        "message": "Job queued.",
        "stage": "Queued",
        "percent": 2,
        "details": [],
        "raw": "",
        "result": None,
        "done": False,
    }
    thread = threading.Thread(target=_run_live_tool_job, args=(job_id, action, _post_copy(post)), daemon=True)
    thread.start()
    return job_id


def get_live_tool_job(job_id):
    return LIVE_TOOL_JOBS.get(job_id) or {
        "id": job_id,
        "kind": "error",
        "message": "Job not found.",
        "stage": "Missing",
        "percent": 100,
        "details": [],
        "raw": "",
        "result": None,
        "done": True,
    }


def _run_live_tool_job(job_id, action, post):
    stages = {
        "span_vlan": ["Validating input", "Scanning selected regions", "Connecting to switches", "Applying VLAN", "Collecting result"],
        "apply_lastmile": ["Validating input", "Opening Telnet", "Applying interface config", "Saving config", "Fetching final running config"],
        "p2p_test": ["Validating input", "Opening Telnet sessions", "Checking VLANs", "Configuring SVIs", "Running ping/drop test", "Cleanup and result"],
        "single_switch_test": ["Validating input", "Opening Telnet session", "Checking VLAN", "Configuring SVI", "Running bidirectional tests", "Cleanup and result"],
        "ios_phase1": ["Validating input", "Opening Telnet", "Running show version", "Running show inventory", "Running dir", "Building Phase 1/2 report"],
    }.get(action, ["Running job"])
    result = None
    try:
        running = True

        def ticker():
            while running and not LIVE_TOOL_JOBS[job_id].get("done"):
                elapsed = time.time() - start_time
                index = min(len(stages) - 1, int(elapsed // 4))
                LIVE_TOOL_JOBS[job_id].update({
                    "stage": stages[index],
                    "message": stages[index],
                    "percent": min(94, 5 + int(elapsed * 2)),
                    "details": stages[:index + 1],
                })
                time.sleep(1)

        start_time = time.time()
        tick_thread = threading.Thread(target=ticker, daemon=True)
        tick_thread.start()
        fn_map = {
            "span_vlan": span_vlan,
            "apply_lastmile": apply_lastmile,
            "p2p_test": run_p2p_test,
            "single_switch_test": run_single_switch_test,
            "ios_phase1": cisco_ios_phase1,
        }
        fn = fn_map.get(action)
        if not fn:
            result = message("error", "Unsupported live action.")
        else:
            result = fn(post)
    except Exception as exc:
        result = message("error", f"Unhandled live job error: {exc}")
    finally:
        running = False
    LIVE_TOOL_JOBS[job_id].update({
        "kind": (result or {}).get("kind", "info"),
        "message": (result or {}).get("message", ""),
        "stage": "Completed" if (result or {}).get("kind") == "success" else "Finished with issue",
        "percent": 100,
        "details": (result or {}).get("details", []),
        "raw": (result or {}).get("raw", ""),
        "result": result,
        "done": True,
    })
    activity_info = LIVE_ACTION_ACTIVITY.get(action)
    if activity_info:
        tool_slug, tool_name, activity_action = activity_info
        log_activity(post.get("username", "").strip(), tool_slug, tool_name, activity_action, result)


def _read_activity():
    if not ACTIVITY_LOG.exists():
        return []
    try:
        return json.loads(ACTIVITY_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []


def _read_mac_cache():
    if not MAC_CACHE.exists():
        return {}
    try:
        return json.loads(MAC_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_mac_cache(rows):
    MAC_CACHE.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def format_mac_count(value):
    try:
        number = int(value)
    except Exception:
        return "0"
    if number >= 1000:
        return f"{number / 1000:.2f}K"
    return str(number)


def mac_cache_is_fresh(row):
    try:
        ts = datetime.fromisoformat(row.get("updated_at", ""))
    except Exception:
        return False
    return (datetime.now() - ts).total_seconds() < 86400


def parse_mac_count_output(output):
    prompt_match = re.search(r"([\w.-]+)#\s*show\s+mac\s+address-table\s+count", output or "", re.I)
    hostname = prompt_match.group(1) if prompt_match else ""
    count_match = re.search(r"Total MAC Addresses in Use.*?:\s*(\d+)", output or "", re.I)
    if not count_match:
        count_match = re.search(r"Dynamic Address Count:\s*(\d+)", output or "", re.I)
    count = int(count_match.group(1)) if count_match else None
    return hostname, count


def parse_inventory_model(output):
    text = output or ""
    pids = [match.group(1).strip() for match in re.finditer(r"PID:\s*([^,\s]+)", text, re.I) if match.group(1).strip()]
    descriptions = [match.group(1).strip() for match in re.finditer(r'DESCR:\s*"([^"]+)"', text, re.I)]
    candidates = pids + descriptions
    for candidate in candidates:
        upper = candidate.upper()
        for key in MAC_MODEL_CAPACITY:
            if key in upper:
                return key
        model_match = re.search(r"(N[369]K-C[0-9A-Z-]+|C[0-9]{4,}[0-9A-Z-]*)", upper)
        if model_match:
            return model_match.group(1)
    return ""


def mac_capacity_for_model(model):
    upper = (model or "").upper()
    for key, capacity in MAC_MODEL_CAPACITY.items():
        if key in upper:
            return capacity
    return 0


def mac_utilization(count, model):
    capacity = mac_capacity_for_model(model)
    if not capacity:
        return {
            "capacity": 0,
            "capacity_display": "Not mapped",
            "percent": None,
            "percent_display": "N/A",
            "level": "unknown",
        }
    percent = min(999, (int(count or 0) / capacity) * 100)
    if percent < 50:
        level = "good"
    elif percent <= 80:
        level = "warn"
    else:
        level = "bad"
    return {
        "capacity": capacity,
        "capacity_display": format_mac_count(capacity),
        "percent": round(percent, 2),
        "percent_display": f"{percent:.1f}%",
        "level": level,
    }


def fetch_root_switch_mac(ip, username, password):
    tn, login_msg = telnet_login(ip, username, password, timeout=10)
    if not tn:
        return {"ok": False, "message": login_msg}
    try:
        tn.write(b"terminal length 0\r\n")
        time.sleep(0.4)
        tn.read_very_eager()
        tn.write(b"show inventory\r\n")
        inventory_raw = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=20)
        tn.write(b"show mac address-table count\r\n")
        mac_raw = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=25)
        tn.write(b"exit\r\n")
        tn.close()
    except Exception as exc:
        try:
            tn.close()
        except Exception:
            pass
        return {"ok": False, "message": f"Telnet command error: {exc}"}
    raw = f"{inventory_raw}\n{mac_raw}"
    hostname, count = parse_mac_count_output(mac_raw)
    model = parse_inventory_model(inventory_raw)
    if count is None:
        return {"ok": False, "message": "Total MAC count was not found in switch output.", "raw": raw}
    return {"ok": True, "hostname": hostname or ip, "model": model, "count": count, "count_display": format_mac_count(count), "raw": raw}


def mac_dashboard_for(switches):
    cache = _read_mac_cache()
    rows = []
    total = 0
    for switch in switches:
        row = cache.get(switch["ip"], {})
        count = int(row.get("count", 0) or 0)
        total += count
        rows.append({
            "name": switch["name"],
            "ip": switch["ip"],
            "hostname": row.get("hostname", "Not updated"),
            "model": row.get("model", "Not detected"),
            "count": count,
            "count_display": format_mac_count(count),
            "utilization": mac_utilization(count, row.get("model", "")),
            "updated_at": row.get("updated_at", ""),
            "fresh": mac_cache_is_fresh(row) if row else False,
            "status": row.get("status", "not-updated"),
            "message": row.get("message", "Not updated yet."),
        })
    current = 0
    pie_segments = []
    gradient_parts = []
    colors = USER_COLORS + ["#5dd9c1", "#ff6f91", "#a3e635", "#38bdf8"]
    def pie_sort_key(item):
        util = item.get("utilization", {})
        if util.get("percent") is None:
            return (1, 999999, -item["count"])
        return (0, -util.get("percent", 0), -item["count"])

    for index, row in enumerate(sorted(rows, key=pie_sort_key)):
        if not row["count"] or not total:
            continue
        pct = row["count"] / total * 100
        color = colors[index % len(colors)]
        util = row.get("utilization", {})
        pie_segments.append({
            "name": row["name"],
            "count": row["count_display"],
            "percent": round(pct, 4),
            "color": color,
            "model": row.get("model", "Not detected"),
            "capacity": util.get("capacity_display", "Not mapped"),
            "utilization": util.get("percent_display", "N/A"),
            "utilization_value": util.get("percent") or 0,
            "utilization_level": util.get("level", "unknown"),
        })
        gradient_parts.append(f"{color} {current:.2f}% {current + pct:.2f}%")
        current += pct
    return {
        "total": total,
        "total_display": format_mac_count(total),
        "rows": rows,
        "pie_segments": pie_segments,
        "pie_gradient": ", ".join(gradient_parts) if gradient_parts else "#26343a 0% 100%",
    }


def mac_dashboard():
    return mac_dashboard_for(ROOT_SWITCHES)


def dc_oc_mac_dashboard():
    return mac_dashboard_for(DC_OC_SWITCHES)


def update_mac_cache_for_switch(ip, username, password):
    all_switches = ROOT_SWITCHES + DC_OC_SWITCHES
    switch = next((item for item in all_switches if item["ip"] == ip), None)
    if not switch:
        return {"ok": False, "message": "Unknown root switch IP."}
    result = fetch_root_switch_mac(ip, username, password)
    cache = _read_mac_cache()
    if result.get("ok"):
        cache[ip] = {
            "hostname": result.get("hostname") or switch["name"],
            "model": result.get("model") or "Not detected",
            "count": result.get("count", 0),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "status": "success",
            "message": "Updated successfully.",
        }
    else:
        previous = cache.get(ip, {})
        previous.update({
            "updated_at": previous.get("updated_at", ""),
            "status": "error",
            "message": result.get("message", "Update failed."),
        })
        cache[ip] = previous
    _write_mac_cache(cache)
    dashboard = mac_dashboard()
    updated_row = next((row for row in dashboard["rows"] if row["ip"] == ip), None)
    return {
        "ok": result.get("ok", False),
        "message": result.get("message", ""),
        "row": updated_row,
        "total": dashboard["total_display"],
        "pie_gradient": dashboard["pie_gradient"],
        "pie_segments": dashboard["pie_segments"],
    }


def update_all_mac_cache(username, password):
    results = []
    for switch in ROOT_SWITCHES + DC_OC_SWITCHES:
        results.append(update_mac_cache_for_switch(switch["ip"], username, password))
    dashboard = mac_dashboard()
    dc_dashboard = dc_oc_mac_dashboard()
    ok_count = sum(1 for row in results if row.get("ok"))
    return {
        "ok": ok_count > 0,
        "message": f"Updated {ok_count}/{len(ROOT_SWITCHES) + len(DC_OC_SWITCHES)} switches.",
        "total": dashboard["total_display"],
        "rows": dashboard["rows"],
        "pie_gradient": dashboard["pie_gradient"],
        "pie_segments": dashboard["pie_segments"],
        "dc_dashboard": dc_dashboard,
    }


def log_activity(username, tool_slug, tool_name, action, result):
    entry = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "user": username or "unknown",
        "tool_slug": tool_slug,
        "tool_name": tool_name,
        "action": action,
        "status": (result or {}).get("kind", "info"),
        "message": (result or {}).get("message", ""),
    }
    rows = _read_activity()
    rows.append(entry)
    ACTIVITY_LOG.write_text(json.dumps(rows[-300:], indent=2), encoding="utf-8")


def overview_activity():
    today = datetime.now().date().isoformat()
    rows = list(reversed(_read_activity()))
    today_rows = [row for row in rows if row.get("time", "").startswith(today)]
    users = sorted({row.get("user", "unknown") for row in today_rows})
    success_count = sum(1 for row in today_rows if row.get("status") == "success")
    issue_count = sum(1 for row in today_rows if row.get("status") in {"warning", "error"})
    by_tool = {}
    by_user = {}
    by_status = {"success": 0, "warning": 0, "error": 0, "info": 0}
    hourly = {f"{hour:02d}": 0 for hour in range(24)}
    for row in today_rows:
        user = row.get("user", "unknown")
        by_user[user] = by_user.get(user, 0) + 1
        status = row.get("status", "info")
        by_status[status] = by_status.get(status, 0) + 1
        hour = row.get("time", "")[11:13]
        if hour in hourly:
            hourly[hour] += 1
        slug = row.get("tool_slug", "")
        by_tool.setdefault(slug, {"total": 0, "success": 0, "issues": 0})
        by_tool[slug]["total"] += 1
        if row.get("status") == "success":
            by_tool[slug]["success"] += 1
        elif row.get("status") in {"warning", "error"}:
            by_tool[slug]["issues"] += 1
    total_for_pie = sum(by_user.values())
    current = 0
    pie_segments = []
    gradient_parts = []
    for index, (user, count) in enumerate(sorted(by_user.items(), key=lambda item: item[1], reverse=True)):
        pct = (count / total_for_pie * 100) if total_for_pie else 0
        color = user_color(user, index)
        pie_segments.append({"user": user, "count": count, "percent": round(pct), "color": color})
        gradient_parts.append(f"{color} {current:.2f}% {current + pct:.2f}%")
        current += pct
    status_total = sum(by_status.values()) or 1
    status_current = 0
    status_colors = {"success": "#42c77b", "warning": "#d9ad35", "error": "#e85b5b", "info": "#5ab0ff"}
    status_segments = []
    status_gradient = []
    for status, count in by_status.items():
        if not count:
            continue
        pct = count / status_total * 100
        color = status_colors.get(status, "#5ab0ff")
        status_segments.append({"status": status, "count": count, "color": color})
        status_gradient.append(f"{color} {status_current:.2f}% {status_current + pct:.2f}%")
        status_current += pct
    max_hourly = max(hourly.values()) if hourly else 0
    hourly_bars = [
        {"hour": hour, "count": count, "height": round((count / max_hourly * 100) if max_hourly else 0)}
        for hour, count in hourly.items()
        if count
    ]
    return {
        "today_total": len(today_rows),
        "success_count": success_count,
        "issue_count": issue_count,
        "users": users,
        "user_count": len(users),
        "recent": today_rows[:30],
        "by_tool": by_tool,
        "by_status": by_status,
        "status_segments": status_segments,
        "status_gradient": ", ".join(status_gradient) if status_gradient else "#26343a 0% 100%",
        "hourly_bars": hourly_bars,
        "pie_segments": pie_segments,
        "pie_gradient": ", ".join(gradient_parts) if gradient_parts else "#26343a 0% 100%",
    }


def validate_vlan_id(vlan_id):
    try:
        vlan_num = int(vlan_id)
    except ValueError:
        return "VLAN ID must be numeric."
    if vlan_num < 1 or vlan_num > 4094:
        return "VLAN ID must be between 1 and 4094."
    return None


def format_flash_space(total_bytes, free_bytes):
    def human(value):
        if value is None:
            return "Not detected"
        gb = value / (1024 ** 3)
        mb = value / (1024 ** 2)
        if gb >= 1:
            return f"{gb:.2f} GB"
        return f"{mb:.2f} MB"

    if total_bytes is None or free_bytes is None:
        return "Not detected"
    return f"{human(total_bytes)} total ({human(free_bytes)} free)"


def format_file_size(size_bytes):
    if size_bytes is None:
        return "Unknown size"
    gb = size_bytes / (1024 ** 3)
    mb = size_bytes / (1024 ** 2)
    if gb >= 1:
        return f"{gb:.2f} GB"
    return f"{mb:.2f} MB"


def parse_tftp_size(size_text):
    value = (size_text or "").strip()
    match = re.match(r"([\d.]+)\s*([KMG]?)", value, re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2).upper()
    multiplier = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}.get(unit, 1)
    return int(number * multiplier)


def ios_family_for_model(model):
    model_text = (model or "").lower()
    if "4948e" in model_text or "4948e-f" in model_text:
        return "cat4500e"
    if "3560e" in model_text:
        return "c3560e"
    if "3750e" in model_text:
        return "c3750e"
    if "3560" in model_text:
        return "c3560"
    if "3750" in model_text:
        return "c3750"
    return ""


def fetch_tftp_ios_options(model, current_ios, free_bytes):
    family = ios_family_for_model(model)
    options = []
    if not family:
        return {
            "family": "",
            "options": options,
            "unsupported": True,
            "message": SUPPORTED_IOS_MODEL_MESSAGE,
            "tftp_url": TFTP_IOS_URL,
        }
    try:
        response = requests.get(TFTP_IOS_URL, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        return {
            "family": family,
            "options": options,
            "message": f"TFTP IOS list could not be fetched: {exc}",
            "tftp_url": TFTP_IOS_URL,
        }

    current_clean = (current_ios or "").replace("\\", "/").split("/")[-1]
    if ":" in current_clean:
        current_clean = current_clean.split(":", 1)[1]
    current_name = current_clean.lower()
    for row in re.findall(r"<tr>.*?</tr>", response.text, re.I | re.S):
        href_match = re.search(r'<a\s+href="([^"]+\.bin)">', row, re.I)
        if not href_match:
            continue
        filename = href_match.group(1)
        if not filename.lower().startswith(f"{family}-"):
            continue
        size_cells = re.findall(r'<td\s+align="right">\s*([^<]+?)\s*</td>', row, re.I | re.S)
        size_text = size_cells[-1].strip() if size_cells else ""
        size_bytes = parse_tftp_size(size_text)
        already_current = filename.lower() == current_name
        has_space = bool(free_bytes and size_bytes and free_bytes >= size_bytes)
        if already_current:
            status = "IOS Already Updated - no need to update IOS."
            kind = "success"
        elif has_space:
            status = "IOS needs to be upgraded and space is available."
            kind = "success"
        else:
            status = "Space is not available. Create space manually."
            kind = "error"
        options.append({
            "filename": filename,
            "size": format_file_size(size_bytes),
            "size_bytes": size_bytes,
            "status": status,
            "kind": kind,
            "already_current": already_current,
            "has_space": has_space,
        })

    already_current_options = [option for option in options if option["already_current"]]
    alternate_options = [option for option in options if not option["already_current"]]
    if already_current_options:
        message_text = "IOS Already Updated - no need to update IOS. Wanna configure the other one?"
        default_options = alternate_options
        current_status = "already_updated"
    elif options:
        message_text = "IOS needs to be upgraded. Select the target IOS below."
        default_options = options
        current_status = "needs_upgrade"
    else:
        message_text = f"No IOS files found for {family}."
        default_options = []
        current_status = "no_options"
    return {
        "family": family,
        "unsupported": False,
        "options": default_options,
        "all_options": options,
        "current_ios_match": bool(already_current_options),
        "current_status": current_status,
        "message": message_text,
        "tftp_url": TFTP_IOS_URL,
    }


def enrich_phase2_with_uploaded(phase2, uploaded_ios_files):
    uploaded_map = {item["filename"].lower(): item for item in uploaded_ios_files or []}
    for option in phase2.get("options", []):
        uploaded = uploaded_map.get(option["filename"].lower())
        option["uploaded_on_switch"] = bool(uploaded)
        option["uploaded_size"] = uploaded.get("size") if uploaded else ""
        if option.get("already_current"):
            option["status"] = "IOS Already Updated - no need to update IOS."
        elif uploaded:
            option["status"] = f"IOS is already uploaded on switch ({uploaded['size']}). If you want to use it, configure boot manually from CLI."
            option["kind"] = "info"
        elif option.get("has_space"):
            option["status"] = "IOS needs to be uploaded/upgraded and space is available."
        else:
            option["status"] = "Space is not available. Create space manually."
    if phase2.get("current_ios_match"):
        phase2["message"] = "IOS Already Updated - no need to update IOS. Other uploaded IOS can be used manually from CLI if required."
    return phase2


def ios_destination_for_family(family):
    return "bootflash:" if family == "cat4500e" else "flash:"


def ios_post_upload_guidelines(family):
    if family == "cat4500e":
        return [
            "4948E and 4948E-F",
            "IOS upload is complete. Verify it from CLI and set the bootvar.",
            "Check config-register. If it is 0x2101 and only one IOS exists, you can simply reload.",
            "If config-register is 0x2102, make sure the IOS is properly present in bootvar.",
        ]
    return [
        "3560-3750 Family",
        "IOS upload is complete. Verify it from CLI, set the bootvar, and restart manually.",
    ]


def _parse_dir_file_size(dir_output, ios_file):
    for line in (dir_output or "").splitlines():
        if ios_file in line:
            match = re.search(r"^\s*(?:\d+\s+)?(?:-\S+\s+)?(\d+)\s+.*" + re.escape(ios_file), line)
            if match:
                return int(match.group(1)), line.strip()
    return None, ""


def parse_dir_ios_files(dir_output, running_ios):
    running_name = (running_ios or "").replace("\\", "/").split("/")[-1]
    if ":" in running_name:
        running_name = running_name.split(":", 1)[1]
    running_name = running_name.lower()
    files = []
    for line in (dir_output or "").splitlines():
        match = re.search(r"^\s*(?:\d+\s+)?(?:-\S+\s+)?(\d+)\s+.*?(\S+\.bin)\s*$", line, re.I)
        if not match:
            continue
        size_bytes = int(match.group(1))
        filename = match.group(2).strip()
        is_running = filename.lower() == running_name
        files.append({
            "filename": filename,
            "size": format_file_size(size_bytes),
            "size_bytes": size_bytes,
            "is_running": is_running,
            "kind": "running" if is_running else "uploaded",
        })
    return files


def _set_ios_job(job_id, **updates):
    job = IOS_UPLOAD_JOBS.get(job_id)
    if not job:
        return
    job.update(updates)


def start_cisco_ios_upload_job(post):
    job_id = uuid.uuid4().hex
    data = {key: post.get(key, "") for key in ["username", "password", "device_ip", "model", "ios_file", "ios_size_bytes", "free_bytes", "family"]}
    IOS_UPLOAD_JOBS[job_id] = {
        "id": job_id,
        "status": "running",
        "kind": "info",
        "message": "IOS upload started.",
        "output": "",
        "verification": "",
        "percent": 0,
        "tftp_size": "",
        "uploaded_size": "",
        "guidelines": [],
        "done": False,
    }
    thread = threading.Thread(target=_run_cisco_ios_upload_job, args=(job_id, data), daemon=True)
    thread.start()
    return job_id


def get_cisco_ios_upload_job(job_id):
    return IOS_UPLOAD_JOBS.get(job_id) or {
        "id": job_id,
        "status": "missing",
        "kind": "error",
        "message": "Upload job was not found.",
        "output": "",
        "verification": "",
        "done": True,
    }


def _run_cisco_ios_upload_job(job_id, data):
    def append(text):
        job = IOS_UPLOAD_JOBS.get(job_id)
        if job and text:
            job["output"] += text

    username = data.get("username", "").strip()
    password = data.get("password", "")
    device_ip = data.get("device_ip", "").strip()
    model = data.get("model", "").strip()
    ios_file = data.get("ios_file", "").strip()
    family = data.get("family", "").strip() or ios_family_for_model(model)
    try:
        ios_size_bytes = int(data.get("ios_size_bytes", ""))
        free_bytes = int(data.get("free_bytes", ""))
    except Exception:
        _set_ios_job(job_id, status="error", kind="error", message="IOS size or free flash space was not detected.", done=True)
        return
    if not all([username, password, device_ip, model, ios_file, family]):
        _set_ios_job(job_id, status="error", kind="error", message="Device credentials, model, and selected IOS are required.", done=True)
        return
    if free_bytes < ios_size_bytes:
        _set_ios_job(job_id, status="error", kind="error", message="Space is not available. Create space manually.", done=True)
        return

    destination = ios_destination_for_family(family)
    source_url = urljoin(TFTP_IOS_URL, ios_file)
    command = f"copy {source_url} {destination}"
    _set_ios_job(job_id, message=f"Connecting to {device_ip} and starting IOS upload.", tftp_size=format_file_size(ios_size_bytes), percent=3)
    tn, login_msg = telnet_login(device_ip, username, password, timeout=10)
    if not tn:
        _set_ios_job(job_id, status="error", kind="error", message=login_msg, done=True)
        return
    try:
        tn.write(b"terminal length 0\r\n")
        time.sleep(0.5)
        tn.read_very_eager()
        append(f"IOS UPLOAD\n{'=' * 60}\nDevice: {device_ip}\nModel: {model}\nSource: {source_url}\nDestination: {destination}\nCommand: {command}\n\nDEVICE OUTPUT\n{'=' * 60}\n")
        tn.write(command.encode("ascii") + b"\r\n")
        start = time.time()
        destination_answered = False
        failed = False
        while time.time() - start < 900:
            time.sleep(0.5)
            chunk = tn.read_very_eager().decode("ascii", errors="ignore")
            if not chunk:
                continue
            append(chunk)
            elapsed = time.time() - start
            percent = min(95, max(8, int(8 + elapsed * 1.4)))
            _set_ios_job(job_id, message=f"IOS upload is running. {percent}% completed.", percent=percent)
            if "Destination filename" in IOS_UPLOAD_JOBS[job_id]["output"] and not destination_answered:
                tn.write(ios_file.encode("ascii") + b"\r\n")
                destination_answered = True
            if re.search(r"(Error|timed out|No such file|Permission denied|not enough space|aborted|failed)", chunk, re.I):
                failed = True
                break
            all_output = IOS_UPLOAD_JOBS[job_id]["output"]
            if "#" in chunk and re.search(r"(bytes copied|copied|OK)", all_output, re.I):
                break

        all_output = IOS_UPLOAD_JOBS[job_id]["output"]
        copy_failed = re.search(r"(Error|timed out|No such file|Permission denied|not enough space|aborted|failed)", all_output, re.I)
        copy_ok = re.search(r"(\[OK\]|bytes copied|copied)", all_output, re.I)
        if copy_failed or not copy_ok:
            failed = True

        append("\n\nVERIFYING UPLOADED FILE SIZE\n" + ("=" * 60) + "\n")
        _set_ios_job(job_id, message="Upload finished. Verifying file size with dir.", percent=97)
        tn.write(b"dir\r\n")
        dir_output = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=30)
        append(dir_output)
        uploaded_size, dir_line = _parse_dir_file_size(dir_output, ios_file)
        if uploaded_size is not None:
            verification = f"Switch copy response OK. TFTP file size {format_file_size(ios_size_bytes)}. Uploaded file size {format_file_size(uploaded_size)}."
            append("\n" + verification + "\n")
        elif uploaded_size is None:
            verification = f"Switch copy response {'OK' if copy_ok and not copy_failed else 'not confirmed'}. Uploaded IOS was not found in dir output."
            append("\n" + verification + "\n")
        tn.write(b"exit\r\n")
        tn.close()
        _set_ios_job(
            job_id,
            status="error" if failed else "success",
            kind="error" if failed else "success",
            message="IOS upload aborted or switch returned an error." if failed else "IOS uploaded successfully.",
            verification=verification,
            percent=100,
            tftp_size=format_file_size(ios_size_bytes),
            uploaded_size=format_file_size(uploaded_size) if uploaded_size is not None else "Not found",
            guidelines=ios_post_upload_guidelines(family),
            done=True,
        )
    except Exception as exc:
        try:
            tn.close()
        except Exception:
            pass
        _set_ios_job(job_id, status="error", kind="error", message=f"IOS upload aborted: {exc}", done=True)


def cisco_ios_upload(post):
    username = post.get("username", "").strip()
    password = post.get("password", "")
    device_ip = post.get("device_ip", "").strip()
    model = post.get("model", "").strip()
    ios_file = post.get("ios_file", "").strip()
    ios_size = post.get("ios_size_bytes", "").strip()
    free_space = post.get("free_bytes", "").strip()
    family = post.get("family", "").strip() or ios_family_for_model(model)
    if not all([username, password, device_ip, model, ios_file, family]):
        return message("error", "Device credentials, model, and selected IOS are required.")

    try:
        ios_size_bytes = int(ios_size)
        free_bytes = int(free_space)
    except Exception:
        return message("error", "IOS size or free flash space was not detected.")
    if free_bytes < ios_size_bytes:
        return {
            "kind": "error",
            "message": "Space is not available. Create space manually.",
            "details": [],
            "raw": "",
            "ios_upload": {
                "device_ip": device_ip,
                "model": model,
                "ios_file": ios_file,
                "destination": ios_destination_for_family(family),
                "status": "Space is not available. Create space manually.",
            },
        }

    tn, login_msg = telnet_login(device_ip, username, password, timeout=10)
    if not tn:
        return message("error", login_msg)

    destination = ios_destination_for_family(family)
    source_url = urljoin(TFTP_IOS_URL, ios_file)
    command = f"copy {source_url} {destination}"
    raw = ""
    try:
        tn.write(b"terminal length 0\r\n")
        time.sleep(0.5)
        tn.read_very_eager()
        tn.write(command.encode("ascii") + b"\r\n")
        start = time.time()
        destination_answered = False
        while time.time() - start < 900:
            time.sleep(1)
            chunk = tn.read_very_eager().decode("ascii", errors="ignore")
            if chunk:
                raw += chunk
                if "Destination filename" in raw and not destination_answered:
                    tn.write(ios_file.encode("ascii") + b"\r\n")
                    destination_answered = True
                if re.search(r"(Error|timed out|No such file|Permission denied|not enough space|aborted|failed)", chunk, re.I):
                    break
                if "#" in chunk and ("bytes copied" in raw.lower() or "[OK" in raw or "copied" in raw.lower()):
                    break
        tn.write(b"exit\r\n")
        tn.close()
    except Exception as exc:
        try:
            tn.close()
        except Exception:
            pass
        return message("error", f"IOS upload aborted: {exc}")

    failed = re.search(r"(Error|timed out|No such file|Permission denied|not enough space|aborted|failed)", raw, re.I)
    copied = re.search(r"(bytes copied|copied|OK)", raw, re.I)
    kind = "error" if failed or not copied else "success"
    status = "IOS upload completed." if kind == "success" else "IOS upload aborted or failed."
    return {
        "kind": kind,
        "message": status,
        "details": [],
        "raw": f"IOS UPLOAD\n{'=' * 60}\nDevice: {device_ip}\nModel: {model}\nSource: {source_url}\nDestination: {destination}\nCommand: {command}\n\nDEVICE OUTPUT\n{'=' * 60}\n{raw.strip()}",
        "ios_upload": {
            "device_ip": device_ip,
            "model": model,
            "ios_file": ios_file,
            "destination": destination,
            "source_url": source_url,
            "status": status,
        },
    }


def validate_p2p_vlan(vlan_id):
    error = validate_vlan_id(vlan_id)
    if error:
        return error
    if int(vlan_id) in RESERVED_VLANS:
        return f"VLAN {vlan_id} is reserved."
    return None


def is_reserved_ip(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except Exception:
        return False, None
    for network in RESERVED_NETWORKS:
        if ip_obj in network:
            return True, f"{ip_str} lies in reserved network {network}"
    return False, None


def validate_p2p_inputs(post):
    vlan = post.get("vlan_id", "").strip()
    sw1_ip = post.get("sw1_ip", "").strip()
    sw2_ip = post.get("sw2_ip", "").strip()
    sw1_interface_ip = post.get("sw1_interface_ip", "").strip()
    sw2_interface_ip = post.get("sw2_interface_ip", "").strip()
    error = validate_p2p_vlan(vlan)
    if error:
        return error
    try:
        sw1 = ipaddress.ip_address(sw1_ip)
        sw2 = ipaddress.ip_address(sw2_ip)
        iface1 = ipaddress.ip_interface(sw1_interface_ip)
        iface2 = ipaddress.ip_interface(sw2_interface_ip)
    except Exception as exc:
        return f"Invalid IP/CIDR input: {exc}"
    if sw1 == sw2:
        return "Switch IPs must not be identical."
    if iface1.ip == iface2.ip:
        return "SVI interface IPs must not be identical."
    if iface1.network != iface2.network:
        return "SVI IPs must be in the same subnet."
    for iface, label in [(iface1, "SW1 SVI"), (iface2, "SW2 SVI")]:
        if iface.ip == iface.network.network_address:
            return f"{label} cannot be the network address."
        if iface.ip == iface.network.broadcast_address:
            return f"{label} cannot be the broadcast address."
        reserved, msg = is_reserved_ip(str(iface.ip))
        if reserved:
            return msg
    return None


def validate_single_switch_inputs(post):
    vlan = post.get("vlan_id", "").strip()
    switch_ip = post.get("single_switch_ip", "").strip()
    interface_ip = post.get("switch_interface_ip", "").strip()
    target_ip = post.get("target_ip", "").strip()
    error = validate_p2p_vlan(vlan)
    if error:
        return error
    try:
        ipaddress.ip_address(switch_ip)
        switch_iface = ipaddress.ip_interface(interface_ip)
        target = ipaddress.ip_address(target_ip)
    except Exception as exc:
        return f"Invalid IP/CIDR input: {exc}"
    if target not in switch_iface.network:
        return "Client IP must be in the same subnet as switch SVI."
    for ip_value in [str(switch_iface.ip), str(target)]:
        reserved, msg = is_reserved_ip(ip_value)
        if reserved:
            return msg
    return None


def ping_host(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    wait = "-w" if platform.system().lower() == "windows" else "-W"
    try:
        result = subprocess.run(
            ["ping", param, "1", wait, "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_auth_error_msg(msg):
    checks = ["Login incorrect", "Please Verify your Password", "Password verification required", "Please Verify"]
    return any(check in (msg or "") for check in checks)


def configure_vlan(ip, username, password, vlan_id, vlan_name, retries=3, first_device=False):
    if first_device:
        error = validate_vlan_id(vlan_id)
        if error:
            return f"ERROR {ip} - {error}"
    if username.lower() == "support":
        return f"ERROR {ip} - Support user does not have configuration access"

    for attempt in range(1, retries + 1):
        try:
            tn = telnetlib.Telnet(ip, timeout=8)
            tn.read_until(b"Username:", timeout=5)
            tn.write(username.encode("ascii") + b"\r\n")
            tn.read_until(b"Password:", timeout=5)
            tn.write(password.encode("ascii") + b"\r\n")
            time.sleep(6)
            output = tn.read_very_eager().decode("ascii", errors="ignore")
            if "Login incorrect" in output:
                tn.close()
                return f"ERROR {ip} - Login incorrect (attempt {attempt})"
            if "Please Verify" in output or "Password verification required" in output:
                tn.close()
                return f"ERROR {ip} - Password verification required (attempt {attempt})"

            tn.write(b"conf t\r\n")
            conf_output = tn.read_until(b"(config)#", timeout=5).decode("ascii", errors="ignore")
            if "(config)#" not in conf_output:
                tn.write(b"conf\r\n")
                tn.write(f"vlan {vlan_id}\r\n".encode("ascii"))
                tn.write(f"name {vlan_name}\r\n".encode("ascii"))
                tn.write(b"exit\r\n")
                tn.write(b"wr all\r\n")
                time.sleep(0.5)

            tn.write(f"vlan {vlan_id}\r\n".encode("ascii"))
            tn.read_until(b"(config-vlan)#", timeout=5)
            tn.write(f"name {vlan_name}\r\n".encode("ascii"))
            time.sleep(0.5)
            tn.write(b"end\r\n")
            tn.read_until(b"#", timeout=5)
            tn.write(b"copy running-config startup-config\r\n")
            output = tn.read_until(b"[OK]", timeout=7)
            if b"[OK]" not in output and b"Destination filename [startup-config]?" in output:
                tn.write(b"\r\n")
            time.sleep(1)
            tn.write(b"exit\r\n")
            tn.close()
            return f"OK VLAN {vlan_id} created and saved on {ip} (attempt {attempt})"
        except Exception as exc:
            if attempt < retries:
                time.sleep(2)
                continue
            return f"ERROR Failed on {ip} after {retries} attempts: {exc}"


def span_vlan(post):
    username = post.get("username", "").strip()
    password = post.get("password", "")
    vlan_id = post.get("vlan_id", "").strip()
    vlan_name = post.get("vlan_name", "").strip()
    selected_regions = post.getlist("regions")
    exclude_ips_input = post.get("exclude_ips", "")
    if not all([username, password, vlan_id, vlan_name]) or not selected_regions:
        return message("error", "Please fill all fields and select at least one region.")
    error = validate_vlan_id(vlan_id)
    if error:
        return message("error", error)

    start_time = time.time()
    subnets = [REGION_SUBNETS[r] for r in selected_regions if r in REGION_SUBNETS]
    exclude_ips = {ip.strip() for ip in exclude_ips_input.split(",") if ip.strip()}
    for region in selected_regions:
        exclude_ips.update(REGION_EXCLUDE_IPS.get(region, []))

    live_ips = []
    for subnet in subnets:
        net = ipaddress.ip_network(subnet, strict=False)
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(ping_host, str(ip)): str(ip) for ip in net.hosts()}
            for future in as_completed(futures):
                ip = futures[future]
                if ip not in exclude_ips and future.result():
                    live_ips.append(ip)

    if not live_ips:
        return message("warning", f"No live devices found. Excluded {len(exclude_ips)} IPs.")

    results = []
    auth_failed_ips = []
    first_result = configure_vlan(live_ips[0], username, password, vlan_id, vlan_name, first_device=True)
    results.append(first_result)
    if is_auth_error_msg(first_result):
        auth_failed_ips.append(live_ips[0])

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(configure_vlan, ip, username, password, vlan_id, vlan_name): ip for ip in live_ips[1:]}
        for future in as_completed(futures):
            ip = futures[future]
            res = future.result()
            results.append(res)
            if is_auth_error_msg(res):
                auth_failed_ips.append(ip)
            if len(auth_failed_ips) >= 3:
                break

    if len(auth_failed_ips) >= 3:
        return message("error", "Wrong username/password detected on multiple devices.", auth_failed_ips)

    elapsed = time.time() - start_time
    errors = [r for r in results if r.startswith("ERROR")]
    successes = [r for r in results if r.startswith("OK")]
    raw_lines = [
        f"VLAN {vlan_id} ({vlan_name}) span completed.",
        f"Selected regions: {', '.join(selected_regions)}",
        f"Live devices found: {len(live_ips)}",
        f"Success: {len(successes)}",
        f"Failed: {len(errors)}",
        f"Excluded IPs: {len(exclude_ips)}",
        f"Total time: {elapsed:.2f}s",
    ]
    if errors:
        raw_lines.append("")
        raw_lines.append("FAILED DEVICES")
        raw_lines.extend(errors)
    step_details = [
        "OK Input validation passed",
        f"OK Scanned selected regions and found {len(live_ips)} live devices",
        f"OK VLAN configured on {len(successes)} devices" if successes else "ERROR No device was configured successfully",
        f"ERROR {len(errors)} device(s) failed" if errors else "OK No device failures reported",
    ]
    step_details.extend(errors)
    step_details.extend(successes)
    return {
        "kind": "success",
        "message": f"VLAN span completed. {len(successes)} success, {len(errors)} failed.",
        "details": step_details,
        "raw": "\n".join(raw_lines),
    }


def telnet_login(ip, username, password, timeout=8):
    try:
        tn = telnetlib.Telnet(ip, 23, timeout=timeout)
        output = tn.read_until(b":", timeout=5).decode(errors="ignore")
        if any(token in output for token in ["Username", "username", "login", "Login"]):
            tn.write(username.encode() + b"\n")
            tn.read_until(b"Password:", timeout=5)
            tn.write(password.encode() + b"\n")
        elif "Password" in output:
            tn.write(password.encode() + b"\n")
        else:
            tn.write(username.encode() + b"\n")
            time.sleep(1)
            tn.write(password.encode() + b"\n")

        start = time.time()
        output = ""
        while time.time() - start < 20:
            time.sleep(0.5)
            output += tn.read_very_eager().decode(errors="ignore")
            if any(x in output for x in [">", "#", "$"]):
                return tn, "Login successful"
            if any(x in output for x in ["Login incorrect", "Invalid", "Authentication failed", "Please Verify your Password"]):
                break
        tn.close()
        return None, "Wrong username or password"
    except Exception as exc:
        return None, f"Telnet error: {exc}"


def telnet_run_commands_fast(ip, username, password, commands, login_timeout=5):
    try:
        tn = telnetlib.Telnet(ip, timeout=8)
        tn.read_until(b"Username:", timeout=login_timeout)
        tn.write(username.encode("ascii") + b"\r\n")
        tn.read_until(b"Password:", timeout=login_timeout)
        tn.write(password.encode("ascii") + b"\r\n")
        time.sleep(1)
        tn.read_very_eager()
        tn.write(("\r\n".join(commands) + "\r\n").encode("ascii"))
        time.sleep(6)
        output = tn.read_very_eager().decode("ascii", errors="ignore")
        tn.write(b"exit\r\n")
        tn.close()
        return output
    except Exception as exc:
        return f"ERROR Telnet error to {ip}: {exc}"


def telnet_apply_fast(ip, username, password, commands, login_timeout=5):
    try:
        tn = telnetlib.Telnet(ip, timeout=8)
        tn.read_until(b"Username:", timeout=login_timeout)
        tn.write(username.encode("ascii") + b"\r\n")
        tn.read_until(b"Password:", timeout=login_timeout)
        tn.write(password.encode("ascii") + b"\r\n")
        time.sleep(1)
        tn.read_very_eager()
        output = ""

        for command in commands:
            tn.write(command.encode("ascii") + b"\r\n")
            time.sleep(0.8)
            output += f"\n=> {command}\n"
            output += tn.read_very_eager().decode("ascii", errors="ignore")

            if command.lower().strip() == "copy running-config startup-config":
                time.sleep(1)
                output += tn.read_very_eager().decode("ascii", errors="ignore")
                tn.write(b"\r\n")
                time.sleep(0.8)
                output += tn.read_very_eager().decode("ascii", errors="ignore")
                tn.write(b"\r\n")
                time.sleep(2)
                output += read_full_output(tn, end_prompt=b"#", max_wait=20)

        tn.write(b"exit\r\n")
        tn.close()
        return output
    except Exception as exc:
        return f"ERROR Telnet error to {ip}: {exc}"


def telnet_apply_and_show_interface(ip, username, password, commands, interface_name, login_timeout=5):
    try:
        tn = telnetlib.Telnet(ip, timeout=8)
        tn.read_until(b"Username:", timeout=login_timeout)
        tn.write(username.encode("ascii") + b"\r\n")
        tn.read_until(b"Password:", timeout=login_timeout)
        tn.write(password.encode("ascii") + b"\r\n")
        time.sleep(1)
        tn.read_very_eager()
        apply_output = ""

        for command in commands:
            tn.write(command.encode("ascii") + b"\r\n")
            time.sleep(0.8)
            apply_output += f"\n=> {command}\n"
            apply_output += tn.read_very_eager().decode("ascii", errors="ignore")
            if command.lower().strip() == "copy running-config startup-config":
                time.sleep(1)
                apply_output += tn.read_very_eager().decode("ascii", errors="ignore")
                tn.write(b"\r\n")
                time.sleep(0.8)
                apply_output += tn.read_very_eager().decode("ascii", errors="ignore")
                tn.write(b"\r\n")
                time.sleep(2)
                apply_output += read_full_output(tn, end_prompt=b"#", max_wait=25)

        show_command = f"show run interface {interface_name}"
        tn.write(show_command.encode("ascii") + b"\r\n")
        time.sleep(2)
        final_config = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=20)
        tn.write(b"exit\r\n")
        tn.close()
        return apply_output, final_config
    except Exception as exc:
        return f"ERROR Telnet error to {ip}: {exc}", ""


def read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=15):
    output = b""
    start_time = time.time()
    while time.time() - start_time <= max_wait:
        chunk = tn.read_very_eager()
        if chunk:
            output += chunk
            if more_prompt in chunk:
                tn.write(b" ")
        if end_prompt in output:
            break
        time.sleep(0.1)
    return output.decode("ascii", errors="ignore")


def parse_show_interfaces_status(output_text):
    ports = []
    lines = output_text.splitlines()
    row_pattern = re.compile(
        r"^\s*(?P<port>(?:Fa|Gi|Te|Eth|Po)\S+)\s+"
        r"(?P<middle>.*?)"
        r"(?P<status>connected|notconnect|disabled|suspended|err-disabled)\s+"
        r"(?P<vlan>\S+)\s+"
        r"(?P<duplex>\S+)\s+"
        r"(?P<speed>\S+)\s+"
        r"(?P<type>\S+)\s*$",
        re.I,
    )

    for line in lines:
        match = row_pattern.match(line)
        if match:
            row = match.groupdict()
            ports.append({
                "port": row.get("port", ""),
                "name": row.get("middle", "").strip(),
                "status": row.get("status", ""),
                "vlan": row.get("vlan", ""),
                "duplex": row.get("duplex", ""),
                "speed": row.get("speed", ""),
                "type": row.get("type", ""),
            })
    if ports:
        return ports

    for line in lines:
        if not re.match(r"^\s*(Fa|Gi|Te|Eth|Po)\S+", line):
            continue
        line = line.strip()
        parts = re.split(r"\s{2,}", line)
        if len(parts) >= 7:
            ports.append({
                "port": parts[0].strip(),
                "name": parts[1].strip(),
                "status": parts[2].strip(),
                "vlan": parts[3].strip(),
                "duplex": parts[4].strip() if len(parts) > 4 else "",
                "speed": parts[5].strip() if len(parts) > 5 else "",
                "type": parts[6].strip() if len(parts) > 6 else "",
            })
    return ports


def fetch_lastmile_ports(post):
    ip = post.get("lastmile_ip", "").strip()
    username = post.get("username", "").strip()
    password = post.get("password", "")
    if not all([ip, username, password]):
        return message("error", "Last-mile IP, username, and password are required.")
    tn, login_msg = telnet_login(ip, username, password)
    if not tn:
        return message("error", login_msg)
    tn.write(b"show interfaces status\n")
    raw = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=20)
    tn.write(b"exit\n")
    tn.close()
    ports = parse_show_interfaces_status(raw)
    return {"kind": "success" if ports else "warning", "message": f"Fetched {len(ports)} ports from {ip}.", "details": [f"{p['port']} | {p['name'] or 'No Description'} | VLAN {p['vlan']} | {p['status']}" for p in ports], "raw": raw}


def fetch_lastmile_port_rows(ip, username, password):
    if not all([ip, username, password]):
        return False, "Last-mile IP, username, and password are required.", [], ""
    tn, login_msg = telnet_login(ip, username, password)
    if not tn:
        return False, login_msg, [], ""
    tn.write(b"show interfaces status\n")
    raw = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=20)
    tn.write(b"exit\n")
    tn.close()
    ports = parse_show_interfaces_status(raw)
    if not ports:
        return False, "No interfaces parsed from switch output.", ports, raw
    return True, f"Fetched {len(ports)} ports from {ip}.", ports, raw


def cisco_ios_phase1(post):
    username = post.get("username", "").strip()
    password = post.get("password", "")
    device_ip = post.get("device_ip", "").strip()
    if not all([username, password, device_ip]):
        return message("error", "Username, password, and device IP are required.")

    tn, login_msg = telnet_login(device_ip, username, password)
    if not tn:
        return message("error", login_msg)

    outputs = {}
    try:
        for command, wait_time in [
            ("terminal length 0", 1),
            ("show version", 3),
            ("show inventory", 3),
            ("dir", 3),
        ]:
            tn.write(command.encode("ascii") + b"\r\n")
            time.sleep(wait_time)
            outputs[command] = read_full_output(tn, end_prompt=b"#", more_prompt=b"--More--", max_wait=15)
        tn.write(b"exit\r\n")
        tn.close()
    except Exception as exc:
        try:
            tn.close()
        except Exception:
            pass
        return message("error", f"Telnet command error: {exc}")

    version_output = outputs.get("show version", "")
    inventory_output = outputs.get("show inventory", "")
    dir_output = outputs.get("dir", "")
    ios_match = re.search(r'System image file is\s+"([^"]+)"', version_output, re.I)
    ios_image = ios_match.group(1) if ios_match else "Not detected"

    models = []
    for match in re.finditer(r'DESCR:\s+"([^"]+)"', inventory_output, re.I):
        descr = match.group(1).strip()
        model_match = re.search(r"(WS-C[0-9A-Z-]+|C[0-9]{4}[0-9A-Z-]*)", descr, re.I)
        models.append(model_match.group(1) if model_match else descr)
    for match in re.finditer(r"PID:\s*([^,\s]+)", inventory_output, re.I):
        pid = match.group(1).strip()
        if pid and pid not in models:
            models.append(pid)
    model = models[0] if models else "Not detected"

    space_match = re.search(r"(\d+)\s+bytes\s+total\s+\((\d+)\s+bytes\s+free\)", dir_output, re.I)
    total_bytes = int(space_match.group(1)) if space_match else None
    free_bytes = int(space_match.group(2)) if space_match else None
    total_space = format_flash_space(total_bytes, free_bytes) if space_match else "Not detected"
    bytes_space = f"{total_bytes:,} bytes total ({free_bytes:,} bytes free)" if space_match else "Not detected"
    switch_ios_files = parse_dir_ios_files(dir_output, ios_image)
    phase2 = enrich_phase2_with_uploaded(fetch_tftp_ios_options(model, ios_image, free_bytes), switch_ios_files)

    raw = (
        "PHASE 1 REPORT\n"
        "============================================================\n"
        f"Device IP: {device_ip}\n"
        f"Switch Model: {model}\n"
        f"Current IOS: {ios_image}\n"
        f"Flash Space: {total_space}\n"
        f"Flash Bytes: {bytes_space}\n"
    )
    return {
        "kind": "success",
        "message": "Cisco IOS Phase 1 completed.",
        "details": [
            "OK Telnet access successful",
            "OK Current IOS detected" if ios_match else "ERROR Current IOS was not detected",
            "OK Switch model detected" if model != "Not detected" else "ERROR Switch model was not detected",
            "OK Flash space detected" if space_match else "ERROR Flash space was not detected",
        ],
        "raw": raw,
        "ios_report": {
            "device_ip": device_ip,
            "model": model,
            "ios_image": ios_image,
            "total_space": total_space,
            "bytes_space": bytes_space,
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "phase2": phase2,
            "switch_ios_files": switch_ios_files,
        },
    }


def generate_acl_commands(acl_name, public_ips, customer_subnet="192.168.20.0 0.0.0.255"):
    commands = [
        f"ip access-list extended {acl_name}",
        " deny   tcp any range 135 139 any",
        " deny   tcp any eq 445 any",
        " deny   udp any range 135 netbios-ss any",
        " deny   udp any eq 445 any",
        " deny   tcp any any range 135 139",
        " deny   tcp any any eq 445",
        " deny   udp any any range 135 netbios-ss",
        " deny   udp any any eq 445",
        " deny   ip any 10.0.0.0 0.255.255.255",
        " deny   ip 10.0.0.0 0.255.255.255 any",
    ]
    for ip in public_ips:
        commands.append(f" permit ip host {ip} {customer_subnet}" if " " not in ip and "/" not in ip else f" permit ip {ip} {customer_subnet}")
        commands.append(f" permit ip {customer_subnet} host {ip}" if " " not in ip and "/" not in ip else f" permit ip {customer_subnet} {ip}")
    commands.extend([
        " deny   ip 192.168.0.0 0.0.255.255 any",
        " deny   ip any 192.168.0.0 0.0.255.255",
        " deny   ip 172.16.0.0 0.0.255.255 any",
        " deny   ip any 172.16.0.0 0.0.255.255",
    ])
    for ip in public_ips:
        commands.append(f" permit ip host {ip} any" if " " not in ip and "/" not in ip else f" permit ip {ip} any")
    commands.append(" deny   ip any any")
    return commands


def apply_lastmile(post):
    ip = post.get("lastmile_ip", "").strip()
    username = post.get("username", "").strip()
    password = post.get("password", "")
    vlan_id = post.get("vlan_id", "").strip()
    vlan_name = post.get("vlan_name", "").strip()
    port = post.get("port", "").strip()
    mode = post.get("lastmile_type", "DATA")
    if not all([ip, username, password, vlan_id, vlan_name, port]):
        return message("error", "Last-mile IP, credentials, VLAN, VLAN name, and port are required.")

    if mode == "BW":
        public_ips = [item.strip() for item in re.split(r"[\n,]+", post.get("public_ips", "")) if item.strip()]
        if not public_ips:
            return message("error", "Public IPs are required for BW configuration.")
        acl_source = post.get("acl_name", "").strip() or vlan_name
        acl_name = re.sub(r"[^a-zA-Z0-9]", "-", acl_source).upper()
        commands = ["conf t", f"default interface {port}"] + generate_acl_commands(acl_name, public_ips) + [
            f"interface {port}",
            f"description {acl_source}",
            f"switchport access vlan {vlan_id}",
            "switchport mode access",
            "switchport nonegotiate",
            "switchport port-security maximum 10",
            "switchport port-security",
            "switchport port-security aging time 3",
            "switchport port-security violation restrict",
            "switchport port-security aging type inactivity",
            f"ip access-group {acl_name} in",
            "storm-control broadcast level 1.00",
            "storm-control action shutdown",
            "storm-control action trap",
            "no cdp enable",
            "spanning-tree portfast",
            "spanning-tree bpdufilter enable",
            "end",
            "copy running-config startup-config",
        ]
    else:
        service_policy = post.get("service_policy", "5Mb").strip() or "5Mb"
        commands = [
            "conf t",
            f"default interface {port}",
            f"interface {port}",
            f"description {vlan_name}",
            f"switchport access vlan {vlan_id}",
            "switchport mode access",
            "switchport port-security maximum 10",
            "switchport port-security",
            "switchport port-security aging time 3",
            "switchport port-security violation restrict",
            "switchport port-security aging type inactivity",
            "storm-control broadcast level 0.10",
            "storm-control action shutdown",
            "storm-control action trap",
            "no cdp enable",
            "spanning-tree portfast",
            "spanning-tree bpdufilter enable",
            f"service-policy input {service_policy}",
            "end",
            "copy running-config startup-config",
        ]
    raw, final_config = telnet_apply_and_show_interface(ip, username, password, commands, port)
    save_lines = []
    for line in raw.splitlines():
        clean = line.strip()
        if "[OK]" in clean or "bytes copied" in clean.lower() or "copied" in clean.lower():
            save_lines.append(clean)
    save_summary = "\n".join(save_lines[-4:]) if save_lines else "Save command completed. Prompt returned."
    combined_raw = f"{save_summary}\n\nFINAL RUNNING CONFIG\n{'=' * 60}\n{final_config}"
    kind = "warning" if "ERROR" in raw or "% Invalid" in raw else "success"
    has_error = kind == "warning"
    saved_ok = bool(save_lines) or "[OK]" in raw or "copied" in raw.lower()
    final_ok = bool(final_config.strip()) and "ERROR" not in final_config
    step_details = [
        "OK Input validation passed",
        "OK Telnet session opened and commands were sent" if not raw.startswith("ERROR") else raw,
        "OK Interface command set completed" if not has_error else "ERROR Device returned an error while applying commands",
        "OK Configuration saved" if saved_ok else "ERROR Save confirmation was not detected",
        "OK Final running configuration fetched" if final_ok else "ERROR Final running configuration was not fetched",
    ]
    return {
        "kind": kind,
        "message": f"{mode} configuration sent to {ip} on {port}. Final running config fetched below.",
        "details": step_details,
        "raw": combined_raw,
    }


def show_interface(post):
    raw = telnet_run_commands_fast(post.get("lastmile_ip", ""), post.get("username", ""), post.get("password", ""), [f"show run interface {post.get('port', '')}"])
    return {"kind": "success", "message": "Final running configuration fetched.", "details": [], "raw": raw}


def create_olt_vlan(post):
    olt_ip = post.get("olt_ip", "").strip()
    username = post.get("username", "").strip()
    password = post.get("password", "")
    vlan_id = post.get("vlan_id", "").strip()
    if not all([olt_ip, username, password, vlan_id]):
        return message("error", "OLT IP, username, password, and VLAN ID are required.")
    try:
        base_url = f"https://{olt_ip}/"
        session = requests.Session()
        session.verify = False
        r = session.post(urljoin(base_url, "action/login.html"), data={"user": username, "pass": password}, timeout=10)
        if r.status_code != 200:
            return message("error", f"Login failed: HTTP {r.status_code}")
        resp = session.post(
            urljoin(base_url, "goform/set_vlan"),
            data={"vlanId": vlan_id, "vlanName": f"VLAN_{vlan_id}", "vlanType": "tag"},
            timeout=10,
        )
        if resp.status_code == 200:
            return message("success", f"VLAN {vlan_id} created successfully on {olt_ip}.")
        return message("error", f"VLAN creation failed: HTTP {resp.status_code}")
    except Exception as exc:
        return message("error", f"Exception: {exc}")


def cidr_to_ip_mask(cidr):
    interface = ipaddress.ip_interface(cidr)
    return str(interface.ip), str(interface.network.netmask)


def run_command(tn, command, wait_time=2):
    tn.write(command.encode() + b"\n")
    time.sleep(wait_time)
    return tn.read_very_eager().decode(errors="ignore")


def check_vlan_exists(tn, vlan):
    output = run_command(tn, f"show vlan id {vlan}", wait_time=2)
    if re.search(r"(not\s+exist|not\s+found|invalid|unknown)", output, re.I):
        return False, f"VLAN {vlan} does not exist on device"
    return True, f"VLAN {vlan} exists on device"


def _entered_config_mode(output):
    return bool(re.search(r"\(config[^\)]*\)#", output or "", re.I))


def configure_svi_interface(tn, vlan, ip, mask, label, replace_existing=False):
    """Configure SVI while preserving Cisco/Nexus and MTLink CLI handling."""
    output_parts = []
    config_output = run_command(tn, "conf t", wait_time=2)
    output_parts.append(config_output)
    mtlink_mode = not _entered_config_mode(config_output)

    if mtlink_mode:
        output_parts.append(run_command(tn, "conf", wait_time=1))
        if replace_existing:
            output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
        output_parts.append(run_command(tn, f"interface vlan {vlan}", wait_time=1))
        ip_output = run_command(tn, f"ip address {ip} {mask}", wait_time=2)
        output_parts.append(ip_output)
        if re.search(r"(overlaps|Duplicate|already configured)", ip_output, re.I):
            output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
            output_parts.append(run_command(tn, "exit", wait_time=1))
            output_parts.append(run_command(tn, "exit", wait_time=1))
            return False, f"Duplicate/Overlap on {label}", "\n".join(output_parts), "MTLink"
        output_parts.append(run_command(tn, "no shut", wait_time=1))
        output_parts.append(run_command(tn, "exit", wait_time=1))
        output_parts.append(run_command(tn, "exit", wait_time=1))
    else:
        if replace_existing:
            output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
        output_parts.append(run_command(tn, f"interface vlan {vlan}", wait_time=1))
        ip_output = run_command(tn, f"ip address {ip} {mask}", wait_time=2)
        output_parts.append(ip_output)
        if re.search(r"(overlaps|Duplicate|already configured)", ip_output, re.I):
            output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
            output_parts.append(run_command(tn, "end", wait_time=1))
            return False, f"Duplicate/Overlap on {label}", "\n".join(output_parts), "Cisco/Nexus"
        output_parts.append(run_command(tn, "no shut", wait_time=1))
        output_parts.append(run_command(tn, "end", wait_time=1))

    time.sleep(3)
    return True, f"{label} SVI configured", "\n".join(output_parts), "MTLink" if mtlink_mode else "Cisco/Nexus"


def cleanup_svi_interface(tn, vlan):
    output_parts = []
    config_output = run_command(tn, "conf t", wait_time=2)
    output_parts.append(config_output)
    if not _entered_config_mode(config_output):
        output_parts.append(run_command(tn, "conf", wait_time=1))
        output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
        output_parts.append(run_command(tn, "exit", wait_time=1))
    else:
        output_parts.append(run_command(tn, f"no interface vlan {vlan}", wait_time=1))
        output_parts.append(run_command(tn, "end", wait_time=1))
    return "\n".join(output_parts)


def get_p2p_arp_table(tn, vlan=None, target_ip=None):
    output = run_command(tn, f"show ip arp vlan {vlan}" if vlan else "show ip arp", wait_time=2)
    if target_ip and re.search(r"(Too many parameters|Invalid input|Unknown command|\^)", output, re.I):
        output = run_command(tn, f"show arp | include {target_ip}", wait_time=2)
        if re.search(r"(Invalid input|Unknown command|\^)", output, re.I):
            output = run_command(tn, "show arp", wait_time=2)
    return output


def _read_ping_until_done(tn, max_wait=15):
    output = ""
    start_time = time.time()
    while True:
        time.sleep(0.5)
        if tn.sock_avail():
            chunk = tn.read_very_eager().decode(errors="ignore")
            output += chunk
            if re.search(r"(Success rate is|packets transmitted|packet loss)", output, re.I):
                break
        if time.time() - start_time > max_wait:
            break
    return output


def _ping_failed(output):
    text = output or ""
    return bool(
        re.search(r"Success\s+rate\s+is\s+0\s+percent\s*\(0/\d+\)", text, re.I)
        or re.search(r"0\s+percent\s*\(0/5\)", text, re.I)
        or re.search(r"\d+\s+packets\s+transmitted,\s*0\s+(?:packets\s+)?received,\s*100(?:\.0+)?%\s+packet\s+loss", text, re.I)
        or re.search(r"100(?:\.0+)?%\s+packet\s+loss", text, re.I)
    )


def run_smart_ping(tn, target_ip):
    tn.write(f"ping {target_ip}\n".encode())
    simple_ping_output = _read_ping_until_done(tn, max_wait=15)
    if _ping_failed(simple_ping_output):
        return simple_ping_output, False

    repeat_output = ""
    repeat_done = False
    for command in [
        f"ping {target_ip} repeat 1000 size 1500",
        f"ping {target_ip} count 1000",
        f"ping {target_ip} -n 1000",
    ]:
        tn.write(f"{command}\n".encode())
        current_output = _read_ping_until_done(tn, max_wait=20)
        repeat_output = current_output
        if not re.search(r"(%\s*Invalid|Invalid input|Unknown command|Incomplete command|Ambiguous command|Too many parameters|\^|Error)", current_output, re.I):
            repeat_done = bool(re.search(r"(Success rate|packets transmitted|packet loss)", current_output, re.I))
            if repeat_done:
                break

    combined = (
        simple_ping_output
        + "\n"
        + "=" * 50
        + "\nExtended Ping Result (1000 packets):\n"
        + "=" * 50
        + "\n"
        + repeat_output
    )
    return combined, repeat_done


def run_p2p_test(post):
    username = post.get("username", "").strip()
    password = post.get("password", "")
    sw1_ip = post.get("sw1_ip", "").strip()
    sw2_ip = post.get("sw2_ip", "").strip()
    vlan = post.get("vlan_id", "").strip()
    sw1_interface_ip = post.get("sw1_interface_ip", "").strip()
    sw2_interface_ip = post.get("sw2_interface_ip", "").strip()
    cleanup = post.get("clean_up_interfaces") == "on"
    if not all([username, password, sw1_ip, sw2_ip, vlan, sw1_interface_ip, sw2_interface_ip]):
        return message("error", "All P2P fields are required.")
    validation_error = validate_p2p_inputs(post)
    if validation_error:
        return message("error", validation_error)
    tn1, msg1 = telnet_login(sw1_ip, username, password)
    if not tn1:
        return message("error", f"SW1: {msg1}")
    tn2, msg2 = telnet_login(sw2_ip, username, password)
    if not tn2:
        tn1.close()
        return message("error", f"SW2: {msg2}")
    ok1, vlan_msg1 = check_vlan_exists(tn1, vlan)
    ok2, vlan_msg2 = check_vlan_exists(tn2, vlan)
    if not ok1 or not ok2:
        tn1.close()
        tn2.close()
        return message("error", "VLAN check failed.", [vlan_msg1, vlan_msg2])
    sw1_addr, sw1_mask = cidr_to_ip_mask(sw1_interface_ip)
    sw2_addr, sw2_mask = cidr_to_ip_mask(sw2_interface_ip)
    ok_config1, config_msg1, out1, mode1 = configure_svi_interface(tn1, vlan, sw1_addr, sw1_mask, "SW1")
    if not ok_config1:
        tn1.close()
        tn2.close()
        return message("error", config_msg1, [out1])
    ok_config2, config_msg2, out2, mode2 = configure_svi_interface(tn2, vlan, sw2_addr, sw2_mask, "SW2")
    if not ok_config2:
        cleanup1 = cleanup_svi_interface(tn1, vlan)
        tn1.close()
        tn2.close()
        return message("error", config_msg2, [out2, "SW1 rollback:", cleanup1])
    ping, repeat_done = run_smart_ping(tn1, sw2_addr)
    cleanup_output = "Cleanup skipped. SVI remains bound."
    if cleanup:
        cleanup1 = cleanup_svi_interface(tn1, vlan)
        cleanup2 = cleanup_svi_interface(tn2, vlan)
        cleanup_output = f"SW1 cleanup:\n{cleanup1}\n\nSW2 cleanup:\n{cleanup2}"
    tn1.close()
    tn2.close()
    verdict = analyze_ping_output(ping)
    return {
        "kind": "success",
        "message": "P2P test completed.",
        "details": ["OK Input validation passed", f"OK SW1: {vlan_msg1}", f"OK SW2: {vlan_msg2}", "OK Ping test completed", "OK SVI cleanup completed" if cleanup else "OK SVI cleanup skipped"],
        "raw": f"TEST SUMMARY\nVLAN: {vlan}\nSW1: {sw1_ip} -> {sw1_addr}/{sw1_mask} ({mode1})\nSW2: {sw2_ip} -> {sw2_addr}/{sw2_mask} ({mode2})\n\nCONFIG OUTPUT\n{'=' * 60}\nSW1:\n{out1}\n\nSW2:\n{out2}\n\nPING OUTPUT\n{'=' * 60}\n{ping}\n\nSVI CLEANUP\n{'=' * 60}\n{cleanup_output}",
        "p2p": {
            "type": "P2P Switch to Switch",
            "summary": [
                ("Test Type", "P2P Switch to Switch"),
                ("SW1", sw1_ip),
                ("SW2", sw2_ip),
                ("VLAN", vlan),
                ("SW1 IP", sw1_addr),
                ("SW2 IP", sw2_addr),
            ],
            "progress": 100,
            "stage": "Test Completed Successfully",
            "checks": [f"SW1: {vlan_msg1}", f"SW2: {vlan_msg2}", f"SW1 CLI mode: {mode1}", f"SW2 CLI mode: {mode2}"],
            "ping_title": "Ping Output (SW1->SW2) - Basic + 1000 Pings" if repeat_done else "Ping Output (SW1->SW2) - Basic Ping Only",
            "ping_output": ping,
            "verdict": verdict,
            "cleanup": "Cleanup Completed" if cleanup else "Cleanup Skipped",
        },
    }


def run_single_switch_test(post):
    username = post.get("username", "").strip()
    password = post.get("password", "")
    switch_ip = post.get("single_switch_ip", "").strip()
    vlan = post.get("vlan_id", "").strip()
    interface_ip = post.get("switch_interface_ip", "").strip()
    target_ip = post.get("target_ip", "").strip()
    cleanup = post.get("clean_up_interfaces") == "on"
    if not all([username, password, switch_ip, vlan, interface_ip, target_ip]):
        return message("error", "All single-switch fields are required.")
    validation_error = validate_single_switch_inputs(post)
    if validation_error:
        return message("error", validation_error)
    tn, login_msg = telnet_login(switch_ip, username, password)
    if not tn:
        return message("error", login_msg)
    ok, vlan_msg = check_vlan_exists(tn, vlan)
    if not ok:
        tn.close()
        return message("error", vlan_msg)
    addr, mask = cidr_to_ip_mask(interface_ip)
    config_ok1, config_msg1, config1, mode1 = configure_svi_interface(tn, vlan, addr, mask, "switch interface")
    if not config_ok1:
        tn.close()
        return message("error", config_msg1, [config1])
    gw_to_client_ping, gw_repeat_done = run_smart_ping(tn, target_ip)
    arp1 = ""
    if _ping_failed(gw_to_client_ping):
        arp1 = get_p2p_arp_table(tn, vlan=vlan, target_ip=target_ip)

    config_ok2, config_msg2, config2, mode2 = configure_svi_interface(tn, vlan, target_ip, mask, "client interface", replace_existing=True)
    if not config_ok2:
        cleanup_output = cleanup_svi_interface(tn, vlan)
        tn.close()
        return message("error", config_msg2, [config2, "Cleanup:", cleanup_output])
    client_to_gw_ping, client_repeat_done = run_smart_ping(tn, addr)
    arp2 = ""
    if _ping_failed(client_to_gw_ping):
        arp2 = get_p2p_arp_table(tn, vlan=vlan, target_ip=addr)
    cleanup_output = "Cleanup skipped. SVI remains bound."
    if cleanup:
        cleanup_output = cleanup_svi_interface(tn, vlan)
    tn.close()
    gw_verdict = analyze_ping_output(gw_to_client_ping)
    client_verdict = analyze_ping_output(client_to_gw_ping)
    if gw_verdict["kind"] == "error" or client_verdict["kind"] == "error":
        verdict = {"kind": "error", "text": "Connectivity failed in one or both directions"}
    elif gw_verdict["kind"] == "warning" or client_verdict["kind"] == "warning":
        verdict = gw_verdict
    else:
        verdict = {"kind": "success", "text": "Bidirectional connectivity verified"}
    return {
        "kind": "success",
        "message": "Single-switch test completed.",
        "details": ["OK Input validation passed", f"OK {vlan_msg}", f"OK GW -> Client test completed ({mode1})", f"OK Client -> GW test completed ({mode2})", "OK SVI cleanup completed" if cleanup else "OK SVI cleanup skipped"],
        "raw": f"TEST SUMMARY\nVLAN: {vlan}\nSwitch: {switch_ip}\nSwitch SVI: {addr}/{mask}\nClient IP: {target_ip}\n\nTEST 1 CONFIG OUTPUT\n{'=' * 60}\n{config1}\n\nGW TO CLIENT PING OUTPUT\n{'=' * 60}\n{gw_to_client_ping}\n\nARP OUTPUT - GW TO CLIENT\n{'=' * 60}\n{arp1 or 'ARP check skipped because ping did not fully fail.'}\n\nTEST 2 CONFIG OUTPUT\n{'=' * 60}\n{config2}\n\nCLIENT TO GW PING OUTPUT\n{'=' * 60}\n{client_to_gw_ping}\n\nARP OUTPUT - CLIENT TO GW\n{'=' * 60}\n{arp2 or 'ARP check skipped because ping did not fully fail.'}\n\nSVI CLEANUP\n{'=' * 60}\n{cleanup_output}",
        "p2p": {
            "type": "Single Switch to End User",
            "summary": [
                ("Test Type", "Single Switch to End User"),
                ("Switch IP", switch_ip),
                ("VLAN", vlan),
                ("Switch Interface IP", f"{addr}/{mask}"),
                ("Target IP", target_ip),
            ],
            "progress": 100,
            "stage": "Test Completed Successfully",
            "checks": [f"Switch: {vlan_msg}", f"GW -> Client test completed ({mode1})", f"Client -> GW test completed ({mode2})"],
            "ping_title": "Bidirectional Ping Output - Basic + 1000 Pings" if (gw_repeat_done or client_repeat_done) else "Bidirectional Ping Output - Basic Ping Only",
            "ping_output": f"GW -> Client\n{'=' * 60}\n{gw_to_client_ping}\n\nClient -> GW\n{'=' * 60}\n{client_to_gw_ping}",
            "verdict": verdict,
            "cleanup": "Cleanup Completed" if cleanup else "Cleanup Skipped",
        },
    }


def analyze_ping_output(output):
    text = output or ""
    if re.search(r"Success\s+rate\s+is\s+0\s+percent", text, re.I) or re.search(r"100(?:\.0+)?%\s+packet\s+loss", text, re.I):
        return {"kind": "error", "text": "Ping Failed - No Connectivity (0%)"}

    success = None
    loss = None
    cisco_matches = re.findall(r"Success\s+rate\s+is\s+(\d+)\s*percent.*?\((\d+)/(\d+)\)", text, re.I)
    linux_matches = re.findall(
        r"(\d+)\s+packets\s+transmitted.*?(\d+)\s+(?:packets\s+)?received.*?([\d.]+)%\s*packet\s*loss",
        text,
        re.S | re.I,
    )
    if cisco_matches:
        success_text, received_text, transmitted_text = cisco_matches[-1]
        success = int(success_text)
        received = int(received_text)
        transmitted = int(transmitted_text) or 1
        loss = round(((transmitted - received) / transmitted) * 100, 2)
    elif linux_matches:
        transmitted_text, received_text, loss_text = linux_matches[-1]
        transmitted = int(transmitted_text) or 1
        received = int(received_text)
        loss = float(loss_text)
        success = round((received / transmitted) * 100, 2)
    else:
        matches = re.findall(r"Success\s+rate\s+is\s+(\d+)\s+percent", text, re.I)
        success = int(matches[-1]) if matches else None
        loss = 100 - success if success is not None else None

    if success is None:
        return {"kind": "warning", "text": "Ping Output Format Unexpected"}
    if success == 100:
        return {"kind": "success", "text": f"Perfect Connectivity - {success}% (~0.00% loss)"}
    if success >= 98:
        return {"kind": "success", "text": f"Results fine - {success}% (~{loss:.2f}% loss)"}
    if success >= 80:
        if loss >= 5:
            return {"kind": "error", "text": f"Severe Drops observed - {success}% (~{loss:.1f}% loss)"}
        return {"kind": "warning", "text": f"Minor Drops Observed - {success}% (~{loss:.1f}% loss)"}
    return {"kind": "error", "text": f"Severe Drops Detected - {success}% (~{loss:.1f}% loss)"}


def onu_fetch_status(post):
    host = post.get("olt_ip", "").strip()
    username = post.get("username", "").strip()
    password = post.get("password", "")
    serial = post.get("serial", "").strip()
    if not all([host, username, password, serial]):
        return message("error", "OLT IP, username, password, and ONU serial/MAC are required.")
    tn, login_msg = telnet_login(host, username, password, timeout=15)
    if not tn:
        return message("error", login_msg)
    commands = [
        "terminal length 0",
        "show gpon onu state",
        "show epon onu-information",
    ]
    raw = ""
    for cmd in commands:
        raw += f"\n\n=> {cmd}\n{run_command(tn, cmd, 4)}"
    tn.close()
    matches = [line for line in raw.splitlines() if serial.lower().replace(":", "") in line.lower().replace(":", "")]
    return {"kind": "success" if matches else "warning", "message": f"Found {len(matches)} matching ONU line(s).", "details": matches, "raw": raw}
