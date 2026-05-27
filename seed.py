import os
import secrets
from datetime import datetime, timezone
from app.models import db, User, Team, UserFavoriteTeam, Group, GroupMember, IncidentReport
from app.analytics.models import LabLeague


# ── NBA ───────────────────────────────────────────────────────────────────────

NBA_TEAMS = [
    ("ATL", "Hawks", "Atlanta", "#E03A3E", "#C1D32F"),
    ("BOS", "Celtics", "Boston", "#007A33", "#BA9653"),
    ("BKN", "Nets", "Brooklyn", "#000000", "#FFFFFF"),
    ("CHA", "Hornets", "Charlotte", "#1D1160", "#00788C"),
    ("CHI", "Bulls", "Chicago", "#CE1141", "#000000"),
    ("CLE", "Cavaliers", "Cleveland", "#860038", "#FDBB30"),
    ("DAL", "Mavericks", "Dallas", "#00538C", "#002B5E"),
    ("DEN", "Nuggets", "Denver", "#0E2240", "#FEC524"),
    ("DET", "Pistons", "Detroit", "#C8102E", "#006BB6"),
    ("GSW", "Warriors", "Golden State", "#1D428A", "#FFC72C"),
    ("HOU", "Rockets", "Houston", "#CE1141", "#000000"),
    ("IND", "Pacers", "Indiana", "#002D62", "#FDBB30"),
    ("LAC", "Clippers", "Los Angeles", "#C8102E", "#1D428A"),
    ("LAL", "Lakers", "Los Angeles", "#552583", "#FDB927"),
    ("MEM", "Grizzlies", "Memphis", "#5D76A9", "#12173F"),
    ("MIA", "Heat", "Miami", "#98002E", "#F9A01B"),
    ("MIL", "Bucks", "Milwaukee", "#00471B", "#EEE1C6"),
    ("MIN", "Timberwolves", "Minnesota", "#0C2340", "#236192"),
    ("NOP", "Pelicans", "New Orleans", "#0C2340", "#C8102E"),
    ("NYK", "Knicks", "New York", "#006BB6", "#F58426"),
    ("OKC", "Thunder", "Oklahoma City", "#007AC1", "#EF3B24"),
    ("ORL", "Magic", "Orlando", "#0077C0", "#C4CED4"),
    ("PHI", "76ers", "Philadelphia", "#006BB6", "#ED174C"),
    ("PHX", "Suns", "Phoenix", "#1D1160", "#E56020"),
    ("POR", "Trail Blazers", "Portland", "#E03A3E", "#000000"),
    ("SAC", "Kings", "Sacramento", "#5A2D81", "#63727A"),
    ("SAS", "Spurs", "San Antonio", "#C4CED4", "#000000"),
    ("TOR", "Raptors", "Toronto", "#CE1141", "#000000"),
    ("UTA", "Jazz", "Utah", "#002B5C", "#00471B"),
    ("WAS", "Wizards", "Washington", "#002B5C", "#E31837"),
]

# ── NFL ───────────────────────────────────────────────────────────────────────

NFL_TEAMS = [
    ("ARI", "Cardinals", "Arizona", "#97233F", "#000000"),
    ("ATL", "Falcons", "Atlanta", "#A71930", "#000000"),
    ("BAL", "Ravens", "Baltimore", "#241773", "#9E7C0C"),
    ("BUF", "Bills", "Buffalo", "#00338D", "#C60C30"),
    ("CAR", "Panthers", "Carolina", "#0085CA", "#101820"),
    ("CHI", "Bears", "Chicago", "#0B162A", "#C83803"),
    ("CIN", "Bengals", "Cincinnati", "#FB4F14", "#000000"),
    ("CLE", "Browns", "Cleveland", "#311D00", "#FF3C00"),
    ("DAL", "Cowboys", "Dallas", "#003594", "#869397"),
    ("DEN", "Broncos", "Denver", "#FB4F14", "#002244"),
    ("DET", "Lions", "Detroit", "#0076B6", "#B0B7BC"),
    ("GB", "Packers", "Green Bay", "#203731", "#FFB612"),
    ("HOU", "Texans", "Houston", "#03202F", "#A71930"),
    ("IND", "Colts", "Indianapolis", "#002C5F", "#A2AAAD"),
    ("JAX", "Jaguars", "Jacksonville", "#101820", "#D7A22A"),
    ("KC", "Chiefs", "Kansas City", "#E31837", "#FFB81C"),
    ("LAC", "Chargers", "Los Angeles", "#0080C6", "#FFC20E"),
    ("LAR", "Rams", "Los Angeles", "#003594", "#FFA300"),
    ("LV", "Raiders", "Las Vegas", "#000000", "#A5ACAF"),
    ("MIA", "Dolphins", "Miami", "#008E97", "#FC4C02"),
    ("MIN", "Vikings", "Minnesota", "#4F2683", "#FFC62F"),
    ("NE", "Patriots", "New England", "#002244", "#C60C30"),
    ("NO", "Saints", "New Orleans", "#D3BC8D", "#101820"),
    ("NYG", "Giants", "New York", "#0B2265", "#A71930"),
    ("NYJ", "Jets", "New York", "#125740", "#000000"),
    ("PHI", "Eagles", "Philadelphia", "#004C54", "#A5ACAF"),
    ("PIT", "Steelers", "Pittsburgh", "#FFB612", "#101820"),
    ("SEA", "Seahawks", "Seattle", "#002244", "#69BE28"),
    ("SF", "49ers", "San Francisco", "#AA0000", "#B3995D"),
    ("TB", "Buccaneers", "Tampa Bay", "#D50A0A", "#FF7900"),
    ("TEN", "Titans", "Tennessee", "#0C2340", "#4B92DB"),
    ("WAS", "Commanders", "Washington", "#5A1414", "#FFB612"),
]

# ── MLB ───────────────────────────────────────────────────────────────────────

MLB_TEAMS = [
    ("ARI", "Diamondbacks", "Arizona", "#A71930", "#E3D4AD"),
    ("ATL", "Braves", "Atlanta", "#CE1141", "#13274F"),
    ("BAL", "Orioles", "Baltimore", "#DF4601", "#000000"),
    ("BOS", "Red Sox", "Boston", "#BD3039", "#0C2340"),
    ("CHC", "Cubs", "Chicago", "#0E3386", "#CC3433"),
    ("CWS", "White Sox", "Chicago", "#27251F", "#C4CED4"),
    ("CIN", "Reds", "Cincinnati", "#C6011F", "#000000"),
    ("CLE", "Guardians", "Cleveland", "#0C2340", "#E31937"),
    ("COL", "Rockies", "Colorado", "#33006F", "#C4CED4"),
    ("DET", "Tigers", "Detroit", "#0C2340", "#FA4616"),
    ("HOU", "Astros", "Houston", "#002D62", "#EB6E1F"),
    ("KC", "Royals", "Kansas City", "#004687", "#BD9B60"),
    ("LAA", "Angels", "Los Angeles", "#BA0021", "#003263"),
    ("LAD", "Dodgers", "Los Angeles", "#005A9C", "#EF3E42"),
    ("MIA", "Marlins", "Miami", "#00A3E0", "#FF6600"),
    ("MIL", "Brewers", "Milwaukee", "#FFC52F", "#12284B"),
    ("MIN", "Twins", "Minnesota", "#002B5C", "#D31145"),
    ("NYM", "Mets", "New York", "#002D72", "#FF5910"),
    ("NYY", "Yankees", "New York", "#0C2340", "#C4CED4"),
    ("OAK", "Athletics", "Oakland", "#003831", "#EFB21E"),
    ("PHI", "Phillies", "Philadelphia", "#E81828", "#002D72"),
    ("PIT", "Pirates", "Pittsburgh", "#FDB827", "#27251F"),
    ("SD", "Padres", "San Diego", "#2F241D", "#FFC425"),
    ("SF", "Giants", "San Francisco", "#FD5A1E", "#27251F"),
    ("SEA", "Mariners", "Seattle", "#0C2C56", "#005C5C"),
    ("STL", "Cardinals", "St. Louis", "#C41E3A", "#0C2340"),
    ("TB", "Rays", "Tampa Bay", "#092C5C", "#8FBCE6"),
    ("TEX", "Rangers", "Texas", "#003278", "#C0111F"),
    ("TOR", "Blue Jays", "Toronto", "#134A8E", "#1D2D5C"),
    ("WSH", "Nationals", "Washington", "#AB0003", "#14225A"),
]

# ── NHL ───────────────────────────────────────────────────────────────────────

NHL_TEAMS = [
    ("ANA", "Ducks", "Anaheim", "#F47A38", "#B9975B"),
    ("BOS", "Bruins", "Boston", "#FFB81C", "#000000"),
    ("BUF", "Sabres", "Buffalo", "#003087", "#FCB514"),
    ("CAR", "Hurricanes", "Carolina", "#CC0000", "#000000"),
    ("CBJ", "Blue Jackets", "Columbus", "#002654", "#CE1126"),
    ("CGY", "Flames", "Calgary", "#C8102E", "#F1BE48"),
    ("CHI", "Blackhawks", "Chicago", "#CF0A2C", "#000000"),
    ("COL", "Avalanche", "Colorado", "#6F263D", "#236192"),
    ("DAL", "Stars", "Dallas", "#006847", "#8F8F8C"),
    ("DET", "Red Wings", "Detroit", "#CE1126", "#FFFFFF"),
    ("EDM", "Oilers", "Edmonton", "#041E42", "#FF4C00"),
    ("FLA", "Panthers", "Florida", "#041E42", "#C8102E"),
    ("LAK", "Kings", "Los Angeles", "#111111", "#A2AAAD"),
    ("MIN", "Wild", "Minnesota", "#154734", "#A6192E"),
    ("MTL", "Canadiens", "Montreal", "#AF1E2D", "#192168"),
    ("NJD", "Devils", "New Jersey", "#CE1126", "#000000"),
    ("NSH", "Predators", "Nashville", "#FFB81C", "#041E42"),
    ("NYI", "Islanders", "New York", "#003087", "#FC4C02"),
    ("NYR", "Rangers", "New York", "#0038A8", "#CE1126"),
    ("OTT", "Senators", "Ottawa", "#C52032", "#C69214"),
    ("PHI", "Flyers", "Philadelphia", "#F74902", "#000000"),
    ("PIT", "Penguins", "Pittsburgh", "#FCB514", "#000000"),
    ("SEA", "Kraken", "Seattle", "#001628", "#68A2B9"),
    ("SJS", "Sharks", "San Jose", "#006D75", "#EA7200"),
    ("STL", "Blues", "St. Louis", "#002F87", "#FCB514"),
    ("TBL", "Lightning", "Tampa Bay", "#002868", "#FFFFFF"),
    ("TOR", "Maple Leafs", "Toronto", "#00205B", "#FFFFFF"),
    ("UTA", "Utah HC", "Utah", "#71AFE5", "#010101"),
    ("VAN", "Canucks", "Vancouver", "#00843D", "#00205B"),
    ("VGK", "Golden Knights", "Vegas", "#B4975A", "#333F48"),
    ("WPG", "Jets", "Winnipeg", "#041E42", "#AC162C"),
    ("WSH", "Capitals", "Washington", "#041E42", "#C8102E"),
]

# ── EPL (English Premier League) ─────────────────────────────────────────────

EPL_TEAMS = [
    ("ARS", "Arsenal", "London", "#EF0107", "#063672"),
    ("AVL", "Aston Villa", "Birmingham", "#95BFE5", "#670E36"),
    ("BOU", "Bournemouth", "Bournemouth", "#DA291C", "#000000"),
    ("BRE", "Brentford", "London", "#E30613", "#FBB800"),
    ("BHA", "Brighton", "Brighton", "#0057B8", "#FFCD00"),
    ("CHE", "Chelsea", "London", "#034694", "#DBA111"),
    ("CRY", "Crystal Palace", "London", "#1B458F", "#C4122E"),
    ("EVE", "Everton", "Liverpool", "#003399", "#FFFFFF"),
    ("FUL", "Fulham", "London", "#000000", "#FFFFFF"),
    ("IPS", "Ipswich", "Ipswich", "#3A64A3", "#FFFFFF"),
    ("LEI", "Leicester", "Leicester", "#003090", "#FDBE11"),
    ("LIV", "Liverpool", "Liverpool", "#C8102E", "#00B2A9"),
    ("MCI", "Manchester City", "Manchester", "#6CABDD", "#1C2C5B"),
    ("MUN", "Manchester Utd", "Manchester", "#DA291C", "#FBE122"),
    ("NEW", "Newcastle", "Newcastle", "#241F20", "#41B6E6"),
    ("NFO", "Nottm Forest", "Nottingham", "#DD0000", "#FFFFFF"),
    ("SOU", "Southampton", "Southampton", "#D71920", "#130C0E"),
    ("TOT", "Tottenham", "London", "#132257", "#FFFFFF"),
    ("WHU", "West Ham", "London", "#7A263A", "#1BB1E7"),
    ("WOL", "Wolves", "Wolverhampton", "#FDB913", "#231F20"),
]

# ── FIFA (National Teams) ─────────────────────────────────────────────────────

FIFA_TEAMS = [
    ("ARG", "Argentina", "Argentina", "#74ACDF", "#FFFFFF"),
    ("AUS", "Australia", "Australia", "#00843D", "#FFD700"),
    ("AUT", "Austria", "Austria", "#ED2939", "#FFFFFF"),
    ("BEL", "Belgium", "Belgium", "#000000", "#E40521"),
    ("BRA", "Brazil", "Brazil", "#009C3B", "#FFDF00"),
    ("CHI", "Chile", "Chile", "#D52B1E", "#FFFFFF"),
    ("COL", "Colombia", "Colombia", "#FCD116", "#003087"),
    ("CRO", "Croatia", "Croatia", "#FF0000", "#FFFFFF"),
    ("CZE", "Czech Republic", "Czech Republic", "#D7141A", "#FFFFFF"),
    ("DEN", "Denmark", "Denmark", "#C60C30", "#FFFFFF"),
    ("ENG", "England", "England", "#FFFFFF", "#CF081F"),
    ("ESP", "Spain", "Spain", "#AA151B", "#F1BF00"),
    ("FRA", "France", "France", "#002395", "#FFFFFF"),
    ("GER", "Germany", "Germany", "#000000", "#FFFFFF"),
    ("GHA", "Ghana", "Ghana", "#006B3F", "#FCD116"),
    ("HUN", "Hungary", "Hungary", "#CE2939", "#FFFFFF"),
    ("IRL", "Ireland", "Ireland", "#169B62", "#FF883E"),
    ("ITA", "Italy", "Italy", "#0066CC", "#FFFFFF"),
    ("JAP", "Japan", "Japan", "#BC002D", "#FFFFFF"),
    ("KOR", "South Korea", "South Korea", "#003478", "#CD2E3A"),
    ("MAR", "Morocco", "Morocco", "#C1272D", "#006233"),
    ("MEX", "Mexico", "Mexico", "#006847", "#CE1126"),
    ("NED", "Netherlands", "Netherlands", "#FF6600", "#FFFFFF"),
    ("NGA", "Nigeria", "Nigeria", "#008751", "#FFFFFF"),
    ("POL", "Poland", "Poland", "#FFFFFF", "#DC143C"),
    ("POR", "Portugal", "Portugal", "#006600", "#FF0000"),
    ("ROU", "Romania", "Romania", "#002B7F", "#FCD116"),
    ("SCO", "Scotland", "Scotland", "#003399", "#FFFFFF"),
    ("SEN", "Senegal", "Senegal", "#00853F", "#FDEF42"),
    ("SRB", "Serbia", "Serbia", "#C6363C", "#0C4076"),
    ("SUI", "Switzerland", "Switzerland", "#FF0000", "#FFFFFF"),
    ("SWE", "Sweden", "Sweden", "#006AA7", "#FECC02"),
    ("TUR", "Turkey", "Turkey", "#E30A17", "#FFFFFF"),
    ("UKR", "Ukraine", "Ukraine", "#005BBB", "#FFD500"),
    ("URU", "Uruguay", "Uruguay", "#5AAAE7", "#FFFFFF"),
    ("USA", "United States", "United States", "#B22234", "#3C3B6E"),
    ("WAL", "Wales", "Wales", "#C8102E", "#007A3D"),
]

# ── F1 (Constructors) ─────────────────────────────────────────────────────────

F1_TEAMS = [
    ("RBR", "Red Bull Racing", "Milton Keynes", "#3671C6", "#CC1E4A"),
    ("FER", "Ferrari", "Maranello", "#E8002D", "#FFFFFF"),
    ("MER", "Mercedes", "Brackley", "#27F4D2", "#000000"),
    ("MCL", "McLaren", "Woking", "#FF8000", "#000000"),
    ("AMR", "Aston Martin", "Silverstone", "#358C75", "#000000"),
    ("ALP", "Alpine", "Enstone", "#0093CC", "#FF87BC"),
    ("WIL", "Williams", "Grove", "#005AFF", "#FFFFFF"),
    ("VCR", "Visa Cash App RB", "Faenza", "#6692FF", "#FFFFFF"),
    ("SAU", "Kick Sauber", "Hinwil", "#52E252", "#000000"),
    ("HAA", "Haas", "Kannapolis", "#B6BABD", "#E8002D"),
]

# ── PGA (Golfers) ─────────────────────────────────────────────────────────────

PGA_PLAYERS = [
    ("SCH", "Scottie Scheffler", "United States", "#00663A", "#E5B53B"),
    ("ROR", "Rory McIlroy", "Northern Ireland", "#00663A", "#E5B53B"),
    ("XAN", "Xander Schauffele", "United States", "#00663A", "#E5B53B"),
    ("MOA", "Collin Morikawa", "United States", "#00663A", "#E5B53B"),
    ("HOV", "Viktor Hovland", "Norway", "#00663A", "#E5B53B"),
    ("AAB", "Ludvig Åberg", "Sweden", "#00663A", "#E5B53B"),
    ("RJN", "Jon Rahm", "Spain", "#00663A", "#E5B53B"),
    ("BCK", "Brooks Koepka", "United States", "#00663A", "#E5B53B"),
    ("BRY", "Bryson DeChambeau", "United States", "#00663A", "#E5B53B"),
    ("JSP", "Jordan Spieth", "United States", "#00663A", "#E5B53B"),
    ("JTH", "Justin Thomas", "United States", "#00663A", "#E5B53B"),
    ("MAT", "Tommy Fleetwood", "England", "#00663A", "#E5B53B"),
    ("SHA", "Shane Lowry", "Ireland", "#00663A", "#E5B53B"),
    ("TYR", "Tyrrell Hatton", "England", "#00663A", "#E5B53B"),
    ("HID", "Hideki Matsuyama", "Japan", "#00663A", "#E5B53B"),
    ("TOF", "Tony Finau", "United States", "#00663A", "#E5B53B"),
    ("MXH", "Max Homa", "United States", "#00663A", "#E5B53B"),
    ("MFT", "Matt Fitzpatrick", "England", "#00663A", "#E5B53B"),
    ("ADS", "Adam Scott", "Australia", "#00663A", "#E5B53B"),
    ("JAD", "Jason Day", "Australia", "#00663A", "#E5B53B"),
    ("WZA", "Will Zalatoris", "United States", "#00663A", "#E5B53B"),
    ("PHM", "Phil Mickelson", "United States", "#00663A", "#E5B53B"),
    ("TIG", "Tiger Woods", "United States", "#00663A", "#E5B53B"),
    ("DJO", "Dustin Johnson", "United States", "#00663A", "#E5B53B"),
    ("SAB", "Sam Burns", "United States", "#00663A", "#E5B53B"),
]


def run_seed():
    is_dev = os.environ.get("FLASK_ENV", "development") != "production"

    # ── Teams ────────────────────────────────────────────────────────────────
    existing_teams = Team.query.count()
    if existing_teams == 0:
        league_data = [
            ("NBA", NBA_TEAMS),
            ("NFL", NFL_TEAMS),
            ("MLB", MLB_TEAMS),
            ("NHL", NHL_TEAMS),
            ("EPL", EPL_TEAMS),
            ("FIFA", FIFA_TEAMS),
            ("F1", F1_TEAMS),
            ("PGA", PGA_PLAYERS),
        ]
        total = 0
        for league, teams in league_data:
            for abbr, name, city, primary, secondary in teams:
                db.session.add(Team(
                    league=league, name=name, abbreviation=abbr,
                    city=city, primary_color=primary, secondary_color=secondary
                ))
                total += 1
        db.session.commit()
        print(f"Seeded {total} teams across {len(league_data)} leagues.")
    else:
        print(f"Teams already seeded ({existing_teams}).")

    def get_team(league, name):
        return Team.query.filter_by(league=league, name=name).first()

    # ── Users ────────────────────────────────────────────────────────────────
    users_data = [
        ("Fenix", "fenix@friedsports.dev", "password123"),
        ("Cody", "cody@friedsports.dev", "password123"),
        ("AJ", "aj@friedsports.dev", "password123"),
        ("Lynn", "lynn@friedsports.dev", "password123"),
    ]
    users = {}
    for display_name, email, pw in users_data:
        u = User.query.filter_by(email=email).first()
        if not u:
            u = User(display_name=display_name, email=email)
            u.set_password(pw)
            db.session.add(u)
            db.session.flush()
        users[display_name] = u
    # Fenix is app admin
    users["Fenix"].role = "admin"
    db.session.commit()
    print(f"Seeded {len(users)} users.")

    # ── Favorite teams ────────────────────────────────────────────────────────
    fav_map = {
        "Fenix": [("NBA", "Spurs"), ("NFL", "Cowboys"), ("MLB", "Rangers")],
        "Cody": [("NBA", "Lakers"), ("NFL", "Rams"), ("MLB", "Dodgers")],
        "AJ": [("NFL", "Cowboys"), ("NBA", "Mavericks"), ("MLB", "Rangers")],
        "Lynn": [("NBA", "Celtics"), ("NFL", "Patriots"), ("MLB", "Red Sox")],
    }
    for uname, pairs in fav_map.items():
        u = users[uname]
        for league, tname in pairs:
            team = get_team(league, tname)
            if not team:
                continue
            existing = UserFavoriteTeam.query.filter_by(user_id=u.id, league=league).first()
            if not existing:
                db.session.add(UserFavoriteTeam(user_id=u.id, league=league, team_id=team.id))
    db.session.commit()

    # ── Groups ────────────────────────────────────────────────────────────────
    groups_data = [
        ("The Slander Room", "MULTI", "private"),
        ("NBA Fraud Watch", "NBA", "private"),
    ]
    groups = {}
    owner = users["Fenix"]
    for gname, scope, privacy in groups_data:
        g = Group.query.filter_by(name=gname).first()
        if not g:
            g = Group(
                name=gname,
                owner_id=owner.id,
                league_scope=scope,
                privacy=privacy,
                invite_code=secrets.token_urlsafe(6),
            )
            db.session.add(g)
            db.session.flush()
        groups[gname] = g

    role_map = {"Fenix": "owner", "Cody": "admin", "AJ": "member", "Lynn": "member"}
    for gname, g in groups.items():
        for uname, u in users.items():
            existing = GroupMember.query.filter_by(group_id=g.id, user_id=u.id).first()
            if not existing:
                db.session.add(GroupMember(
                    group_id=g.id,
                    user_id=u.id,
                    role=role_map.get(uname, "member"),
                ))
    db.session.commit()
    print(f"Seeded {len(groups)} groups.")

    # ── Sample incidents (dev only) ───────────────────────────────────────────
    if is_dev:
        from app.services.incident_service import create_incident_thread

        slander_room = groups["The Slander Room"]
        nba_group = groups["NBA Fraud Watch"]

        incidents_data = [
            {
                "group": slander_room,
                "reporter": users["Cody"],
                "target": users["Fenix"],
                "team_league": "NBA", "team_name": "Spurs",
                "incident_type": "BLOWOUT_ALERT",
                "severity": 3,
                "reported_score_text": "Down 28 in the 3rd",
            },
            {
                "group": slander_room,
                "reporter": users["AJ"],
                "target": users["Fenix"],
                "team_league": "NFL", "team_name": "Cowboys",
                "incident_type": "CHOKED_LEAD",
                "severity": 4,
                "reported_score_text": "Blew a 17-point lead in the 4th",
            },
            {
                "group": nba_group,
                "reporter": users["Lynn"],
                "target": users["Cody"],
                "team_league": "NBA", "team_name": "Lakers",
                "incident_type": "FRAUD_WATCH",
                "severity": 2,
                "reported_score_text": "Lost by 5 to the Nuggets at home",
            },
        ]

        seeded_incidents = 0
        for inc in incidents_data:
            team = get_team(inc["team_league"], inc["team_name"])
            if not team:
                continue
            existing = IncidentReport.query.filter_by(
                group_id=inc["group"].id,
                target_user_id=inc["target"].id,
                target_team_id=team.id,
                incident_type=inc["incident_type"],
            ).first()
            if existing:
                continue

            report = IncidentReport(
                reporter_user_id=inc["reporter"].id,
                group_id=inc["group"].id,
                target_user_id=inc["target"].id,
                target_team_id=team.id,
                league=team.league,
                incident_type=inc["incident_type"],
                severity=inc["severity"],
                reported_score_text=inc["reported_score_text"],
                status="active",
            )
            db.session.add(report)
            db.session.flush()
            create_incident_thread(report)
            db.session.commit()
            seeded_incidents += 1

        print(f"Seeded {seeded_incidents} sample incidents (dev only).")

    # ── Lab Leagues ───────────────────────────────────────────────────────────
    lab_leagues_data = [
        ("National Basketball Association", "NBA", "basketball"),
        ("National Football League", "NFL", "football"),
        ("Major League Baseball", "MLB", "baseball"),
        ("National Hockey League", "NHL", "hockey"),
        ("English Premier League", "EPL", "soccer"),
        ("FIFA International", "FIFA", "soccer"),
        ("Formula One", "F1", "motorsport"),
        ("PGA Tour", "PGA", "golf"),
    ]
    seeded_leagues = 0
    for name, abbr, sport_type in lab_leagues_data:
        if not LabLeague.query.filter_by(abbreviation=abbr).first():
            db.session.add(LabLeague(name=name, abbreviation=abbr, sport_type=sport_type))
            seeded_leagues += 1
    db.session.commit()
    print(f"Seeded {seeded_leagues} lab leagues.")
    print("Seed complete.")
