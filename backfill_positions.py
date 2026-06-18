"""
backfill_positions.py
======================
One-time script to backfill athlete.position and athlete.position_group
from roster_2025.csv. Matches on the short "name" format (e.g. "J. Barrett")
since that's what db.py's get_players() returns and what's stored as
display_name/first+last in the athlete table.

Run from project root:
    python backfill_positions.py
"""

import os
import csv
import uuid
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
client = create_client(SUPABASE_URL, SUPABASE_KEY)

ROSTER_CSV = "roster_2025.csv"

# Manual overrides for known name mismatches between Supabase athlete table
# and roster_2025.csv (e.g. multi-part names parsed differently).
# Format: db_short_name -> csv_short_name
NAME_OVERRIDES = {
    "E. Emanuele": "E. Goetzke",  # "Ezequiel Emanuele Goetzke" — parsed as first=Emanuele in DB, last=Goetzke in CSV
}

# Map CSV's "pos" abbreviations to clean position labels if needed.
# Keeping raw values from CSV as-is for now — adjust here if you want
# different labels in the UI (e.g. "GK" -> "Goalkeeper").
POS_GROUP_MAP = {
    "GK": "GK",
    "DEF": "DEF",
    "MID": "MID",
    "ATT": "ATT",
}


def load_roster_csv(path):
    """Returns dict: short_name -> {full_name, first_name, last_name, number, pos, group}"""
    roster = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        header = next(reader)  # header row is comma-delimited but rest is tab-delimited — see note below
        for row in reader:
            if len(row) < 5:
                continue
            short_name, full_name, number, pos, group = [c.strip() for c in row[:5]]
            name_parts = full_name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            roster[short_name] = {
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "number": int(number) if number.isdigit() else None,
                "pos": pos,
                "group": group,
            }
    return roster


def main():
    roster = load_roster_csv(ROSTER_CSV)
    print(f"Loaded {len(roster)} players from {ROSTER_CSV}")

    # Pull current athletes from Supabase
    res = client.table("athlete").select(
        "id, first_name, last_name, display_name"
    ).execute()
    athletes = res.data or []
    print(f"Found {len(athletes)} athletes in Supabase")

    updated, unmatched = [], []

    for a in athletes:
        # Reconstruct the "F. Lastname" short form used in the CSV
        display = a.get("display_name") or f"{a.get('first_name','')} {a.get('last_name','')}"
        first = (a.get("first_name") or "").strip()
        last = (a.get("last_name") or "").strip()
        short_form = f"{first[0]}. {last}" if first and last else display

        match = roster.get(short_form) or roster.get(display)
        if not match and short_form in NAME_OVERRIDES:
            match = roster.get(NAME_OVERRIDES[short_form])

        if not match:
            unmatched.append(display)
            continue

        update_payload = {
            "position": match["pos"],
            "position_group": match["group"],
            "jersey_number": match["number"],
        }
        # Only backfill first_name if it's currently missing — don't clobber existing data
        if not (a.get("first_name") or "").strip():
            update_payload["first_name"] = match["first_name"]

        client.table("athlete").update(update_payload).eq("id", a["id"]).execute()

        updated.append(f"{display} -> #{match['number']} {match['pos']} ({match['group']})")

    print(f"\nUpdated {len(updated)} athletes:")
    for u in updated:
        print(f"  {u}")

    if unmatched:
        print(f"\n⚠️  {len(unmatched)} athletes had NO match in roster CSV (left blank):")
        for u in unmatched:
            print(f"  {u}")

    # Check for roster CSV entries that never made it into the athlete table at all
    matched_csv_keys = set()
    for a in athletes:
        display = a.get("display_name") or f"{a.get('first_name','')} {a.get('last_name','')}"
        first = (a.get("first_name") or "").strip()
        last = (a.get("last_name") or "").strip()
        short_form = f"{first[0]}. {last}" if first and last else display
        if short_form in roster:
            matched_csv_keys.add(short_form)
        elif short_form in NAME_OVERRIDES and NAME_OVERRIDES[short_form] in roster:
            matched_csv_keys.add(NAME_OVERRIDES[short_form])

    missing_from_db = set(roster.keys()) - matched_csv_keys
    if missing_from_db:
        print(f"\n⚠️  {len(missing_from_db)} players in roster CSV but NOT in athlete table — inserting now:")
        for name in missing_from_db:
            r = roster[name]
            new_id = str(uuid.uuid4())
            client.table("athlete").insert({
                "id": new_id,
                "first_name": r["first_name"],
                "last_name": r["last_name"],
                "display_name": name,
                "position": r["pos"],
                "position_group": r["group"],
                "jersey_number": r["number"],
                "status": "active",
            }).execute()
            print(f"  Inserted {name} ({r['full_name']}) -> {new_id}")


if __name__ == "__main__":
    main()
