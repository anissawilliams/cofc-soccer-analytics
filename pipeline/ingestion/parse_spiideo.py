"""
parse_spiideo.py — Parse Spiideo tag XML export
Extracts COUG events (ASET + PEAK) and all tagged moments
"""

import xml.etree.ElementTree as ET
from pathlib import Path


def read_spiideo_xml(path: Path) -> ET.Element:
    """Read Spiideo XML — typically UTF-8."""
    raw = path.read_bytes()
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return ET.fromstring(raw.decode(enc))
        except (UnicodeDecodeError, ET.ParseError):
            continue
    raise ValueError(f"Could not parse Spiideo XML: {path}")


def parse_spiideo(path: Path) -> dict:
    """
    Parse Spiideo tag XML.
    Returns:
        coug_events  — ASET + PEAK tagged moments
        all_events   — every tagged instance (for offset calculation)
    """
    root = read_spiideo_xml(path)

    coug_events = []
    all_events  = []

    for inst in root.findall(".//instance"):
        code  = inst.find("code").text if inst.find("code") is not None else ""
        start = float(inst.find("start").text) if inst.find("start") is not None else 0
        end   = float(inst.find("end").text)   if inst.find("end")   is not None else 0

        all_events.append({"code": code, "start": start, "end": end})

        if not code:
            continue

        # COUG events only
        is_aset = "ASET" in code
        is_peak = "PEAK" in code or "Peak" in code

        if not (is_aset or is_peak):
            continue

        if is_aset:
            category = "ASET"
            subtype  = (code
                .replace("ASET -", "")
                .replace("ASET", "")
                .strip()) or "General"
        else:
            category = "PEAK"
            subtype  = (code
                .replace("PEAK -", "")
                .replace("Peak -", "")
                .replace("PEAK", "")
                .replace("Peak", "")
                .strip()) or "General"

        coug_events.append({
            "category":    category,
            "subtype":     subtype,
            "spiideo_t":   start,
            "end":         end,
            "spiideo_code": code,
        })

    aset_count = sum(1 for e in coug_events if e["category"] == "ASET")
    peak_count = sum(1 for e in coug_events if e["category"] == "PEAK")
    print(f"  Spiideo: {len(coug_events)} COUG events "
          f"(ASET: {aset_count}, PEAK: {peak_count}) "
          f"out of {len(all_events)} total tags")

    return {
        "coug_events": coug_events,
        "all_events":  all_events,
    }
