"""
Reading a PowerBook G4 through /proc and /sys.

Nothing here raises. A sensor that is missing, unreadable or in a format we
did not expect returns None, and the caller leaves that line off the page.
A dead thermistor must not take down a status service.

THE HONEST CAVEAT, READ THIS FIRST
----------------------------------
This file was written without access to the target machine. The /proc
parsing is safe - the formats are stable and ancient. The *sensor paths*
are educated guesses, because PowerPC thermal support moved between three
different drivers over the years and which one binds depends on the exact
PowerBook model and the kernel:

  therm_adt746x  -> /sys/devices/temperatures/*        (PowerBook G4 era)
  windfarm       -> /sys/devices/platform/windfarm*/   (later PowerMacs)
  hwmon          -> /sys/class/hwmon/hwmon*/           (modern generic)

So every sensor tries a LIST of candidates and reports which one answered.
The published page carries a "sensors" line naming what resolved and what
did not - your first look at the page tells you what this machine has.

TO CONFIRM ON THE BOX (read-only, safe to paste as-is):

    cat /proc/cpuinfo
    ls -l /sys/devices/temperatures/ 2>/dev/null
    ls -l /sys/class/hwmon/*/ 2>/dev/null
    ls -d /sys/devices/platform/windfarm* 2>/dev/null
    ls -l /sys/class/power_supply/ 2>/dev/null
    cat /proc/pmu/info 2>/dev/null

Then add whatever real paths you find to the CANDIDATES lists below. They
are plain tuples, in priority order, and adding one is a one-line change.
"""

import glob
import os

# ---------------------------------------------------------------- reading


def read(path):
    """
    One file, or None. Every failure mode collapses to the same answer,
    because for our purposes "the file is not there", "we are not allowed"
    and "the driver returned garbage" are the same event: no reading.
    """

    try:
        with open(path, "r", errors="replace") as handle:
            return handle.read().strip()

    except (OSError, UnicodeError):
        return None


def first(patterns):
    """
    Walk candidate paths in priority order and return (path, text) for the
    first that answers with something non-empty. Globs are allowed, which
    is how hwmon gets found - the number in hwmon0/hwmon1 is assigned in
    probe order and is not stable across reboots.
    """

    for pattern in patterns:

        for path in sorted(glob.glob(pattern)):
            text = read(path)

            if text:
                return path, text

    return None, None


def number(text):
    """First token of a file as a float, or None. Handles '41000\\n'."""

    if not text:
        return None

    try:
        return float(text.split()[0])

    except (ValueError, IndexError):
        return None


# ------------------------------------------------------------ /proc/cpuinfo


def parse_keyvals(text):
    """
    /proc/cpuinfo, /proc/pmu/info and friends are all 'key : value' lines.
    Keys are lowercased and stripped so 'detected as' and 'L2 cache' can be
    looked up without worrying about the exact spacing the kernel used.
    """

    found = {}

    for line in (text or "").splitlines():

        if ":" not in line:
            continue

        key, _, value = line.partition(":")
        key = key.strip().lower()

        if key and key not in found:
            found[key] = value.strip()

    return found


def machine():
    """
    Static identity. Read once at startup, not every sample - none of it
    changes while the kernel is running.

    A PowerPC /proc/cpuinfo looks like this, which is most of why this
    service is interesting to publish at all:

        cpu             : 7447A, altivec supported
        clock           : 1666.666000MHz
        machine         : PowerBook5,6
        motherboard     : PowerBook5,6 MacRISC3 Power Macintosh
        detected as     : 287 (PowerBook G4 15")
        L2 cache        : 512K unified
        pmac-generation : NewWorld

    On x86 none of machine/motherboard/detected as exist, so this returns
    None for them and the page simply omits those lines. That is what makes
    it safe to run this on your laptop while developing.
    """

    info = parse_keyvals(read("/proc/cpuinfo"))

    # 'model name' and 'cpu MHz' are the x86 spellings. They are here only
    # so that running this on a development laptop produces something
    # sensible - the PowerPC keys are the ones that matter in production.
    #
    # Note what is NOT in this list: the bare x86 'model' key, which holds a
    # CPU model *number*. Falling back to it made the page's heading render
    # as "60".
    return {
        "cpu": info.get("cpu") or info.get("model name"),
        "clock": info.get("clock") or info.get("cpu mhz"),
        "machine": info.get("machine") or info.get("model name"),
        "motherboard": info.get("motherboard"),
        "detected": info.get("detected as"),
        "cache": info.get("l2 cache"),
        "generation": info.get("pmac-generation"),
        "kernel": (os.uname().release if hasattr(os, "uname") else None),
        "arch": (os.uname().machine if hasattr(os, "uname") else None),
    }


# ------------------------------------------------------------------- gauges


def loadavg():
    """/proc/loadavg -> the 1-minute figure. '0.41 0.38 0.30 1/234 5678'."""

    return number(read("/proc/loadavg"))


def uptime_seconds():
    """/proc/uptime -> seconds since boot. '1234567.89 9876543.21'."""

    return number(read("/proc/uptime"))


def parse_meminfo(text):
    """
    /proc/meminfo in kB -> bytes.

    MemAvailable is the honest number and has existed since Linux 3.14, but
    a Debian ports kernel on 32-bit PowerPC is worth being careful about, so
    fall back to MemFree rather than reporting nothing.
    """

    values = {}

    for line in (text or "").splitlines():
        key, _, rest = line.partition(":")
        amount = number(rest)

        if amount is not None:
            values[key.strip()] = amount * 1024

    total = values.get("MemTotal")
    available = values.get("MemAvailable", values.get("MemFree"))

    used = None
    if total is not None and available is not None:
        used = total - available

    return {
        "total": total,
        "available": available,
        "used": used,
        "swap_total": values.get("SwapTotal"),
        "swap_used": (
            values["SwapTotal"] - values["SwapFree"]
            if "SwapTotal" in values and "SwapFree" in values
            else None
        ),
    }


def memory():
    return parse_meminfo(read("/proc/meminfo"))


def parse_stat(text):
    """
    The aggregate 'cpu' line of /proc/stat as (busy, total) jiffies.

    Idle is fields 4 and 5 (idle, iowait); everything else counts as busy.
    These are monotonic counters since boot, so a single reading is
    meaningless - see cpu_busy() below.
    """

    for line in (text or "").splitlines():

        if not line.startswith("cpu "):
            continue

        fields = [f for f in line.split()[1:] if f.isdigit()]

        if len(fields) < 5:
            return None

        values = [int(f) for f in fields]
        total = sum(values)
        idle = values[3] + values[4]

        return total - idle, total

    return None


def cpu_busy(before, after):
    """
    Percent busy between two /proc/stat readings.

    Pure, so it is testable without a CPU. Returns None when the counters
    did not advance (two samples inside the same jiffy) or went backwards
    (only possible across a reboot, but cheap to guard).
    """

    if not before or not after:
        return None

    busy = after[0] - before[0]
    total = after[1] - before[1]

    if total <= 0 or busy < 0:
        return None

    return 100.0 * busy / total


# ------------------------------------------------------------------ thermal

# Priority order. The first that answers wins. Add real paths here once you
# have run the ls commands from the module docstring on the PowerBook.
TEMPERATURE_CANDIDATES = (
    "/sys/devices/temperatures/cpu_temperature",     # therm_adt746x, G4 era
    "/sys/devices/temperatures/sensor1_temperature",
    "/sys/class/hwmon/hwmon*/temp1_input",           # generic hwmon
    "/sys/devices/platform/windfarm*/temp*",
    "/sys/class/thermal/thermal_zone*/temp",
)

FAN_CANDIDATES = (
    "/sys/devices/temperatures/sensor1_fan_speed",   # therm_adt746x, RPM
    "/sys/class/hwmon/hwmon*/fan1_input",            # generic hwmon, RPM
    "/sys/devices/platform/windfarm*/fan*",
)


def scaled_temperature(value):
    """
    hwmon reports millidegrees (41000), therm_adt746x reports plain degrees
    (41). Telling them apart by magnitude is crude but unambiguous in the
    range a laptop can survive: nothing is running at 1000 C, and nothing
    that is running is at 0.041 C.
    """

    if value is None:
        return None

    return value / 1000.0 if value > 200 else value


def temperature():
    path, text = first(TEMPERATURE_CANDIDATES)
    return path, scaled_temperature(number(text))


def fan_rpm():
    path, text = first(FAN_CANDIDATES)
    return path, number(text)


# ------------------------------------------------------------------ battery

# A PowerBook always has one, and whether it is charging is genuinely part
# of this machine's story as a server. Modern kernels expose power_supply;
# older PowerPC builds expose /proc/pmu/battery_0 instead.
BATTERY_CAPACITY = ("/sys/class/power_supply/BAT*/capacity",)
BATTERY_STATUS = ("/sys/class/power_supply/BAT*/status",)
AC_ONLINE = ("/sys/class/power_supply/A*/online",)


def battery():
    """
    Returns (percent, status) with either or both possibly None.

    Falls back to /proc/pmu/battery_0, whose charge and max_charge are in
    mAh and need dividing rather than reading directly.
    """

    _, capacity = first(BATTERY_CAPACITY)
    _, status = first(BATTERY_STATUS)

    percent = number(capacity)

    if percent is None:
        pmu = parse_keyvals(read("/proc/pmu/battery_0"))
        charge = number(pmu.get("charge"))
        maximum = number(pmu.get("max_charge"))

        if charge is not None and maximum:
            percent = 100.0 * charge / maximum

    if not status:
        _, online = first(AC_ONLINE)

        if online is not None:
            status = "AC" if online.strip() == "1" else "battery"

    return percent, status


# ------------------------------------------------------------------- disk


def disk(path="/"):
    """
    Bytes used and total on the filesystem holding path.

    Uses f_bavail rather than f_bfree: the difference is the reserved
    root blocks, and reporting space that only root can use as "free"
    overstates it on a small disk.
    """

    try:
        stats = os.statvfs(path)

    except OSError:
        return {"total": None, "used": None}

    total = stats.f_blocks * stats.f_frsize
    available = stats.f_bavail * stats.f_frsize

    return {"total": total, "used": total - available}


# ------------------------------------------------------------------ sample


def sample(previous_cpu=None):
    """
    One reading of everything that moves, plus the raw /proc/stat snapshot
    the next call needs to compute CPU busy.

    Returns (reading, cpu_snapshot). The reading is a flat dict of floats
    and None - deliberately flat, because aggregate.py averages it and
    logfile.py serialises it, and neither should have to walk a tree.
    """

    now = parse_stat(read("/proc/stat"))

    temp_path, temp = temperature()
    fan_path, fan = fan_rpm()
    percent, status = battery()

    memory_now = memory()
    disk_now = disk("/")

    reading = {
        "load": loadavg(),
        "cpu_percent": cpu_busy(previous_cpu, now),
        "memory_used": memory_now["used"],
        "memory_total": memory_now["total"],
        "swap_used": memory_now["swap_used"],
        "disk_used": disk_now["used"],
        "disk_total": disk_now["total"],
        "temperature": temp,
        "fan_rpm": fan,
        "battery_percent": percent,
        "battery_status": status,
        "uptime": uptime_seconds(),
    }

    # Which candidate answered, so the page can show what this machine
    # actually exposes rather than silently omitting a sensor that is
    # simply configured wrong.
    sources = {"temperature": temp_path, "fan_rpm": fan_path}

    return reading, now, sources
