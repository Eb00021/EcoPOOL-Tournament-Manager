# EcoPOOL League Manager

A comprehensive pool league management application for the WVU EcoCAR team's Thursday night league at The Met Pool Hall.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-green.svg)

## Features

### 🏠 Dashboard
- Quick stats (players, matches, active games)
- One-click navigation to Match Generator, Scorecard, Tournament, Players, and Leaderboard
- Recent matches and quick rules reference

### 👥 Player Management
- Add, edit, and remove league members
- Profile pictures, email, and Venmo
- Track statistics: wins, win rate, total points, golden breaks, legal 8-ball sinks
- Search and filter players
- Export/import players (JSON)

### 🎲 Match Generator
- **Random pairs** or **skill-based pairs** (balance high/low ranked)
- **Lone Wolf** mode for odd player counts
- **Multi-round schedule**: generates rounds so matches on different tables can run at once without any pair playing twice in the same round
- Optional avoidance of repeat matchups from past nights
- Configurable table count and minimum games per pair
- Create matches and assign to tables; pairings persist when switching views before saving

### 🎯 Interactive Scorecard
- Visual pool table with clickable balls (Solids vs Stripes)
- Real-time scoring: 1 pt per ball, 3 pts for 8-ball (max 10 per team per game)
- Best of 3 format
- Special events:
  - ⭐ Golden Break (17 points for 8-ball on break)
  - ❌ Early 8-ball foul (10 points to opponent)
- Per-game state and ball positions saved
- Export scorecard to PDF

### 🎱 Table Tracker
- Overview of all tables at the venue
- See which tables have active or completed matches
- Configurable table count
- Click a match to jump to Scorecard with that match selected

### 🏆 Tournament Bracket
- Seeded bracket for end-of-semester finals (4, 8, 16, or 32 players)
- Visual bracket with profile pictures and animations
- Export bracket to PDF

### 📜 Match History
- Full history of matches with filters (complete, in progress, finals)
- View detailed game results
- Delete matches; export to PDF or CSV

### 📊 Leaderboard
- Rankings with sort by wins, win rate, points, or average points
- Gold, silver, bronze for top 3
- Export to PDF or CSV

### 📱 Live Scores Web Server
- Built-in Flask server to show live scores on phones and tablets
- **Server-Sent Events (SSE)** for real-time updates without refresh
- **QR code** for quick mobile access (requires `qrcode[pil]`)
- Profile pictures on the live score view
- Start/stop from the sidebar; share the URL or QR with spectators

### 📄 Export & Data Management
- **PDF**: Scorecards, leaderboard, match history, match diagram, bracket
- **CSV**: Players, matches
- **JSON**: Save/load match history (backup/restore); export/import players
- **New Pool Night**: Clear incomplete matches, keep completed games for leaderboard; optional save before clearing

### ✨ Animations & UI
- Custom fonts and dark theme
- Animated cards and buttons on the dashboard
- Celebration effects

## Installation

### Requirements
- Python 3.10 or higher
- Windows, macOS, or Linux

### Setup

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Usage

### First Time Setup
1. Launch the application
2. Go to **Players** → Add your league members (and optionally profile pictures)
3. Use **Match Generator** to create pairs and then matches for league night

### League Night Workflow
1. **Before**: Match Generator → choose Random or Skill-based pairs → generate rounds → Create Matches
2. **During play**: **Table Tracker** to see tables; **Scorecard** to track a match. On the scorecard:
   - Select the match, set Solids vs Stripes, click balls to pocket, use “Pocket for Team 1/2,” then “Team X Wins” when the game is done
3. **Live scores**: Sidebar → **Start Server** → **Show QR Code** so phones can view scores in real time
4. **After**: **Leaderboard** for standings; **Data Management** → Save Match History (JSON) if you want a backup

### Data Management (Sidebar)
- **New Pool Night**: Clear incomplete matches; completed games stay in the leaderboard
- **Save / Load**: Match history to/from JSON
- **Export / Import**: Players to/from JSON

### Scoring Rules (EcoPOOL)
- Regular balls (1–7 solids, 9–15 stripes): **1 point each**
- 8-ball: **3 points**
- Maximum per team per game: **10 points**
- Golden Break (8 on break): **17 points** to the breaking team
- Early 8-ball foul: **10 points** to the opposing team

## File Structure

```
EcoPOOL Toolkit/
├── main.py                 # Main application and UI
├── database.py             # SQLite database (players, matches, games, seasons, league nights, pairs, buy-ins)
├── match_generator.py      # Pair and round-based schedule generation
├── exporter.py             # PDF, CSV, JSON export/import
├── web_server.py          # Live scores Flask server (SSE, QR, mobile)
├── animations.py           # Animated cards, buttons, celebrations
├── fonts.py                # Custom fonts
├── profile_pictures.py     # Profile picture handling
├── requirements.txt
├── profile_pictures/       # Player profile images
├── fonts/                  # Custom font files
├── views/
│   ├── players_view.py
│   ├── match_generator_view.py
│   ├── scorecard_view.py
│   ├── table_tracker_view.py
│   ├── bracket_view.py
│   ├── history_view.py
│   └── leaderboard_view.py
└── (ecopool_league.db created on first run)
```

## Database

SQLite (`ecopool_league.db`) is created on first run. Main tables:

- **players** — Names, email, Venmo, profile picture, stats derived from games
- **matches** — Pairings, table, best-of, finals flag, queue/round/status for scheduling
- **games** — Per-game scores, ball states, golden break, early 8-ball
- **seasons** — Season name and dates
- **league_nights** — Date, location, table count, buy-in, optional season
- **league_night_pairs** — Fixed pairs for a league night
- **league_night_buyins** — Buy-in and payment status per player per night

## Dependencies

- **customtkinter** — GUI
- **Pillow** — Images and pool table graphics
- **reportlab** — PDF export
- **openpyxl** — Excel export
- **flask** — Live scores web server
- **qrcode[pil]** — QR code for mobile access to live scores

## Contributing

This application was created for the WVU EcoCAR pool league. Feel free to modify and adapt for your own league.

## License

MIT License — Use and modify for your own pool leagues.

---

*WVU EcoCAR Pool League — Thursday Nights at The Met Pool Hall*
