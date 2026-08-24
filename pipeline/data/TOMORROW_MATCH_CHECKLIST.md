# Match-Day Intake Checklist

## Undergraduate analyst

1. Create `2026/matches/YYYY-MM-DD_opponent/` with:

   ```text
   00_source/wyscout/
   00_source/official/
   staff/
   20_generated/
   ```

2. Put the six current Wyscout XML downloads in `00_source/wyscout/`.
3. Put the media team's final box score PDF in `00_source/official/`.
4. If staff reports an incident, copy the template to `staff/staff_events.csv`
   and add it. Use `82:30`, not a rounded minute, for an exact off moment.
5. Open `pipeline/notebooks/2026_match_intake.ipynb` in Colab and fill in only
   the setup cell, including your full name in `prepared_by`.
6. Leave `CREATE_REVIEW_BUNDLE = False`, run all cells through inspection, and
   confirm every applicable row is ready:
   - Match analytics
   - COUG player scoring
   - Official minutes/lineups
   - Staff events
7. Confirm the source inventory, opponent, score, 11 starters, and participant
   count. Record any warning; do not edit a source file.
8. Set `CREATE_REVIEW_BUNDLE = True`, rerun the bundle cells, and send the
   validation report plus `20_generated` folder to the staff reviewer.

Use [`UNDERGRAD_GENERATED_REVIEW.md`](UNDERGRAD_GENERATED_REVIEW.md) for the
file-by-file review and clear stop conditions.

Stop if an XML is unknown/invalid, a player does not match the roster, the box
score does not parse, or any visible total is wrong. Students do not publish.

## Staff reviewer

1. Read the validation report and spot-check score, goals, cards, player count,
   starters, minutes, and event totals against the official box score/Wyscout.
2. Complete the generated approval JSON.
3. Run `promote_match_intake.py` without `--apply` and inspect the receipt.
4. Run the match loader directly against the generated Drive folder and review
   its counts. The loader uses the reviewed bundle metadata; a separate manifest
   edit is not required:

   ```bash
   .venv/bin/python pipeline/ingestion/load_match.py \
     --slug YYYY-MM-DD_opponent --season 2026 \
     --bundle-dir "/path/to/20_generated" --dry-run
   ```

5. Apply `load_match.py` first. This creates the session, match, official
   stints, and event evidence, but does not publish a COUG score.
6. Apply `promote_match_intake.py` second so the archived source and generated
   artifacts are registered against the new session.
7. Run `publish_event_derived_coug_scores.py` without `--apply`. Review the
   printed player scores and its review CSV.
8. Only when those totals are approved, rerun the score publisher with
   `--apply` to update the public COUG Table.

The notebook and all dry runs are read-only. `load_match.py` writes evidence;
only the final score-publisher `--apply` changes the public COUG Table.

For a late or corrected incident, run `prepare_staff_events.py` and
`load_staff_events.py` separately, then republish that match's COUG score. Do
not rerun the Wyscout parser.
