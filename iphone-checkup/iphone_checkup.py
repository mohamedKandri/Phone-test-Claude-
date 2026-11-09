"""
iPhone Checkup - reads health info from an iPhone connected by USB cable.

It checks:
  - phone model and iOS version
  - storage (how full the phone is)
  - battery health and charge cycles
  - configuration profiles (hidden settings that can control the phone)
  - installed apps (and flags apps NOT installed from the App Store)
  - crash logs (which apps keep crashing)

It only READS information. It does not change or delete anything on the phone.

The results are saved to "iphone_report.txt" next to this file.
Private identifiers (serial number, IMEI, phone number) are NOT put in the report.
"""

import asyncio
import collections
import datetime
import inspect
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPORT_PATH = os.path.join(HERE, "iphone_report.txt")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

lines = []


def say(text=""):
    print(text)
    lines.append(text)


def heading(title):
    say()
    say("=" * 60)
    say(title)
    say("=" * 60)


# ---------------------------------------------------------------- helpers

def run_cli(args, timeout=180):
    """Run a pymobiledevice3 command. Returns (output, error)."""
    cmd = [sys.executable, "-m", "pymobiledevice3"] + args
    env = dict(os.environ, NO_COLOR="1", PYTHONIOENCODING="utf-8")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, "timed out"
    out = ANSI.sub("", p.stdout or "")
    if p.returncode != 0:
        err = ANSI.sub("", (p.stderr or "") + "\n" + out).strip()
        return None, err[-1500:] or f"exit code {p.returncode}"
    return out, None


def run_cli_json(variants):
    """Try several command variants until one returns JSON."""
    last_err = "no command ran"
    for args in variants:
        out, err = run_cli(args)
        if out is None:
            last_err = err
            continue
        text = out.strip()
        try:
            return json.loads(text), None
        except ValueError:
            # Some versions print log lines before the JSON; find the JSON part.
            for start_char in "{[":
                i = text.find(start_char)
                if i != -1:
                    try:
                        return json.loads(text[i:]), None
                    except ValueError:
                        pass
            last_err = "unexpected output: " + text[:300]
    return None, last_err


def resolve(value):
    if inspect.isawaitable(value):
        return asyncio.run(value) if not asyncio.iscoroutine(value) else asyncio.run(value)
    return value


def find_key(obj, wanted):
    """Find the first value for any of the wanted keys anywhere in nested data."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in wanted:
                return v
        for v in obj.values():
            found = find_key(v, wanted)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = find_key(v, wanted)
            if found is not None:
                return found
    return None


def gb(n):
    return f"{n / 1_000_000_000:.1f} GB"


# ---------------------------------------------------------------- checks

def check_connected():
    data, err = run_cli_json([["usbmux", "list"]])
    if err:
        say("Could not look for devices: " + err)
        return False
    if not data:
        say("No iPhone found.")
        say("  - Plug the iPhone in with the cable and UNLOCK it.")
        say("  - If it asks 'Trust This Computer?', tap Trust and enter your passcode.")
        say("  - Make sure the 'Apple Devices' app (or iTunes) is installed on Windows.")
        return False
    say(f"Found {len(data)} device(s) connected.")
    return True


def check_info():
    heading("PHONE")
    data, err = run_cli_json([["lockdown", "info"]])
    if err:
        say("Could not read phone info: " + err)
        return
    for key, label in [("ProductType", "Model code"), ("ProductVersion", "iOS version"),
                       ("BuildVersion", "iOS build"), ("DeviceClass", "Device")]:
        if key in data:
            say(f"{label}: {data[key]}")


def check_storage():
    heading("STORAGE")
    data, err = None, None
    try:
        from pymobiledevice3.lockdown import create_using_usbmux
        lockdown = resolve(create_using_usbmux())
        data = resolve(lockdown.get_value(domain="com.apple.disk_usage"))
    except Exception as e:  # noqa: BLE001
        err = repr(e)
    if not data:
        say("Could not read storage: " + (err or "no data"))
        say("Check it on the phone: Settings > General > iPhone Storage")
        return
    total = data.get("TotalDataCapacity") or data.get("TotalDiskCapacity")
    free = data.get("TotalDataAvailable") or data.get("AmountDataAvailable")
    if not total or free is None:
        say("Storage data looked unusual: " + json.dumps(data, default=str)[:500])
        return
    used_pct = 100 * (total - free) / total
    say(f"Total: {gb(total)}   Free: {gb(free)}   Used: {used_pct:.0f}%")
    if free / total < 0.10:
        say(">> PROBLEM: storage is almost full. This is a very common cause of lag.")
    else:
        say("OK: enough free space.")


def check_battery():
    heading("BATTERY")
    data, err = run_cli_json([["diagnostics", "battery", "single"]])
    if err:
        say("Could not read battery: " + err)
        return
    design = find_key(data, {"DesignCapacity"})
    max_cap = find_key(data, {"AppleRawMaxCapacity", "NominalChargeCapacity"})
    cycles = find_key(data, {"CycleCount"})
    temp = find_key(data, {"Temperature"})
    if cycles is not None:
        say(f"Charge cycles: {cycles}")
    if design and max_cap and isinstance(design, (int, float)) and isinstance(max_cap, (int, float)) and design > 0:
        health = 100 * max_cap / design
        say(f"Battery health (estimate): {health:.0f}%")
        if health < 80:
            say(">> PROBLEM: battery is worn. iPhones slow themselves down with a worn battery.")
            say("   A battery replacement usually fixes the lag.")
        else:
            say("OK: battery health looks fine.")
    else:
        say("Could not calculate health. Check: Settings > Battery > Battery Health")
    if isinstance(temp, (int, float)):
        celsius = temp / 100 if temp > 100 else temp
        say(f"Battery temperature: {celsius:.0f} C")
        if celsius > 40:
            say(">> The phone is hot. Hot iPhones slow down to cool off.")


def check_profiles():
    heading("CONFIGURATION PROFILES")
    data, err = run_cli_json([["profile", "list"]])
    if err:
        say("Could not read profiles: " + err)
        say("Check on the phone: Settings > General > VPN & Device Management")
        return
    ids = data.get("OrderedIdentifiers", []) if isinstance(data, dict) else []
    meta = data.get("ProfileMetadata", {}) if isinstance(data, dict) else {}
    if not ids and not meta:
        say("OK: no configuration profiles installed.")
        return
    say(f">> {len(ids or meta)} profile(s) installed. If you (or your work/school) did not")
    say("   install these, remove them: Settings > General > VPN & Device Management")
    for pid in ids or list(meta):
        info = meta.get(pid, {})
        name = info.get("PayloadDisplayName", "(no name)")
        org = info.get("PayloadOrganization", "")
        say(f"   - {name}  {('[' + org + ']') if org else ''}  ({pid})")


def check_apps():
    heading("APPS")
    data, err = run_cli_json([["apps", "list", "--type", "User"],
                              ["apps", "list", "-t", "User"],
                              ["apps", "list"]])
    if err:
        say("Could not read apps: " + err)
        return
    apps = data if isinstance(data, dict) else {}
    apps = {bid: a for bid, a in apps.items()
            if isinstance(a, dict) and a.get("ApplicationType", "User") == "User"}
    say(f"{len(apps)} apps installed (not counting Apple's built-in apps).")
    not_store = []
    for bid, a in sorted(apps.items(), key=lambda x: str(x[1].get("CFBundleDisplayName") or x[0]).lower()):
        name = a.get("CFBundleDisplayName") or a.get("CFBundleName") or bid
        signer = str(a.get("SignerIdentity", ""))
        if a.get("ProfileValidated") or (signer and "Apple iPhone OS Application Signing" not in signer):
            not_store.append((name, bid, signer))
    if not_store:
        say()
        say(">> These apps were NOT installed from the App Store. That can be normal")
        say("   (work apps, TestFlight), but if you don't know them, delete them:")
        for name, bid, signer in not_store:
            say(f"   - {name}  ({bid})")
    else:
        say("OK: all apps appear to come from the App Store.")
    say()
    say("Full app list (look for anything you don't remember installing):")
    for bid, a in sorted(apps.items(), key=lambda x: str(x[1].get("CFBundleDisplayName") or x[0]).lower()):
        name = a.get("CFBundleDisplayName") or a.get("CFBundleName") or bid
        say(f"   - {name}  ({bid})")


def check_crashes():
    heading("CRASH LOGS")
    out, err = run_cli(["crash", "ls"])
    if out is None:
        say("Could not read crash logs: " + err)
        return
    text = out.strip()
    try:
        entries = [str(x) for x in json.loads(text)]
    except ValueError:
        entries = [ln.strip() for ln in text.splitlines() if ln.strip()]
    reports = [e for e in entries if e.lower().endswith((".ips", ".crash", ".synced"))]
    counter = collections.Counter()
    for path in reports:
        base = os.path.basename(path.replace("\\", "/"))
        m = re.match(r"(.+?)[-_.]\d{4}-\d{2}-\d{2}", base)
        counter[m.group(1) if m else base.split("-")[0]] += 1
    say(f"{len(reports)} crash/diagnostic reports on the phone.")
    if not counter:
        say("OK: no crash reports.")
        return
    say("Most frequent (app or system part : count):")
    for name, n in counter.most_common(15):
        say(f"   - {name}: {n}")
    say("Many reports for one app = that app is crashing or misbehaving.")
    say("Many 'JetsamEvent' = the phone keeps running out of memory.")


# ---------------------------------------------------------------- main

def main():
    say("iPhone Checkup report - " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if not check_connected():
        save()
        return
    for check in (check_info, check_storage, check_battery, check_profiles, check_apps, check_crashes):
        try:
            check()
        except Exception as e:  # noqa: BLE001 - keep going so the rest of the report is made
            say(f"(this check failed unexpectedly: {e!r})")
    heading("DONE")
    say("Lines starting with >> are things to look at.")
    save()


def save():
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print()
    print("Report saved to: " + REPORT_PATH)


if __name__ == "__main__":
    main()
