# EcoPOOL League Manager

A comprehensive pool league management application for the WVU EcoCAR team's Thursday night league at The Met Pool Hall.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-green.svg)

## Features

### 👥 Player Management
- Add, edit, and remove league members
- Track player statistics across all games
- View win rates, total points, and golden breaks
- Search and filter players

### 🎲 Match Generator
- **Random Mode**: Automatically generate random 2v2 team pairings for league night
- **Ranked Finals Mode**: Create seeded bracket matchups based on player performance
- Handle odd player counts with "Lone Wolf" mode
- Create matches with one click

### 🎯 Interactive Scorecard
- Visual pool table with clickable balls
- Real-time score tracking (1 pt per ball, 3 pts for 8-ball)
- Best of 3 game format
- Special events:
  - ⭐ Golden Break (17 points for 8-ball on break)
  - ❌ Early 8-ball foul (10 points to opponent)
- Group assignment (Solids vs Stripes)
- Per-game state saving

### 🎱 Pool Table Tracker
- Visual overview of all tables at the venue
- See which tables have active matches
- Configurable table count (4-12)
- Real-time status updates

### 📜 Match History
- Complete history of all matches
- Filter by status (complete, in progress, finals)
- View detailed game results
- Delete old matches

### 🏆 Leaderboard
- Player rankings with multiple sort options
- Track wins, win rate, total points, average points
- Gold, silver, and bronze highlighting for top 3

### 📄 Export Functionality
- **PDF Export**: High-quality scorecards and leaderboards
- **CSV Export**: Player data and match history for spreadsheets

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
2. Go to **Players** → Add your league members
3. Use **Match Generator** to create matches for league night

### League Night Workflow
1. **Before the night**: Use Match Generator to create random team pairings
2. **During play**: Open Scorecard to track each match
3. **Scoring a game**:
   - Select the current match from dropdown
   - Set which team has Solids vs Stripes
   - Click balls on the table to pocket them
   - Use "Pocket for Team 1/2" radio buttons
   - Click "Team X Wins" when game is complete
4. **After the night**: View Leaderboard to see updated standings

### Scoring Rules (from EcoPOOL Ruleset)
- Regular balls (1-7 solids, 9-15 stripes): **1 point each**
- 8-ball: **3 points**
- Maximum per team: **10 points**
- Golden Break (8-ball on break): **17 points** to breaking team
- Early 8-ball foul: **10 points** to opposing team

## File Structure

```
EcoPOOL Toolkit/
├── main.py              # Main application entry point
├── database.py          # SQLite database manager
├── match_generator.py   # Random/ranked match generation
├── exporter.py          # PDF and CSV export
├── requirements.txt     # Python dependencies
├── ecopool_league.db    # SQLite database (created on first run)
├── views/
│   ├── players_view.py       # Player management
│   ├── match_generator_view.py   # Match creation
│   ├── scorecard_view.py     # Interactive scoring
│   ├── leaderboard_view.py   # Rankings display
│   ├── history_view.py       # Match history
│   └── table_tracker_view.py # Table status
└── EcoPOOL RULES.txt    # Official league rules
```

## Database

The application uses SQLite for persistent storage. The database file `ecopool_league.db` is created automatically on first run and contains:

- **players**: League member information
- **matches**: Match pairings and metadata
- **games**: Individual game scores and ball states
- **league_nights**: Optional league night tracking
- **rsvps**: Optional RSVP tracking

## Contributing

This application was created for the WVU EcoCAR pool league. Feel free to modify and adapt for your own league!

## License

MIT License - Feel free to use and modify for your own pool leagues.

---

*WVU EcoCAR Pool League - Thursday Nights at The Met Pool Hall*
