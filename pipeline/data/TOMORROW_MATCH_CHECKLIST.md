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
   and add it. Use the exact timestamp. Red cards are `-2`; yellow cards are
   `-0.4` each and do not mark the player off.
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

Use `pipeline/notebooks/2026_match_publish.ipynb` in Colab for the normal
Drive-first workflow.

1. Change `MATCH_SLUG` and `REVIEWED_BY` in the setup cell.
2. Choose **Runtime → Run all**.
3. Read the displayed validation report and final player score preview.
4. Type `PUBLISH YYYY-MM-DD_opponent` once when the results are correct.
5. Do not finish until the notebook displays **PUBLISHED AND VERIFIED**.

The notebook automatically prepares optional staff events, previews and loads
evidence, archives sources and Match Flow, publishes the approved scores, and
verifies all database outputs. Only the final confirmation changes the public
COUG Table.

For a late or corrected incident, run `prepare_staff_events.py` and
`load_staff_events.py` separately, then republish that match's COUG score. Do
not rerun the Wyscout parser.
