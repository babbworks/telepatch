"""
Reading a PowerBook without a PowerBook.

The parsers take text, so the target machine's /proc can be tested from a
string. The fixtures below are the real formats - the cpuinfo is a
PowerBook G4 15", which is what none of this could otherwise be checked
against until the code was already installed on it.
"""

from observer import probe

POWERBOOK_CPUINFO = """\
processor	: 0
cpu		: 7447A, altivec supported
clock		: 1666.666000MHz
revision	: 1.1 (pvr 8003 0101)
bogomips	: 66.56
timebase	: 18432000
platform	: PowerMac
model		: PowerBook5,6
machine		: PowerBook5,6
motherboard	: PowerBook5,6 MacRISC3 Power Macintosh
detected as	: 287 (PowerBook G4 15")
pmac flags	: 0000001b
L2 cache	: 512K unified
pmac-generation	: NewWorld
Memory		: 1024 MB
"""

# The x86 laptop this gets developed on. Included because a parser that
# only works on the target machine cannot be exercised anywhere else.
INTEL_CPUINFO = """\
processor	: 0
vendor_id	: GenuineIntel
cpu family	: 6
model		: 60
model name	: Intel(R) Core(TM) i5-4300M CPU @ 2.60GHz
cpu MHz		: 2910.197
cache size	: 3072 KB
"""


def test_powerpc_fields_are_read():
    info = probe.parse_keyvals(POWERBOOK_CPUINFO)

    assert info["machine"] == "PowerBook5,6"
    assert info["motherboard"] == "PowerBook5,6 MacRISC3 Power Macintosh"
    assert info["detected as"] == '287 (PowerBook G4 15")'
    assert info["l2 cache"] == "512K unified"


def test_keys_are_case_folded_and_stripped():
    """
    The kernel pads these with tabs and mixes case ('L2 cache'). Callers
    should not have to know that.
    """

    info = probe.parse_keyvals(POWERBOOK_CPUINFO)

    assert "l2 cache" in info
    assert "L2 cache" not in info


def test_intel_model_number_is_not_a_machine_name():
    """
    The bug this exists to prevent: falling back to x86's bare 'model' key,
    which holds a CPU model *number*, made the published page's heading
    render as the word "60".
    """

    info = probe.parse_keyvals(INTEL_CPUINFO)

    assert info["model"] == "60"
    assert info["model name"].startswith("Intel")


def test_meminfo_converts_kb_to_bytes():
    text = """\
MemTotal:        1029484 kB
MemFree:          123456 kB
MemAvailable:     654321 kB
SwapTotal:        999999 kB
SwapFree:         888888 kB
"""

    memory = probe.parse_meminfo(text)

    assert memory["total"] == 1029484 * 1024
    assert memory["available"] == 654321 * 1024
    assert memory["used"] == (1029484 - 654321) * 1024
    assert memory["swap_used"] == (999999 - 888888) * 1024


def test_meminfo_falls_back_to_memfree():
    """
    MemAvailable has existed since Linux 3.14, but a Debian ports kernel on
    32-bit PowerPC is worth not assuming about. Reporting nothing would be
    worse than reporting the cruder number.
    """

    memory = probe.parse_meminfo("MemTotal: 1000 kB\nMemFree: 400 kB\n")

    assert memory["available"] == 400 * 1024


def test_meminfo_survives_nonsense():
    memory = probe.parse_meminfo("")

    assert memory["total"] is None
    assert memory["used"] is None


def test_stat_splits_busy_from_idle():
    # user nice system idle iowait irq softirq steal
    snapshot = probe.parse_stat("cpu  100 0 50 800 50 0 0 0\ncpu0 1 2 3 4 5\n")

    assert snapshot == (150, 1000)


def test_cpu_busy_is_a_delta():
    before = (100, 1000)
    after = (150, 1100)

    assert probe.cpu_busy(before, after) == 50.0


def test_cpu_busy_needs_two_readings():
    """The first sample after startup has nothing to compare against."""

    assert probe.cpu_busy(None, (1, 2)) is None


def test_cpu_busy_ignores_counters_going_backwards():
    assert probe.cpu_busy((200, 2000), (100, 1000)) is None


def test_cpu_busy_ignores_a_stopped_clock():
    assert probe.cpu_busy((100, 1000), (100, 1000)) is None


def test_temperature_scale_is_detected():
    """
    hwmon reports millidegrees, therm_adt746x reports degrees. Telling them
    apart by magnitude is crude but unambiguous: nothing runs at 1000 C and
    nothing running is at 0.047 C.
    """

    assert probe.scaled_temperature(47000) == 47.0
    assert probe.scaled_temperature(47) == 47.0
    assert probe.scaled_temperature(None) is None


def test_number_tolerates_trailing_junk():
    assert probe.number("41000\n") == 41000.0
    assert probe.number("") is None
    assert probe.number("not a number") is None


def test_read_returns_none_for_a_missing_file():
    """
    Every failure mode collapses to one answer. A dead thermistor must not
    take down a status service.
    """

    assert probe.read("/proc/definitely-not-a-real-file") is None


def test_sample_never_raises():
    """
    Whatever this machine is, one sample must come back. Values may be
    None; the call may not explode.
    """

    reading, snapshot, sources = probe.sample(None)

    assert "load" in reading
    assert "temperature" in reading
    assert set(sources) == {"temperature", "fan_rpm"}
