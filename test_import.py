"""
Quick test: import S26 EcoPOOL (1).xlsx into a FRESH empty DB and report results.
Run with:  venv/bin/python test_import.py
"""
import os, logging, sqlite3

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TEST_DB = "ecopool_test.db"
XLSX    = "S26 EcoPOOL (1).xlsx"

# Start clean
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

from database import DatabaseManager
from excel_importer import ExcelImporter

db  = DatabaseManager(TEST_DB)
imp = ExcelImporter(db)

print("=== Running import ===")
ok, msg = imp.import_workbook(XLSX)
print(f"\nResult: ok={ok}  msg={msg!r}\n")

# ---------- inspect results ----------
conn = sqlite3.connect(TEST_DB)
conn.row_factory = sqlite3.Row
cur  = conn.cursor()

# Players created
cur.execute("SELECT id, name FROM players ORDER BY id")
players = cur.fetchall()
print(f"=== Players ({len(players)}) ===")
for p in players:
    print(f"  {p['id']:3d}  {p['name']}")

# League nights
cur.execute("SELECT id, date FROM league_nights ORDER BY id")
nights = cur.fetchall()
print(f"\n=== League nights ({len(nights)}) ===")
for n in nights:
    print(f"  id={n['id']}  date={n['date']}")

# For each night show pairs + matches
for night in nights:
    nid = night['id']

    cur.execute("""
        SELECT lnp.id, lnp.pair_name as name, lnp.player1_id, lnp.player2_id
        FROM league_night_pairs lnp
        WHERE lnp.league_night_id = ?
        ORDER BY lnp.id
    """, (nid,))
    night_pairs = cur.fetchall()
    print(f"\n--- Night {nid} '{night['date']}' — {len(night_pairs)} pairs ---")
    for p in night_pairs:
        cur.execute("SELECT name FROM players WHERE id=?", (p['player1_id'],))
        p1 = cur.fetchone()
        p2_name = "solo"
        if p['player2_id']:
            cur.execute("SELECT name FROM players WHERE id=?", (p['player2_id'],))
            r = cur.fetchone()
            p2_name = r['name'] if r else "?"
        print(f"  pair {p['id']:3d}: {p['name']:<40s}  ({p1['name'] if p1 else '?'} / {p2_name})")

    cur.execute("""
        SELECT m.id, m.round_number, m.pair1_id, m.pair2_id
        FROM matches m
        WHERE m.league_night_id = ?
        ORDER BY m.round_number, m.id
    """, (nid,))
    matches = cur.fetchall()
    print(f"  → {len(matches)} matches")
    for m in matches:
        cur.execute("SELECT team1_score, team2_score, winner_team FROM games WHERE match_id=?", (m['id'],))
        g = cur.fetchone()
        score = f"{g['team1_score']}-{g['team2_score']} (W={g['winner_team']})" if g else "no game"
        print(f"    set {m['round_number']}  pair{m['pair1_id']} vs pair{m['pair2_id']}  {score}")

# teammate_pairs
cur.execute("""
    SELECT pl1.name as n1, pl2.name as n2
    FROM teammate_pairs tp
    JOIN players pl1 ON pl1.id = tp.player1_id
    JOIN players pl2 ON pl2.id = tp.player2_id
    ORDER BY tp.id
""")
tps = cur.fetchall()
print(f"\n=== teammate_pairs ({len(tps)}) ===")
for tp in tps:
    print(f"  {tp['n1']} & {tp['n2']}")

conn.close()
print(f"\nDone. Test DB at {TEST_DB}")
