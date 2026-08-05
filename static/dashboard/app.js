(function () {
  function qs(root, selector) { return root.querySelector(selector); }
  function qsa(root, selector) { return Array.prototype.slice.call(root.querySelectorAll(selector)); }

  var sidebar = document.getElementById("sidebar");
  var menu = document.getElementById("menuButton");
  if (menu && sidebar) {
    menu.addEventListener("click", function () { sidebar.classList.toggle("open"); });
  }

  var themeToggle = document.querySelector("[data-theme-toggle]");
  var themeToggleText = document.querySelector("[data-theme-toggle-text]");
  var themeToggleIcon = document.querySelector("[data-theme-toggle-icon]");
  function setTheme(theme) {
    var isLight = theme === "light";
    document.body.classList.toggle("light-theme", isLight);
    if (themeToggleText) themeToggleText.textContent = isLight ? "Dark Theme" : "Light Theme";
    if (themeToggleIcon) themeToggleIcon.textContent = isLight ? "☾" : "☀";
    try { window.localStorage.setItem("networkToolsTheme", isLight ? "light" : "dark"); } catch (error) {}
  }
  try {
    setTheme(window.localStorage.getItem("networkToolsTheme") || "dark");
  } catch (error) {
    setTheme("dark");
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", function () {
      setTheme(document.body.classList.contains("light-theme") ? "dark" : "light");
    });
  }

  function parseLiveJson(response) {
    var contentType = response.headers.get("content-type") || "";
    if (contentType.indexOf("application/json") === -1) {
      return response.text().then(function () {
        throw new Error("Live API returned HTML instead of JSON. HTTP " + response.status + ".");
      });
    }
    return response.json();
  }

  function runLiveForm(form, overlaySelector, barSelector, stepSelector, title) {
    var overlay = document.querySelector(overlaySelector);
    var bar = document.querySelector(barSelector);
    var steps = qsa(document, stepSelector);
    if (!overlay || !bar) return false;
    overlay.hidden = false;
    var card = qs(overlay, ".progress-card");
    var liveBox = qs(overlay, "[data-live-job-output]");
    var backButton = qs(overlay, "[data-live-back-button]");
    if (!liveBox) {
      liveBox = document.createElement("div");
      liveBox.className = "live-copy-preview live-color-output";
      liveBox.setAttribute("data-live-job-output", "");
      card.appendChild(liveBox);
    }
    if (!backButton) {
      backButton = document.createElement("a");
      backButton.className = "primary-button back-overview-button";
      backButton.setAttribute("data-live-back-button", "");
      backButton.href = "#";
      backButton.textContent = "Back to Tool";
      backButton.hidden = true;
      card.appendChild(backButton);
    }
    liveBox.hidden = false;
    liveBox.innerHTML = '<div class="live-line info">Starting live job...</div>';
    backButton.hidden = true;
    if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
    var body = new URLSearchParams(new FormData(form));
    fetch(form.dataset.liveStartUrl, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: body })
      .then(parseLiveJson)
      .then(function (data) {
        if (!data.ok) throw new Error(data.message || "Live job could not start.");
        var statusUrl = form.dataset.liveStatusUrlTemplate.replace("JOB_ID", data.job_id);
        var poll = function () {
          fetch(statusUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
            .then(parseLiveJson)
            .then(function (job) {
              bar.style.width = Math.max(2, Math.min(100, Number(job.percent) || 0)) + "%";
              if (steps.length) {
                var activeIndex = Math.min(steps.length - 1, Math.floor(((Number(job.percent) || 0) / 100) * steps.length));
                steps.forEach(function (step, index) {
                  step.classList.remove("done");
                  step.classList.toggle("active", index === activeIndex && !job.done);
                });
              }
              function esc(value) {
                return String(value || "").replace(/[&<>"']/g, function (char) {
                  return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[char];
                });
              }
              function lineClass(line) {
                if (/^\s*(ERROR|FAIL|FAILED)/i.test(line)) return "error";
                if (/^\s*(OK|SUCCESS|\[OK\])/i.test(line)) return "ok";
                if (/warning|timed out|not found/i.test(line)) return "warn";
                if (/^=+$|^OUTPUT$|^Stage:|^Status:/i.test(line)) return "info";
                if (/^\s*(Current configuration|Building configuration|interface |description |switchport |storm-control|spanning-tree|service-policy|ip access-group|no cdp|end|[A-Za-z0-9_.-]+#)/i.test(line)) return "config";
                return "plain";
              }
              var lines = ["Stage: " + (job.stage || ""), "Status: " + (job.message || ""), ""]
                .concat(job.details || []);
              if (job.raw) lines = lines.concat(["", "OUTPUT", "=".repeat(60)]).concat(String(job.raw).split("\n"));
              liveBox.innerHTML = lines.map(function (line) {
                return '<div class="live-line ' + lineClass(line) + '">' + (esc(line) || "&nbsp;") + "</div>";
              }).join("");
              liveBox.scrollTop = liveBox.scrollHeight;
              if (job.done) {
                if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.add(job.kind === "success" ? "verified" : "failed");
                steps.forEach(function (step) {
                  step.classList.remove("active");
                  step.classList.add("done");
                });
                bar.style.width = "100%";
                var action = (qs(form, 'input[name="action"]') || {}).value || "";
                if (backButton && (action === "span_vlan" || action === "apply_lastmile")) {
                  backButton.href = "/tools/corporate-deployment/";
                  backButton.textContent = "Back to Deployment";
                  backButton.hidden = false;
                } else if (backButton && (action === "p2p_test" || action === "single_switch_test")) {
                  backButton.href = "/tools/p2p-testing/";
                  backButton.textContent = "Back to P2P Tool";
                  backButton.hidden = false;
                }
                return;
              }
              window.setTimeout(poll, 1000);
            })
            .catch(function (error) { liveBox.innerHTML += '<div class="live-line error">Polling failed: ' + error.message + '</div>'; });
        };
        poll();
      })
      .catch(function (error) { liveBox.innerHTML += '<div class="live-line error">Live start failed: ' + error.message + '</div>'; });
    return true;
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form || !form.matches("[data-live-form]")) return;
    var submitterAction = event.submitter ? event.submitter.value : "";
    if (submitterAction === "show_interface") return;
    var actionInput = qs(form, 'input[name="action"]');
    var action = actionInput ? actionInput.value : "";
    var config = {
      "span_vlan": ["[data-progress-overlay]", "[data-progress-bar]", "[data-progress-step]", "VLAN Span Running"],
      "apply_lastmile": ["[data-lastmile-progress]", "[data-lastmile-progress-bar]", "[data-lastmile-progress-step]", "Last-Mile Configuration Running"],
      "p2p_test": ["[data-p2p-progress]", "[data-p2p-progress-bar]", "[data-p2p-progress-step]", "P2P Switch Test Running"],
      "single_switch_test": ["[data-p2p-progress]", "[data-p2p-progress-bar]", "[data-p2p-progress-step]", "Single Switch Test Running"],
      "ios_phase1": ["[data-ios-progress]", "[data-ios-progress-bar]", "[data-ios-progress-step]", "Cisco IOS Phase 1 Running"]
    }[action];
    if (!config) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    runLiveForm(form, config[0], config[1], config[2], config[3]);
  }, true);

  qsa(document, ".result-panel pre, .p2p-ping-output").forEach(function (pre) {
    if (pre.dataset.colored === "yes") return;
    var text = pre.textContent || "";
    function esc(value) {
      return String(value || "").replace(/[&<>"']/g, function (char) {
        return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[char];
      });
    }
    function klass(line) {
      if (/^\s*(ERROR|FAIL|FAILED)/i.test(line)) return "error";
      if (/^\s*(OK|SUCCESS|\[OK\])/i.test(line)) return "ok";
      if (/warning|timed out|not found|drops/i.test(line)) return "warn";
      if (/^=+$|OUTPUT|CONFIG|SUMMARY|FINAL|PING|SVI/i.test(line)) return "info";
      if (/^\s*(Current configuration|Building configuration|interface |description |switchport |storm-control|spanning-tree|service-policy|ip access-group|no cdp|end|[A-Za-z0-9_.-]+#)/i.test(line)) return "config";
      return "plain";
    }
    pre.dataset.colored = "yes";
    pre.classList.add("live-color-output");
    pre.innerHTML = text.split("\n").map(function (line) {
      return '<div class="live-line ' + klass(line) + '">' + (esc(line) || "&nbsp;") + "</div>";
    }).join("");
  });

  var picker = document.querySelector("[data-region-picker]");
  var vlanForm = document.querySelector('[data-progress-form="vlan"]');
  var vlanRegionsApplied = false;

  function validateVlanForm() {
    if (!vlanForm) return false;
    var username = qs(vlanForm, 'input[name="username"]').value.trim();
    var password = qs(vlanForm, 'input[name="password"]').value;
    var vlanIdInput = qs(vlanForm, "[data-vlan-id]");
    var vlanName = qs(vlanForm, 'input[name="vlan_name"]').value.trim();
    var selectedRegions = qsa(vlanForm, 'input[name="regions"]:checked');
    var message = qs(vlanForm, "[data-vlan-message]");
    var button = qs(vlanForm, "[data-vlan-submit]");
    var vlanOk = false;
    var text = "";

    if (vlanIdInput.value.trim()) {
      var vlanNumber = Number(vlanIdInput.value.trim());
      if (!Number.isInteger(vlanNumber)) text = "VLAN ID must be numeric";
      else if (vlanNumber < 1 || vlanNumber > 4094) text = "VLAN ID must be between 1-4094";
      else { vlanOk = true; text = "VLAN ID is valid"; }
    }

    if (message) {
      message.textContent = text;
      message.classList.toggle("ok", vlanOk);
    }

    var ready = Boolean(username && password && vlanOk && vlanName && selectedRegions.length && vlanRegionsApplied);
    if (button) {
      button.classList.toggle("valid", ready);
      button.classList.toggle("invalid", !ready);
    }
    return ready;
  }

  if (picker) {
    var summary = qs(picker, "[data-region-summary]");
    var clear = qs(picker, "[data-clear-regions]");
    var apply = qs(picker, "[data-apply-regions]");
    var checks = qsa(picker, 'input[name="regions"]');
    var excludeBox = document.querySelector('textarea[name="exclude_ips"]');

    function updateRegions() {
      var selected = checks.filter(function (check) { return check.checked; });
      vlanRegionsApplied = false;
      summary.textContent = selected.length ? selected.map(function (check) { return check.value; }).join(", ") : "No region selected";
      if (apply) {
        apply.disabled = !selected.length;
        apply.classList.toggle("ready", Boolean(selected.length));
        apply.classList.toggle("blurred", !selected.length);
        apply.textContent = selected.length ? "Apply Selected Regions" : "Select Region First";
      }
      validateVlanForm();
    }

    function applySelectedRegions() {
      var selected = checks.filter(function (check) { return check.checked; });
      var ips = new Set();
      (excludeBox.value || "").split(",").map(function (ip) { return ip.trim(); }).filter(Boolean).forEach(function (ip) { ips.add(ip); });
      selected.forEach(function (check) {
        (check.dataset.excludes || "").split(",").map(function (ip) { return ip.trim(); }).filter(Boolean).forEach(function (ip) { ips.add(ip); });
      });
      excludeBox.value = Array.from(ips).join(", ");
      vlanRegionsApplied = Boolean(selected.length);
      if (apply) {
        apply.classList.add("applied");
        apply.textContent = "Regions Applied";
      }
      validateVlanForm();
    }

    checks.forEach(function (check) { check.addEventListener("change", updateRegions); });
    if (clear) clear.addEventListener("click", function () {
      checks.forEach(function (check) { check.checked = false; });
      excludeBox.value = "";
      updateRegions();
    });
    if (apply) apply.addEventListener("click", applySelectedRegions);
    updateRegions();
  }

  if (vlanForm) {
    qsa(vlanForm, "input, textarea").forEach(function (field) {
      field.addEventListener("input", validateVlanForm);
      field.addEventListener("change", validateVlanForm);
    });
    vlanForm.addEventListener("submit", function (event) {
      if (!validateVlanForm()) { event.preventDefault(); return; }
      var overlay = document.querySelector("[data-progress-overlay]");
      var bar = document.querySelector("[data-progress-bar]");
      var steps = qsa(document, "[data-progress-step]");
      if (!overlay || !bar || !steps.length) return;
      overlay.hidden = false;
      if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
      var index = 0;
      var tick = function () {
        steps.forEach(function (step, stepIndex) {
          step.classList.remove("done");
          step.classList.toggle("active", stepIndex === index);
        });
        bar.style.width = Math.min(12 + index * 16, 94) + "%";
        index = Math.min(index + 1, steps.length - 1);
      };
      tick();
      window.setInterval(tick, 1800);
    });
    validateVlanForm();
  }

  var resultPanel = document.querySelector("[data-auto-overview-url]");
  if (resultPanel) {
    var countdown = document.querySelector("[data-redirect-countdown]");
    var seconds = 60;
    var url = resultPanel.dataset.autoOverviewUrl || "/";
    var redirectTick = function () {
      if (countdown) countdown.textContent = "Overview will open in " + seconds + " seconds.";
      if (seconds <= 0) {
        window.location.href = url;
        return;
      }
      seconds -= 1;
      window.setTimeout(redirectTick, 1000);
    };
    redirectTick();
  }

  var reservedVlans = [7,8,9,11,13,15,21,23,28,36,100,101,900,910,1000,1900,1901,1902,1903,1904,1905,1906,1907,2500,2300,2520];

  function ipToInt(ip) {
    var parts = ip.split(".").map(Number);
    if (parts.length !== 4 || parts.some(function (part) { return isNaN(part) || part < 0 || part > 255; })) throw new Error("Invalid IP address");
    return (((parts[0] << 24) >>> 0) + (parts[1] << 16) + (parts[2] << 8) + parts[3]) >>> 0;
  }

  function parseCidr(value) {
    var pieces = value.split("/");
    if (pieces.length !== 2) throw new Error("CIDR is required");
    var prefix = Number(pieces[1]);
    if (!Number.isInteger(prefix) || prefix < 1 || prefix > 32) throw new Error("Invalid prefix");
    var ipInt = ipToInt(pieces[0]);
    var mask = prefix === 32 ? 0xffffffff : (0xffffffff << (32 - prefix)) >>> 0;
    var network = ipInt & mask;
    var broadcast = network | (~mask >>> 0);
    return { ip: pieces[0], ipInt: ipInt, prefix: prefix, network: network >>> 0, broadcast: broadcast >>> 0 };
  }

  function validateP2pVlan(vlanValue) {
    var vlan = Number(vlanValue);
    if (!Number.isInteger(vlan)) return "VLAN must be numeric.";
    if (vlan < 1 || vlan > 4094) return "VLAN must be between 1-4094.";
    if (reservedVlans.indexOf(vlan) !== -1) return "VLAN " + vlan + " is reserved.";
    return "";
  }

  function setP2pState(form, ok, message) {
    var msg = qs(form, "[data-p2p-message]");
    var button = qs(form, "[data-p2p-submit]");
    if (msg) {
      msg.textContent = message || (ok ? "Validation passed." : "");
      msg.classList.toggle("ok", ok);
    }
    if (button) {
      button.classList.toggle("valid", ok);
      button.classList.toggle("invalid", !ok);
    }
  }

  function validateP2pForm(form) {
    var type = form.dataset.p2pForm;
    try {
      var username = qs(form, 'input[name="username"]').value.trim();
      var password = qs(form, 'input[name="password"]').value;
      var vlan = qs(form, 'input[name="vlan_id"]').value.trim();
      if (!username || !password || !vlan) throw new Error("Username, password and VLAN are required.");
      var vlanError = validateP2pVlan(vlan);
      if (vlanError) throw new Error(vlanError);
      if (type === "switch") {
        var sw1 = qs(form, 'input[name="sw1_ip"]').value.trim();
        var sw2 = qs(form, 'input[name="sw2_ip"]').value.trim();
        var iface1 = parseCidr(qs(form, 'input[name="sw1_interface_ip"]').value.trim());
        var iface2 = parseCidr(qs(form, 'input[name="sw2_interface_ip"]').value.trim());
        if (!sw1 || !sw2) throw new Error("Both switch IPs are required.");
        if (ipToInt(sw1) === ipToInt(sw2)) throw new Error("Switch IPs must not be identical.");
        if (iface1.ipInt === iface2.ipInt) throw new Error("SVI interface IPs must not be identical.");
        if (iface1.network !== iface2.network || iface1.prefix !== iface2.prefix) throw new Error("SVI IPs must be in the same subnet.");
        if (iface1.ipInt === iface1.network || iface1.ipInt === iface1.broadcast) throw new Error("SW1 SVI cannot be network/broadcast address.");
        if (iface2.ipInt === iface2.network || iface2.ipInt === iface2.broadcast) throw new Error("SW2 SVI cannot be network/broadcast address.");
      } else {
        var switchIp = qs(form, 'input[name="single_switch_ip"]').value.trim();
        var switchIface = parseCidr(qs(form, 'input[name="switch_interface_ip"]').value.trim());
        var targetIp = ipToInt(qs(form, 'input[name="target_ip"]').value.trim());
        if (!switchIp) throw new Error("Switch IP is required.");
        if (targetIp < switchIface.network || targetIp > switchIface.broadcast) throw new Error("Client IP must be in the same subnet as switch SVI.");
      }
      setP2pState(form, true, "Validation passed.");
      return true;
    } catch (error) {
      setP2pState(form, false, error.message);
      return false;
    }
  }

  qsa(document, "[data-p2p-form]").forEach(function (form) {
    qsa(form, "input").forEach(function (field) {
      field.addEventListener("input", function () { validateP2pForm(form); });
      field.addEventListener("change", function () { validateP2pForm(form); });
    });
    form.addEventListener("submit", function (event) {
      if (!validateP2pForm(form)) {
        event.preventDefault();
        return;
      }
      var overlay = document.querySelector("[data-p2p-progress]");
      var bar = document.querySelector("[data-p2p-progress-bar]");
      var steps = qsa(document, "[data-p2p-progress-step]");
      if (!overlay || !bar || !steps.length) return;
      overlay.hidden = false;
      if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
      var index = 0;
      var tick = function () {
        steps.forEach(function (step, stepIndex) {
          step.classList.remove("done");
          step.classList.toggle("active", stepIndex === index);
        });
        bar.style.width = Math.min(10 + index * 12, 94) + "%";
        index = Math.min(index + 1, steps.length - 1);
      };
      tick();
      window.setInterval(tick, 1600);
    });
    validateP2pForm(form);
  });

  qsa(document, "[data-ios-form]").forEach(function (form) {
    var button = qs(form, "[data-ios-submit]");
    var message = qs(form, "[data-ios-message]");
    function validateIosForm() {
      var username = qs(form, 'input[name="username"]').value.trim();
      var password = qs(form, 'input[name="password"]').value;
      var deviceIp = qs(form, 'input[name="device_ip"]').value.trim();
      var ok = Boolean(username && password && deviceIp);
      if (message) {
        message.textContent = ok ? "Ready to run Phase 1 audit." : "Username, password, and device IP are required.";
        message.classList.toggle("ok", ok);
      }
      if (button) {
        button.classList.toggle("valid", ok);
        button.classList.toggle("invalid", !ok);
      }
      return ok;
    }
    qsa(form, "input").forEach(function (field) {
      field.addEventListener("input", validateIosForm);
      field.addEventListener("change", validateIosForm);
    });
    form.addEventListener("submit", function (event) {
      if (!validateIosForm()) {
        event.preventDefault();
        return;
      }
      var overlay = document.querySelector("[data-ios-progress]");
      var bar = document.querySelector("[data-ios-progress-bar]");
      var steps = qsa(document, "[data-ios-progress-step]");
      if (!overlay || !bar || !steps.length) return;
      overlay.hidden = false;
      if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
      var index = 0;
      var tick = function () {
        steps.forEach(function (step, stepIndex) {
          step.classList.remove("done");
          step.classList.toggle("active", stepIndex === index);
          step.classList.toggle("done", stepIndex < index);
        });
        bar.style.width = Math.min(10 + index * 16, 94) + "%";
        index = Math.min(index + 1, steps.length - 1);
      };
      tick();
      window.setInterval(tick, 1600);
    });
    validateIosForm();
  });

  qsa(document, "[data-ios-select]").forEach(function (select) {
    var decision = document.querySelector("[data-ios-decision]");
    var uploadForm = document.querySelector("[data-ios-upload-form]");
    var uploadFile = document.querySelector("[data-ios-upload-file]");
    var uploadSize = document.querySelector("[data-ios-upload-size]");
    var uploadButton = document.querySelector("[data-ios-upload-button]");
    function updateIosDecision() {
      if (!decision || !select.options.length || select.disabled) {
        if (uploadForm) uploadForm.hidden = true;
        return;
      }
      var option = select.options[select.selectedIndex];
      var kind = option.dataset.kind || "";
      var status = option.dataset.status || "Select an IOS image.";
      var size = option.dataset.size || "";
      var hasSpace = option.dataset.space === "yes";
      var alreadyUploaded = option.dataset.uploaded === "yes";
      decision.classList.remove("success", "error");
      if (kind) decision.classList.add(kind);
      decision.innerHTML =
        "<strong>" + status + "</strong>" +
        "<span> Selected image: " + option.value + (size ? " (" + size + ")" : "") + "</span>";
      if (uploadFile) uploadFile.value = option.value || "";
      if (uploadSize) uploadSize.value = option.dataset.sizeBytes || "";
      if (uploadForm) uploadForm.hidden = !hasSpace || alreadyUploaded;
      if (uploadButton) uploadButton.disabled = !hasSpace || alreadyUploaded;
    }
    select.addEventListener("change", updateIosDecision);
    updateIosDecision();
  });

  qsa(document, "[data-ios-progress-form]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var overlay = document.querySelector("[data-ios-upload-progress]");
      var bar = document.querySelector("[data-ios-upload-progress-bar]");
      var steps = qsa(document, "[data-ios-upload-progress-step]");
      var liveOutput = document.querySelector("[data-ios-live-output]");
      var verification = document.querySelector("[data-ios-upload-verification]");
      var percentLabel = document.querySelector("[data-ios-upload-percent]");
      var sizeCompare = document.querySelector("[data-ios-size-compare]");
      var backOverview = document.querySelector("[data-ios-back-overview]");
      var guidelines = document.querySelector("[data-ios-guidelines]");
      if (!overlay || !bar || !steps.length) return;
      overlay.hidden = false;
      if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
      if (liveOutput) liveOutput.textContent = "";
      if (percentLabel) percentLabel.textContent = "0%";
      if (sizeCompare) {
        sizeCompare.hidden = true;
        sizeCompare.innerHTML = "";
      }
      if (backOverview) backOverview.hidden = true;
      if (guidelines) {
        guidelines.hidden = true;
        guidelines.innerHTML = "";
      }
      if (verification) {
        verification.hidden = true;
        verification.classList.remove("error");
        verification.textContent = "";
      }
      var index = 0;
      var smoothPercent = 0;
      var tick = function () {
        steps.forEach(function (step, stepIndex) {
          step.classList.remove("done");
          step.classList.toggle("active", stepIndex === index);
          step.classList.toggle("done", stepIndex < index);
        });
        smoothPercent = Math.min(95, smoothPercent + (smoothPercent < 60 ? 2 : 1));
        if (bar) bar.style.width = smoothPercent + "%";
        if (percentLabel) percentLabel.textContent = smoothPercent + "%";
        index = Math.min(index + 1, steps.length - 1);
      };
      tick();
      var progressTimer = window.setInterval(tick, 1800);
      var body = new URLSearchParams(new FormData(form));
      function parseJsonResponse(response) {
        var contentType = response.headers.get("content-type") || "";
        if (contentType.indexOf("application/json") === -1) {
          return response.text().then(function () {
            throw new Error("Upload API returned HTML instead of JSON. HTTP " + response.status + ".");
          });
        }
        return response.json();
      }
      fetch(form.dataset.iosStartUrl || form.action, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: body })
        .then(parseJsonResponse)
        .then(function (data) {
          if (!data.ok) throw new Error(data.message || "Upload job could not start.");
          var statusUrl = (form.dataset.iosStatusUrlTemplate || "").replace("JOB_ID", data.job_id);
          var poll = function () {
            fetch(statusUrl, { headers: { "X-Requested-With": "XMLHttpRequest" } })
              .then(parseJsonResponse)
              .then(function (job) {
                if (liveOutput) {
                  liveOutput.textContent = job.output || job.message || "";
                  liveOutput.scrollTop = liveOutput.scrollHeight;
                }
                if (job.done) {
                  window.clearInterval(progressTimer);
                  var stepsList = steps.length ? steps[0].parentElement : null;
                  if (stepsList) {
                    stepsList.classList.remove("verified", "failed");
                    stepsList.classList.add(job.kind === "success" ? "verified" : "failed");
                  }
                  steps.forEach(function (step) {
                    step.classList.remove("active");
                    step.classList.add("done");
                  });
                  if (bar) bar.style.width = "100%";
                  if (percentLabel) percentLabel.textContent = "100%";
                  if (verification) {
                    verification.hidden = false;
                    verification.classList.toggle("error", job.kind === "error");
                    verification.textContent = job.verification || job.message || "IOS upload finished.";
                  }
                  if (sizeCompare && (job.tftp_size || job.uploaded_size)) {
                    sizeCompare.hidden = false;
                    sizeCompare.innerHTML =
                      "<span>TFTP file size: " + (job.tftp_size || "Unknown") + "</span>" +
                      "<span>Uploaded file size: " + (job.uploaded_size || "Unknown") + "</span>";
                  }
                  if (backOverview) backOverview.hidden = false;
                  if (guidelines && job.guidelines && job.guidelines.length) {
                    guidelines.hidden = false;
                    guidelines.innerHTML =
                      "<h4>" + job.guidelines[0] + "</h4>" +
                      "<ul>" + job.guidelines.slice(1).map(function (item) {
                        return "<li>" + item + "</li>";
                      }).join("") + "</ul>";
                  }
                  return;
                }
                window.setTimeout(poll, 1000);
              })
              .catch(function (error) {
                if (liveOutput) liveOutput.textContent += "\nStatus polling failed: " + error;
              });
          };
          poll();
        })
        .catch(function (error) {
          window.clearInterval(progressTimer);
          if (liveOutput) liveOutput.textContent += "\nUpload start failed: " + error.message;
          if (verification) {
            verification.hidden = false;
            verification.classList.add("error");
            verification.textContent = error.message;
          }
        });
    });
  });

  var macDashboard = document.querySelector("[data-mac-dashboard]");
  if (macDashboard) {
    var macUsername = qs(macDashboard, 'input[name="mac_username"]');
    var macPassword = qs(macDashboard, 'input[name="mac_password"]');
    var macCsrf = qs(macDashboard, 'input[name="csrfmiddlewaretoken"]');
    var macTotal = qs(macDashboard, "[data-mac-total]");
    var macPie = qs(macDashboard, ".mac-pie-chart");
    var macLegend = qs(macDashboard, "[data-mac-pie-legend]");
    var macTooltip = qs(macDashboard, "[data-mac-slice-tooltip]");
    var macUpdateAllForm = qs(macDashboard, "[data-mac-update-all-form]");
    var macUpdateStatus = qs(macDashboard, "[data-mac-update-status]");
    var macSegments = [];
    var macSegmentsScript = document.getElementById("macPieSegments");
    if (macSegmentsScript) {
      try { macSegments = JSON.parse(macSegmentsScript.textContent || "[]"); } catch (error) { macSegments = []; }
    }
    function setMacSegments(segments) {
      macSegments = Array.isArray(segments) ? segments : [];
    }
    function findMacSegmentFromEvent(event) {
      if (!macPie || !macSegments.length) return null;
      var rect = macPie.getBoundingClientRect();
      var centerX = rect.left + rect.width / 2;
      var centerY = rect.top + rect.height / 2;
      var dx = event.clientX - centerX;
      var dy = event.clientY - centerY;
      var radius = Math.sqrt(dx * dx + dy * dy);
      var outerRadius = rect.width / 2;
      var innerRadius = outerRadius * 0.24;
      if (radius < innerRadius || radius > outerRadius) return null;
      var angle = (Math.atan2(dy, dx) * 180 / Math.PI + 450) % 360;
      var percent = angle / 360 * 100;
      var cumulative = 0;
      for (var i = 0; i < macSegments.length; i += 1) {
        cumulative += Number(macSegments[i].percent) || 0;
        if (percent <= cumulative) return macSegments[i];
      }
      return macSegments[macSegments.length - 1];
    }
    if (macPie && macTooltip) {
      macPie.addEventListener("mousemove", function (event) {
        var item = findMacSegmentFromEvent(event);
        if (!item) {
          macTooltip.classList.remove("show");
          return;
        }
        macTooltip.textContent = item.name + " - " + item.count;
        macTooltip.style.left = (event.clientX + 12) + "px";
        macTooltip.style.top = (event.clientY + 12) + "px";
        macTooltip.classList.add("show");
      });
      macPie.addEventListener("mouseleave", function () {
        macTooltip.classList.remove("show");
      });
    }
    if (macUpdateAllForm) {
      macUpdateAllForm.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!macUsername.value.trim() || !macPassword.value) {
          macUpdateStatus.textContent = "Enter Telnet username and password first.";
          macUpdateStatus.className = "mac-update-status error";
          return;
        }
        var button = qs(macUpdateAllForm, "[data-mac-update-all]");
        button.disabled = true;
        button.textContent = "Updating...";
        macUpdateStatus.textContent = "Connecting to all root switches. This can take a little time...";
        macUpdateStatus.className = "mac-update-status";
        var body = new URLSearchParams();
        body.append("username", macUsername.value.trim());
        body.append("password", macPassword.value);
        body.append("csrfmiddlewaretoken", macCsrf.value);
        fetch(macDashboard.dataset.macUpdateAllUrl, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: body })
          .then(parseLiveJson)
          .then(function (data) {
            macUpdateStatus.textContent = data.message || "Update complete.";
            macUpdateStatus.className = "mac-update-status " + (data.ok ? "ok" : "error");
            if (macTotal && data.total) macTotal.textContent = data.total;
            if (macPie && data.pie_gradient) {
              macPie.style.background = "conic-gradient(" + data.pie_gradient + ")";
              var pieCenter = qs(macPie, "span");
              if (pieCenter && data.total) pieCenter.textContent = data.total;
            }
            if (macLegend && data.pie_segments) {
              macLegend.innerHTML = data.pie_segments.length ? data.pie_segments.map(function (item) {
                return '<span title="' + item.name + ' - ' + item.count + ' MACs"><i style="background: ' + item.color + '"></i>' + item.name + ' - ' + item.count + '</span>';
              }).join("") : "<span><i></i>No MAC data yet</span>";
            }
            if (data.pie_segments) setMacSegments(data.pie_segments);
          })
          .catch(function (error) {
            macUpdateStatus.textContent = error.message;
            macUpdateStatus.className = "mac-update-status error";
          })
          .finally(function () {
            button.disabled = false;
            button.textContent = "Update All Switches";
          });
      });
    }
    qsa(macDashboard, "[data-mac-update]").forEach(function (button) {
      button.addEventListener("click", function () {
        var card = button.closest("[data-mac-card]");
        if (!card) return;
        var message = qs(card, "[data-mac-message]");
        if (!macUsername.value.trim() || !macPassword.value) {
          message.textContent = "Enter Telnet username and password first.";
          card.classList.add("error");
          return;
        }
        card.classList.remove("success", "error");
        card.classList.add("loading");
        button.disabled = true;
        button.textContent = "Updating...";
        var body = new URLSearchParams();
        body.append("ip", card.dataset.ip);
        body.append("username", macUsername.value.trim());
        body.append("password", macPassword.value);
        body.append("csrfmiddlewaretoken", macCsrf.value);
        fetch(macDashboard.dataset.macUpdateUrl, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: body })
          .then(parseLiveJson)
          .then(function (data) {
            card.classList.remove("loading");
            card.classList.toggle("success", Boolean(data.ok));
            card.classList.toggle("error", !data.ok);
            if (data.row) {
              qs(card, "[data-mac-hostname]").textContent = data.row.hostname || "Not detected";
              qs(card, "[data-mac-count]").textContent = data.row.count_display || "0";
              message.textContent = data.row.message || data.message || "";
            } else {
              message.textContent = data.message || "Update failed.";
            }
            if (macTotal && data.total) macTotal.textContent = data.total;
            if (macPie && data.pie_gradient) {
              macPie.style.background = "conic-gradient(" + data.pie_gradient + ")";
              var pieCenter = qs(macPie, "span");
              if (pieCenter && data.total) pieCenter.textContent = data.total;
            }
            if (macLegend && data.pie_segments) {
              macLegend.innerHTML = data.pie_segments.length ? data.pie_segments.map(function (item) {
                return '<span title="' + item.name + ' - ' + item.count + ' MACs"><i style="background: ' + item.color + '"></i>' + item.name + ' - ' + item.count + '</span>';
              }).join("") : "<span><i></i>No MAC data yet</span>";
            }
            if (data.pie_segments) setMacSegments(data.pie_segments);
          })
          .catch(function (error) {
            card.classList.remove("loading");
            card.classList.add("error");
            message.textContent = error.message;
          })
          .finally(function () {
            button.disabled = false;
            button.textContent = "Update";
          });
      });
    });
  }

  var lastmileForm = document.querySelector("[data-lastmile-form]");
  if (!lastmileForm) return;

  var lmUsername = qs(lastmileForm, 'input[name="username"]');
  var lmPassword = qs(lastmileForm, 'input[name="password"]');
  var lmSwitchIp = qs(lastmileForm, "[data-lastmile-ip]");
  var lmPortInput = qs(lastmileForm, "[data-lastmile-port]");
  var lmVlanInput = qs(lastmileForm, "[data-lastmile-vlan-id]");
  var lmVlanName = qs(lastmileForm, 'input[name="vlan_name"]');
  var lmVlanMessage = qs(lastmileForm, "[data-lastmile-vlan-message]");
  var lmSubmit = qs(lastmileForm, "[data-lastmile-submit]");
  var lmType = qs(lastmileForm, "[data-lastmile-type]");
  var lmDataFields = qsa(lastmileForm, "[data-data-field]");
  var lmBwFields = qsa(lastmileForm, "[data-bw-field]");
  var lmStatus = qs(lastmileForm, "[data-interface-status]");
  var lmList = qs(lastmileForm, "[data-port-list]");
  var lmCount = qs(lastmileForm, "[data-port-count]");
  var lmSelectedLabel = qs(lastmileForm, "[data-selected-port]");
  var lmSelectedInfo = qs(lastmileForm, "[data-selected-port-info]");
  var lmTimer = null;
  var lmLastFetchKey = "";

  function setLmStatus(kind, text) {
    lmStatus.classList.remove("loading", "success", "error");
    if (kind) lmStatus.classList.add(kind);
    lmStatus.textContent = text;
  }

  function updateLmTypeFields() {
    var isBw = lmType.value === "BW";
    lmDataFields.forEach(function (field) { field.hidden = isBw; });
    lmBwFields.forEach(function (field) { field.hidden = !isBw; });
  }
  window.ntToggleLastmileType = function () {
    updateLmTypeFields();
    validateLastmile();
  };

  function validateLastmile() {
    var vlanOk = false;
    var text = "";
    if (lmVlanInput.value.trim()) {
      var vlanNumber = Number(lmVlanInput.value.trim());
      if (!Number.isInteger(vlanNumber)) text = "VLAN ID must be numeric";
      else if (vlanNumber < 1 || vlanNumber > 4094) text = "VLAN ID must be between 1-4094";
      else { vlanOk = true; text = "VLAN ID is valid"; }
    }
    lmVlanMessage.textContent = text;
    lmVlanMessage.classList.toggle("ok", vlanOk);
    var ready = Boolean(lmUsername.value.trim() && lmPassword.value && lmSwitchIp.value.trim() && lmPortInput.value.trim() && vlanOk && lmVlanName.value.trim());
    lmSubmit.classList.toggle("valid", ready);
    lmSubmit.classList.toggle("invalid", !ready);
    return ready;
  }

  function renderPortInfo(row) {
    lmSelectedLabel.textContent = "Selected port: " + row.dataset.port;
    lmSelectedInfo.hidden = false;
    lmSelectedInfo.innerHTML =
      "<strong>" + row.dataset.port + "</strong>" +
      "<span>Name: " + (row.dataset.name || "No Description") + "</span>" +
      "<span>Status: " + (row.dataset.status || "Unknown") + "</span>" +
      "<span>VLAN: " + (row.dataset.vlan || "N/A") + "</span>" +
      "<span>Duplex: " + (row.dataset.duplex || "") + "</span>" +
      "<span>Speed: " + (row.dataset.speed || "") + "</span>" +
      "<span>Type: " + (row.dataset.type || "") + "</span>";
  }

  function selectPort(row) {
    qsa(lmList, ".port-option").forEach(function (item) { item.classList.remove("selected"); });
    row.classList.add("selected");
    lmPortInput.value = row.dataset.port || "";
    renderPortInfo(row);
    validateLastmile();
  }
  window.ntSelectPort = selectPort;

  function renderPorts(ports) {
    lmList.innerHTML = "";
    lmCount.textContent = ports.length + " ports";
    if (!ports.length) {
      lmList.innerHTML = '<div class="empty-state">No ports parsed from switch output.</div>';
      return;
    }
    ports.forEach(function (port) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "port-option";
      button.setAttribute("onclick", "window.ntSelectPort && window.ntSelectPort(this); return false;");
      button.dataset.port = port.port || "";
      button.dataset.name = port.name || "";
      button.dataset.status = port.status || "";
      button.dataset.vlan = port.vlan || "";
      button.dataset.duplex = port.duplex || "";
      button.dataset.speed = port.speed || "";
      button.dataset.type = port.type || "";
      button.innerHTML =
        "<strong>" + (port.port || "") + "</strong>" +
        '<span class="port-name">' + (port.name || "No Description") + "</span>" +
        '<span class="port-meta status-' + (port.status || "").toLowerCase().replace(/[^a-z0-9-]/g, "") + '">' + (port.status || "Unknown") + "</span>" +
        '<span class="port-meta">' + (port.vlan || "N/A") + "</span>" +
        '<span class="port-meta">' + (port.duplex || "") + "</span>" +
        '<span class="port-meta">' + (port.speed || "") + "</span>" +
        '<span class="port-meta">' + (port.type || "") + "</span>";
      lmList.appendChild(button);
    });
  }

  lmList.addEventListener("click", function (event) {
    var row = event.target.closest(".port-option");
    if (row) selectPort(row);
  });

  function fetchPorts() {
    var key = lmUsername.value.trim() + "|" + lmPassword.value + "|" + lmSwitchIp.value.trim();
    if (!lmUsername.value.trim() || !lmPassword.value || !lmSwitchIp.value.trim()) {
      setLmStatus("", "Enter username, password, and switch IP to fetch ports.");
      return;
    }
    if (key === lmLastFetchKey) return;
    lmLastFetchKey = key;
    lmPortInput.value = "";
    lmSelectedLabel.textContent = "No port selected";
    lmSelectedInfo.hidden = true;
    renderPorts([]);
    setLmStatus("loading", "Connecting to " + lmSwitchIp.value.trim() + " and fetching interfaces...");

    var body = new URLSearchParams();
    body.append("username", lmUsername.value.trim());
    body.append("password", lmPassword.value);
    body.append("lastmile_ip", lmSwitchIp.value.trim());
    body.append("csrfmiddlewaretoken", qs(lastmileForm, 'input[name="csrfmiddlewaretoken"]').value);

    fetch(lastmileForm.dataset.interfaceUrl, { method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: body })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        renderPorts(data.ports || []);
        setLmStatus(data.ok ? "success" : "error", data.message || "Interface fetch complete.");
        validateLastmile();
      })
      .catch(function (error) {
        renderPorts([]);
        setLmStatus("error", "Interface fetch failed: " + error);
        validateLastmile();
      });
  }

  function scheduleFetch() {
    window.clearTimeout(lmTimer);
    lmTimer = window.setTimeout(fetchPorts, 700);
  }

  [lmUsername, lmPassword, lmSwitchIp].forEach(function (field) {
    field.addEventListener("input", scheduleFetch);
    field.addEventListener("change", scheduleFetch);
  });
  [lmVlanInput, lmVlanName].forEach(function (field) {
    field.addEventListener("input", validateLastmile);
    field.addEventListener("change", validateLastmile);
  });
  lmType.addEventListener("change", function () {
    updateLmTypeFields();
    validateLastmile();
  });
  lastmileForm.addEventListener("submit", function (event) {
    var action = event.submitter ? event.submitter.value : "apply_lastmile";
    if (action === "show_interface") return;
    if (!validateLastmile()) {
      event.preventDefault();
      return;
    }
    var overlay = document.querySelector("[data-lastmile-progress]");
    var bar = document.querySelector("[data-lastmile-progress-bar]");
    var steps = qsa(document, "[data-lastmile-progress-step]");
    if (!overlay || !bar || !steps.length) return;
    overlay.hidden = false;
    if (steps.length && steps[0].parentElement) steps[0].parentElement.classList.remove("verified", "failed");
    var index = 0;
    var tick = function () {
      steps.forEach(function (step, stepIndex) {
        step.classList.remove("done");
        step.classList.toggle("active", stepIndex === index);
      });
      bar.style.width = Math.min(10 + index * 13, 94) + "%";
      index = Math.min(index + 1, steps.length - 1);
    };
    tick();
    window.setInterval(tick, 1600);
  });
  updateLmTypeFields();
  validateLastmile();

})();
