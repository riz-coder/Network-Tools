from django.http import Http404, JsonResponse
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import redirect, render

from . import services


TOOLS = {
    "corporate-deployment": {
        "name": "Corporate Deployment",
        "short_name": "Deployment",
        "description": "VLAN spanning and last-mile switch configuration",
        "icon": "CD",
    },
    "p2p-testing": {
        "name": "P2P Testing",
        "short_name": "P2P Testing",
        "description": "Point-to-point and single-switch connectivity tests",
        "icon": "P2P",
    },
    "onu-configuration": {
        "name": "ONU Configuration",
        "short_name": "ONU Config",
        "description": "VSOL GPON and EPON smart configuration",
        "icon": "ONU",
    },
    "olt-vlan-creator": {
        "name": "OLT VLAN Creator",
        "short_name": "OLT VLAN",
        "description": "Create VLANs on VSOL OLT devices",
        "icon": "OLT",
    },
    "cisco-ios-uploader": {
        "name": "Cisco IOS Uploader",
        "short_name": "IOS Uploader",
        "description": "Phase 1 audit for Cisco IOS image, model, and flash space",
        "icon": "IOS",
    },
    "dealers-access-router": {
        "name": "Access Switch",
        "short_name": "Access Switch",
        "description": "Access switch automation workspace",
        "icon": "AS",
    },
}

VISIBLE_TOOL_SLUGS = ("corporate-deployment", "p2p-testing", "cisco-ios-uploader", "dealers-access-router")


def _context(active_tool=None, **extra):
    visible_tools = {slug: TOOLS[slug] for slug in VISIBLE_TOOL_SLUGS}
    all_users = [
        {"username": user.username, "color": services.user_color(user.username, index)}
        for index, user in enumerate(User.objects.order_by("username"))
    ]
    context = {
        "tools": TOOLS,
        "visible_tools": visible_tools,
        "active_tool": active_tool,
        "selected": TOOLS.get(active_tool),
        "total_users": User.objects.count(),
        "all_users": all_users,
    }
    context.update(extra)
    return context


@login_required
def home(request):
    return render(
        request,
        "dashboard/home.html",
        _context(
            activity=services.overview_activity(),
            mac_dashboard=services.mac_dashboard(),
            dc_oc_mac_dashboard=services.dc_oc_mac_dashboard(),
        ),
    )


@login_required
def users(request):
    if request.user.username != "rizwan":
        return redirect("dashboard:home")
    return render(request, "dashboard/users.html", _context())


@login_required
def access_switch_config(request):
    return render(
        request,
        "dashboard/access_switch_config.html",
        _context("dealers-access-router", access_switch_phase1=request.session.get("access_switch_phase1", {})),
    )


@login_required
def tool(request, tool_slug):
    if tool_slug not in TOOLS:
        raise Http404("Tool not found")

    result = None
    defaults = {}
    selected_regions = []
    if request.method == "POST":
        action = request.POST.get("action", "")
        defaults = request.POST.dict()
        selected_regions = request.POST.getlist("regions")
        try:
            if action == "span_vlan":
                result = services.span_vlan(request.POST)
            elif action == "fetch_lastmile_ports":
                result = services.fetch_lastmile_ports(request.POST)
            elif action == "apply_lastmile":
                result = services.apply_lastmile(request.POST)
            elif action == "show_interface":
                result = services.show_interface(request.POST)
            elif action == "olt_create_vlan":
                result = services.create_olt_vlan(request.POST)
            elif action == "p2p_test":
                result = services.run_p2p_test(request.POST)
            elif action == "single_switch_test":
                result = services.run_single_switch_test(request.POST)
            elif action == "onu_fetch":
                result = services.onu_fetch_status(request.POST)
            elif action == "ios_phase1":
                result = services.cisco_ios_phase1(request.POST)
            elif action == "ios_upload":
                result = services.cisco_ios_upload(request.POST)
            elif action == "dealers_access_phase1":
                result = services.dealer_access_switch_phase1(request.POST)
                dealer_switch = result.get("dealer_switch") if isinstance(result, dict) else None
                if result.get("kind") == "success" and dealer_switch:
                    request.session["access_switch_phase1"] = {
                        "username": request.POST.get("username", "").strip(),
                        "password": request.POST.get("password", ""),
                        "switch_ip": dealer_switch.get("switch_ip", request.POST.get("switch_ip", "").strip()),
                        "cdp_message": dealer_switch.get("cdp", {}).get("message", ""),
                        "cdp_noc_switch": dealer_switch.get("cdp", {}).get("noc_switch", False),
                        "ios_required": dealer_switch.get("ios_decision", {}).get("required", False),
                    }
            else:
                result = services.message("error", "Unknown action.")
            if action in {"span_vlan", "apply_lastmile", "p2p_test", "single_switch_test", "ios_phase1", "ios_upload", "dealers_access_phase1"}:
                services.log_activity(
                    request.POST.get("username", "").strip(),
                    tool_slug,
                    TOOLS[tool_slug]["name"],
                    {
                        "span_vlan": "VLAN Span",
                        "apply_lastmile": "Last-Mile Port",
                        "p2p_test": "P2P Switch Test",
                        "single_switch_test": "Single Switch Test",
                        "ios_phase1": "Cisco IOS Phase 1",
                        "ios_upload": "Cisco IOS Upload",
                        "dealers_access_phase1": "Access Switch Phase 1",
                    }.get(action, action),
                    result,
                    request.user.username,
                )
        except Exception as exc:
            result = services.message("error", f"Unhandled error: {exc}")

    return render(
        request,
        "dashboard/tool.html",
        _context(
            tool_slug,
            result=result,
            defaults=defaults,
            regions=services.REGION_SUBNETS,
            excluded_defaults=services.REGION_EXCLUDE_IPS,
            selected_regions=selected_regions,
        ),
    )


def health(request):
    return JsonResponse({"status": "ok", "application": "NETWORK-TOOLS"})


@login_required
def lastmile_interfaces(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    ok, msg, ports, raw = services.fetch_lastmile_port_rows(
        request.POST.get("lastmile_ip", "").strip(),
        request.POST.get("username", "").strip(),
        request.POST.get("password", ""),
    )
    return JsonResponse({"ok": ok, "message": msg, "ports": ports, "raw": raw})


@login_required
def telnet_check(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    ok, msg = services.check_telnet_access(
        request.POST.get("switch_ip", request.POST.get("lastmile_ip", "")).strip(),
        request.POST.get("username", "").strip(),
        request.POST.get("password", ""),
    )
    return JsonResponse({"ok": ok, "message": msg})


@login_required
def ios_upload_start(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    job_id = services.start_cisco_ios_upload_job(request.POST)
    return JsonResponse({"ok": True, "job_id": job_id})


@login_required
def ios_upload_status(request, job_id):
    job = services.get_cisco_ios_upload_job(job_id)
    return JsonResponse(job)


@login_required
def live_tool_start(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    action = request.POST.get("action", "")
    live_post = request.POST.copy()
    live_post["login_user"] = request.user.username
    job_id = services.start_live_tool_job(action, live_post)
    return JsonResponse({"ok": True, "job_id": job_id})


@login_required
def live_tool_status(request, job_id):
    return JsonResponse(services.get_live_tool_job(job_id))


@login_required
def mac_update(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    result = services.update_mac_cache_for_switch(
        request.POST.get("ip", "").strip(),
        request.POST.get("username", "").strip(),
        request.POST.get("password", ""),
    )
    return JsonResponse(result)


@login_required
def mac_update_all(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "POST required."}, status=405)
    result = services.update_all_mac_cache(
        request.POST.get("username", "").strip(),
        request.POST.get("password", ""),
    )
    return JsonResponse(result)


def logout_user(request):
    logout(request)
    return redirect("login")


@login_required
def add_user(request):
    if request.user.username != "rizwan":
        return redirect("dashboard:home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if username and password:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            if username == "rizwan":
                user.is_staff = True
                user.is_superuser = True
            user.is_active = True
            user.save()
    return redirect("dashboard:users")


@login_required
def delete_user(request):
    if request.user.username != "rizwan":
        return redirect("dashboard:home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        if username and username != "rizwan":
            User.objects.filter(username=username).delete()
    return redirect("dashboard:users")
