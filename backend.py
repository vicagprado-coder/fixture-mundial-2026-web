# -*- coding: utf-8 -*-
"""
Fixture Mundial 2026 - Backend web.

Contiene la lógica del fixture, consultas FIFA, guardado persistente,
estadísticas, jugadores, análisis, clasificados y rondas.
Este archivo es usado por web_app.py para publicar el sistema en hosting.
"""
from __future__ import annotations

import functools
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import http.server
import json
import html as html_parser
import math
import os
import re
import socket
import socketserver
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from io import BytesIO
from typing import Any, Dict, List, Tuple

APP_TITLE = "Fixture Mundial 2026"


def _app_base_dir() -> Path:
    """Carpeta base del aplicativo web."""
    return Path(__file__).resolve().parent


BASE_DIR = _app_base_dir()
HTML_FILE = BASE_DIR / "app_mundial_2026.html"

# Guardado persistente:
# 1) Archivo principal en AppData/Usuario para que no se pierda si cambias de carpeta o actualizas el ZIP.
# 2) Copia de respaldo dentro del proyecto en data/.
def _user_data_dir() -> Path:
    # En hosting web, usar FIXTURE_DATA_DIR para controlar dónde se guardan
    # resultados/cache. Ejemplos: /tmp/fixture_mundial_2026 o un disco persistente.
    custom = os.environ.get("FIXTURE_DATA_DIR")
    if custom:
        return Path(custom).expanduser()
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home())
        return Path(root) / "FixtureMundial2026"
    return Path.home() / ".fixture_mundial_2026"

USER_DATA_DIR = _user_data_dir()
USER_DATA_FILE = USER_DATA_DIR / "resultados_fixture_2026.json"
LOCAL_DATA_DIR = BASE_DIR / "data"
LOCAL_DATA_FILE = LOCAL_DATA_DIR / "resultados_fixture_2026.json"
DATA_DIR = USER_DATA_DIR
DATA_FILE = USER_DATA_FILE

# Banderas locales: se descargan una vez en assets/flags/ y luego la interfaz
# siempre intenta leerlas desde disco. Si no hay internet, se usa fallback remoto/placeholder.
FLAGS_DIR = BASE_DIR / "assets" / "flags"
PLAYER_IMAGES_DIR = BASE_DIR / "assets" / "players"
PLAYER_IMAGE_REPORT_FILE = LOCAL_DATA_DIR / "player_image_cache_report.json"
PLAYER_IMAGE_ERROR_FILE = LOCAL_DATA_DIR / "player_image_errors.json"
PLAYER_IMAGE_DOWNLOAD_LOG_FILE = LOCAL_DATA_DIR / "player_image_download_log.jsonl"
PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE = LOCAL_DATA_DIR / "player_image_download_summary.json"
PLAYER_IMAGE_MANUAL_SOURCES_FILE = LOCAL_DATA_DIR / "player_image_sources_manual.json"
PLAYER_IMAGE_MANUAL_RAW_FILE = BASE_DIR / "FOTOS.txt"
PLAYER_IMAGE_MAX_SIZE = 220
PLAYER_IMAGE_QUALITY = 78
PLAYER_IMAGE_BATCH_SIZE = 5
# Parámetros oficiales observados en FIFA squad para que digitalhub devuelva AVIF real.
FIFA_PLAYER_IMAGE_QUERY = "&io=transform:fill,aspectratio:1x1,width:640,gravity:top&quality=75"
TEAM_ISO_FLAGS = {
    "Mexico": "mx", "South Africa": "za", "Korea Republic": "kr", "Czechia": "cz",
    "Canada": "ca", "Bosnia and Herzegovina": "ba", "Qatar": "qa", "Switzerland": "ch",
    "Brazil": "br", "Morocco": "ma", "Haiti": "ht", "Scotland": "gb-sct",
    "United States": "us", "Paraguay": "py", "Australia": "au", "Türkiye": "tr",
    "Germany": "de", "Curaçao": "cw", "Ivory Coast": "ci", "Ecuador": "ec",
    "Netherlands": "nl", "Japan": "jp", "Sweden": "se", "Tunisia": "tn",
    "Belgium": "be", "Egypt": "eg", "Iran": "ir", "New Zealand": "nz",
    "Spain": "es", "Cape Verde": "cv", "Saudi Arabia": "sa", "Uruguay": "uy",
    "France": "fr", "Senegal": "sn", "Iraq": "iq", "Norway": "no",
    "Argentina": "ar", "Algeria": "dz", "Austria": "at", "Jordan": "jo",
    "Portugal": "pt", "DR Congo": "cd", "Uzbekistan": "uz", "Colombia": "co",
    "England": "gb-eng", "Croatia": "hr", "Ghana": "gh", "Panama": "pa",
}

# Ranking fallback para que el botón funcione aun si no puede conectarse o parsear internet.
# Se puede editar en data/ranking_fifa_manual.json si se desea reemplazar con ranking actualizado.
FALLBACK_RANKING = {
    "FRA": {"rank": 1, "points": 1877.32}, "ESP": {"rank": 2, "points": 1876.40},
    "ARG": {"rank": 3, "points": 1874.81}, "ENG": {"rank": 4, "points": 1825.97},
    "BRA": {"rank": 5, "points": 1761.60}, "POR": {"rank": 6, "points": 1756.12},
    "NED": {"rank": 7, "points": 1752.44}, "BEL": {"rank": 8, "points": 1735.75},
    "GER": {"rank": 9, "points": 1725.00}, "CRO": {"rank": 10, "points": 1718.00},
    "MAR": {"rank": 11, "points": 1708.00}, "URU": {"rank": 12, "points": 1695.00},
    "COL": {"rank": 13, "points": 1689.00}, "USA": {"rank": 14, "points": 1675.00},
    "MEX": {"rank": 15, "points": 1664.00}, "SUI": {"rank": 16, "points": 1655.00},
    "JPN": {"rank": 17, "points": 1648.00}, "SEN": {"rank": 18, "points": 1635.00},
    "IRN": {"rank": 19, "points": 1625.00}, "KOR": {"rank": 20, "points": 1618.00},
    "AUS": {"rank": 23, "points": 1586.00}, "TUR": {"rank": 24, "points": 1580.00},
    "ECU": {"rank": 25, "points": 1574.00}, "AUT": {"rank": 26, "points": 1568.00},
    "CAN": {"rank": 28, "points": 1550.00}, "QAT": {"rank": 30, "points": 1536.00},
    "EGY": {"rank": 31, "points": 1530.00}, "NOR": {"rank": 32, "points": 1525.00},
    "SCO": {"rank": 33, "points": 1518.00}, "PAR": {"rank": 35, "points": 1509.00},
    "RSA": {"rank": 38, "points": 1491.00}, "CIV": {"rank": 40, "points": 1480.00},
    "TUN": {"rank": 42, "points": 1472.00}, "ALG": {"rank": 43, "points": 1469.00},
    "CZE": {"rank": 44, "points": 1464.00}, "BIH": {"rank": 52, "points": 1420.00},
    "KSA": {"rank": 54, "points": 1410.00}, "NZL": {"rank": 57, "points": 1395.00},
    "IRQ": {"rank": 58, "points": 1390.00}, "UZB": {"rank": 59, "points": 1387.00},
    "PAN": {"rank": 60, "points": 1380.00}, "JOR": {"rank": 61, "points": 1375.00},
    "CPV": {"rank": 62, "points": 1370.00}, "COD": {"rank": 63, "points": 1368.00},
    "CUW": {"rank": 64, "points": 1360.00}, "HAI": {"rank": 80, "points": 1290.00},
    "GHA": {"rank": 68, "points": 1342.00},
}

TEAM_CODES = {
    "Mexico": "MEX", "South Africa": "RSA", "Korea Republic": "KOR", "Czechia": "CZE",
    "Canada": "CAN", "Bosnia and Herzegovina": "BIH", "Qatar": "QAT", "Switzerland": "SUI",
    "Brazil": "BRA", "Morocco": "MAR", "Haiti": "HAI", "Scotland": "SCO",
    "United States": "USA", "Paraguay": "PAR", "Australia": "AUS", "Türkiye": "TUR",
    "Germany": "GER", "Curaçao": "CUW", "Ivory Coast": "CIV", "Ecuador": "ECU",
    "Netherlands": "NED", "Japan": "JPN", "Sweden": "SWE", "Tunisia": "TUN",
    "Belgium": "BEL", "Egypt": "EGY", "Iran": "IRN", "New Zealand": "NZL",
    "Spain": "ESP", "Cape Verde": "CPV", "Saudi Arabia": "KSA", "Uruguay": "URU",
    "France": "FRA", "Senegal": "SEN", "Iraq": "IRQ", "Norway": "NOR",
    "Argentina": "ARG", "Algeria": "ALG", "Austria": "AUT", "Jordan": "JOR",
    "Portugal": "POR", "DR Congo": "COD", "Uzbekistan": "UZB", "Colombia": "COL",
    "England": "ENG", "Croatia": "CRO", "Ghana": "GHA", "Panama": "PAN",
}

AS_TEAM_DISCIPLINE_URLS = {
    "yellow": "https://as.com/resultados/futbol/mundial/2026/ranking/equipos/tarjetas-amarillas/",
    "red": "https://as.com/resultados/futbol/mundial/2026/ranking/equipos/tarjetas-rojas/",
}

AS_PLAYER_STAT_URLS = {
    "goals": "https://as.com/resultados/futbol/mundial/2026/ranking/jugadores/goles/",
    "assists": "https://as.com/resultados/futbol/mundial/2026/ranking/jugadores/asistencias/",
    "yellow": "https://as.com/resultados/futbol/mundial/2026/ranking/jugadores/tarjetas-amarillas/",
    "red": "https://as.com/resultados/futbol/mundial/2026/ranking/jugadores/tarjetas-rojas/",
}

# Fuente oficial FIFA para estadísticas agregadas por equipo.
# La página pública de FIFA expone el IdTeam dentro de su API CXM:
# https://cxm-api.fifa.com/fifaplusweb/api/pages/es/tournaments/mens/worldcup/canadamexicousa2026/teams/brazil/stats -> teamId 43924
# Luego las estadísticas se leen desde FDH:
# https://fdh-api.fifa.com/v1/stats/season/285023/team/<IdTeam>.json
FIFA_STATS_SEASON_ID = "285023"
FIFA_TEAM_IDS_DEFAULT = {
    "GER": {"idTeam": "43948", "slug": "germany", "nameEs": "Alemania"},
    "BRA": {"idTeam": "43924", "slug": "brazil", "nameEs": "Brasil"},
}
FIFA_TEAM_STATS_TEMPLATE = "https://fdh-api.fifa.com/v1/stats/season/{season}/team/{team_id}.json"
FIFA_PLAYER_STATS_TEMPLATE = "https://fdh-api.fifa.com/v1/stats/season/{season}/players.json"
FIFA_TEAM_SQUAD_TEMPLATE = "https://api.fifa.com/api/v3/teams/{team_id}/squad?idCompetition={competition}&idSeason={season}&language=es"
FIFA_TEAM_META_TEMPLATE = "https://api.fifa.com/api/v3/teams/{team_id}?language=es"
FIFA_TEAM_PAGE_TEMPLATE = "https://cxm-api.fifa.com/fifaplusweb/api/pages/es/tournaments/mens/worldcup/canadamexicousa2026/teams/{slug}/stats"
FIFA_TEAM_AUTO_CACHE = LOCAL_DATA_DIR / "fifa_team_ids_auto.json"
FIFA_STATS_CACHE = USER_DATA_DIR / "fifa_team_stats_cache.json"
FIFA_STATS_CACHE_BACKUP = LOCAL_DATA_DIR / "fifa_team_stats_cache.json"
FIFA_PLAYER_STATS_CACHE = USER_DATA_DIR / "fifa_player_stats_cache.json"
FIFA_PLAYER_STATS_CACHE_BACKUP = LOCAL_DATA_DIR / "fifa_player_stats_cache.json"
FIFA_STATS_TTL_SECONDS = 6 * 60 * 60
FIFA_DISCOVER_WORKERS = 10
FIFA_STATS_WORKERS = 14
FIFA_SQUAD_WORKERS = 14
FIFA_EXPECTED_TEAMS = 48
FIFA_EXPECTED_PLAYERS_PER_TEAM = 26
FIFA_EXPECTED_PLAYERS = FIFA_EXPECTED_TEAMS * FIFA_EXPECTED_PLAYERS_PER_TEAM

# Estadísticas de jugador que sí se pueden sumar para crear totales de equipo.
# Se excluyen métricas contextuales como GoalsConceded, CleanSheets, Possession
# o AttemptAtGoalAgainst porque suelen venir repetidas por jugador y no deben sumarse.
FIFA_PLAYER_SUM_STATS = [
    "Goals", "Assists", "OwnGoals",
    "YellowCards", "RedCards", "DirectRedCards", "IndirectRedCards",
    "Passes", "PassesCompleted", "Crosses", "CrossesCompleted",
    "AttemptAtGoal", "AttemptAtGoalOnTarget", "AttemptAtGoalOffTarget", "AttemptAtGoalBlocked",
    "AttemptAtGoalInsideThePenaltyArea", "AttemptAtGoalInsideThePenaltyAreaOnTarget",
    "AttemptAtGoalOutsideThePenaltyArea", "AttemptAtGoalOutsideThePenaltyAreaOnTarget",
    "AttemptAtGoalFromBallProgression", "AttemptAtGoalFromCorner", "AttemptAtGoalFromCross",
    "AttemptAtGoalFromFreeKicks", "AttemptAtGoalFromOther", "AttemptAtGoalFromPass",
    "AttemptAtGoalFromPenalty", "AttemptAtGoalFromRebound", "HeadedAttemptAtGoal",
    "Corners", "FreeKicks", "DirectFreeKicks", "IndirectFreeKicks", "GoalKicks", "ThrowIns",
    "FoulsFor", "FoulsAgainst", "Penalties", "PenaltiesScored", "Offsides",
    "TakeOnsCompleted", "AttemptedBallProgressions", "CompletedBallProgressions",
    "AttemptedSwitchesOfPlay", "CompletedSwitchesOfPlay",
    "DefensivePressuresApplied", "DirectDefensivePressuresApplied", "ForcedTurnovers",
    "DistributionsUnderPressure", "DistributionsCompletedUnderPressure",
    "FinalThirdEntriesReceptionCentralChannel", "FinalThirdEntriesReceptionInsideLeftChannel",
    "FinalThirdEntriesReceptionInsideRightChannel", "FinalThirdEntriesReceptionLeftChannel",
    "FinalThirdEntriesReceptionRightChannel",
    "LinebreaksAttempted", "LinebreaksAttemptedCompleted", "LinebreaksAttemptedUnderPressure",
    "LinebreaksCompletedUnderPressure", "LinebreaksAttemptedAllLines", "LinebreaksCompletedAllLines",
    "LinebreaksAttemptedAttackingLine", "LinebreaksAttemptedAttackingLineCompleted",
    "LinebreaksAttemptedMidfieldLine", "LinebreaksAttemptedMidfieldLineCompleted",
    "LinebreaksAttemptedDefensiveLine", "LinebreaksAttemptedDefensiveLineCompleted",
    "LinebreaksAttemptedAttackingAndMidfieldLine", "LinebreaksCompletedAttackingAndMidfieldLine",
    "LinebreaksAttemptedMidfieldAndDefensiveLine", "LinebreaksCompletedMidfieldAndDefensiveLine",
    "OffersToReceiveTotal", "OffersToReceiveInBehind", "OffersToReceiveInBetween", "OffersToReceiveInFront",
    "OffersToReceiveInside", "OffersToReceiveOutside", "ReceivedOffersToReceive",
    "ReceptionsBetweenMidfieldAndDefensiveLine", "ReceptionsInBehind",
    "ReceptionsUnderPressure", "ReceptionsUnderDirectPressure", "ReceptionsUnderIndirectPressure",
    "ReceptionsUnderNoPressure",
    "SpeedRuns", "Sprints", "TotalDistance", "DistanceWalking", "DistanceJogging",
    "DistanceHighSpeedRunning", "DistanceLowSpeedSprinting", "DistanceHighSpeedSprinting",
    "XG", "Threat",
    "GoalkeeperSaves", "GoalkeeperSavesOnTarget",
    "GoalkeeperDefensiveActionsInsidePenaltyArea", "GoalkeeperDefensiveActionsOutsidePenaltyArea",
]

# Slugs usados por FIFA.com. Se incluyen variantes para nombres que suelen cambiar
# entre inglés/español o por acentos. La app intenta resolver automáticamente el IdTeam.
FIFA_TEAM_SLUGS = {
    "MEX": ["mexico"],
    "RSA": ["south-africa"],
    "KOR": ["korea-republic", "south-korea"],
    "CZE": ["czechia", "czech-republic"],
    "CAN": ["canada"],
    "BIH": ["bosnia-and-herzegovina", "bosnia-herzegovina"],
    "QAT": ["qatar"],
    "SUI": ["switzerland"],
    "BRA": ["brazil"],
    "MAR": ["morocco"],
    "HAI": ["haiti"],
    "SCO": ["scotland"],
    "USA": ["united-states", "usa"],
    "PAR": ["paraguay"],
    "AUS": ["australia"],
    "TUR": ["turkiye", "turkey"],
    "GER": ["germany"],
    "CUW": ["curacao", "curaçao"],
    "CIV": ["cote-divoire", "cote-d-ivoire", "ivory-coast"],
    "ECU": ["ecuador"],
    "NED": ["netherlands"],
    "JPN": ["japan"],
    "SWE": ["sweden"],
    "TUN": ["tunisia"],
    "BEL": ["belgium"],
    "EGY": ["egypt"],
    "IRN": ["ir-iran"],
    "NZL": ["new-zealand"],
    "ESP": ["spain"],
    "CPV": ["cabo-verde", "cape-verde"],
    "KSA": ["saudi-arabia"],
    "URU": ["uruguay"],
    "FRA": ["france"],
    "SEN": ["senegal"],
    "IRQ": ["iraq"],
    "NOR": ["norway"],
    "ARG": ["argentina"],
    "ALG": ["algeria"],
    "AUT": ["austria"],
    "JOR": ["jordan"],
    "POR": ["portugal"],
    "COD": ["dr-congo", "congo-dr", "democratic-republic-of-the-congo"],
    "UZB": ["uzbekistan"],
    "COL": ["colombia"],
    "ENG": ["england"],
    "CRO": ["croatia"],
    "GHA": ["ghana"],
    "PAN": ["panama"],
}

AS_TEAM_ALIASES = {
    "mexico": "Mexico", "méxico": "Mexico", "mex": "Mexico",
    "sudáfrica": "South Africa", "sudafrica": "South Africa", "saf": "South Africa", "rsa": "South Africa",
    "corea del sur": "Korea Republic", "cor": "Korea Republic", "kor": "Korea Republic",
    "r. checa": "Czechia", "república checa": "Czechia", "republica checa": "Czechia", "chequia": "Czechia", "rch": "Czechia",
    "canadá": "Canada", "canada": "Canada", "can": "Canada",
    "bosnia": "Bosnia and Herzegovina", "bosnia y herzegovina": "Bosnia and Herzegovina", "bih": "Bosnia and Herzegovina",
    "qatar": "Qatar", "qat": "Qatar",
    "suiza": "Switzerland", "sui": "Switzerland",
    "brasil": "Brazil", "bra": "Brazil",
    "marruecos": "Morocco", "mar": "Morocco",
    "haití": "Haiti", "haiti": "Haiti", "hai": "Haiti",
    "escocia": "Scotland", "esc": "Scotland", "sco": "Scotland",
    "ee.uu": "United States", "ee.uu.": "United States", "estados unidos": "United States", "usa": "United States",
    "paraguay": "Paraguay", "par": "Paraguay",
    "australia": "Australia", "aus": "Australia",
    "turquía": "Türkiye", "turquia": "Türkiye", "tur": "Türkiye",
    "alemania": "Germany", "ger": "Germany",
    "curazao": "Curaçao", "curacao": "Curaçao", "cur": "Curaçao", "cuw": "Curaçao",
    "c. marfil": "Ivory Coast", "c marfil": "Ivory Coast", "costa de marfil": "Ivory Coast", "cdm": "Ivory Coast", "civ": "Ivory Coast",
    "ecuador": "Ecuador", "ecu": "Ecuador",
    "países bajos": "Netherlands", "paises bajos": "Netherlands", "ndl": "Netherlands", "ned": "Netherlands",
    "japón": "Japan", "japon": "Japan", "jap": "Japan", "jpn": "Japan",
    "suecia": "Sweden", "sue": "Sweden", "swe": "Sweden",
    "túnez": "Tunisia", "tunez": "Tunisia", "tun": "Tunisia",
    "bélgica": "Belgium", "belgica": "Belgium", "bel": "Belgium",
    "egipto": "Egypt", "egy": "Egypt",
    "irán": "Iran", "iran": "Iran", "irn": "Iran", "iri": "Iran", "ir iran": "Iran", "ir-iran": "Iran",
    "nueva zelanda": "New Zealand", "nzl": "New Zealand",
    "españa": "Spain", "espana": "Spain", "esp": "Spain",
    "cabo verde": "Cape Verde", "cve": "Cape Verde", "cpv": "Cape Verde",
    "arabia saudita": "Saudi Arabia", "ksa": "Saudi Arabia",
    "uruguay": "Uruguay", "uru": "Uruguay",
    "francia": "France", "fra": "France",
    "senegal": "Senegal", "sen": "Senegal",
    "irak": "Iraq", "irq": "Iraq",
    "noruega": "Norway", "nor": "Norway",
    "argentina": "Argentina", "arg": "Argentina",
    "argelia": "Algeria", "alg": "Algeria",
    "austria": "Austria", "aut": "Austria",
    "jordania": "Jordan", "jor": "Jordan",
    "portugal": "Portugal", "por": "Portugal",
    "rd congo": "DR Congo", "r.d. congo": "DR Congo", "congo rd": "DR Congo", "cod": "DR Congo",
    "uzbekistán": "Uzbekistan", "uzbekistan": "Uzbekistan", "uzb": "Uzbekistan",
    "colombia": "Colombia", "col": "Colombia",
    "inglaterra": "England", "eng": "England",
    "croacia": "Croatia", "cro": "Croatia",
    "ghana": "Ghana", "gha": "Ghana",
    "panamá": "Panama", "panama": "Panama", "pan": "Panama",
}


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    # Se asigna desde start_server(api). Permite que el navegador normal también
    # guarde JSON y consulte internet, no solo pywebview.
    api: Any = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def guess_type(self, path: str) -> str:  # noqa: D401
        # Windows/Python antiguos no siempre conocen AVIF. Si no se envía
        # image/avif, el WebView puede no mostrar la foto aunque el archivo exista.
        if str(path).lower().endswith(".avif"):
            return "image/avif"
        return super().guess_type(path)

    def end_headers(self) -> None:  # noqa: N802
        # Los assets locales optimizados pueden cachearse en navegador/WebView.
        # El HTML principal conserva no-store desde _send_html.
        try:
            path = urllib.parse.urlparse(self.path).path
            if path.startswith("/assets/"):
                self.send_header("Cache-Control", "public, max-age=2592000, immutable")
        except Exception:
            pass
        super().end_headers()

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, content: str, status: int = 200) -> None:
        raw = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _serve_app_html(self) -> None:
        html = HTML_FILE.read_text(encoding="utf-8")
        state = None
        try:
            if self.api:
                state = self.api.load_results().get("data")
        except Exception:
            state = None
        boot = "<script>window.__INITIAL_STATE__ = " + json.dumps(state, ensure_ascii=False) + ";</script>"
        if "</head>" in html:
            html = html.replace("</head>", boot + "\n</head>", 1)
        else:
            html = boot + html
        self._send_html(html)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        return json.loads(raw or "{}")

    def do_GET(self) -> None:  # noqa: N802
        parsed_path = urllib.parse.urlparse(self.path).path
        if parsed_path in ("/", "/app_mundial_2026.html"):
            self._serve_app_html()
            return
        if self.path.startswith("/api/load"):
            self._send_json(self.api.load_results() if self.api else {"ok": False, "error": "API no inicializada"})
            return
        if self.path.startswith("/api/status"):
            self._send_json({"ok": True, "backend": "http", "data_file": str(DATA_FILE), "backup_file": str(LOCAL_DATA_FILE), "flags_dir": str(FLAGS_DIR)})
            return
        if self.path.startswith("/api/cache_flags"):
            self._send_json(self.api.cache_flags({}) if self.api else {"ok": False, "error": "API no inicializada"})
            return
        if self.path.startswith("/api/player_image_status"):
            self._send_json(self.api.player_image_status({}) if self.api else {"ok": False, "error": "API no inicializada"})
            return
        if self.path.startswith("/api/player_image_log"):
            self._send_json(self.api.player_image_log({}) if self.api else {"ok": False, "error": "API no inicializada"})
            return
        if self.path.startswith("/api/player_image_sources_manual"):
            self._send_json(self.api.player_image_sources_manual({}) if self.api else {"ok": False, "error": "API no inicializada"})
            return
        if self.path.startswith("/api/player_image_manual_download_status"):
            self._send_json(self.api.player_image_manual_download_status({}) if self.api else {"ok": False, "error": "API no inicializada"})
            return
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        try:
            payload = self._read_json()
            if self.path.startswith("/api/close"):
                self._send_json(self.api.close_app(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/save"):
                self._send_json(self.api.save_results(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/analyze_full"):
                self._send_json(self.api.analyze_full(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/analyze"):
                self._send_json(self.api.analyze_internet(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/sync"):
                self._send_json(self.api.sync_from_internet(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_stats"):
                self._send_json(self.api.load_player_stats(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/fifa_team_stats"):
                self._send_json(self.api.load_fifa_team_stats(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/fifa_player_stats"):
                self._send_json(self.api.load_fifa_player_stats(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/cache_player_images"):
                self._send_json(self.api.cache_player_images(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_save"):
                self._send_json(self.api.player_image_save(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_attempt_log"):
                self._send_json(self.api.player_image_attempt_log(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_status"):
                self._send_json(self.api.player_image_status(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_log"):
                self._send_json(self.api.player_image_log(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_sources_manual"):
                self._send_json(self.api.player_image_sources_manual(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_manual_download_start"):
                self._send_json(self.api.player_image_manual_download_start(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/player_image_manual_download_status"):
                self._send_json(self.api.player_image_manual_download_status(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/search_events"):
                self._send_json(self.api.search_match_events(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            if self.path.startswith("/api/cache_flags"):
                self._send_json(self.api.cache_flags(payload) if self.api else {"ok": False, "error": "API no inicializada"})
                return
            self._send_json({"ok": False, "error": "Ruta API no encontrada"}, 404)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, 500)


def start_server(api: Any) -> Tuple[socketserver.TCPServer, int]:
    port = find_free_port()
    QuietHandler.api = api
    handler = functools.partial(QuietHandler, directory=str(BASE_DIR))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    server = socketserver.ThreadingTCPServer(("0.0.0.0", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def http_get(url: str, timeout: int = 10) -> str:
    # User-Agent de navegador real: algunas fuentes, incluido AS.com, devuelven
    # HTML vacío o incompleto cuando el agente parece bot/script.
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "es-PE,es-419;q=0.9,es;q=0.8,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.google.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - user-triggered public URLs
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")



def http_get_bytes(url: str, timeout: int = 10) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/png,image/*,*/*;q=0.8",
            "Accept-Language": "es-PE,es-419;q=0.9,es;q=0.8,en;q=0.6",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://flagcdn.com/",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - user-triggered public URLs
        return response.read()


def http_get_image(url: str, timeout: int = 10, referer: str = "https://www.fifa.com/") -> Tuple[bytes, str]:
    """Descarga una imagen para cache local.

    v64: descarga la URL exacta entregada por FIFA DigitalHub
    (por ejemplo .../MUSIALA-Jamal_429642), sin crear variantes ni
    agregar .avif. Si FIFA responde image/avif, se guarda tal cual.
    """
    req = urllib.request.Request(
        url,
        headers={
            # Mismos headers del descargador aparte: FIFA DigitalHub responde mejor
            # cuando la petición se parece a un navegador real.
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": referer,
            "Origin": "https://www.fifa.com",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "cross-site",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:  # noqa: S310 - user-triggered public URLs
        content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        data = response.read()
        if not content_type.startswith("image/") and not _looks_like_image_bytes(data):
            raise ValueError(f"respuesta no es imagen: {content_type or 'sin content-type'}; bytes={len(data)}")
        return data, content_type


def _looks_like_image_bytes(data: bytes) -> bool:
    """Validación tolerante de imágenes descargadas.

    FIFA DigitalHub suele responder AVIF, pero el encabezado puede venir como
    ftypmif1 con marca compatible avif más adelante. Las versiones previas
    solo buscaban avif entre bytes 8-16 y rechazaban blobs válidos; por eso
    no se guardaban fotos aunque Chrome sí las mostrara.
    """
    head = bytes(data[:96] or b"")
    return (
        head.startswith(b"\xff\xd8\xff") or
        head.startswith(b"\x89PNG\r\n\x1a\n") or
        head.startswith(b"GIF87a") or
        head.startswith(b"GIF89a") or
        (head.startswith(b"RIFF") and b"WEBP" in head[:24]) or
        (len(head) >= 12 and head[4:8] == b"ftyp" and (b"avif" in head or b"avis" in head or b"mif1" in head or b"msf1" in head))
    )

def fetch_url(url: str, timeout: int = 10) -> str:
    # Alias explícito: versiones anteriores llamaban fetch_url pero solo existía http_get.
    # Ese NameError impedía cargar tarjetas AS.com.
    return http_get(url, timeout=timeout)


class AppApi:
    def __init__(self) -> None:
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        self._manual_image_job_lock = threading.Lock()
        self._manual_image_job_thread: threading.Thread | None = None
        self._manual_image_job_status: Dict[str, Any] = {
            "ok": True,
            "running": False,
            "message": "Sin descarga activa.",
            "total_urls": 0,
            "total": 0,
            "done": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "errors_sample": [],
            "latest_logs": [],
            "last_event": "",
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
        }

    def close_app(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Cierra la ventana de escritorio y finaliza el proceso local.
        Se ejecuta en hilo para devolver respuesta al frontend antes de apagar.
        """
        def _shutdown() -> None:
            time.sleep(0.25)
            try:
                import webview  # type: ignore
                for win in list(getattr(webview, "windows", []) or []):
                    try:
                        win.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                srv = getattr(self, "_server", None)
                if srv is not None:
                    srv.shutdown()
            except Exception:
                pass
            # En ejecución desde .bat, asegura que también termine la consola/proceso.
            time.sleep(0.20)
            os._exit(0)

        threading.Thread(target=_shutdown, daemon=True).start()
        return {"ok": True, "message": "Cerrando aplicativo..."}



    def cache_flags(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Descarga banderas una sola vez y las deja en assets/flags.
        La UI siempre usa primero /assets/flags/<iso>.png. Si ya existe, no vuelve a descargar.
        """
        FLAGS_DIR.mkdir(parents=True, exist_ok=True)
        downloaded: List[str] = []
        existing: List[str] = []
        failed: List[Dict[str, str]] = []
        for team, iso in TEAM_ISO_FLAGS.items():
            if not iso:
                continue
            target = FLAGS_DIR / f"{iso}.png"
            if target.exists() and target.stat().st_size > 100:
                existing.append(iso)
                continue
            url = f"https://flagcdn.com/w160/{iso}.png"
            try:
                data = http_get_bytes(url, timeout=8)
                if len(data) < 100:
                    raise ValueError("archivo de bandera vacío o inválido")
                target.write_bytes(data)
                downloaded.append(iso)
            except Exception as exc:
                failed.append({"team": team, "iso": iso, "error": str(exc)})
        return {
            "ok": True,
            "flags_dir": str(FLAGS_DIR),
            "downloaded": downloaded,
            "existing": existing,
            "failed": failed,
            "total_local": len([p for p in FLAGS_DIR.glob("*.png") if p.is_file()]),
            "message": "Banderas locales listas" if not failed else "Algunas banderas no se pudieron descargar; se usará fallback remoto/placeholder.",
        }

    def load_results(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        try:
            # Fuente principal: AppData/Usuario. Respaldo: data/ dentro del proyecto.
            source = None
            if USER_DATA_FILE.exists():
                source = USER_DATA_FILE
            elif LOCAL_DATA_FILE.exists():
                source = LOCAL_DATA_FILE
            if source:
                data = json.loads(source.read_text(encoding="utf-8"))
                # Migrar automáticamente al archivo persistente de usuario si venía del respaldo local.
                if source != USER_DATA_FILE:
                    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
                    USER_DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"ok": True, "data": data, "path": str(USER_DATA_FILE), "loaded_from": str(source), "backup_path": str(LOCAL_DATA_FILE)}
            return {"ok": True, "data": None, "path": str(USER_DATA_FILE), "backup_path": str(LOCAL_DATA_FILE)}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "data": None, "path": str(USER_DATA_FILE), "backup_path": str(LOCAL_DATA_FILE)}

    def save_results(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            payload = payload or {}
            # v106: proteger el archivo persistente contra guardados parciales.
            # Si el navegador/API trae menos equipos o jugadores que el último JSON bueno,
            # se conserva la información previa en lugar de reducirla.
            existing = self._read_existing_payload_for_merge()
            if isinstance(payload.get("fifaTeamStats"), dict) and isinstance(existing.get("fifaTeamStats"), dict):
                payload["fifaTeamStats"] = self._merge_fifa_team_stats(payload.get("fifaTeamStats") or {}, existing.get("fifaTeamStats") or {})
            if isinstance(payload.get("fifaPlayerStats"), dict) and isinstance(existing.get("fifaPlayerStats"), dict):
                payload["fifaPlayerStats"] = self._merge_fifa_player_stats_payload(payload.get("fifaPlayerStats") or {}, existing.get("fifaPlayerStats") or {})
            payload["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            text = json.dumps(payload, ensure_ascii=False, indent=2)
            USER_DATA_FILE.write_text(text, encoding="utf-8")
            # Copia de respaldo visible dentro del proyecto.
            LOCAL_DATA_FILE.write_text(text, encoding="utf-8")
            return {"ok": True, "path": str(USER_DATA_FILE), "backup_path": str(LOCAL_DATA_FILE), "saved_at": payload["saved_at"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "path": str(USER_DATA_FILE), "backup_path": str(LOCAL_DATA_FILE)}

    def get_save_path(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {"ok": True, "path": str(USER_DATA_FILE), "backup_path": str(LOCAL_DATA_FILE)}

    def _read_existing_payload_for_merge(self) -> Dict[str, Any]:
        for path in (USER_DATA_FILE, LOCAL_DATA_FILE):
            try:
                if path.exists():
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        return data
            except Exception:
                continue
        return {}

    def _merge_fifa_team_stats(self, incoming: Dict[str, Any], existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Evita que una actualización parcial borre equipos ya cargados.

        FIFA puede devolver temporalmente menos equipos o fallar en la resolución de
        un slug/IdTeam. En ese caso se conserva el último dato bueno por código.
        """
        if not isinstance(incoming, dict):
            return existing if isinstance(existing, dict) else incoming
        if not isinstance(existing, dict):
            return incoming
        in_rows = incoming.get("teams") if isinstance(incoming.get("teams"), list) else []
        old_rows = existing.get("teams") if isinstance(existing.get("teams"), list) else []
        if not old_rows:
            return incoming

        def row_code(row: Dict[str, Any]) -> str:
            c = str((row or {}).get("code") or "").upper().strip()
            if c:
                return c
            team = str((row or {}).get("team") or "")
            return str(TEAM_CODES.get(team, "")).upper().strip()

        in_by_code = {row_code(r): dict(r) for r in in_rows if isinstance(r, dict) and row_code(r)}
        old_by_code = {row_code(r): dict(r) for r in old_rows if isinstance(r, dict) and row_code(r)}
        preserved = []
        completed = []
        for code, old in old_by_code.items():
            cur = in_by_code.get(code)
            if not cur:
                in_by_code[code] = old
                preserved.append(code)
                continue
            # Si la fila nueva viene sin metadatos clave o con todo en cero, conserva los metadatos previos.
            for key in ("idTeam", "slug", "pageUrl", "nameEs", "source"):
                if old.get(key) and not cur.get(key):
                    cur[key] = old.get(key)
                    completed.append(code)
            # Si el refresh trae una fila sin partidos ni stats pero el anterior sí tenía datos, conserva la fila anterior.
            new_score = sum(float(cur.get(k) or 0) for k in ("matches", "goals", "assists", "yellow", "red", "shots", "xg"))
            old_score = sum(float(old.get(k) or 0) for k in ("matches", "goals", "assists", "yellow", "red", "shots", "xg"))
            if old_score > 0 and new_score == 0:
                in_by_code[code] = old
                preserved.append(code)
            else:
                in_by_code[code] = cur

        ordered = []
        for team, code_raw in TEAM_CODES.items():
            code = str(code_raw).upper()
            if code in in_by_code:
                row = dict(in_by_code[code])
                row.setdefault("team", team)
                row.setdefault("code", code)
                ordered.append(row)
        known = {str(c).upper() for c in TEAM_CODES.values()}
        for code, row in in_by_code.items():
            if code not in known:
                ordered.append(row)
        incoming = dict(incoming)
        incoming["teams"] = ordered
        catalog = {}
        if isinstance(existing.get("catalog"), dict):
            catalog.update(existing.get("catalog") or {})
        if isinstance(incoming.get("catalog"), dict):
            catalog.update(incoming.get("catalog") or {})
        incoming["catalog"] = catalog
        notes = list(incoming.get("notes") or []) if isinstance(incoming.get("notes"), list) else []
        if preserved:
            notes.insert(0, "v106: se conservaron datos FIFA previos para no reducir la información por respuesta parcial: " + ", ".join(sorted(set(preserved))[:20]))
        if completed:
            notes.append("v106: se completaron metadatos FIFA desde caché para: " + ", ".join(sorted(set(completed))[:20]))
        incoming["notes"] = list(dict.fromkeys([str(x) for x in notes if x]))[:18]
        incoming["ok"] = bool(incoming.get("teams"))
        incoming["preservedTeamCodes"] = sorted(set(preserved))
        return incoming

    def _merge_fifa_player_stats_payload(self, incoming: Dict[str, Any], existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Evita que un guardado/refresh parcial reduzca el plantel cargado."""
        if not isinstance(incoming, dict):
            return existing if isinstance(existing, dict) else incoming
        if not isinstance(existing, dict):
            return incoming
        in_players = incoming.get("players") if isinstance(incoming.get("players"), list) else []
        old_players = existing.get("players") if isinstance(existing.get("players"), list) else []
        if not old_players or len(in_players) >= len(old_players):
            return incoming

        def by_code(players):
            out: Dict[str, List[Dict[str, Any]]] = {}
            for p in players:
                if isinstance(p, dict):
                    c = str(p.get("code") or "").upper().strip()
                    if c:
                        out.setdefault(c, []).append(p)
            return out

        nb, ob = by_code(in_players), by_code(old_players)
        old_aggs = existing.get("teamAggregates") if isinstance(existing.get("teamAggregates"), dict) else {}
        new_aggs = incoming.get("teamAggregates") if isinstance(incoming.get("teamAggregates"), dict) else {}
        merged = []
        aggs = {}
        preserved = []
        for _team, code_raw in TEAM_CODES.items():
            code = str(code_raw).upper()
            np = nb.get(code, [])
            op = ob.get(code, [])
            use_old = bool(op) and (not np or len(np) < min(len(op), FIFA_EXPECTED_PLAYERS_PER_TEAM))
            chosen = op if use_old else np
            if use_old:
                preserved.append(f"{code} ({len(op)} jugadores cacheados; nuevo {len(np)})")
            merged.extend(chosen)
            if use_old and code in old_aggs:
                aggs[code] = old_aggs[code]
            elif code in new_aggs:
                aggs[code] = new_aggs[code]
            elif code in old_aggs:
                aggs[code] = old_aggs[code]
        incoming = dict(incoming)
        incoming["players"] = merged or old_players
        incoming["teamAggregates"] = aggs or old_aggs
        notes = list(incoming.get("notes") or []) if isinstance(incoming.get("notes"), list) else []
        if preserved:
            notes.insert(0, "v106: se conservaron planteles previos para evitar reducción por respuesta parcial FIFA: " + "; ".join(preserved[:20]))
        incoming["notes"] = list(dict.fromkeys([str(x) for x in notes if x]))[:18]
        incoming["preservedFromCache"] = list(dict.fromkeys((incoming.get("preservedFromCache") or []) + preserved))[:60]
        try:
            incoming = self._finalize_player_freshness(incoming, raw_stats_count=int(incoming.get("rawStatsPlayers") or 0))
        except Exception:
            pass
        return incoming


    def analyze_full(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Análisis único optimizado.

        Esta versión ya no dispara varias consultas lentas en cadena. El análisis
        cruza únicamente los resultados guardados del fixture con las estadísticas
        oficiales FIFA por equipo. Las estadísticas FIFA se leen con caché local y,
        cuando hace falta actualizar, se descargan en paralelo.
        """
        try:
            payload = payload or {}
            with_internet = bool(payload.get("with_internet", True))
            matches = payload.get("matches", []) if isinstance(payload, dict) else []
            if not isinstance(matches, list) or not matches:
                matches = self._base_matches_py()

            base_payload = dict(payload)
            base_payload["matches"] = matches
            base_payload.setdefault("playerEvents", payload.get("playerEvents", {}) or {})
            base_payload.setdefault("teamDiscipline", payload.get("teamDiscipline", {}) or {})
            notes: List[str] = []
            sources: List[str] = []

            analysis_fifa_stats: Dict[str, Any] = {}

            # v69: el análisis tiene 2 modos claros.
            # - with_internet=True: vuelve a consultar internet de forma explícita.
            # - with_internet=False: usa únicamente JSON/caché local.
            if with_internet:
                # Resultados/eventos desde internet, solo cuando el usuario lo pide.
                try:
                    sync_result = self._merge_espn_scoreboard(matches)
                    sources.extend(sync_result.get("sources", []) or [])
                    notes.extend(sync_result.get("notes", []) or [])
                    incoming_events = sync_result.get("player_events", {}) or {}
                    current_events = base_payload.get("playerEvents", {}) or {}
                    if not isinstance(current_events, dict):
                        current_events = {}
                    for key in ("goals", "assists", "yellow", "red"):
                        merged = list(current_events.get(key, []) or [])
                        seen = {json.dumps(x, ensure_ascii=False, sort_keys=True) for x in merged if isinstance(x, dict)}
                        for item in incoming_events.get(key, []) or []:
                            sig = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, dict) else str(item)
                            if sig not in seen:
                                merged.append(item)
                                seen.add(sig)
                        current_events[key] = merged
                    base_payload["playerEvents"] = current_events
                except Exception as exc:
                    notes.append("No se pudo refrescar resultados/eventos desde internet: " + str(exc)[:160])

                # Equipos FIFA desde internet, forzando actualización.
                try:
                    fifa_stats = self._fetch_fifa_team_stats(force=True)
                    if isinstance(fifa_stats, dict) and fifa_stats.get("teams"):
                        fifa_stats = self._merge_fifa_team_stats(fifa_stats, base_payload.get("fifaTeamStats") or self._read_fifa_stats_cache(max_age_seconds=None))
                        base_payload["fifaTeamStats"] = fifa_stats
                        base_payload["teamDiscipline"] = self._team_discipline_from_fifa(fifa_stats)
                        sources.extend(fifa_stats.get("sources", []) or [])
                        notes.extend(fifa_stats.get("notes", []) or [])
                        notes.append("Equipos FIFA actualizado desde internet por solicitud del usuario.")
                    else:
                        notes.append("No se recibió Team Stats desde internet; se intentará usar caché local.")
                except Exception as exc:
                    notes.append("No se pudo refrescar Equipos FIFA desde internet: " + str(exc)[:160])

                # Jugadores FIFA desde internet, sin descargar fotos aquí para no lentejar el análisis.
                try:
                    catalog = {}
                    if isinstance(base_payload.get("fifaTeamStats"), dict):
                        catalog = base_payload.get("fifaTeamStats", {}).get("catalog") or {}
                    fifa_player_stats = self._fetch_fifa_player_stats(force=True, catalog=catalog, cache_images=False)
                    if isinstance(fifa_player_stats, dict) and fifa_player_stats.get("players"):
                        fifa_player_stats = self._merge_fifa_player_stats_payload(fifa_player_stats, base_payload.get("fifaPlayerStats") or self._read_fifa_player_stats_cache(max_age_seconds=None))
                        base_payload["fifaPlayerStats"] = fifa_player_stats
                        sources.extend(fifa_player_stats.get("sources", []) or [])
                        notes.extend(fifa_player_stats.get("notes", []) or [])
                        notes.append("Jugadores FIFA actualizado desde internet; fotos se descargan aparte con el botón Fotos faltantes.")
                    else:
                        notes.append("No se recibió Players/Squad desde internet; se intentará usar caché local.")
                except Exception as exc:
                    notes.append("No se pudo refrescar Jugadores FIFA desde internet: " + str(exc)[:160])
            else:
                notes.append("Análisis local: no se hicieron consultas a internet; se usa JSON/caché guardado.")

            fifa_stats = base_payload.get("fifaTeamStats", {}) or self._read_fifa_stats_cache(max_age_seconds=None)
            fifa_player_stats = base_payload.get("fifaPlayerStats", {}) or self._read_fifa_player_stats_cache(max_age_seconds=None)
            if isinstance(fifa_stats, dict) and fifa_stats.get("teams"):
                base_payload["fifaTeamStats"] = fifa_stats
                base_payload["teamDiscipline"] = self._team_discipline_from_fifa(fifa_stats)
                sources.extend(fifa_stats.get("sources", []) or [])
                notes.extend(fifa_stats.get("notes", []) or [])
                if isinstance(fifa_player_stats, dict) and fifa_player_stats.get("players"):
                    base_payload["fifaPlayerStats"] = fifa_player_stats
                    analysis_fifa_stats = self._apply_player_aggregates_to_team_stats(fifa_stats, fifa_player_stats)
                    sources.extend(fifa_player_stats.get("sources", []) or [])
                    notes.extend(fifa_player_stats.get("notes", []) or [])
                else:
                    analysis_fifa_stats = fifa_stats
                notes.append("Análisis consolidado con datos FIFA disponibles.")
            else:
                notes.append("Aún no hay FIFA Team Stats cargado. Usa Equipos FIFA o Actualizar internet en Análisis.")

            # Siempre calcular un único modelo mixto con resultados + FIFA.
            analysis_payload = dict(base_payload)
            if analysis_fifa_stats:
                analysis_payload["fifaTeamStats"] = analysis_fifa_stats
            mixed = self.analyze_internet(analysis_payload)
            if mixed.get("ok"):
                base_payload["externalAnalysis"] = mixed
                sources.extend(mixed.get("sources", []) or [])
            else:
                notes.append("No se pudo calcular análisis consolidado: " + str(mixed.get("error", "sin detalle")))

            offline_summary = self._offline_summary(base_payload.get("matches", []), base_payload.get("playerEvents", {}) or {})
            unified = {
                "ok": True,
                "mode": "internet" if with_internet else "offline",
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "offline": offline_summary,
                "external": mixed if mixed.get("ok") else None,
                "sources": list(dict.fromkeys([str(x) for x in sources if x]))[:18],
                "notes": list(dict.fromkeys([str(x) for x in notes if x]))[:12],
            }
            base_payload["unifiedAnalysis"] = unified
            base_payload["matches"] = base_payload.get("matches", matches)
            self.save_results(base_payload)
            return {
                "ok": True,
                "matches": base_payload.get("matches", matches),
                "playerEvents": base_payload.get("playerEvents", {}),
                "teamDiscipline": base_payload.get("teamDiscipline", {}),
                "fifaTeamStats": base_payload.get("fifaTeamStats", {}),
                "fifaPlayerStats": base_payload.get("fifaPlayerStats", {}),
                "externalAnalysis": base_payload.get("externalAnalysis"),
                "unifiedAnalysis": unified,
                "path": str(USER_DATA_FILE),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _offline_summary(self, matches: List[Dict[str, Any]], player_events: Dict[str, Any]) -> Dict[str, Any]:
        stats = self._team_stats(matches or [])
        played = sorted(
            [s for s in stats.values() if s.get("pj", 0) > 0],
            key=lambda s: (s.get("pts", 0), s.get("dg", 0), s.get("gf", 0)),
            reverse=True,
        )
        done = self._count_completed(matches or [])
        goals = 0
        biggest = None
        for m in matches or []:
            if not self._match_has_result(m):
                continue
            try:
                hg, ag = int(m.get("hg", 0)), int(m.get("ag", 0))
            except Exception:
                continue
            goals += hg + ag
            diff = abs(hg - ag)
            if biggest is None or diff > biggest.get("diff", -1):
                biggest = {"match": f"{m.get('h')} {hg}-{ag} {m.get('a')}", "diff": diff, "group": m.get("g")}
        event_counts = {}
        for key in ("goals", "assists", "yellow", "red"):
            event_counts[key] = len((player_events or {}).get(key, []) or [])
        return {
            "completed_matches": done,
            "total_goals": goals,
            "avg_goals": round(goals / done, 2) if done else 0,
            "leader": played[0] if played else None,
            "best_attack": max(played, key=lambda s: s.get("gf", 0), default=None),
            "best_defense": min(played, key=lambda s: s.get("gc", 999), default=None),
            "biggest_win": biggest,
            "event_counts": event_counts,
            "top_teams": played[:8],
        }


    def sync_from_internet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Actualiza solo resultados/eventos desde ESPN.

        Optimización v34: ya no carga estadísticas FIFA dentro de esta acción,
        porque eso duplicaba consultas y hacía lenta cualquier sincronización. Las
        estadísticas FIFA se actualizan únicamente desde el análisis o Equipos FIFA.
        """
        try:
            payload = payload or {}
            matches = payload.get("matches", []) if isinstance(payload, dict) else []
            if not isinstance(matches, list) or not matches:
                matches = self._base_matches_py()

            before = self._count_completed(matches)
            sources: List[str] = []
            notes: List[str] = []
            updated_matches = 0
            player_events = {"goals": [], "assists": [], "yellow": [], "red": []}

            try:
                result = self._merge_espn_scoreboard(matches)
                updated_matches += int(result.get("updated_matches", 0))
                sources.extend(result.get("sources", []))
                notes.extend(result.get("notes", []))
                for key in ("goals", "assists", "yellow", "red"):
                    player_events.setdefault(key, [])
                    player_events[key].extend(result.get("player_events", {}).get(key, []))
            except Exception as exc:
                notes.append(f"ESPN no devolvió datos procesables: {exc}")

            payload_out = dict(payload)
            payload_out["matches"] = matches
            payload_out["internetSync"] = {
                "ok": True,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "completed_before": before,
                "completed_after": self._count_completed(matches),
                "updated_matches": updated_matches,
                "player_events_found": sum(len(v) for v in player_events.values()),
                "sources": list(dict.fromkeys(sources))[:10],
                "notes": notes[:8] + ["Optimizado: FIFA Team Stats se carga por separado para evitar consultas duplicadas."],
            }
            payload_out["playerEvents"] = player_events
            self.save_results(payload_out)
            return {"ok": True, "matches": matches, "internetSync": payload_out["internetSync"], "playerEvents": player_events, "teamDiscipline": payload.get("teamDiscipline", {}), "fifaTeamStats": payload.get("fifaTeamStats", {})}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _base_matches_py(self) -> List[Dict[str, Any]]:
        raw = [
            ('A','Mexico','South Africa','11 Jun'),('A','Korea Republic','Czechia','11 Jun'),('A','Czechia','South Africa','18 Jun'),('A','Mexico','Korea Republic','18 Jun'),('A','Czechia','Mexico','24 Jun'),('A','South Africa','Korea Republic','24 Jun'),
            ('B','Canada','Bosnia and Herzegovina','12 Jun'),('B','Qatar','Switzerland','13 Jun'),('B','Switzerland','Bosnia and Herzegovina','18 Jun'),('B','Canada','Qatar','18 Jun'),('B','Switzerland','Canada','24 Jun'),('B','Bosnia and Herzegovina','Qatar','24 Jun'),
            ('C','Brazil','Morocco','13 Jun'),('C','Haiti','Scotland','13 Jun'),('C','Scotland','Morocco','19 Jun'),('C','Brazil','Haiti','19 Jun'),('C','Scotland','Brazil','24 Jun'),('C','Morocco','Haiti','24 Jun'),
            ('D','United States','Paraguay','12 Jun'),('D','Australia','Türkiye','14 Jun'),('D','United States','Australia','19 Jun'),('D','Türkiye','Paraguay','19 Jun'),('D','Türkiye','United States','25 Jun'),('D','Paraguay','Australia','25 Jun'),
            ('E','Germany','Curaçao','14 Jun'),('E','Ivory Coast','Ecuador','14 Jun'),('E','Germany','Ivory Coast','20 Jun'),('E','Ecuador','Curaçao','20 Jun'),('E','Ecuador','Germany','25 Jun'),('E','Curaçao','Ivory Coast','25 Jun'),
            ('F','Netherlands','Japan','14 Jun'),('F','Sweden','Tunisia','14 Jun'),('F','Netherlands','Sweden','20 Jun'),('F','Tunisia','Japan','21 Jun'),('F','Tunisia','Netherlands','25 Jun'),('F','Japan','Sweden','25 Jun'),
            ('G','Belgium','Egypt','15 Jun'),('G','Iran','New Zealand','15 Jun'),('G','Belgium','Iran','21 Jun'),('G','New Zealand','Egypt','21 Jun'),('G','New Zealand','Belgium','26 Jun'),('G','Egypt','Iran','26 Jun'),
            ('H','Spain','Cape Verde','15 Jun'),('H','Saudi Arabia','Uruguay','15 Jun'),('H','Spain','Saudi Arabia','21 Jun'),('H','Uruguay','Cape Verde','21 Jun'),('H','Uruguay','Spain','26 Jun'),('H','Cape Verde','Saudi Arabia','26 Jun'),
            ('I','France','Senegal','16 Jun'),('I','Iraq','Norway','16 Jun'),('I','France','Iraq','22 Jun'),('I','Norway','Senegal','22 Jun'),('I','Norway','France','26 Jun'),('I','Senegal','Iraq','26 Jun'),
            ('J','Argentina','Algeria','16 Jun'),('J','Austria','Jordan','17 Jun'),('J','Argentina','Austria','22 Jun'),('J','Jordan','Algeria','22 Jun'),('J','Jordan','Argentina','27 Jun'),('J','Algeria','Austria','27 Jun'),
            ('K','Portugal','DR Congo','17 Jun'),('K','Uzbekistan','Colombia','17 Jun'),('K','Portugal','Uzbekistan','23 Jun'),('K','Colombia','DR Congo','23 Jun'),('K','Colombia','Portugal','27 Jun'),('K','DR Congo','Uzbekistan','27 Jun'),
            ('L','England','Croatia','17 Jun'),('L','Ghana','Panama','17 Jun'),('L','England','Ghana','23 Jun'),('L','Panama','Croatia','23 Jun'),('L','Panama','England','27 Jun'),('L','Croatia','Ghana','27 Jun'),
        ]
        return [{"id": f"{g}-{idx+1}", "g": g, "h": h, "a": a, "d": d, "hg": None, "ag": None} for idx, (g, h, a, d) in enumerate(raw)]

    @staticmethod
    def _count_completed(matches: List[Dict[str, Any]]) -> int:
        total = 0
        for m in matches or []:
            if m.get("hg") is not None and m.get("ag") is not None:
                total += 1
        return total

    def _merge_espn_scoreboard(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        # ESPN pública suele exponer resultados del Mundial en este endpoint sin API key.
        urls = [
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates=20260611-20260627&limit=200",
            "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?limit=200",
        ]
        data = None
        used_url = ""
        for url in urls:
            try:
                data = json.loads(http_get(url, timeout=10))
                used_url = url
                if data.get("events"):
                    break
            except Exception:
                data = None
        if not data or not data.get("events"):
            return {"updated_matches": 0, "sources": [], "notes": ["No se encontraron eventos en ESPN scoreboard."], "player_events": {"goals": [], "assists": [], "yellow": [], "red": []}}

        by_code: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for m in matches:
            hc, ac = TEAM_CODES.get(str(m.get("h")), ""), TEAM_CODES.get(str(m.get("a")), "")
            if hc and ac:
                by_code[(hc, ac)] = m
                by_code[(ac, hc)] = m

        updated = 0
        player_events = {"goals": [], "assists": [], "yellow": [], "red": []}
        for ev in data.get("events", []):
            comps = ev.get("competitions") or []
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors") or []
            if len(competitors) < 2:
                continue
            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
            hcode = (home.get("team") or {}).get("abbreviation", "")
            acode = (away.get("team") or {}).get("abbreviation", "")
            m = by_code.get((hcode, acode))
            if not m:
                continue
            try:
                hs, as_ = int(home.get("score", 0)), int(away.get("score", 0))
            except Exception:
                continue
            status = ((ev.get("status") or {}).get("type") or {}).get("state", "")
            completed = status.lower() in ("post", "final") or ((ev.get("status") or {}).get("type") or {}).get("completed")
            if completed:
                # Respetar orientación del fixture local.
                if TEAM_CODES.get(str(m.get("h"))) == hcode:
                    m["hg"], m["ag"] = hs, as_
                else:
                    m["hg"], m["ag"] = as_, hs
                updated += 1
            events = m.get("events") if isinstance(m.get("events"), dict) else {}
            events["internetUpdatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
            events["internetSources"] = events.get("internetSources", []) + [{"title": ev.get("name", "ESPN match"), "link": ev.get("links", [{}])[0].get("href", used_url) if ev.get("links") else used_url, "source": "ESPN"}]
            # Buscar detalles del partido para goleadores y tarjetas.
            ev_id = ev.get("id")
            if ev_id:
                detail_events = self._fetch_espn_event_details(str(ev_id), m)
                for key in ("goals", "assists", "yellow", "red"):
                    player_events.setdefault(key, [])
                    player_events[key].extend(detail_events.get(key, []))
                if detail_events.get("notes"):
                    old_notes = str(events.get("notes", "") or "")
                    events["notes"] = (old_notes + "\n" if old_notes else "") + "\n".join(detail_events["notes"])
            m["events"] = events
        return {"updated_matches": updated, "sources": [used_url], "notes": ["Resultados actualizados desde ESPN cuando el partido ya figura como finalizado."], "player_events": player_events}

    def _fetch_espn_event_details(self, event_id: str, match: Dict[str, Any]) -> Dict[str, Any]:
        """Lee el resumen ESPN del partido y extrae goles, asistencias y tarjetas.

        En algunas respuestas ESPN los datos vienen en scoringPlays; en otras vienen
        como detalles/comentarios anidados. Por eso se hace una búsqueda recursiva
        conservadora en todo el JSON del partido.
        """
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary?event={urllib.parse.quote(event_id)}"
        out: Dict[str, Any] = {"goals": [], "assists": [], "yellow": [], "red": [], "notes": []}
        try:
            data = json.loads(http_get(url, timeout=8))
        except Exception as exc:
            out["notes"].append(f"No se pudo leer ESPN summary {event_id}: {exc}")
            return out

        def append(kind: str, player: str, team: str = "", minute: str = "", source: str = "ESPN summary") -> None:
            player = self._clean_text(player)
            team = self._normalize_team_from_text(team or "")
            if not player or len(player) < 3:
                return
            # Evitar falsos positivos típicos de textos narrativos.
            if player.lower() in {"goal", "gol", "yellow card", "red card", "assist", "penalty", "substitution"}:
                return
            sig = (kind, player.lower(), team.lower(), str(minute).lower(), f"{match.get('h')} vs {match.get('a')}")
            existing = {(k, str(x.get('player','')).lower(), str(x.get('team','')).lower(), str(x.get('minute','')).lower(), str(x.get('match',''))) for k, arr in out.items() if isinstance(arr, list) for x in arr if isinstance(x, dict)}
            if sig in existing:
                return
            out[kind].append({"player": player, "team": team, "minute": minute, "match": f"{match.get('h')} vs {match.get('a')}", "source": source})

        # 1) Goles directos de scoringPlays.
        for sp in data.get("scoringPlays", []) or []:
            player = self._extract_player_name(sp)
            team = self._event_team_from_obj(sp, match) or self._infer_team_from_text(str(sp), match)
            minute = sp.get("time", {}).get("displayValue") or sp.get("clock", {}).get("displayValue") or sp.get("minute", "") or ""
            append("goals", player, team, str(minute))
            # Algunos scoringPlays traen participantes con rol assist/assistProvider.
            for participant in sp.get("participants", []) or sp.get("athletes", []) or []:
                txt = json.dumps(participant, ensure_ascii=False).lower() if isinstance(participant, dict) else str(participant).lower()
                if "assist" in txt or "asistencia" in txt:
                    ap = self._extract_player_name(participant if isinstance(participant, dict) else {"text": str(participant)})
                    append("assists", ap, team, str(minute))

        # 2) Recorrido recursivo de detalles/comentarios.
        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                text_parts: List[str] = []
                for key in ("type", "text", "shortText", "displayName", "description", "headline", "summary"):
                    if obj.get(key):
                        text_parts.append(str(obj.get(key)))
                txt_raw = " ".join(text_parts)
                txt = txt_raw.lower()
                if any(word in txt for word in ["goal", "gol", "yellow", "amarilla", "red card", "tarjeta roja", " roja", "assist", "asistencia"]):
                    player = self._extract_player_name(obj)
                    team = self._event_team_from_obj(obj, match) or self._infer_team_from_text(txt_raw, match)
                    minute = str((obj.get("clock") or {}).get("displayValue") or (obj.get("time") or {}).get("displayValue") or obj.get("minute", "") or "")
                    # Intentar extraer jugadores desde el texto cuando el objeto no los trae estructurados.
                    if not player:
                        player = self._extract_player_from_event_text(txt_raw)
                    if "yellow" in txt or "amarilla" in txt:
                        append("yellow", player, team, minute)
                    elif "red card" in txt or "tarjeta roja" in txt or " roja" in txt:
                        append("red", player, team, minute)
                    elif "assist" in txt or "asistencia" in txt:
                        append("assists", player, team, minute)
                    elif "goal" in txt or "gol" in txt:
                        append("goals", player, team, minute)
                for value in obj.values():
                    if isinstance(value, (dict, list)):
                        walk(value)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item)

        walk(data)

        count = len(out["goals"]) + len(out["assists"]) + len(out["yellow"]) + len(out["red"])
        if count:
            out["notes"].append(
                f"ESPN summary: {len(out['goals'])} goles, {len(out['assists'])} asistencias, "
                f"{len(out['yellow'])} amarillas, {len(out['red'])} rojas detectadas."
            )
        else:
            out["notes"].append("ESPN summary no expuso asistencias/tarjetas parseables para este partido.")
        return out

    def _extract_player_name(self, obj: Dict[str, Any]) -> str:
        candidates: List[Any] = []
        if not isinstance(obj, dict):
            return ""
        for key in ("athletes", "participants", "players"):
            value = obj.get(key)
            if isinstance(value, list):
                candidates.extend(value)
        for c in candidates:
            if isinstance(c, dict):
                for key in ("displayName", "shortName", "name", "fullName"):
                    if c.get(key):
                        return str(c[key])
                athlete = c.get("athlete")
                if isinstance(athlete, dict):
                    for key in ("displayName", "shortName", "name", "fullName"):
                        if athlete.get(key):
                            return str(athlete[key])
        for key in ("athlete", "player"):
            v = obj.get(key)
            if isinstance(v, dict):
                for k in ("displayName", "shortName", "name", "fullName"):
                    if v.get(k):
                        return str(v[k])
            elif isinstance(v, str):
                return v
        for key in ("participant", "person"):
            v = obj.get(key)
            if isinstance(v, dict):
                for k in ("displayName", "shortName", "name", "fullName"):
                    if v.get(k):
                        return str(v[k])
        text = str(obj.get("text", "") or obj.get("shortText", "") or obj.get("description", "") or "")
        return self._extract_player_from_event_text(text)

    def _extract_player_from_event_text(self, text: str) -> str:
        text = self._clean_text(text or "")
        if not text:
            return ""
        # Patrones frecuentes: "Yellow Card John Smith", "Goal! ... John Smith ...", "Assist by John Smith".
        patterns = [
            r"(?:Yellow Card|Red Card|Tarjeta amarilla|Tarjeta roja)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,45})",
            r"(?:Assist by|Assisted by|Asistencia de)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,45})",
            r"(?:Goal!|Gol!|Goal|Gol)\s*(?:[^.]{0,90}\.)?\s*([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,45})",
            r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,45})\s+\((?:[^)]*)\)\s*(?:Goal|Yellow Card|Red Card|Assist|Gol|Amarilla|Roja)",
        ]
        for pattern in patterns:
            m = re.search(pattern, text, flags=re.I)
            if m:
                player = m.group(1).strip(" .-–—")
                if player.lower() not in {"goal", "gol", "yellow card", "red card", "assist"}:
                    return player
        # Último recurso, pero evitando palabras de evento.
        m = re.match(r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{3,40})", text)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in {"goal", "gol", "yellow", "red", "assist", "substitution"}:
                return cand
        return ""

    def _infer_team_from_text(self, text: str, match: Dict[str, Any]) -> str:
        low = self._clean_text(text or "").lower()
        for t in (str(match.get("h", "")), str(match.get("a", ""))):
            if t and t.lower() in low:
                return t
            code = TEAM_CODES.get(t, "")
            if code and code.lower() in low:
                return t
        return ""

    def _event_team_from_obj(self, obj: Dict[str, Any], match: Dict[str, Any]) -> str:
        team = obj.get("team")
        abbr = ""
        if isinstance(team, dict):
            abbr = str(team.get("abbreviation", "") or team.get("code", ""))
        for t in (match.get("h"), match.get("a")):
            if TEAM_CODES.get(str(t)) == abbr:
                return str(t)
        return ""

    def _news_tokens(self, text: str) -> set:
        text = self._clean_text(text or "").lower()
        text = re.split(r"\s[-|–—]\s", text)[0]
        text = re.sub(r"https?://\S+", " ", text)
        text = re.sub(r"[^a-záéíóúñ0-9 ]+", " ", text)
        stop = {"del", "de", "la", "el", "los", "las", "un", "una", "y", "en", "por", "para", "con", "world", "cup", "mundial", "2026", "fifa", "copa", "futbol", "fútbol", "soccer", "vs", "tras", "ante", "sobre", "desde"}
        return {t for t in text.split() if len(t) > 2 and t not in stop}

    def _news_key(self, item: Dict[str, Any]) -> str:
        title = self._clean_text(str(item.get("title", "") or ""))
        title = re.split(r"\s[-|–—]\s", title)[0]
        title = re.sub(r"[^A-Za-zÁÉÍÓÚáéíóúÑñ0-9 ]+", " ", title.lower())
        title = re.sub(r"\s+", " ", title).strip()
        return title[:140]

    def _dedupe_news_items(self, items: List[Dict[str, Any]], limit: int = 8) -> List[Dict[str, Any]]:
        """Quita noticias repetidas o casi iguales.

        Google News suele devolver la misma noticia replicada por varios medios o con
        títulos casi idénticos. Se conserva la primera fuente y se descartan duplicados
        por URL/título normalizado y por similitud de tokens.
        """
        out: List[Dict[str, Any]] = []
        seen_urls: set = set()
        seen_keys: set = set()
        token_sets: List[set] = []
        for item in items or []:
            title = self._clean_text(str(item.get("title", "") or ""))
            link = self._clean_text(str(item.get("link", "") or ""))
            if not title:
                continue
            url_key = re.sub(r"[?#].*$", "", link).lower()
            key = self._news_key({"title": title})
            toks = self._news_tokens(title)
            if url_key and url_key in seen_urls:
                continue
            if key and key in seen_keys:
                continue
            duplicate = False
            for old in token_sets:
                if not old or not toks:
                    continue
                inter = len(old & toks)
                union = len(old | toks) or 1
                if inter / union >= 0.72 or (inter >= 5 and inter / max(1, min(len(old), len(toks))) >= 0.86):
                    duplicate = True
                    break
            if duplicate:
                continue
            clean_item = dict(item)
            clean_item["title"] = title
            if link:
                clean_item["link"] = link
                seen_urls.add(url_key)
            if key:
                seen_keys.add(key)
            token_sets.append(toks)
            out.append(clean_item)
            if len(out) >= limit:
                break
        return out

    def _dedupe_headlines(self, headlines: List[str], limit: int = 5) -> List[str]:
        items = [{"title": h, "link": ""} for h in headlines or []]
        return [x["title"] for x in self._dedupe_news_items(items, limit=limit)]

    def search_match_events(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Busca en internet reportes/noticias del partido y agrega hallazgos a eventos.

        El objetivo es reemplazar la carga manual/CSV: el usuario presiona un botón y el
        aplicativo consulta internet. La extracción es conservadora: guarda fuentes,
        titulares y texto sugerido en notas para que el usuario valide antes de tomarlo
        como dato oficial.
        """
        try:
            payload = payload or {}
            matches = payload.get("matches", []) if isinstance(payload, dict) else []
            group = str(payload.get("group", "") or "")
            match_id = str(payload.get("match_id", "") or "")
            scope = str(payload.get("scope", "group") or "group")

            if not isinstance(matches, list):
                return {"ok": False, "error": "No se recibió una lista válida de partidos."}

            targets: List[Dict[str, Any]] = []
            for m in matches:
                if not isinstance(m, dict):
                    continue
                if match_id and m.get("id") != match_id:
                    continue
                if not match_id:
                    if scope == "group" and m.get("g") != group:
                        continue
                    if scope == "completed" and not self._match_has_result(m):
                        continue
                # Para evitar búsquedas sin contexto, priorizamos partidos con marcador.
                if self._match_has_result(m) or match_id:
                    targets.append(m)

            if not targets:
                return {
                    "ok": False,
                    "error": "No hay partidos con resultado para buscar. Guarda un marcador o usa buscar por partido.",
                    "matches": matches,
                }

            updated = 0
            findings: List[Dict[str, Any]] = []
            for m in targets[:16]:
                result = self._search_events_for_match(m)
                items = result.get("items", [])
                finding = {
                    "match_id": m.get("id"),
                    "match": f"{m.get('h')} vs {m.get('a')}",
                    "items_found": len(items),
                    "query": result.get("query"),
                    "items": items[:5],
                }
                findings.append(finding)
                if not items:
                    continue

                events = m.get("events") or {}
                if not isinstance(events, dict):
                    events = {}
                old_notes = str(events.get("notes", "") or "").strip()
                new_lines = [
                    f"[Búsqueda internet {time.strftime('%Y-%m-%d %H:%M')}] {m.get('h')} vs {m.get('a')}",
                    "Revisar y validar fuentes antes de considerarlo oficial.",
                ]
                for idx, item in enumerate(items[:5], 1):
                    title = item.get("title", "").strip()
                    snippet = item.get("snippet", "").strip()
                    link = item.get("link", "").strip()
                    line = f"{idx}. {title}"
                    if snippet:
                        line += f" — {snippet}"
                    if link:
                        line += f" ({link})"
                    new_lines.append(line)
                events["notes"] = (old_notes + "\n\n" if old_notes else "") + "\n".join(new_lines)
                events["internetSources"] = items[:8]
                events["internetUpdatedAt"] = time.strftime("%Y-%m-%d %H:%M:%S")
                m["events"] = events
                updated += 1

            # Guardado inmediato en archivo para que no se pierda lo encontrado.
            try:
                saved_payload = dict(payload)
                saved_payload["matches"] = matches
                self.save_results(saved_payload)
            except Exception:
                pass

            return {
                "ok": True,
                "matches": matches,
                "updated_count": updated,
                "searched_count": len(targets[:16]),
                "findings": findings,
                "sources": [
                    "Google News RSS: búsqueda de reportes, goles, tarjetas y sanciones por partido",
                    "DuckDuckGo HTML: respaldo de búsqueda web cuando esté disponible",
                ],
                "note": "La búsqueda guarda hallazgos y fuentes en notas del partido. Para datos oficiales, validar contra FIFA/match centre/proveedor deportivo.",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    def _match_has_result(m: Dict[str, Any]) -> bool:
        return m.get("hg") is not None and m.get("ag") is not None

    def _search_events_for_match(self, m: Dict[str, Any]) -> Dict[str, Any]:
        home = str(m.get("h", ""))
        away = str(m.get("a", ""))
        score = ""
        if self._match_has_result(m):
            score = f" {m.get('hg')}-{m.get('ag')}"
        query = f'{home} {away}{score} World Cup 2026 scorers goals yellow cards red card match report'
        items: List[Dict[str, str]] = []

        # 1) Google News RSS: estable, sin API key, devuelve titulares recientes.
        try:
            q = urllib.parse.quote(query)
            url = f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=PE&ceid=PE:es-419"
            xml_text = http_get(url, timeout=8)
            root = ET.fromstring(xml_text)
            for it in root.findall(".//item")[:8]:
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                if title:
                    items.append({"title": self._clean_text(title), "snippet": "", "link": link, "source": "Google News"})
        except Exception:
            pass

        # 2) DuckDuckGo HTML como respaldo. Puede fallar si el proveedor bloquea scraping.
        if len(items) < 3:
            try:
                ddg_url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(query)
                html_text = http_get(ddg_url, timeout=8)
                results = self._parse_duckduckgo(html_text)
                for item in results:
                    key = item["title"].lower()
                    if all(key != x.get("title", "").lower() for x in items):
                        items.append(item)
                    if len(items) >= 8:
                        break
            except Exception:
                pass

        items = self._dedupe_news_items(items, limit=8)
        return {"query": query, "items": items[:8]}

    def _parse_duckduckgo(self, html_text: str) -> List[Dict[str, str]]:
        rows: List[Dict[str, str]] = []
        blocks = re.findall(r'<div class="result results_links.*?</div>\s*</div>', html_text, flags=re.S)
        if not blocks:
            blocks = re.findall(r'<a[^>]+class="result__a".*?</a>.*?(?:<a[^>]+class="result__snippet".*?</a>)?', html_text, flags=re.S)
        for block in blocks[:8]:
            title_match = re.search(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
            if not title_match:
                continue
            link = html_parser.unescape(title_match.group(1))
            title = self._clean_text(title_match.group(2))
            if "uddg=" in link:
                try:
                    parsed = urllib.parse.urlparse(link)
                    qs = urllib.parse.parse_qs(parsed.query)
                    link = qs.get("uddg", [link])[0]
                except Exception:
                    pass
            snippet = ""
            sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, flags=re.S)
            if sn:
                snippet = self._clean_text(sn.group(1))
            if title:
                rows.append({"title": title, "snippet": snippet, "link": link, "source": "DuckDuckGo"})
        return rows

    @staticmethod
    def _clean_text(value: str) -> str:
        value = re.sub(r"<[^>]+>", " ", value or "")
        value = html_parser.unescape(value)
        value = re.sub(r"\s+", " ", value).strip()
        return value


    def load_player_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Carga estadísticas de jugadores desde internet y las persiste.

        La tarjeta de Google Sports que el usuario abre en el navegador es dinámica y no
        ofrece un endpoint estable para scraping. Por eso se usan fuentes web públicas
        accesibles por HTTP y se combina con los eventos de partidos detectados por ESPN.
        """
        try:
            payload = payload or {}
            # Primero actualizamos resultados/eventos de partido; esto aporta goleadores y tarjetas cuando ESPN summary los expone.
            sync = self.sync_from_internet(payload)
            base_payload = dict(payload)
            if sync.get("ok"):
                base_payload["matches"] = sync.get("matches", payload.get("matches", []))
                current_events = sync.get("playerEvents", {}) or {}
            else:
                current_events = payload.get("playerEvents", {}) or {}

            player_events = {
                "goals": list(current_events.get("goals", []) or []),
                "assists": list(current_events.get("assists", []) or []),
                "yellow": list(current_events.get("yellow", []) or []),
                "red": list(current_events.get("red", []) or []),
            }
            fetched = self._fetch_player_stats_public()
            for key in ("goals", "assists", "yellow", "red"):
                player_events[key].extend(fetched.get(key, []))

            # Deduplicar suavemente por jugador/equipo/fuente/tipo.
            for key in player_events:
                seen = set()
                deduped = []
                for item in player_events[key]:
                    sig = (str(item.get("player", "")).lower(), str(item.get("team", "")).lower(), str(item.get("source", "")).lower(), str(item.get("count", "")), key)
                    if sig in seen:
                        continue
                    seen.add(sig)
                    deduped.append(item)
                player_events[key] = deduped

            base_payload["playerEvents"] = player_events
            base_payload["internetSync"] = {
                "ok": True,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "updated_matches": (sync.get("internetSync", {}) or {}).get("updated_matches", 0) if sync.get("ok") else 0,
                "player_events_found": sum(len(v) for v in player_events.values()),
                "sources": list(dict.fromkeys((sync.get("internetSync", {}) or {}).get("sources", []) + fetched.get("sources", [])))[:12],
                "notes": [
                    "Estadísticas de jugadores consultadas desde internet.",
                    "Google Sports es una tarjeta dinámica; se usan fuentes HTTP accesibles y eventos ESPN como respaldo.",
                ] + fetched.get("notes", [])[:6],
            }
            self.save_results(base_payload)
            return {"ok": True, "matches": base_payload.get("matches", []), "playerEvents": player_events, "internetSync": base_payload["internetSync"]}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _fetch_player_stats_public(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"goals": [], "assists": [], "yellow": [], "red": [], "sources": [], "notes": []}
        # Fuentes públicas accesibles por HTTP. Google Sports no ofrece endpoint estable;
        # por eso se intenta la página de Google como apoyo, pero se priorizan fuentes que sí devuelven HTML/JSON.
        urls = [
            AS_PLAYER_STAT_URLS["goals"],
            AS_PLAYER_STAT_URLS["assists"],
            AS_PLAYER_STAT_URLS["yellow"],
            AS_PLAYER_STAT_URLS["red"],
            "https://www.espn.com/soccer/stats/_/league/fifa.world",
            "https://www.espn.com/soccer/stats/_/league/FIFA.WORLD/view/discipline",
            "https://www.espn.co.uk/football/stats/_/league/FIFA.WORLD/view/discipline",
            "https://www.365scores.com/football/league/fifa-world-cup-5930/stats",
            "https://www.google.com/search?q=estad%C3%ADsticas+de+copa+mundial+de+f%C3%BAtbol+goles+asistencias+tarjetas+amarillas+rojas",
        ]
        for url in urls:
            try:
                txt = http_get(url, timeout=12)
                parsed = self._parse_player_stats_text(txt, url)
                added = 0
                for k in ("goals", "assists", "yellow", "red"):
                    vals = parsed.get(k, [])
                    out[k].extend(vals)
                    added += len(vals)
                if added:
                    out["sources"].append(url)
                elif "No Data Available" in txt or "No hay datos" in txt:
                    out["notes"].append(f"{url}: la fuente respondió sin datos disponibles todavía.")
            except Exception as exc:
                out["notes"].append(f"No se pudo leer {url}: {exc}")
        # Deduplicar por jugador/equipo/tipo.
        for k in ("goals", "assists", "yellow", "red"):
            seen = set(); arr = []
            for item in out[k]:
                sig = (str(item.get("player", "")).lower(), str(item.get("team", "")).lower(), str(item.get("count", "1")), k)
                if sig in seen:
                    continue
                seen.add(sig); arr.append(item)
            out[k] = arr[:50]
        if not any(out[k] for k in ("goals", "assists", "yellow", "red")):
            out["notes"].append("No se encontraron tablas parseables de asistencias/tarjetas. La app no inventa datos: mostrará 0 hasta que una fuente pública los publique o ESPN los exponga por partido.")
        return out

    def _parse_as_player_rank(self, html: str, kind: str, source: str) -> List[Dict[str, Any]]:
        """Parsea rankings AS.com por jugador.

        Las páginas de AS pueden entregar filas renderizadas o datos dentro de scripts.
        Este parser busca patrones jugador + equipo + valor sin depender de una clase CSS.
        """
        decoded = html_parser.unescape(html or "")
        flat = re.sub(r"</(?:tr|li|article|div|p)>", " | ", decoded, flags=re.I)
        flat = re.sub(r"<script[\s\S]*?</script>", lambda m: " " + m.group(0) + " ", flat, flags=re.I)
        flat = re.sub(r"<style[\s\S]*?</style>", " ", flat, flags=re.I)
        flat = re.sub(r"<[^>]+>", " ", flat)
        flat = self._clean_text(flat)
        flat = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", flat)
        chunks = [c.strip() for c in re.split(r"\s*\|\s*", flat) if c.strip()]
        entries: Dict[Tuple[str, str], Dict[str, Any]] = {}
        alias_to_team: List[Tuple[str, str]] = []
        for alias, team in AS_TEAM_ALIASES.items():
            alias_to_team.append((alias, team))
        for team in TEAM_CODES:
            alias_to_team.append((team.lower(), team))
            alias_to_team.append((TEAM_CODES[team].lower(), team))
        alias_to_team = sorted(alias_to_team, key=lambda x: len(x[0]), reverse=True)

        def clean_player(v: str) -> str:
            v = self._clean_text(v)
            v = re.sub(r"^\d{1,3}\s+", "", v).strip(" -·•")
            v = re.sub(r"\b(?:ranking|jugadores|goles|asistencias|tarjetas|amarillas|rojas|mundial|fifa|world|cup)\b", " ", v, flags=re.I)
            v = self._clean_text(v).strip(" -·•")
            parts = v.split()
            if len(parts) > 5:
                v = " ".join(parts[-4:])
            return v

        def put(player: str, team: str, value: int) -> None:
            player = clean_player(player)
            team = self._normalize_team_from_text(team)
            if not player or len(player) < 3 or len(player) > 55:
                return
            if player.lower() in {"goles", "asistencias", "tarjetas", "amarillas", "rojas", "jugador", "equipo"}:
                return
            key = (player.lower(), TEAM_CODES.get(team, team[:3].upper()))
            current = entries.get(key)
            if current is None or value > int(current.get("count", 0)):
                entries[key] = {"player": player, "team": team, "count": int(value), "match": "AS.com ranking World Cup 2026", "source": source}

        for chunk in chunks:
            nums = [int(n) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", chunk)]
            if not nums:
                continue
            value = nums[-1]
            if value < 0 or value > 30:
                continue
            low = chunk.lower()
            for alias, team in alias_to_team:
                m = re.search(r"\b" + re.escape(alias) + r"\b", low, flags=re.I)
                if not m:
                    continue
                before = chunk[:m.start()].strip()
                put(before, team, value)
                break

        team_forms = sorted(set([a for a, _ in alias_to_team]), key=len, reverse=True)
        team_re = "|".join(re.escape(x) for x in team_forms if len(x) >= 3)
        if team_re:
            pattern = re.compile(r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,65}?)\s+(" + team_re + r")\s+(?:[A-Za-zÁÉÍÓÚáéíóúÑñ.]{2,8}\s+)?(\d{1,2})(?!\d)", re.I)
            for m in pattern.finditer(flat):
                team = self._canonical_team_from_as(m.group(2), "")
                put(m.group(1), team, int(m.group(3)))

        out = list(entries.values())
        out.sort(key=lambda x: (-int(x.get("count", 0)), str(x.get("player", ""))))
        return out[:50]

    def _parse_player_stats_text(self, text: str, source: str) -> Dict[str, List[Dict[str, Any]]]:
        clean = self._clean_text(text)
        result: Dict[str, List[Dict[str, Any]]] = {"goals": [], "assists": [], "yellow": [], "red": []}
        if "as.com/resultados/futbol/mundial/2026/ranking/jugadores" in (source or ""):
            kind = ""
            for k, url in AS_PLAYER_STAT_URLS.items():
                if url in source:
                    kind = k
                    break
            if not kind:
                if "asistencias" in source:
                    kind = "assists"
                elif "tarjetas-amarillas" in source:
                    kind = "yellow"
                elif "tarjetas-rojas" in source:
                    kind = "red"
                elif "goles" in source:
                    kind = "goals"
            if kind:
                result[kind].extend(self._parse_as_player_rank(text, kind, source))
                return result

        def add(kind: str, player: str, team: str = "", count: int = 1) -> None:
            player = self._clean_text(player)
            team = self._normalize_team_from_text(team)
            if not player or len(player) < 3:
                return
            if player.lower() in {"player", "team", "ranking", "rank", "goals", "assists", "yellow cards", "red cards"}:
                return
            try:
                count_i = max(1, int(count or 1))
            except Exception:
                count_i = 1
            result[kind].append({"player": player, "team": team, "count": count_i, "match": "World Cup 2026 stats", "source": source})

        # 1) Patrones explícitos en inglés/español.
        explicit_patterns = [
            ("goals", r"(?:Top Scorers|Most Goals|Goleadores|Goles)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,60})\s*\(([^)]+)\)\s*[-:]?\s*(\d+)"),
            ("assists", r"(?:Top Assists|Most Assists|Asistencias|Líderes en asistencias)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,60})\s*\(([^)]+)\)\s*[-:]?\s*(\d+)"),
            ("yellow", r"(?:Yellow Cards|Tarjetas amarillas|Amarillas)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,60})\s*\(([^)]+)\)\s*[-:]?\s*(\d+)"),
            ("red", r"(?:Red Cards|Tarjetas rojas|Rojas)\s+([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,60})\s*\(([^)]+)\)\s*[-:]?\s*(\d+)"),
        ]
        for kind, pattern in explicit_patterns:
            for m in re.finditer(pattern, clean, flags=re.I):
                add(kind, m.group(1), m.group(2), int(m.group(3)))

        # 2) Detectar bloques/sections de tablas: Goals, Assists, Yellow Cards, Red Cards.
        section_defs = [
            ("goals", ["Top Scorers", "Scoring", "Goals", "Goles", "Goleadores"]),
            ("assists", ["Top Assists", "Assists", "Asistencias"]),
            ("yellow", ["Yellow Cards", "YC", "Tarjetas amarillas", "Amarillas"]),
            ("red", ["Red Cards", "RC", "Tarjetas rojas", "Rojas"]),
        ]
        all_labels = [lbl for _, labels in section_defs for lbl in labels]
        teams = list(TEAM_CODES.keys()) + ["United States", "South Korea", "Congo DR", "Côte d'Ivoire", "Ivory Coast"]
        teams_re = "|".join(re.escape(t) for t in sorted(set(teams), key=len, reverse=True))
        # Nombre + equipo + conteo. Sirve para ESPN/365Scores cuando el texto queda lineal.
        row_re = re.compile(r"([A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ' .-]{2,55})\s+(" + teams_re + r")\s+(\d{1,2})(?:\s|$)", re.I)
        for kind, labels in section_defs:
            for label in labels:
                for sm in re.finditer(re.escape(label), clean, flags=re.I):
                    start = sm.end()
                    # Fin aproximado en la próxima sección conocida.
                    next_positions = []
                    for lbl in all_labels:
                        if lbl.lower() == label.lower():
                            continue
                        nm = re.search(re.escape(lbl), clean[start:start+7000], flags=re.I)
                        if nm:
                            next_positions.append(start + nm.start())
                    end = min(next_positions) if next_positions else min(len(clean), start + 5000)
                    chunk = clean[start:end]
                    if "No Data Available" in chunk[:180] or "No hay datos" in chunk[:180]:
                        continue
                    for m in row_re.finditer(chunk):
                        player, team, count = m.group(1), m.group(2), int(m.group(3))
                        add(kind, player, team, count)
                        if len(result[kind]) >= 20:
                            break
                    if result[kind]:
                        break
                if result[kind]:
                    break

        # 3) JSON incrustado: buscar objetos con nombres de columnas comunes.
        # Esto ayuda con páginas React/Next que dejan data en script.
        if not any(result[k] for k in ("goals", "assists", "yellow", "red")):
            decoded = html_parser.unescape(text)
            for kind, labels in {
                "goals": ["goals", "G", "goles"],
                "assists": ["assists", "A", "asistencias"],
                "yellow": ["yellowCards", "yellow_cards", "YC", "amarillas"],
                "red": ["redCards", "red_cards", "RC", "rojas"],
            }.items():
                # patrón jugador/equipo/valor en JSON simplificado.
                for m in re.finditer(r'"(?:displayName|name|playerName)"\s*:\s*"([^"{}]{3,80})"[^{}]{0,800}?"(?:team|teamName|country)"\s*:\s*"([^"{}]{2,80})"[^{}]{0,800}?"(?:' + "|".join(map(re.escape, labels)) + r')"\s*:\s*(\d{1,2})', decoded, flags=re.I):
                    add(kind, m.group(1), m.group(2), int(m.group(3)))
                    if len(result[kind]) >= 30:
                        break
        return result

    def _normalize_team_from_text(self, value: str) -> str:
        low = self._clean_text(value).lower()
        aliases = {
            **AS_TEAM_ALIASES,
            "usa": "United States", "united states": "United States", "usmnt": "United States",
            "turkiye": "Türkiye", "turkey": "Türkiye", "cote d'ivoire": "Ivory Coast", "côte d’ivoire": "Ivory Coast",
            "south korea": "Korea Republic", "korea republic": "Korea Republic", "czech republic": "Czechia",
            "dr congo": "DR Congo", "d r congo": "DR Congo", "congo dr": "DR Congo", "congo democratic republic": "DR Congo", "côte d’ivoire": "Ivory Coast", "cote d’ivoire": "Ivory Coast",
        }
        if low in aliases:
            return aliases[low]
        for team in TEAM_CODES:
            if low == team.lower():
                return team
        return value

    def analyze_internet(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Combina resultados cargados + ranking fallback/manual + señales públicas de noticias.

        No pretende reemplazar un proveedor deportivo profesional. Es un análisis indicativo.
        """
        try:
            matches = payload.get("matches", []) if isinstance(payload, dict) else []
            player_events = payload.get("playerEvents", {}) if isinstance(payload, dict) else {}
            team_discipline = payload.get("teamDiscipline", {}) if isinstance(payload, dict) else {}
            fifa_team_stats = payload.get("fifaTeamStats", {}) if isinstance(payload, dict) else {}
            if not isinstance(team_discipline, dict) or not (team_discipline.get("yellow") or team_discipline.get("red")):
                if isinstance(fifa_team_stats, dict) and fifa_team_stats.get("teams"):
                    team_discipline = self._team_discipline_from_fifa(fifa_team_stats)
            if not isinstance(team_discipline, dict) or not (team_discipline.get("yellow") or team_discipline.get("red")):
                team_discipline = {"yellow": [], "red": [], "sources": [], "notes": ["Disciplina vacía: no se hicieron consultas extra; carga Equipos FIFA para completar tarjetas."], "ok": True}
            ranking = self._load_ranking()
            stats = self._team_stats(matches)
            self._apply_player_events_to_stats(stats, player_events or {})
            self._apply_team_discipline_to_stats(stats, team_discipline or {})
            contenders = self._rank_contenders(stats, ranking)
            top_candidates = contenders[:8]
            # v34: se desactiva la búsqueda de noticias por equipo para acelerar el análisis.
            # El modelo se enfoca en resultados cargados + estadísticas FIFA ya consultadas.
            for item in contenders:
                item["injury_news_risk"] = 0
                item["injury_headlines"] = []
                # Ajuste final: rendimiento 65%, ranking 25%, disciplina/FIFA 10%.
                item["mixed_score"] = round(
                    item["result_score"] * 0.65
                    + item["ranking_score"] * 0.25
                    + item["discipline_score"] * 0.10,
                    2,
                )
            contenders.sort(key=lambda x: x["mixed_score"], reverse=True)
            champion = contenders[0] if contenders else None
            return {
                "ok": True,
                "champion": champion,
                "ranking": contenders[:12],
                "sources": [
                    "FIFA/Coca-Cola World Ranking: https://www.fifa.com/en/world-rankings",
                    "FIFA Team Stats API: " + FIFA_TEAM_STATS_TEMPLATE.format(season=FIFA_STATS_SEASON_ID, team_id="<IdTeam>"),
                    "Resultados cargados localmente en el fixture",
                    "Caché local FIFA Team Stats para acelerar consultas",
                ],
                "teamDiscipline": team_discipline,
                "note": "Análisis indicativo optimizado. Combina resultados cargados y estadísticas oficiales FIFA por equipo; no consulta noticias para acelerar la carga.",
                "saved_file": str(DATA_FILE),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


    def _canonical_team_from_as(self, text_value: str, code_value: str = "") -> str:
        raw = self._clean_text(text_value or "").strip().lower().replace("/", " ")
        code = self._clean_text(code_value or "").strip().lower().replace("/", " ")
        for key in (raw, code):
            key = re.sub(r"\s+", " ", key).strip(" .")
            if key in AS_TEAM_ALIASES:
                return AS_TEAM_ALIASES[key]
        return self._normalize_team_from_text(text_value or code_value or "")

    def _parse_as_team_rank(self, html: str, kind: str, source: str) -> List[Dict[str, Any]]:
        """Parsea rankings AS.com por equipos: tarjetas amarillas/rojas.

        La versión anterior fallaba por dos motivos: llamaba a fetch_url sin definirlo
        y dependía de un único patrón de fila. Esta versión acepta HTML renderizado,
        datos incrustados en scripts y filas con o sin código de equipo.
        """
        decoded = html_parser.unescape(html or "")
        row_text = re.sub(r"</(?:tr|li|article|div|p)>", " | ", decoded, flags=re.I)
        row_text = re.sub(r"<style[\s\S]*?</style>", " ", row_text, flags=re.I)
        row_text = re.sub(r"<[^>]+>", " ", row_text)
        row_text = self._clean_text(row_text)
        row_text = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", row_text)
        chunks = [c.strip() for c in re.split(r"\s*\|\s*", row_text) if c.strip()]
        entries: Dict[str, Dict[str, Any]] = {}

        alias_to_team: List[Tuple[str, str]] = []
        for alias, team in AS_TEAM_ALIASES.items():
            alias_to_team.append((alias, team))
        for team, code in TEAM_CODES.items():
            alias_to_team.append((team.lower(), team))
            alias_to_team.append((code.lower(), team))
        alias_to_team = sorted(alias_to_team, key=lambda x: len(x[0]), reverse=True)

        def put(team: str, value: int) -> None:
            team = self._normalize_team_from_text(team)
            if not team:
                return
            code = TEAM_CODES.get(team, team[:3].upper())
            current = entries.get(code)
            if current is None or value > int(current.get("value", 0)):
                entries[code] = {"team": team, "code": code, "value": int(value), "source": source, "kind": kind}

        for chunk in chunks:
            nums = [int(n) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", chunk)]
            if not nums:
                continue
            value = nums[-1]
            if value < 0 or value > 40:
                continue
            low = chunk.lower()
            for alias, team in alias_to_team:
                if re.search(r"\b" + re.escape(alias) + r"\b", low, flags=re.I):
                    put(team, value)
                    break

        flat = row_text
        for alias, team in alias_to_team:
            if len(alias) < 3:
                continue
            for m in re.finditer(r"\b" + re.escape(alias) + r"\b", flat.lower(), flags=re.I):
                window = flat[m.start(): m.start() + 150]
                nums = [int(n) for n in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", window)]
                if nums:
                    value = nums[-1]
                    if 0 <= value <= 40:
                        put(team, value)

        json_like = decoded
        for alias, team in alias_to_team:
            if len(alias) < 3:
                continue
            pat = re.compile(re.escape(alias) + r"[^{}]{0,240}?(?:tarjetas|cards|value|total|yellow|red)[^{}]{0,80}?(\d{1,2})", re.I)
            for m in pat.finditer(json_like):
                value = int(m.group(1))
                if 0 <= value <= 40:
                    put(team, value)

        out = list(entries.values())
        out.sort(key=lambda x: (-int(x.get("value", 0)), str(x.get("team", ""))))
        return out


    def _default_fifa_catalog(self) -> Dict[str, Dict[str, str]]:
        catalog: Dict[str, Dict[str, str]] = {}
        for code, value in FIFA_TEAM_IDS_DEFAULT.items():
            if isinstance(value, dict):
                catalog[str(code).upper()] = {k: str(v) for k, v in value.items() if v is not None}
            else:
                catalog[str(code).upper()] = {"idTeam": str(value)}
        return catalog

    def _read_fifa_catalog_file(self, path: Path) -> Dict[str, Dict[str, str]]:
        out: Dict[str, Dict[str, str]] = {}
        try:
            if not path.exists():
                return out
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return out
            for code, value in raw.items():
                c = str(code).strip().upper()
                if not c:
                    continue
                if isinstance(value, dict):
                    item = {k: str(v).strip() for k, v in value.items() if v is not None and str(v).strip()}
                    if item.get("idTeam") or item.get("teamId"):
                        item["idTeam"] = item.get("idTeam") or item.get("teamId")
                        out[c] = item
                else:
                    v = str(value).strip()
                    if v:
                        out[c] = {"idTeam": v}
        except Exception:
            return out
        return out

    def _write_fifa_auto_catalog(self, catalog: Dict[str, Dict[str, str]]) -> None:
        try:
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            safe = {k: v for k, v in catalog.items() if isinstance(v, dict) and v.get("idTeam")}
            FIFA_TEAM_AUTO_CACHE.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        try:
            USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            safe = {k: v for k, v in catalog.items() if isinstance(v, dict) and v.get("idTeam")}
            (USER_DATA_DIR / "fifa_team_ids_auto.json").write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _slugify_team(self, value: str) -> str:
        import unicodedata
        txt = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
        txt = re.sub(r"[^A-Za-z0-9]+", "-", txt.lower()).strip("-")
        return txt

    def _fifa_slug_candidates(self, code: str, team: str) -> List[str]:
        code = (code or "").upper().strip()
        configured = FIFA_TEAM_SLUGS.get(code) or []
        # v106: probar todas las variantes configuradas.
        # Antes solo se probaba la primera variante y equipos como BIH, CIV, COD
        # podían quedar con "slug no resuelto" aunque existiera otro slug válido.
        candidates = list(configured)
        generated = self._slugify_team(team or self._team_from_code(code))
        if generated:
            candidates.append(generated)
        if code:
            candidates.append(code.lower())
        seen = set()
        out = []
        for x in candidates:
            x = str(x).strip().lower()
            if x and x not in seen:
                seen.add(x)
                out.append(x)
        return out

    def _extract_cxm_meta(self, data: Dict[str, Any], code: str, slug: str, url: str) -> Dict[str, str]:
        item: Dict[str, str] = {"code": code, "slug": slug, "pageUrl": url}
        team_id = str(data.get("teamId") or data.get("teamID") or "").strip()
        if team_id:
            item["idTeam"] = team_id
        season_id = str(data.get("seasonId") or "").strip()
        if season_id:
            item["seasonId"] = season_id
        # Nombre en español desde meta.title o titleBanner
        name_es = ""
        try:
            title = ((data.get("meta") or {}).get("title") or "").split("|")[0].strip()
            if title:
                name_es = title
        except Exception:
            pass
        if not name_es:
            for sec in data.get("sections", []) or []:
                if isinstance(sec, dict) and sec.get("entryType") == "titleBanner":
                    heading = ((sec.get("properties") or {}).get("heading") or "").strip()
                    if heading:
                        name_es = heading.strip()
                        break
        if name_es:
            item["nameEs"] = name_es
        try:
            image = (data.get("meta") or {}).get("image") or ""
            if image:
                if not str(image).startswith("http"):
                    image = "https://" + str(image).lstrip("/")
                item["imageUrl"] = image
        except Exception:
            pass
        return item

    def _discover_fifa_team_meta(self, code: str, team: str) -> Dict[str, str]:
        for slug in self._fifa_slug_candidates(code, team):
            url = FIFA_TEAM_PAGE_TEMPLATE.format(slug=urllib.parse.quote(slug))
            try:
                raw = fetch_url(url, timeout=10)
                data = json.loads(raw)
                item = self._extract_cxm_meta(data, code, slug, url)
                if item.get("idTeam"):
                    return item
            except Exception:
                continue
        return {}


    def _normalise_catalog_for_known_slugs(self, catalog: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """Corrige slugs conocidos sin disparar nuevas consultas.

        Especialmente Irán: FIFA responde por /teams/ir-iran/stats.
        Si el usuario ya tiene un caché antiguo, se respeta el idTeam pero se
        normaliza slug/pageUrl para no probar ni guardar variantes innecesarias.
        """
        if not isinstance(catalog, dict):
            return catalog
        if isinstance(catalog.get("IRN"), dict):
            item = dict(catalog.get("IRN") or {})
            item["slug"] = "ir-iran"
            item["pageUrl"] = FIFA_TEAM_PAGE_TEMPLATE.format(slug="ir-iran")
            catalog["IRN"] = item
        return catalog

    @staticmethod
    def _image_ext_from_type_or_url(content_type: str, url: str, data: bytes | None = None) -> str:
        ct = (content_type or "").lower().strip()
        raw = bytes(data[:96] or b"") if data else b""
        if raw.startswith(b"\xff\xd8\xff") or "jpeg" in ct or "jpg" in ct:
            return ".jpg"
        if raw.startswith(b"\x89PNG\r\n\x1a\n") or "png" in ct:
            return ".png"
        if (raw.startswith(b"RIFF") and b"WEBP" in raw[:24]) or "webp" in ct:
            return ".webp"
        if raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a") or "gif" in ct:
            return ".gif"
        if (len(raw) >= 12 and raw[4:8] == b"ftyp" and (b"avif" in raw or b"avis" in raw or b"mif1" in raw or b"msf1" in raw)) or "avif" in ct:
            return ".avif"
        try:
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower()
            if suffix in {".webp", ".png", ".jpg", ".jpeg", ".gif", ".avif"}:
                return ".jpg" if suffix == ".jpeg" else suffix
        except Exception:
            pass
        return ".jpg"

    @staticmethod
    def _normalise_fifa_player_picture_url(url: str) -> str:
        """Devuelve la URL exacta de FIFA DigitalHub sin generar variantes.

        La URL que trae el squad ya es descargable directamente, por ejemplo:
        https://digitalhub.fifa.com/transform/.../MUSIALA-Jamal_429642

        En v64 no se agrega .avif ni parámetros extra. La extensión local se
        decide después usando el Content-Type real devuelto por FIFA
        (normalmente image/avif).
        """
        raw = str(url or "").strip()
        if not raw:
            return ""
        try:
            parsed = urllib.parse.urlparse(raw)
            # quitar espacios accidentales y dejar intactos path/query oficiales
            if parsed.scheme and parsed.netloc:
                return urllib.parse.urlunparse(parsed)
        except Exception:
            pass
        return raw

    @staticmethod
    def _player_picture_filename_from_url(player_id: str, url: str, ext: str = "") -> str:
        """Devuelve el nombre local de la foto respetando el formato FIFA.

        Ejemplo esperado:
        ST-CLAIR-Dayne_441255.avif

        Si no se puede obtener un nombre confiable desde la URL, usa fallback
        p_<IdPlayer>.<ext>.
        """
        pid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(player_id or "")).strip("_")
        ext = (ext or "").lower()
        if ext == ".jpeg":
            ext = ".jpg"
        if ext not in {".jpg", ".png", ".webp", ".gif", ".avif"}:
            ext = ".jpg"
        try:
            parsed = urllib.parse.urlparse(str(url or ""))
            raw_name = urllib.parse.unquote(Path(parsed.path).name or "")
            if raw_name:
                name_path = Path(raw_name)
                stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", name_path.stem).strip("._-")
                suffix = name_path.suffix.lower() or ext or ".avif"
                if suffix == ".jpeg":
                    suffix = ".jpg"
                if suffix not in {".jpg", ".png", ".webp", ".gif", ".avif"}:
                    suffix = ext if ext in {".jpg", ".png", ".webp", ".gif", ".avif"} else ".avif"
                # Solo se acepta el nombre FIFA si termina con _IdPlayer.
                if pid and stem.endswith("_" + pid):
                    return f"{stem}{suffix}"
        except Exception:
            pass
        return f"p_{pid}{ext}" if pid else f"player{ext}"

    @staticmethod
    def _is_player_image_file(path: Path) -> bool:
        try:
            return (
                path.is_file()
                and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
                and path.stat().st_size > 100
            )
        except Exception:
            return False

    @staticmethod
    def _optimise_player_image_bytes(data: bytes, content_type: str, url: str) -> Tuple[bytes, str, str]:
        """Reduce peso cuando es seguro; AVIF se guarda tal cual.

        FIFA DigitalHub normalmente devuelve image/avif. En Windows/Python, Pillow
        puede no soportar AVIF; por eso v62 guarda AVIF directo, sin intentar
        convertirlo. Si la imagen es JPG/PNG/WEBP y Pillow existe, se optimiza.
        """
        ext = AppApi._image_ext_from_type_or_url(content_type, url, data)
        if ext == ".avif" or "avif" in (content_type or "").lower():
            return data, content_type or "image/avif", ".avif"
        try:
            from PIL import Image  # type: ignore

            im = Image.open(BytesIO(data))
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((PLAYER_IMAGE_MAX_SIZE, PLAYER_IMAGE_MAX_SIZE))
            out = BytesIO()
            im.save(out, format="JPEG", quality=PLAYER_IMAGE_QUALITY, optimize=True, progressive=True)
            optimised = out.getvalue()
            if len(optimised) > 100:
                return optimised, "image/jpeg", ".jpg"
        except Exception:
            pass
        return data, content_type, ext

    def _existing_player_picture(self, player_id: str) -> str:
        """Busca foto local por IdPlayer.

        Acepta el formato anterior p_<IdPlayer>.* y el formato FIFA real
        <APELLIDO-Nombre>_<IdPlayer>.avif, por ejemplo:
        ST-CLAIR-Dayne_441255.avif
        """
        pid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(player_id or "")).strip("_")
        if not pid:
            return ""
        patterns = [f"p_{pid}.*", f"*_{pid}.*"]
        seen: set[str] = set()
        for pattern in patterns:
            for path in PLAYER_IMAGES_DIR.glob(pattern):
                try:
                    key = str(path.resolve())
                    if key in seen:
                        continue
                    seen.add(key)
                    if self._is_player_image_file(path):
                        return path.relative_to(BASE_DIR).as_posix()
                except Exception:
                    continue
        return ""

    def _append_player_image_log(self, item: Dict[str, Any]) -> None:
        """Escribe un log JSONL por cada intento de descarga de foto."""
        try:
            LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
            row = dict(item or {})
            row.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
            with PLAYER_IMAGE_DOWNLOAD_LOG_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _write_player_image_download_summary(self, summary: Dict[str, Any]) -> None:
        try:
            self._write_json_safe(PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE, summary)
        except Exception:
            pass

    def _cache_player_picture(self, player_id: str, url: str) -> Dict[str, str]:
        """Descarga una foto FIFA DigitalHub y la guarda localmente.

        La imagen se descarga desde la URL exacta del squad. Si FIFA responde
        image/avif, se guarda tal cual, sin convertirla. Si falla, se omite
        y se deja trazabilidad en data/player_image_download_log.jsonl.
        """
        pid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(player_id or "")).strip("_")
        url_original = str(url or "").strip()
        url_final = self._normalise_fifa_player_picture_url(url_original)
        base_log = {
            "idPlayer": pid,
            "source_original": url_original[:500],
            "source_final": url_final[:500],
        }
        if not pid or not url_final.startswith("http"):
            res = {"player_id": pid, "local": "", "status": "empty", "error": "sin URL fuente"}
            self._append_player_image_log({**base_log, **res})
            return res
        existing = self._existing_player_picture(pid)
        if existing:
            res = {"player_id": pid, "local": existing, "status": "existing"}
            self._append_player_image_log({**base_log, **res})
            return res
        try:
            PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            data, content_type = http_get_image(url_final, timeout=25, referer="https://www.fifa.com/")
            # Aceptar AVIF/WEBP/JPG/PNG válidos por Content-Type aunque el magic
            # del contenedor no coincida con la validación rápida. Esto evita
            # rechazar fotos reales de FIFA DigitalHub.
            if len(data) < 100 or not (_looks_like_image_bytes(data) or str(content_type or '').lower().startswith('image/')):
                raise ValueError(f"imagen vacía o inválida; content-type={content_type or 'sin tipo'}; bytes={len(data)}")

            ext = self._image_ext_from_type_or_url(content_type, url_final, data)
            # AVIF de FIFA se guarda directo; no se pasa por Pillow.
            if ext == ".avif" or "avif" in (content_type or "").lower():
                final_data = data
                final_type = content_type or "image/avif"
                final_ext = ".avif"
            else:
                final_data, final_type, final_ext = self._optimise_player_image_bytes(data, content_type, url_final)

            target_name = self._player_picture_filename_from_url(pid, url_final, final_ext)
            target = PLAYER_IMAGES_DIR / target_name
            if not target.name.startswith("p_") and f"_{pid}" not in target.stem:
                target = PLAYER_IMAGES_DIR / f"p_{pid}{final_ext}"
            target.write_bytes(final_data)
            if not target.exists() or target.stat().st_size < 100:
                raise ValueError("archivo local no se escribió correctamente")
            res = {
                "player_id": pid,
                "local": target.relative_to(BASE_DIR).as_posix(),
                "status": "downloaded",
                "bytes": str(target.stat().st_size),
                "content_type": final_type,
                "source": url_final,
                "filename": target.name,
            }
            self._append_player_image_log({**base_log, **res})
            return res
        except Exception as exc:
            msg = f"{type(exc).__name__}: {str(exc)}".replace("\n", " ")[:300]
            res = {"player_id": pid, "local": "", "status": "failed", "error": msg, "source": url_final[:500], "source_original": url_original[:500]}
            self._append_player_image_log({**base_log, **res})
            return res

    def _build_player_image_status(self, data: Dict[str, Any], update_paths: bool = False) -> Dict[str, Any]:
        """Verifica fotos locales sin consultar FIFA ni internet.

        Lee fifaPlayerStats actual/caché y compara cada IdPlayer contra
        assets/players/p_<IdPlayer>.* o *_<IdPlayer>.*. Sirve para confirmar visualmente si la
        descarga funcionó y cuántos jugadores ya cargan desde disco local.
        """
        players = data.get("players") if isinstance(data, dict) else []
        if not isinstance(players, list):
            players = []
        sources = data.get("playerImageSources") if isinstance(data, dict) else {}
        if not isinstance(sources, dict):
            sources = {}
        local_files = []
        try:
            PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            local_files = [x for x in PLAYER_IMAGES_DIR.glob("*.*") if self._is_player_image_file(x)]
        except Exception:
            local_files = []

        local_players = 0
        shown_local = 0
        missing = 0
        missing_source = 0
        sample_missing: List[Dict[str, str]] = []
        sample_local: List[Dict[str, str]] = []
        for p in players:
            if not isinstance(p, dict):
                continue
            pid_raw = str(p.get("idPlayer") or "")
            pid = re.sub(r"[^A-Za-z0-9_-]+", "_", pid_raw).strip("_")
            if not pid:
                continue
            local = self._existing_player_picture(pid)
            if local:
                local_players += 1
                if update_paths and p.get("pictureUrl") != local:
                    p["pictureUrl"] = local
                if len(sample_local) < 8:
                    sample_local.append({
                        "idPlayer": pid,
                        "player": str(p.get("player") or p.get("shortName") or pid),
                        "team": str(p.get("code") or p.get("team") or ""),
                        "file": local,
                    })
            else:
                missing += 1
                src = str(sources.get(pid) or p.get("pictureSourceUrl") or "")
                if not src.startswith("http"):
                    missing_source += 1
                if len(sample_missing) < 10:
                    sample_missing.append({
                        "idPlayer": pid,
                        "player": str(p.get("player") or p.get("shortName") or pid),
                        "team": str(p.get("code") or p.get("team") or ""),
                        "source": "sí" if src.startswith("http") else "no",
                    })
            shown = str(p.get("pictureUrl") or "")
            if shown and not shown.startswith("http"):
                shown_local += 1
            if isinstance(p, dict):
                p.pop("pictureSourceUrl", None)

        return {
            "total_players": len([p for p in players if isinstance(p, dict) and str(p.get("idPlayer") or "")]),
            "local_players": local_players,
            "shown_local": shown_local,
            "missing": missing,
            "missing_source": missing_source,
            "total_local_files": len(local_files),
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "report_file": PLAYER_IMAGE_REPORT_FILE.relative_to(BASE_DIR).as_posix(),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample_local": sample_local,
            "sample_missing": sample_missing,
        }

    def _write_player_image_report(self, data: Dict[str, Any], status: Dict[str, Any] | None = None) -> None:
        try:
            if status is None:
                status = self._build_player_image_status(data, update_paths=False)
            self._write_json_safe(PLAYER_IMAGE_REPORT_FILE, {"ok": True, "imageStatus": status})
        except Exception:
            pass

    def _ensure_player_images_cached(self, data: Dict[str, Any], force: bool = False) -> Dict[str, int]:
        """Garantiza que las fotos en fifaPlayerStats apunten a archivos locales.

        - Si ya existe assets/players/p_<IdPlayer>.* o *_<IdPlayer>.*, no consulta internet.
        - Si no existe y hay URL fuente guardada, descarga una sola vez.
        - Nunca deja pictureUrl remoto para el frontend; si no hay local, usa placeholder.
        """
        counters = {"existing": 0, "downloaded": 0, "failed": 0, "updated": 0, "missing_source": 0, "failed_sample": []}
        if not isinstance(data, dict):
            return counters
        players = data.get("players") or []
        if not isinstance(players, list):
            return counters
        sources = data.get("playerImageSources") or {}
        if not isinstance(sources, dict):
            sources = {}
        jobs: Dict[str, str] = {}
        for p in players:
            if not isinstance(p, dict):
                continue
            pid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(p.get("idPlayer") or "")).strip("_")
            if not pid:
                continue
            current = str(p.get("pictureUrl") or "").strip()
            # Si viene un remoto desde un caché viejo, convertirlo en fuente y quitarlo del frontend.
            if current.startswith("http"):
                sources.setdefault(pid, self._normalise_fifa_player_picture_url(current))
                p["pictureUrl"] = ""
                current = ""
                counters["updated"] += 1
            existing = self._existing_player_picture(pid)
            if existing and not force:
                if p.get("pictureUrl") != existing:
                    p["pictureUrl"] = existing
                    counters["updated"] += 1
                counters["existing"] += 1
                continue
            src = str(sources.get(pid) or p.get("pictureSourceUrl") or "").strip()
            src = self._normalise_fifa_player_picture_url(src)
            if src.startswith("http"):
                sources[pid] = src
                jobs[pid] = src
            else:
                p["pictureUrl"] = current if (current and not current.startswith("http")) else ""
                counters["missing_source"] += 1
            p.pop("pictureSourceUrl", None)
        if jobs:
            PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            # v59: descarga progresiva en lotes de 5 para no saturar FIFA/digitalhub
            # ni congelar la app intentando bajar todas las fotos a la vez.
            batch_size = PLAYER_IMAGE_BATCH_SIZE
            counters["batch_size"] = batch_size
            job_items = list(jobs.items())
            counters["batches"] = math.ceil(len(job_items) / batch_size) if job_items else 0
            for start in range(0, len(job_items), batch_size):
                batch = job_items[start:start + batch_size]
                with ThreadPoolExecutor(max_workers=min(batch_size, max(1, len(batch)))) as pool:
                    future_map = {pool.submit(self._cache_player_picture, pid, url): pid for pid, url in batch}
                    for fut in as_completed(future_map):
                        pid = future_map[fut]
                        try:
                            res = fut.result()
                        except Exception as exc:
                            res = {"player_id": pid, "local": "", "status": "failed", "error": str(exc)[:140]}
                        status = str(res.get("status") or "")
                        if status == "downloaded":
                            counters["downloaded"] += 1
                        elif status == "existing":
                            counters["existing"] += 1
                        elif status == "failed":
                            counters["failed"] += 1
                            if len(counters.get("failed_sample", [])) < 12:
                                counters.setdefault("failed_sample", []).append({
                                    "idPlayer": pid,
                                    "error": str(res.get("error") or "sin detalle")[:220],
                                    "source": str(res.get("source") or "")[:180],
                                })
                        local = str(res.get("local") or "")
                        if local:
                            for p in players:
                                if isinstance(p, dict) and str(p.get("idPlayer") or "") == pid:
                                    p["pictureUrl"] = local
                                    counters["updated"] += 1
                                    break
                # Pausa mínima entre lotes para que la descarga sea estable.
                if start + batch_size < len(job_items):
                    time.sleep(0.25)
        # Limpieza final: frontend nunca debe recibir URL remota.
        for p in players:
            if isinstance(p, dict):
                if str(p.get("pictureUrl") or "").startswith("http"):
                    p["pictureUrl"] = ""
                    counters["updated"] += 1
                p.pop("pictureSourceUrl", None)
        data["playerImageSources"] = sources
        status = self._build_player_image_status(data, update_paths=True)
        data["imageCache"] = {
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_players": status.get("total_players", 0),
            "local_players": status.get("local_players", 0),
            "missing": status.get("missing", 0),
            "total_local_files": status.get("total_local_files", 0),
            **counters,
        }
        self._write_player_image_report(data, status)
        try:
            if counters.get("failed_sample"):
                self._write_json_safe(PLAYER_IMAGE_ERROR_FILE, {
                    "ok": False,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "failed": counters.get("failed", 0),
                    "failed_sample": counters.get("failed_sample", []),
                    "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
                })
        except Exception:
            pass
        self._write_player_image_download_summary({
            "ok": True,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
            "summary_file": PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE.relative_to(BASE_DIR).as_posix(),
            **counters,
        })
        return counters

    def _read_json_safe(self, path: Path) -> Dict[str, Any]:
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {}

    def _write_json_safe(self, path: Path, data: Dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _read_fifa_stats_cache(self, max_age_seconds: Any = FIFA_STATS_TTL_SECONDS) -> Dict[str, Any]:
        """Lee caché local de FIFA Team Stats.

        max_age_seconds=None permite usar el caché aunque esté viejo.
        """
        for path in (FIFA_STATS_CACHE, FIFA_STATS_CACHE_BACKUP):
            data = self._read_json_safe(path)
            if not isinstance(data, dict) or not data.get("teams"):
                continue
            if max_age_seconds is None:
                return data
            try:
                ts = float(data.get("cache_ts") or 0)
                if ts and (time.time() - ts) <= float(max_age_seconds):
                    return data
            except Exception:
                continue
        return {}

    def _write_fifa_stats_cache(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict) or not data.get("teams"):
            return
        data = dict(data)
        data["cache_ts"] = time.time()
        self._write_json_safe(FIFA_STATS_CACHE, data)
        self._write_json_safe(FIFA_STATS_CACHE_BACKUP, data)

    def _load_fifa_team_catalog(self, discover: bool = True) -> Dict[str, Dict[str, str]]:
        catalog = self._default_fifa_catalog()
        # Cache automático generado por la app
        for path in (FIFA_TEAM_AUTO_CACHE, USER_DATA_DIR / "fifa_team_ids_auto.json"):
            catalog.update(self._read_fifa_catalog_file(path))
        # Manual del usuario: puede pisar el cache si se desea
        for path in (USER_DATA_DIR / "fifa_team_ids_manual.json", LOCAL_DATA_DIR / "fifa_team_ids_manual.json"):
            catalog.update(self._read_fifa_catalog_file(path))

        catalog = self._normalise_catalog_for_known_slugs(catalog)

        if discover:
            missing = []
            for team, code in TEAM_CODES.items():
                code = code.upper()
                if code not in catalog or not catalog.get(code, {}).get("idTeam"):
                    missing.append((code, team))
            if missing:
                changed = False
                # Resolver IdTeam en paralelo. Antes se hacía secuencial y era lo más lento.
                with ThreadPoolExecutor(max_workers=min(FIFA_DISCOVER_WORKERS, max(1, len(missing)))) as pool:
                    future_map = {pool.submit(self._discover_fifa_team_meta, code, team): (code, team) for code, team in missing}
                    for fut in as_completed(future_map):
                        code, _team = future_map[fut]
                        try:
                            item = fut.result()
                            if item.get("idTeam"):
                                catalog[code] = {**catalog.get(code, {}), **item}
                                changed = True
                        except Exception:
                            continue
                if changed:
                    catalog = self._normalise_catalog_for_known_slugs(catalog)
                    self._write_fifa_auto_catalog(catalog)
        return self._normalise_catalog_for_known_slugs(catalog)

    def _load_fifa_team_ids(self) -> Dict[str, str]:
        catalog = self._load_fifa_team_catalog(discover=True)
        return {code: str(item.get("idTeam")) for code, item in catalog.items() if isinstance(item, dict) and item.get("idTeam")}

    def _team_from_code(self, code: str) -> str:
        code = (code or "").upper().strip()
        for team, abbr in TEAM_CODES.items():
            if abbr.upper() == code:
                return team
        return code

    @staticmethod
    def _fifa_stat_value(rows: Any, key: str, default: float = 0) -> float:
        """Extrae valores desde el JSON FDH de FIFA aunque cambie el formato.

        FIFA ha devuelto el endpoint de Team Stats en varios formatos:
        - lista de listas: ["Goals", 2]
        - lista de diccionarios: {"name": "Goals", "value": 2}
        - objeto con data/items/statistics anidados
        - objeto con claves directas: {"Goals": 2}

        Las versiones antiguas solo leían lista de listas; por eso el botón JSON podía
        mostrar datos nuevos, pero la tarjeta seguía sin actualizar algunos campos.
        """
        wanted = str(key or "").strip().lower()
        if not wanted:
            return default

        def to_number(value: Any) -> float | None:
            try:
                if value is None or value == "":
                    return None
                if isinstance(value, bool):
                    return float(int(value))
                if isinstance(value, (int, float)):
                    return float(value)
                txt = str(value).strip().replace(",", "")
                # Acepta "43.5%" y valores con texto alrededor.
                m = re.search(r"-?\d+(?:\.\d+)?", txt)
                if not m:
                    return None
                return float(m.group(0))
            except Exception:
                return None

        def normalize_name(value: Any) -> str:
            return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())

        wanted_norm = normalize_name(wanted)
        name_keys = ("key", "name", "stat", "stats", "statname", "statkey", "statistic", "statisticname", "type", "id", "code", "label", "displayname")
        value_keys = ("value", "val", "total", "count", "amount", "statvalue", "numericvalue", "number", "data")

        def scan(obj: Any, depth: int = 0) -> float | None:
            if depth > 8:
                return None
            if isinstance(obj, dict):
                # Clave directa: {"Goals": 2}
                for k, v in obj.items():
                    if normalize_name(k) == wanted_norm:
                        n = to_number(v)
                        if n is not None:
                            return n
                # Objeto tipo {name/key/stat: "Goals", value/total: 2}
                row_name = None
                for nk in name_keys:
                    if nk in obj:
                        row_name = obj.get(nk)
                        break
                    # tolerante a mayúsculas
                    for actual in obj.keys():
                        if normalize_name(actual) == normalize_name(nk):
                            row_name = obj.get(actual)
                            break
                    if row_name is not None:
                        break
                if row_name is not None and normalize_name(row_name) == wanted_norm:
                    for vk in value_keys:
                        if vk in obj:
                            n = to_number(obj.get(vk))
                            if n is not None:
                                return n
                        for actual in obj.keys():
                            if normalize_name(actual) == normalize_name(vk):
                                n = to_number(obj.get(actual))
                                if n is not None:
                                    return n
                # Formatos anidados frecuentes
                for container_key in ("data", "items", "rows", "stats", "statistics", "teamStats", "values", "result"):
                    if container_key in obj:
                        n = scan(obj.get(container_key), depth + 1)
                        if n is not None:
                            return n
                    for actual in obj.keys():
                        if normalize_name(actual) == normalize_name(container_key):
                            n = scan(obj.get(actual), depth + 1)
                            if n is not None:
                                return n
                return None
            if isinstance(obj, list):
                for row in obj:
                    # Lista clásica: ["Goals", 2] o ["Goals", "Goles", 2]
                    if isinstance(row, list) and row:
                        if normalize_name(row[0]) == wanted_norm:
                            for value in row[1:]:
                                n = to_number(value)
                                if n is not None:
                                    return n
                        # Algunas respuestas traen pares internos o listas anidadas.
                        n = scan(row, depth + 1)
                        if n is not None:
                            return n
                    else:
                        n = scan(row, depth + 1)
                        if n is not None:
                            return n
                return None
            return None

        found = scan(rows)
        return default if found is None else found

    def _fetch_fifa_team_stats(self, force: bool = False) -> Dict[str, Any]:
        """Lee estadísticas agregadas por equipo desde FIFA con caché y concurrencia.

        Optimización v34:
        - Reutiliza caché local si está vigente.
        - Si el caché está incompleto, solo consulta los equipos faltantes.
        - Resuelve IdTeam en paralelo desde CXM.
        - Consulta FDH en paralelo.
        - Omite metadatos adicionales por equipo para evitar 48 llamadas extra.
        """
        cache = self._read_fifa_stats_cache(max_age_seconds=FIFA_STATS_TTL_SECONDS)
        if not force and cache.get("teams") and len(cache.get("teams", [])) >= len(TEAM_CODES):
            cache = dict(cache)
            cache.setdefault("notes", [])
            cache["notes"] = ["FIFA Team Stats leído desde caché local para acelerar la carga."] + cache.get("notes", [])[:6]
            cache["from_cache"] = True
            return cache

        catalog = self._load_fifa_team_catalog(discover=True)
        cached_any = self._read_fifa_stats_cache(max_age_seconds=None)
        cached_by_code = {}
        if isinstance(cached_any, dict):
            for row in cached_any.get("teams", []) or []:
                c = str(row.get("code") or "").upper().strip()
                if c:
                    cached_by_code[c] = row

        result: Dict[str, Any] = {
            "ok": True,
            "teams": [],
            "sources": [],
            "notes": [],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "season": FIFA_STATS_SEASON_ID,
            "catalog": catalog,
            "from_cache": False,
        }
        errors: List[str] = []
        jobs: List[Tuple[str, str, Dict[str, str]]] = []
        used_cached = 0

        # Usar datos cacheados para equipos ya cargados, salvo que se pida force.
        for team_name_default, default_code in TEAM_CODES.items():
            code = default_code.upper()
            meta_item = dict(catalog.get(code, {}) or {})
            team_id = str(meta_item.get("idTeam") or "").strip()
            if not team_id:
                errors.append(f"{code}: sin IdTeam FIFA resuelto")
                continue
            if not force and code in cached_by_code:
                row = dict(cached_by_code[code])
                row.setdefault("team", self._team_from_code(code))
                row.setdefault("code", code)
                row.setdefault("idTeam", team_id)
                result["teams"].append(row)
                used_cached += 1
            else:
                jobs.append((self._team_from_code(code), code, meta_item))

        def fetch_one(job: Tuple[str, str, Dict[str, str]]) -> Dict[str, Any]:
            team_name_default, code, meta_item = job
            team_id = str(meta_item.get("idTeam") or "").strip()
            stats_url = FIFA_TEAM_STATS_TEMPLATE.format(season=FIFA_STATS_SEASON_ID, team_id=team_id)
            request_url = stats_url + (("?t=" + str(int(time.time()))) if force else "")
            rows = json.loads(fetch_url(request_url, timeout=8))
            team_name = self._team_from_code(code)
            tr_direct = int(self._fifa_stat_value(rows, "DirectRedCards", 0) or 0)
            tr_indirect = int(self._fifa_stat_value(rows, "IndirectRedCards", 0) or 0)
            red_total = int(self._fifa_stat_value(rows, "RedCards", 0) or 0)
            if red_total == 0:
                red_total = tr_direct + tr_indirect
            return {
                "team": team_name,
                "nameEs": meta_item.get("nameEs") or team_name,
                "code": code,
                "idTeam": str(team_id),
                "slug": meta_item.get("slug") or "",
                "pageUrl": meta_item.get("pageUrl") or (FIFA_TEAM_PAGE_TEMPLATE.format(slug=meta_item.get("slug")) if meta_item.get("slug") else ""),
                "imageUrl": "",
                "flagUrl": "",
                "matches": int(self._fifa_stat_value(rows, "MatchesPlayed", 0) or 0),
                "goals": int(self._fifa_stat_value(rows, "Goals", 0) or 0),
                "goalsConceded": int(self._fifa_stat_value(rows, "GoalsConceded", 0) or 0),
                "assists": int(self._fifa_stat_value(rows, "Assists", 0) or 0),
                "yellow": int(self._fifa_stat_value(rows, "YellowCards", 0) or 0),
                "red": red_total,
                "directRed": tr_direct,
                "indirectRed": tr_indirect,
                "shots": int(self._fifa_stat_value(rows, "AttemptAtGoal", 0) or 0),
                "shotsOnTarget": int(self._fifa_stat_value(rows, "AttemptAtGoalOnTarget", 0) or 0),
                "xg": round(float(self._fifa_stat_value(rows, "XG", 0) or 0), 3),
                "possession": round((lambda v: v * 100 if v <= 1 else v)(float(self._fifa_stat_value(rows, "Possession", 0) or 0)), 2),
                "passes": int(self._fifa_stat_value(rows, "Passes", 0) or 0),
                "passesCompleted": int(self._fifa_stat_value(rows, "PassesCompleted", 0) or 0),
                "corners": int(self._fifa_stat_value(rows, "Corners", 0) or 0),
                "foulsAgainst": int(self._fifa_stat_value(rows, "FoulsAgainst", 0) or 0),
                "foulsFor": int(self._fifa_stat_value(rows, "FoulsFor", 0) or 0),
                "source": stats_url,
            }

        if jobs:
            with ThreadPoolExecutor(max_workers=min(FIFA_STATS_WORKERS, max(1, len(jobs)))) as pool:
                future_map = {pool.submit(fetch_one, job): job for job in jobs}
                for fut in as_completed(future_map):
                    _team, code, meta_item = future_map[fut]
                    try:
                        item = fut.result()
                        result["teams"].append(item)
                        result["sources"].append(item.get("source", ""))
                        if item.get("pageUrl"):
                            result["sources"].append(item["pageUrl"])
                    except Exception as exc:
                        team_id = str((meta_item or {}).get("idTeam") or "")
                        errors.append(f"{code}/{team_id}: {exc}")

        # Fuentes de filas cacheadas.
        for item in result["teams"]:
            if item.get("source"):
                result["sources"].append(item["source"])
            if item.get("pageUrl"):
                result["sources"].append(item["pageUrl"])

        # v106: si FIFA devuelve una respuesta parcial, no reducir lo que ya existía en caché.
        if cached_any.get("teams"):
            result = self._merge_fifa_team_stats(result, cached_any)
        result["teams"].sort(key=lambda x: (str(x.get("team") or "")))
        if not result["teams"]:
            result["ok"] = False
            result["error"] = "; ".join(errors) if errors else "No hay IdTeam configurados o resueltos para FIFA Team Stats"
        else:
            result["notes"].append(f"FIFA Team Stats optimizado: {len(result['teams'])} equipo(s) disponibles; {used_cached} desde caché; {len(jobs)} consultado(s) en paralelo.")
            missing = len(TEAM_CODES) - len(result["teams"])
            if missing > 0:
                result["notes"].append(f"Pendientes sin datos FDH o sin IdTeam resuelto: {missing} equipo(s).")
            if errors:
                result["notes"].append("Advertencias FIFA: " + "; ".join(errors[:12]))
            self._write_fifa_stats_cache(result)
        result["sources"] = list(dict.fromkeys([x for x in result["sources"] if x]))[:120]
        return result


    def _read_fifa_player_stats_cache(self, max_age_seconds: Any = FIFA_STATS_TTL_SECONDS) -> Dict[str, Any]:
        """Lee caché local de jugadores FIFA.

        max_age_seconds=None permite usar el caché aunque esté viejo.
        """
        for path in (FIFA_PLAYER_STATS_CACHE, FIFA_PLAYER_STATS_CACHE_BACKUP):
            data = self._read_json_safe(path)
            if not isinstance(data, dict) or not data.get("players"):
                continue
            if max_age_seconds is None:
                return data
            try:
                ts = float(data.get("cache_ts") or 0)
                if ts and (time.time() - ts) <= float(max_age_seconds):
                    return data
            except Exception:
                continue
        return {}

    def _write_fifa_player_stats_cache(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict) or not data.get("players"):
            return
        data = dict(data)
        data["cache_ts"] = time.time()
        self._write_json_safe(FIFA_PLAYER_STATS_CACHE, data)
        self._write_json_safe(FIFA_PLAYER_STATS_CACHE_BACKUP, data)

    @staticmethod
    def _localized_value(items: Any, fallback: str = "") -> str:
        if isinstance(items, str):
            return items
        if isinstance(items, list):
            for locale in ("es-ES", "es", "en-GB", "en"):
                for item in items:
                    if isinstance(item, dict) and str(item.get("Locale", "")).lower() == locale.lower():
                        value = str(item.get("Description") or "").strip()
                        if value:
                            return value
            for item in items:
                if isinstance(item, dict):
                    value = str(item.get("Description") or "").strip()
                    if value:
                        return value
        return fallback

    @staticmethod
    def _player_stats_rows_to_dict(rows: Any) -> Dict[str, float]:
        """Convierte filas FDH de jugadores a diccionario numérico.

        v95: no se descartan filas por el tercer valor booleano. En los JSON FDH
        ese campo puede actuar como metadato de visualización y no como validez
        del dato; al filtrarlo se estaban perdiendo goles, asistencias, minutos y
        tarjetas de algunos jugadores.
        """
        stats: Dict[str, float] = {}
        if isinstance(rows, dict):
            rows = [[k, v] for k, v in rows.items()]
        if not isinstance(rows, list):
            return stats
        for row in rows:
            try:
                if isinstance(row, dict):
                    key = str(row.get("key") or row.get("name") or row.get("stat") or row.get("Stat") or "").strip()
                    value = row.get("value", row.get("Value", 0))
                elif isinstance(row, list) and len(row) >= 2:
                    key = str(row[0] or "").strip()
                    value = row[1] if row[1] is not None else 0
                else:
                    continue
                if not key:
                    continue
                if isinstance(value, bool):
                    value = int(value)
                if isinstance(value, (int, float)):
                    stats[key] = float(value)
                else:
                    try:
                        stats[key] = float(str(value).replace(",", "."))
                    except Exception:
                        stats[key] = 0.0
            except Exception:
                continue
        return stats

    def _fetch_fifa_squad(self, code: str, team: str, team_id: str) -> Dict[str, Any]:
        url = FIFA_TEAM_SQUAD_TEMPLATE.format(
            team_id=urllib.parse.quote(str(team_id)),
            competition=urllib.parse.quote("17"),
            season=urllib.parse.quote(FIFA_STATS_SEASON_ID),
        )
        raw = fetch_url(url, timeout=10)
        data = json.loads(raw)
        players = data.get("Players") if isinstance(data, dict) else []
        if not isinstance(players, list):
            players = []
        return {"code": code, "team": team, "idTeam": str(team_id), "url": url, "raw": data, "players": players}

    def _player_team_counts(self, players: Any) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        if not isinstance(players, list):
            return counts
        for p in players:
            if not isinstance(p, dict):
                continue
            c = str(p.get("code") or "").upper().strip()
            if c:
                counts[c] = counts.get(c, 0) + 1
        return counts

    def _merge_player_refresh_with_cache(self, result: Dict[str, Any], cached_any: Dict[str, Any]) -> Dict[str, Any]:
        """Evita que un refresh parcial de FIFA borre planteles completos.

        Si FIFA falla para una selección, o devuelve menos jugadores que el caché
        anterior, se conserva el último plantel bueno de esa selección y se marca
        en notas. Esto corrige los casos en los que desaparecían jugadores tras
        presionar Actualizar.
        """
        if not isinstance(result, dict):
            return result
        if not isinstance(cached_any, dict) or not isinstance(cached_any.get("players"), list):
            return result
        new_players = result.get("players") if isinstance(result.get("players"), list) else []
        old_players = cached_any.get("players") if isinstance(cached_any.get("players"), list) else []
        if not old_players:
            return result
        new_by_code: Dict[str, List[Dict[str, Any]]] = {}
        old_by_code: Dict[str, List[Dict[str, Any]]] = {}
        for p in new_players:
            if isinstance(p, dict):
                c = str(p.get("code") or "").upper().strip()
                if c:
                    new_by_code.setdefault(c, []).append(p)
        for p in old_players:
            if isinstance(p, dict):
                c = str(p.get("code") or "").upper().strip()
                if c:
                    old_by_code.setdefault(c, []).append(p)

        old_aggs = cached_any.get("teamAggregates") if isinstance(cached_any.get("teamAggregates"), dict) else {}
        new_aggs = result.get("teamAggregates") if isinstance(result.get("teamAggregates"), dict) else {}
        merged_players: List[Dict[str, Any]] = []
        merged_aggs: Dict[str, Any] = {}
        preserved: List[str] = []
        incomplete: List[str] = []
        for _team, code_raw in TEAM_CODES.items():
            code = str(code_raw).upper()
            np = new_by_code.get(code, [])
            op = old_by_code.get(code, [])
            # Plantel completo esperado: 26. Si el refresh trae menos que el último
            # dato bueno, se considera parcial y se conserva el caché de ese equipo.
            use_old = bool(op) and (not np or len(np) < min(len(op), FIFA_EXPECTED_PLAYERS_PER_TEAM))
            chosen = op if use_old else np
            if use_old:
                preserved.append(f"{code} ({len(op)} jugadores cacheados; FIFA devolvió {len(np)})")
            if chosen and len(chosen) < FIFA_EXPECTED_PLAYERS_PER_TEAM:
                incomplete.append(f"{code}:{len(chosen)}")
            merged_players.extend(chosen)
            if use_old and code in old_aggs:
                merged_aggs[code] = old_aggs[code]
            elif code in new_aggs:
                merged_aggs[code] = new_aggs[code]
            elif code in old_aggs:
                merged_aggs[code] = old_aggs[code]

        # Conserva jugadores con códigos no mapeados, si los hubiera.
        known = {str(c).upper() for c in TEAM_CODES.values()}
        for c, arr in new_by_code.items():
            if c not in known:
                merged_players.extend(arr)
        if preserved:
            result["players"] = merged_players
            result["teamAggregates"] = merged_aggs
            result["preservedFromCache"] = preserved
            notes = result.get("notes") if isinstance(result.get("notes"), list) else []
            notes.append("Se conservaron planteles desde caché porque FIFA devolvió una respuesta parcial: " + "; ".join(preserved[:12]))
            result["notes"] = notes
        if incomplete:
            result["incompleteTeamCounts"] = incomplete
        return result

    def _finalize_player_freshness(self, result: Dict[str, Any], raw_stats_count: int = 0) -> Dict[str, Any]:
        players = result.get("players") if isinstance(result.get("players"), list) else []
        team_counts = self._player_team_counts(players)
        missing_codes = [str(c).upper() for c in TEAM_CODES.values() if str(c).upper() not in team_counts]
        incomplete_codes = [f"{c}:{n}" for c, n in sorted(team_counts.items()) if n < FIFA_EXPECTED_PLAYERS_PER_TEAM]
        result["expectedTeams"] = FIFA_EXPECTED_TEAMS
        result["expectedPlayers"] = FIFA_EXPECTED_PLAYERS
        result["loadedTeams"] = len([c for c in team_counts if team_counts.get(c, 0) > 0])
        result["loadedPlayers"] = len(players)
        result["rawStatsPlayers"] = int(raw_stats_count or 0)
        result["missingTeamCodes"] = missing_codes
        result["incompleteTeamCounts"] = list(dict.fromkeys((result.get("incompleteTeamCounts") or []) + incomplete_codes))[:60]
        result["isCompleteRoster"] = (result["loadedTeams"] >= FIFA_EXPECTED_TEAMS and result["loadedPlayers"] >= FIFA_EXPECTED_PLAYERS and not missing_codes)
        result["freshnessStatus"] = "OK" if result["isCompleteRoster"] else "PARCIAL"
        notes = result.get("notes") if isinstance(result.get("notes"), list) else []
        notes.insert(0, f"Control v95: {result['loadedPlayers']}/{FIFA_EXPECTED_PLAYERS} jugadores y {result['loadedTeams']}/{FIFA_EXPECTED_TEAMS} selecciones cargadas desde FIFA/caché.")
        if missing_codes:
            notes.append("Selecciones sin plantel visible: " + ", ".join(missing_codes[:20]))
        if result.get("incompleteTeamCounts"):
            notes.append("Selecciones con plantel incompleto: " + ", ".join(result.get("incompleteTeamCounts", [])[:20]))
        result["notes"] = list(dict.fromkeys([str(x) for x in notes if x]))[:18]
        return result

    def _fetch_fifa_player_stats(self, force: bool = False, catalog: Dict[str, Any] | None = None, cache_images: bool = True) -> Dict[str, Any]:
        """Cruza squad por selección con players.json y agrega totales por equipo.

        Fuente base:
        - Squad: api.fifa.com/api/v3/teams/<IdTeam>/squad
        - Stats: fdh-api.fifa.com/v1/stats/season/285023/players.json
        """
        cache = self._read_fifa_player_stats_cache(max_age_seconds=FIFA_STATS_TTL_SECONDS)
        if not force and cache.get("players"):
            cache = dict(cache)
            image_counts = self._ensure_player_images_cached(cache, force=False)
            cache["notes"] = [
                "FIFA Player Stats leído desde caché local para acelerar la carga.",
                f"Fotos locales: {image_counts.get('existing', 0)} existentes, {image_counts.get('downloaded', 0)} descargadas en esta apertura."
            ] + cache.get("notes", [])[:8]
            if image_counts.get("downloaded") or image_counts.get("updated"):
                self._write_fifa_player_stats_cache(cache)
            return cache

        catalog = dict(catalog or {}) or self._load_fifa_team_catalog(discover=True)
        cached_any = self._read_fifa_player_stats_cache(max_age_seconds=None)
        stats_url = FIFA_PLAYER_STATS_TEMPLATE.format(season=FIFA_STATS_SEASON_ID)
        raw_stats = json.loads(fetch_url(stats_url, timeout=15))
        if not isinstance(raw_stats, dict):
            raw_stats = {}

        jobs: List[Tuple[str, str, str]] = []
        errors: List[str] = []
        for team, code in TEAM_CODES.items():
            item = catalog.get(code.upper(), {}) or {}
            team_id = str(item.get("idTeam") or "").strip()
            if team_id:
                jobs.append((code.upper(), team, team_id))
            else:
                errors.append(f"{code}: sin IdTeam para consultar squad")

        squads: List[Dict[str, Any]] = []
        if jobs:
            with ThreadPoolExecutor(max_workers=min(FIFA_SQUAD_WORKERS, max(1, len(jobs)))) as pool:
                future_map = {pool.submit(self._fetch_fifa_squad, code, team, team_id): (code, team, team_id) for code, team, team_id in jobs}
                for fut in as_completed(future_map):
                    code, _team, team_id = future_map[fut]
                    try:
                        squads.append(fut.result())
                    except Exception as exc:
                        errors.append(f"{code}/{team_id}: {exc}")

        players_out: List[Dict[str, Any]] = []
        team_aggregates: Dict[str, Dict[str, Any]] = {}
        sources = [stats_url]
        player_keys_with_stats = 0
        image_sources: Dict[str, str] = {}

        for squad in squads:
            code = str(squad.get("code") or "").upper()
            team = squad.get("team") or self._team_from_code(code)
            id_team = str(squad.get("idTeam") or "")
            sources.append(str(squad.get("url") or ""))
            aggregate: Dict[str, Any] = {"team": team, "code": code, "idTeam": id_team, "players": 0, "playersWithStats": 0, "stats": {}}
            for stat in FIFA_PLAYER_SUM_STATS:
                aggregate["stats"][stat] = 0.0
            total_minutes_for_speed = 0.0
            weighted_speed = 0.0
            top_speed = 0.0
            total_time_played = 0.0

            for player in squad.get("players", []) or []:
                if not isinstance(player, dict):
                    continue
                player_id = str(player.get("IdPlayer") or player.get("idPlayer") or "").strip()
                stat_rows = raw_stats.get(player_id, []) if player_id else []
                stats = self._player_stats_rows_to_dict(stat_rows)
                if stats:
                    player_keys_with_stats += 1
                    aggregate["playersWithStats"] += 1
                aggregate["players"] += 1
                for stat in FIFA_PLAYER_SUM_STATS:
                    aggregate["stats"][stat] = float(aggregate["stats"].get(stat, 0.0) or 0.0) + float(stats.get(stat, 0.0) or 0.0)
                minutes = float(stats.get("TimePlayed", 0.0) or 0.0)
                total_time_played += minutes
                avg_speed = float(stats.get("AvgSpeed", 0.0) or 0.0)
                if minutes > 0 and avg_speed > 0:
                    weighted_speed += avg_speed * minutes
                    total_minutes_for_speed += minutes
                top_speed = max(top_speed, float(stats.get("TopSpeed", 0.0) or 0.0))

                player_name = self._localized_value(player.get("PlayerName"), "Sin nombre")
                short_name = self._localized_value(player.get("ShortName"), player_name)
                position = self._localized_value(player.get("PositionLocalized"), "")
                picture_source = ""
                try:
                    picture_source = str((player.get("PlayerPicture") or {}).get("PictureUrl") or "")
                except Exception:
                    picture_source = ""
                picture_source = self._normalise_fifa_player_picture_url(picture_source)
                if picture_source and player_id:
                    image_sources[player_id] = picture_source
                picture_local = self._existing_player_picture(player_id)
                players_out.append({
                    "team": team,
                    "code": code,
                    "idCountry": player.get("IdCountry") or code,
                    "idTeam": id_team,
                    "idPlayer": player_id,
                    "player": player_name,
                    "shortName": short_name,
                    "jersey": player.get("JerseyNum"),
                    "position": position,
                    "pictureUrl": picture_local,
                    "pictureSourceUrl": picture_source if not picture_local else "",
                    "stats": stats,
                    "goals": int(stats.get("Goals", 0) or 0),
                    "assists": int(stats.get("Assists", 0) or 0),
                    "yellow": int(stats.get("YellowCards", 0) or 0),
                    "red": int(stats.get("RedCards", 0) or 0),
                    "passes": int(stats.get("Passes", 0) or 0),
                    "passesCompleted": int(stats.get("PassesCompleted", 0) or 0),
                    "shots": int(stats.get("AttemptAtGoal", 0) or 0),
                    "shotsOnTarget": int(stats.get("AttemptAtGoalOnTarget", 0) or 0),
                    "xg": round(float(stats.get("XG", 0) or 0), 3),
                    "totalDistance": round(float(stats.get("TotalDistance", 0) or 0), 2),
                    "avgSpeed": round(float(stats.get("AvgSpeed", 0) or 0), 3),
                    "topSpeed": round(float(stats.get("TopSpeed", 0) or 0), 3),
                    "sprints": int(stats.get("Sprints", 0) or 0),
                    "timePlayed": round(minutes, 4),
                })

            aggregate["stats"]["TimePlayed"] = total_time_played
            aggregate["stats"]["AvgSpeed"] = (weighted_speed / total_minutes_for_speed) if total_minutes_for_speed > 0 else 0.0
            aggregate["stats"]["TopSpeed"] = top_speed
            saves = float(aggregate["stats"].get("GoalkeeperSaves", 0.0) or 0.0)
            saves_on_target = float(aggregate["stats"].get("GoalkeeperSavesOnTarget", 0.0) or 0.0)
            aggregate["stats"]["GoalkeeperSavePercentage"] = (saves / saves_on_target) if saves_on_target > 0 else 0.0
            team_aggregates[code] = aggregate

        # Cache local de fotos: el navegador no debe cargar imágenes remotas pesadas.
        # Solo se descarga cada URL una vez y luego queda en assets/players.
        image_downloaded = 0
        image_existing = 0
        image_failed = 0
        image_jobs: Dict[str, str] = {}
        for p in players_out:
            if p.get("pictureUrl"):
                image_existing += 1
                continue
            src = self._normalise_fifa_player_picture_url(str(p.get("pictureSourceUrl") or ""))
            pid = str(p.get("idPlayer") or "")
            if src and pid and pid not in image_jobs:
                image_jobs[pid] = src
        image_results: Dict[str, Dict[str, str]] = {}
        if cache_images and image_jobs:
            # Descarga automática progresiva en lotes de 5. No intenta bajar
            # todas las fotos a la vez y no genera URLs alternativas.
            job_items = list(image_jobs.items())
            for start in range(0, len(job_items), PLAYER_IMAGE_BATCH_SIZE):
                batch = job_items[start:start + PLAYER_IMAGE_BATCH_SIZE]
                with ThreadPoolExecutor(max_workers=min(PLAYER_IMAGE_BATCH_SIZE, max(1, len(batch)))) as pool:
                    future_map = {pool.submit(self._cache_player_picture, pid, url): pid for pid, url in batch}
                    for fut in as_completed(future_map):
                        pid = future_map[fut]
                        try:
                            res = fut.result()
                        except Exception as exc:
                            res = {"player_id": pid, "local": "", "status": "failed", "error": str(exc)[:140]}
                        image_results[pid] = res
                        if res.get("status") == "downloaded":
                            image_downloaded += 1
                        elif res.get("status") == "existing":
                            image_existing += 1
                        elif res.get("status") == "failed":
                            image_failed += 1
                if start + PLAYER_IMAGE_BATCH_SIZE < len(job_items):
                    time.sleep(0.25)
        elif not cache_images and image_jobs:
            image_failed = 0
        for p in players_out:
            pid = str(p.get("idPlayer") or "")
            res = image_results.get(pid) or {}
            if res.get("local"):
                p["pictureUrl"] = res.get("local")
            # No exponer URL remota al frontend: si la foto local no existe se usa placeholder.
            p.pop("pictureSourceUrl", None)

        players_out.sort(key=lambda x: (str(x.get("team") or ""), int(x.get("jersey") or 999), str(x.get("player") or "")))
        result: Dict[str, Any] = {
            "ok": True,
            "season": FIFA_STATS_SEASON_ID,
            "competition": "17",
            "players": players_out,
            "teamAggregates": team_aggregates,
            "playerImageSources": image_sources,
            "sources": list(dict.fromkeys([x for x in sources if x]))[:140],
            "notes": [
                f"Jugadores FIFA cargados: {len(players_out)}; jugadores con estadísticas activas: {player_keys_with_stats}.",
                (f"Fotos de jugadores: {image_existing} existentes, {image_downloaded} descargadas desde URL exacta FIFA, {image_failed} fallidas." if cache_images else "Fotos de jugadores: descarga omitida en este proceso para acelerar el análisis; usa Fotos faltantes en Jugadores FIFA."),
                "Los totales de equipo se calculan sumando estadísticas activas de jugadores y excluyendo métricas contextuales que no deben sumarse.",
            ],
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "forceRefresh": bool(force),
            "rawStatsPlayers": len(raw_stats) if isinstance(raw_stats, dict) else 0,
            "imageCache": {
                "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                "existing": image_existing,
                "downloaded": image_downloaded,
                "failed": image_failed,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        }
        result = self._merge_player_refresh_with_cache(result, cached_any)
        result = self._finalize_player_freshness(result, raw_stats_count=(len(raw_stats) if isinstance(raw_stats, dict) else 0))
        # Reordenar después de una posible mezcla con caché.
        if isinstance(result.get("players"), list):
            result["players"].sort(key=lambda x: (str(x.get("team") or ""), int(x.get("jersey") or 999), str(x.get("player") or "")))
        if errors:
            result["notes"].append("Advertencias de squad: " + "; ".join(errors[:12]))
        if not result.get("players"):
            result["ok"] = False
            result["error"] = "; ".join(errors) if errors else "No se pudo construir la lista de jugadores FIFA"
        else:
            self._write_fifa_player_stats_cache(result)
        return result

    def _apply_player_aggregates_to_team_stats(self, fifa_stats: Dict[str, Any], fifa_player_stats: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(fifa_stats, dict) or not isinstance(fifa_player_stats, dict):
            return fifa_stats
        aggregates = fifa_player_stats.get("teamAggregates") or {}
        if not isinstance(aggregates, dict) or not aggregates:
            return fifa_stats
        out = dict(fifa_stats)
        rows: List[Dict[str, Any]] = []
        mapping = {
            "goals": "Goals",
            "assists": "Assists",
            "yellow": "YellowCards",
            "red": "RedCards",
            "directRed": "DirectRedCards",
            "indirectRed": "IndirectRedCards",
            "shots": "AttemptAtGoal",
            "shotsOnTarget": "AttemptAtGoalOnTarget",
            "xg": "XG",
            "passes": "Passes",
            "passesCompleted": "PassesCompleted",
            "corners": "Corners",
            "foulsAgainst": "FoulsAgainst",
            "foulsFor": "FoulsFor",
        }
        for row in out.get("teams", []) or []:
            item = dict(row)
            code = str(item.get("code") or "").upper()
            agg = aggregates.get(code) or {}
            stats = agg.get("stats") or {}
            if agg and int(agg.get("playersWithStats", 0) or 0) > 0:
                # Reconciliación FIFA equipo vs suma de jugadores:
                # - Normalmente se usa la suma de jugadores.
                # - Pero si la suma de jugadores llega en 0 y la estadística oficial del equipo
                #   trae un valor mayor, se conserva el valor oficial para no perder goles/tarjetas/etc.
                #   Ejemplo: team/43834.json trae Goals=1 aunque players.json no lo asigne todavía
                #   a un jugador del squad.
                fallbacks: Dict[str, Dict[str, float]] = {}
                for target, source in mapping.items():
                    value = stats.get(source)
                    if value is None:
                        continue
                    official_value = item.get(target)
                    try:
                        official_num = float(official_value or 0)
                    except Exception:
                        official_num = 0.0
                    try:
                        player_num = float(value or 0)
                    except Exception:
                        player_num = 0.0
                    # Para la copia de análisis no pisamos el total oficial del equipo
                    # con una suma parcial de jugadores. Ejemplo: USA puede traer 4 goles
                    # en Team Stats y 3 goles asignados en players.json; el análisis debe
                    # considerar 4 como total de equipo y usar jugadores como detalle.
                    if official_num > 0:
                        final_num = official_num
                        if player_num != official_num:
                            fallbacks[target] = {"official": official_num, "players": player_num}
                    else:
                        final_num = player_num
                    if target == "xg":
                        item[target] = round(float(final_num or 0), 3)
                    else:
                        item[target] = int(round(float(final_num or 0)))
                item["playerDerived"] = True
                if fallbacks:
                    item["teamOfficialFallbacks"] = fallbacks
                    item["reconciledWithTeamOfficial"] = True
                item["players"] = int(agg.get("players", 0) or 0)
                item["playersWithStats"] = int(agg.get("playersWithStats", 0) or 0)
                item["playerStats"] = {
                    "totalDistance": round(float(stats.get("TotalDistance", 0) or 0) / 1000, 2),
                    "avgSpeed": round(float(stats.get("AvgSpeed", 0) or 0), 2),
                    "topSpeed": round(float(stats.get("TopSpeed", 0) or 0), 2),
                    "sprints": int(round(float(stats.get("Sprints", 0) or 0))),
                    "timePlayed": round(float(stats.get("TimePlayed", 0) or 0), 2),
                }
            rows.append(item)
        out["teams"] = rows
        out.setdefault("notes", [])
        out["notes"] = list(dict.fromkeys(out.get("notes", []) + ["Copia conciliada usada solo para análisis: conserva totales oficiales de FIFA Team Stats y usa jugadores FIFA como detalle/fallback cuando el dato oficial no existe."]))[:14]
        return out

    def load_fifa_team_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Endpoint exclusivo de Equipos FIFA.

        Consulta o lee del caché únicamente FIFA Team Stats. No modifica ni recarga
        jugadores. Esto evita que una suma parcial de players.json cambie, por
        ejemplo, los goles oficiales de USA en la sección Equipos FIFA.
        """
        try:
            payload = payload or {}
            force = bool(payload.get("force", False))
            fifa_stats = self._fetch_fifa_team_stats(force=force)
            base_payload = dict(payload)
            if isinstance(fifa_stats, dict):
                fifa_stats = self._merge_fifa_team_stats(fifa_stats, payload.get("fifaTeamStats") or self._read_fifa_stats_cache(max_age_seconds=None))
            if fifa_stats.get("ok"):
                base_payload["fifaTeamStats"] = fifa_stats
                base_payload["teamDiscipline"] = self._team_discipline_from_fifa(fifa_stats)
                # Conserva cualquier información de jugadores ya cargada, pero no la modifica.
                if isinstance(payload.get("fifaPlayerStats"), dict):
                    base_payload["fifaPlayerStats"] = payload.get("fifaPlayerStats")
                self.save_results(base_payload)
            return {"ok": bool(fifa_stats.get("ok")), "fifaTeamStats": fifa_stats, "teamDiscipline": base_payload.get("teamDiscipline", {}), "error": fifa_stats.get("error")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def player_image_attempt_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Registra intentos/fallos de descarga hechos desde el navegador.

        Esto cubre el caso en el que Python/urllib no puede descargar desde
        DigitalHub, pero Chrome/Edge sí ve la imagen. El frontend descarga el
        blob con fetch y este endpoint solo deja trazabilidad del intento.
        """
        try:
            payload = payload or {}
            item = {
                "idPlayer": str(payload.get("idPlayer") or payload.get("player_id") or ""),
                "status": str(payload.get("status") or "browser_failed"),
                "error": str(payload.get("error") or "")[:900],
                "source": str(payload.get("source") or payload.get("url") or "")[:900],
                "phase": str(payload.get("phase") or "browser"),
                "mode": "browser_fetch",
            }
            self._append_player_image_log(item)
            return {"ok": True, "logged": item}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def player_image_save(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Guarda localmente una foto que el navegador ya descargó como Blob.

        Soluciona el caso observado: la URL DigitalHub responde 200 y se ve en
        Chrome, pero Python/urllib puede fallar por TLS/CloudFront/proxy/cache.
        Como DigitalHub expone Access-Control-Allow-Origin: *, el navegador puede
        hacer fetch(url), leer los bytes y mandarlos al backend web para escribir
        assets/players/<NOMBRE_FIFA>.<ext>.
        """
        try:
            payload = payload or {}
            pid = re.sub(r"[^A-Za-z0-9_-]+", "_", str(payload.get("idPlayer") or payload.get("player_id") or "")).strip("_")
            url = self._normalise_fifa_player_picture_url(str(payload.get("url") or payload.get("source") or "").strip())
            content_type = str(payload.get("contentType") or payload.get("content_type") or "").split(";")[0].strip().lower()
            data_b64 = str(payload.get("dataBase64") or payload.get("data") or "")
            base_log = {"idPlayer": pid, "source_final": url[:700], "mode": "browser_fetch_save"}
            if not pid:
                res = {"ok": False, "player_id": pid, "status": "failed", "error": "sin IdPlayer"}
                self._append_player_image_log({**base_log, **res})
                return res
            if not data_b64:
                res = {"ok": False, "player_id": pid, "status": "failed", "error": "sin datos base64"}
                self._append_player_image_log({**base_log, **res})
                return res
            try:
                data = base64.b64decode(data_b64, validate=False)
            except Exception as exc:
                res = {"ok": False, "player_id": pid, "status": "failed", "error": "base64 inválido: " + str(exc)[:180]}
                self._append_player_image_log({**base_log, **res})
                return res
            # El blob puede ser image/avif con contenedor ftyp/mif1; validar
            # también por Content-Type para no rechazar imágenes que Chrome sí
            # descarga correctamente.
            if len(data) < 100 or not (_looks_like_image_bytes(data) or content_type.startswith("image/")):
                res = {"ok": False, "player_id": pid, "status": "failed", "error": f"blob no es imagen válida; content-type={content_type or 'sin tipo'}; bytes={len(data)}"}
                self._append_player_image_log({**base_log, **res})
                return res
            ext = self._image_ext_from_type_or_url(content_type, url, data)
            target_name = self._player_picture_filename_from_url(pid, url, ext)
            target = PLAYER_IMAGES_DIR / target_name
            if not target.name.startswith("p_") and f"_{pid}" not in target.stem:
                target = PLAYER_IMAGES_DIR / f"p_{pid}{ext}"
            PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if not target.exists() or target.stat().st_size < 100:
                raise ValueError("archivo local no se escribió correctamente")
            res = {
                "ok": True,
                "player_id": pid,
                "local": target.relative_to(BASE_DIR).as_posix(),
                "status": "downloaded",
                "bytes": str(target.stat().st_size),
                "content_type": content_type or "image/*",
                "source": url,
                "filename": target.name,
                "mode": "browser_fetch_save",
            }
            self._append_player_image_log({**base_log, **res})
            return res
        except Exception as exc:
            msg = f"{type(exc).__name__}: {str(exc)}".replace("\n", " ")[:300]
            try:
                self._append_player_image_log({"status": "failed", "error": msg, "mode": "browser_fetch_save"})
            except Exception:
                pass
            return {"ok": False, "status": "failed", "error": msg}

    def cache_player_images(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Descarga/optimiza fotos de jugadores usando datos ya cargados.

        No consulta squad ni players.json. Solo usa las URLs fuente que ya quedaron
        guardadas en fifaPlayerStats/playerImageSources y completa assets/players.
        """
        try:
            payload = payload or {}
            force = bool(payload.get("force", False))
            fifa_player_stats = payload.get("fifaPlayerStats") if isinstance(payload.get("fifaPlayerStats"), dict) else {}
            if not fifa_player_stats or not fifa_player_stats.get("players"):
                fifa_player_stats = self._read_fifa_player_stats_cache(max_age_seconds=None)
            if not isinstance(fifa_player_stats, dict) or not fifa_player_stats.get("players"):
                return {
                    "ok": False,
                    "error": "Primero carga Jugadores FIFA para obtener las URLs fuente de las fotos.",
                    "imageCache": {"existing": 0, "downloaded": 0, "failed": 0, "missing_source": 0},
                }
            counters = self._ensure_player_images_cached(fifa_player_stats, force=force)
            self._write_fifa_player_stats_cache(fifa_player_stats)
            base_payload = dict(payload)
            base_payload["fifaPlayerStats"] = fifa_player_stats
            # Conserva cualquier otro módulo recibido, pero no consulta ni modifica FIFA equipos.
            self.save_results(base_payload)
            total_local = len([p for p in PLAYER_IMAGES_DIR.glob("*.*") if self._is_player_image_file(p)])
            return {
                "ok": True,
                "fifaPlayerStats": fifa_player_stats,
                "imageCache": {**counters, "total_local": total_local, "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(), "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(), "summary_file": PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE.relative_to(BASE_DIR).as_posix()},
                "message": f"Fotos locales listas: {counters.get('existing', 0)} existentes, {counters.get('downloaded', 0)} descargadas, {counters.get('failed', 0)} fallidas.",
                "failedSample": counters.get("failed_sample", []),
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


    def player_image_log(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Devuelve resumen y últimas líneas del log de descarga de fotos."""
        try:
            limit = 80
            try:
                limit = int((payload or {}).get("limit", 80) or 80)
            except Exception:
                limit = 80
            lines: List[Dict[str, Any]] = []
            if PLAYER_IMAGE_DOWNLOAD_LOG_FILE.exists():
                raw_lines = PLAYER_IMAGE_DOWNLOAD_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
                for line in raw_lines[-max(1, min(limit, 500)):]:
                    try:
                        lines.append(json.loads(line))
                    except Exception:
                        lines.append({"raw": line})
            summary = self._read_json_safe(PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE)
            return {
                "ok": True,
                "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
                "summary_file": PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE.relative_to(BASE_DIR).as_posix(),
                "summary": summary,
                "total_lines": len(PLAYER_IMAGE_DOWNLOAD_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()) if PLAYER_IMAGE_DOWNLOAD_LOG_FILE.exists() else 0,
                "items": lines,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


    def _read_manual_player_image_sources(self) -> Dict[str, str]:
        """Lee FOTOS.txt como fuente principal de fotos de jugadores.

        v77: se elimina la prioridad del JSON temporal para evitar que el
        aplicativo tome URLs de prueba como http://127.0.0.1:9/nope.
        La lógica queda igual al descargador_fotos_fifa.py: buscar pares
        "idPlayer": "https://digitalhub.fifa.com/transform/..." en FOTOS.txt.
        Solo si FOTOS.txt no existe o no trae URLs válidas, se usa
        data/player_image_sources_manual.json como respaldo.
        """
        def _clean_pid(value: Any) -> str:
            return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_")

        def _from_text(txt: str) -> Dict[str, str]:
            out: Dict[str, str] = {}
            for pid, url in re.findall(r'"(?P<id>\d+)"\s*:\s*"(?P<url>https://digitalhub\.fifa\.com/transform/[^"\\]+)"', txt, flags=re.I):
                pid_s = _clean_pid(pid)
                url_s = str(url or "").strip()
                if pid_s and url_s.startswith("https://digitalhub.fifa.com/transform/"):
                    out[pid_s] = url_s
            return dict(sorted(out.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0))

        sources: Dict[str, str] = {}

        # 1) Fuente principal: FOTOS.txt en la raíz del aplicativo.
        try:
            if PLAYER_IMAGE_MANUAL_RAW_FILE.exists():
                txt = PLAYER_IMAGE_MANUAL_RAW_FILE.read_text(encoding="utf-8", errors="ignore")
                sources = _from_text(txt)
                if sources:
                    # Reescribe el JSON de trabajo para que ya no quede un caché viejo o de prueba.
                    try:
                        PLAYER_IMAGE_MANUAL_SOURCES_FILE.parent.mkdir(parents=True, exist_ok=True)
                        PLAYER_IMAGE_MANUAL_SOURCES_FILE.write_text(
                            json.dumps({
                                "ok": True,
                                "source": "FOTOS.txt",
                                "total": len(sources),
                                "playerImageSources": sources,
                            }, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                    except Exception:
                        pass
                    return sources
        except Exception:
            sources = {}

        # 2) Respaldo: JSON manual, pero solo aceptando URLs reales de DigitalHub.
        try:
            if PLAYER_IMAGE_MANUAL_SOURCES_FILE.exists():
                raw_json = self._read_json_safe(PLAYER_IMAGE_MANUAL_SOURCES_FILE)
                if isinstance(raw_json, dict):
                    raw_sources = raw_json.get("playerImageSources") or raw_json.get("sources") or raw_json
                    if isinstance(raw_sources, dict):
                        for pid, url in raw_sources.items():
                            pid_s = _clean_pid(pid)
                            url_s = str(url or "").strip()
                            if pid_s and url_s.startswith("https://digitalhub.fifa.com/transform/"):
                                sources[pid_s] = url_s
        except Exception:
            pass
        return dict(sorted(sources.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 0))

    def player_image_sources_manual(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Devuelve todas las URLs cargadas desde FOTOS.txt/data para que el navegador las descargue y las guarde."""
        try:
            sources = self._read_manual_player_image_sources()
            existing: Dict[str, str] = {}
            local_count = 0
            for pid in sources.keys():
                local = self._existing_player_picture(pid)
                if local:
                    existing[pid] = local
                    local_count += 1
            return {
                "ok": True,
                "count": len(sources),
                "local_count": local_count,
                "missing_count": max(0, len(sources) - local_count),
                "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                "source_file": PLAYER_IMAGE_MANUAL_SOURCES_FILE.relative_to(BASE_DIR).as_posix() if PLAYER_IMAGE_MANUAL_SOURCES_FILE.exists() else PLAYER_IMAGE_MANUAL_RAW_FILE.name,
                "playerImageSources": sources,
                "existing": existing,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}



    def _manual_image_job_snapshot(self) -> Dict[str, Any]:
        with self._manual_image_job_lock:
            return dict(self._manual_image_job_status)

    def _manual_image_job_update(self, **kwargs: Any) -> None:
        with self._manual_image_job_lock:
            self._manual_image_job_status.update(kwargs)

    def _manual_image_job_event(self, message: str, level: str = "info", **extra: Any) -> None:
        """Registra un evento de descarga para mostrarlo en vivo en la UI."""
        item = {
            "ts": time.strftime("%H:%M:%S"),
            "level": level,
            "message": str(message or "")[:500],
        }
        for k, v in extra.items():
            try:
                item[k] = str(v)[:500]
            except Exception:
                pass
        with self._manual_image_job_lock:
            logs = list(self._manual_image_job_status.get("latest_logs") or [])
            logs.append(item)
            self._manual_image_job_status["latest_logs"] = logs[-120:]
            self._manual_image_job_status["last_event"] = item.get("message", "")
        try:
            self._append_player_image_log({"status": "event", "mode": "backend_manual_txt_v77", **item})
        except Exception:
            pass

    def _download_one_manual_player_image_backend(self, pid: str, url: str, force: bool = False) -> Dict[str, Any]:
        """Descarga una imagen desde FOTOS.txt usando Python backend y la guarda como p_<idPlayer>.<ext>."""
        start = time.time()
        pid_s = re.sub(r"[^A-Za-z0-9_-]+", "_", str(pid or "")).strip("_")
        url_s = self._normalise_fifa_player_picture_url(str(url or "").strip())
        base = {"idPlayer": pid_s, "source": url_s[:900], "mode": "backend_manual_txt"}
        if not pid_s or not url_s.startswith("http"):
            res = {**base, "status": "failed", "error": "idPlayer o URL inválidos", "elapsed_ms": int((time.time() - start) * 1000)}
            self._append_player_image_log(res)
            return res
        try:
            existing = self._existing_player_picture(pid_s)
            if existing and not force:
                res = {**base, "status": "skipped", "local": existing, "elapsed_ms": int((time.time() - start) * 1000)}
                self._append_player_image_log(res)
                self._manual_image_job_event(f"Omitida p_{pid_s}: ya existe", "skip", idPlayer=pid_s, file=existing)
                return res
            self._manual_image_job_event(f"Iniciando descarga p_{pid_s}", "info", idPlayer=pid_s, url=url_s)
            data, content_type = http_get_image(url_s, timeout=12, referer="https://www.fifa.com/")
            if len(data) < 100 or not (_looks_like_image_bytes(data) or (content_type or "").startswith("image/")):
                raise ValueError(f"respuesta no parece imagen; content-type={content_type or 'sin tipo'}; bytes={len(data)}")
            ext = self._image_ext_from_type_or_url(content_type, url_s, data)
            # Guardado compatible y estable para el aplicativo: siempre p_<idPlayer>.<ext>
            target = PLAYER_IMAGES_DIR / f"p_{pid_s}{ext}"
            tmp = PLAYER_IMAGES_DIR / f".tmp_p_{pid_s}{ext}"
            PLAYER_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            os.replace(tmp, target)
            if not target.exists() or target.stat().st_size < 100:
                raise ValueError("archivo local no se escribió correctamente")
            res = {
                **base,
                "status": "downloaded",
                "local": target.relative_to(BASE_DIR).as_posix(),
                "filename": target.name,
                "content_type": content_type or "image/*",
                "bytes": target.stat().st_size,
                "elapsed_ms": int((time.time() - start) * 1000),
            }
            self._append_player_image_log(res)
            self._manual_image_job_event(f"OK p_{pid_s} → {target.name} ({target.stat().st_size} bytes)", "ok", idPlayer=pid_s, file=target.name)
            return res
        except Exception as exc:
            res = {**base, "status": "failed", "error": f"{type(exc).__name__}: {str(exc)}"[:700], "elapsed_ms": int((time.time() - start) * 1000)}
            self._append_player_image_log(res)
            self._manual_image_job_event(f"ERROR p_{pid_s}: {res.get('error')}", "error", idPlayer=pid_s)
            return res

    def _run_manual_image_download_job(self, sources: Dict[str, str], force: bool, workers: int) -> None:
        started = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            items = [(str(pid), str(url)) for pid, url in sources.items() if str(url).strip().startswith("http")]
            total_urls = len(items)
            jobs: List[Tuple[str, str]] = []
            skipped_pre = 0
            for pid, url in items:
                if not force and self._existing_player_picture(pid):
                    skipped_pre += 1
                else:
                    jobs.append((pid, url))
            total_jobs = len(jobs)
            self._manual_image_job_update(
                ok=True,
                running=True,
                started_at=started,
                finished_at="",
                total_urls=total_urls,
                total=total_jobs,
                done=0,
                downloaded=0,
                skipped=skipped_pre,
                failed=0,
                errors_sample=[],
                current="",
                latest_logs=[],
                last_event="Preparando descargas",
                dir=PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                log_file=PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
                summary_file=PLAYER_IMAGE_DOWNLOAD_SUMMARY_FILE.relative_to(BASE_DIR).as_posix(),
                message=f"Descarga iniciada: {total_jobs} fotos pendientes de {total_urls} URLs. Carpeta: assets/players",
            )
            self._manual_image_job_event(f"Se leyeron {total_urls} URLs. Pendientes: {total_jobs}. Ya existentes: {skipped_pre}.", "info")
            if total_jobs == 0:
                summary = {
                    "ok": True,
                    "mode": "backend_manual_txt_v77",
                    "total_urls": total_urls,
                    "total_jobs": 0,
                    "downloaded": 0,
                    "skipped": skipped_pre,
                    "failed": 0,
                    "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                    "started_at": started,
                    "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "message": "Todas las fotos ya existían localmente.",
                }
                self._write_player_image_download_summary(summary)
                self._manual_image_job_update(running=False, finished_at=summary["finished_at"], message=summary["message"], summary=summary)
                return
            downloaded = 0
            failed = 0
            errors_sample: List[Dict[str, Any]] = []
            done = 0
            max_workers = max(1, min(int(workers or 8), 16))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                future_map = {ex.submit(self._download_one_manual_player_image_backend, pid, url, force): (pid, url) for pid, url in jobs}
                for fut in as_completed(future_map):
                    res = fut.result()
                    done += 1
                    pid = str(res.get("idPlayer") or "")
                    if res.get("status") == "downloaded":
                        downloaded += 1
                    elif res.get("status") == "skipped":
                        skipped_pre += 1
                    else:
                        failed += 1
                        if len(errors_sample) < 8:
                            errors_sample.append({"idPlayer": pid, "error": str(res.get("error") or "")[:250], "url": str(res.get("source") or "")[:300]})
                    self._manual_image_job_update(
                        done=done,
                        downloaded=downloaded,
                        skipped=skipped_pre,
                        failed=failed,
                        current=pid,
                        errors_sample=errors_sample,
                        message=f"Descargando fotos: {done}/{total_jobs} procesadas · OK {downloaded} · Error {failed} · Omitidas {skipped_pre}",
                    )
            finished = time.strftime("%Y-%m-%d %H:%M:%S")
            summary = {
                "ok": True,
                "mode": "backend_manual_txt_v77",
                "total_urls": total_urls,
                "total_jobs": total_jobs,
                "downloaded": downloaded,
                "skipped": skipped_pre,
                "failed": failed,
                "errors_sample": errors_sample,
                "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
                "started_at": started,
                "finished_at": finished,
            }
            summary["message"] = f"Descarga finalizada: {downloaded} guardadas, {failed} fallidas, {skipped_pre} omitidas."
            self._write_player_image_download_summary(summary)
            self._manual_image_job_update(running=False, finished_at=finished, message=summary["message"], summary=summary)
        except Exception as exc:
            finished = time.strftime("%Y-%m-%d %H:%M:%S")
            msg = f"Error general en descarga: {type(exc).__name__}: {exc}"
            self._manual_image_job_event(msg, "error")
            summary = {"ok": False, "mode": "backend_manual_txt_v77", "error": msg, "finished_at": finished}
            self._write_player_image_download_summary(summary)
            self._manual_image_job_update(ok=False, running=False, finished_at=finished, message=msg, summary=summary)

    def player_image_manual_download_start(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Inicia en segundo plano la descarga de todas las fotos desde FOTOS.txt/data.

        v76: se vuelve tolerante a estados colgados. Si la UI envía restart=true
        o si el hilo anterior ya no está vivo, se reinicia el estado y arranca un
        nuevo proceso. Esto evita que la pantalla quede en 0/0 sin logs.
        """
        payload = payload or {}
        restart = bool(payload.get("restart") or payload.get("force_restart") or False)
        with self._manual_image_job_lock:
            running = bool(self._manual_image_job_status.get("running"))
            thread_alive = bool(self._manual_image_job_thread and self._manual_image_job_thread.is_alive())
            if running and thread_alive and not restart:
                return dict(self._manual_image_job_status)
            if running and (restart or not thread_alive):
                # Estado anterior quedó en ejecución o el usuario pidió reiniciar.
                self._manual_image_job_status.update({
                    "running": False,
                    "message": "Reiniciando descarga TXT...",
                    "last_event": "Reiniciando descarga TXT...",
                    "latest_logs": [{"ts": time.strftime("%H:%M:%S"), "level": "warn", "message": "Se reinició una descarga anterior que no avanzaba."}],
                })

        started = time.strftime("%Y-%m-%d %H:%M:%S")
        # Publica estado inmediatamente para que la UI no se quede esperando.
        pre = {
            "ok": True,
            "running": True,
            "started_at": started,
            "finished_at": "",
            "message": "Leyendo FOTOS.txt y preparando descarga...",
            "total_urls": 0,
            "total": 0,
            "done": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "errors_sample": [],
            "latest_logs": [{"ts": time.strftime("%H:%M:%S"), "level": "info", "message": "Solicitud recibida por HTTP web: leyendo FOTOS.txt."}],
            "last_event": "Solicitud recibida por HTTP web: leyendo FOTOS.txt.",
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
        }
        self._manual_image_job_update(**pre)

        sources = self._read_manual_player_image_sources()
        if not sources:
            status = {
                "ok": False,
                "running": False,
                "message": "No se encontraron URLs en FOTOS.txt ni en data/player_image_sources_manual.json.",
                "total_urls": 0,
                "total": 0,
                "done": 0,
                "downloaded": 0,
                "skipped": 0,
                "failed": 0,
                "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
                "latest_logs": [{"ts": time.strftime("%H:%M:%S"), "level": "error", "message": "No se encontraron URLs válidas."}],
                "last_event": "No se encontraron URLs válidas.",
            }
            self._manual_image_job_update(**status)
            return status
        try:
            workers = int(payload.get("workers", 6) or 6)
        except Exception:
            workers = 6
        force = bool(payload.get("force") or False)
        initial = {
            "ok": True,
            "running": True,
            "started_at": started,
            "finished_at": "",
            "message": f"Iniciando descarga en segundo plano: {len(sources)} URLs detectadas...",
            "total_urls": len(sources),
            "total": 0,
            "done": 0,
            "downloaded": 0,
            "skipped": 0,
            "failed": 0,
            "errors_sample": [],
            "latest_logs": [
                {"ts": time.strftime("%H:%M:%S"), "level": "info", "message": "Solicitud recibida por HTTP web."},
                {"ts": time.strftime("%H:%M:%S"), "level": "info", "message": f"FOTOS.txt leído correctamente: {len(sources)} URLs."},
                {"ts": time.strftime("%H:%M:%S"), "level": "info", "message": "Iniciando hilo backend de descarga."},
            ],
            "last_event": "Iniciando hilo backend de descarga.",
            "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
            "log_file": PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix(),
        }
        self._manual_image_job_update(**initial)
        t = threading.Thread(target=self._run_manual_image_download_job, args=(sources, force, workers), daemon=True)
        self._manual_image_job_thread = t
        t.start()
        return self._manual_image_job_snapshot()

    def player_image_manual_download_status(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Devuelve progreso de la descarga backend desde FOTOS.txt."""
        status = self._manual_image_job_snapshot()
        status.setdefault("ok", True)
        status.setdefault("dir", PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix())
        status.setdefault("log_file", PLAYER_IMAGE_DOWNLOAD_LOG_FILE.relative_to(BASE_DIR).as_posix())
        try:
            status["local_files"] = len([p for p in PLAYER_IMAGES_DIR.glob("p_*.*") if p.is_file() and self._is_player_image_file(p)])
        except Exception:
            status["local_files"] = 0
        try:
            file_items: List[Dict[str, Any]] = []
            if PLAYER_IMAGE_DOWNLOAD_LOG_FILE.exists():
                lines = PLAYER_IMAGE_DOWNLOAD_LOG_FILE.read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
                for line in lines:
                    try:
                        obj = json.loads(line)
                        msg = obj.get("message") or obj.get("status") or obj.get("error") or "registro"
                        file_items.append({
                            "ts": str(obj.get("ts") or obj.get("time") or "")[-8:],
                            "level": str(obj.get("level") or obj.get("status") or "info"),
                            "message": str(msg)[:500],
                            "idPlayer": str(obj.get("idPlayer") or obj.get("player_id") or ""),
                            "error": str(obj.get("error") or "")[:300],
                        })
                    except Exception:
                        pass
            mem = list(status.get("latest_logs") or [])
            status["live_logs"] = (mem + file_items)[-80:]
        except Exception:
            status["live_logs"] = status.get("latest_logs") or []
        return status

    def player_image_status(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Verifica si las fotos están realmente descargadas en assets/players.

        No consulta squad, players.json ni FIFA Team Stats. Solo lee disco local y
        el caché actual para que la verificación sea rápida.
        """
        try:
            payload = payload or {}
            fifa_player_stats = payload.get("fifaPlayerStats") if isinstance(payload.get("fifaPlayerStats"), dict) else {}
            if not fifa_player_stats or not fifa_player_stats.get("players"):
                fifa_player_stats = self._read_fifa_player_stats_cache(max_age_seconds=None)
            if not isinstance(fifa_player_stats, dict):
                fifa_player_stats = {}
            status = self._build_player_image_status(fifa_player_stats, update_paths=True)
            if fifa_player_stats.get("players"):
                fifa_player_stats["imageCache"] = {
                    **(fifa_player_stats.get("imageCache") if isinstance(fifa_player_stats.get("imageCache"), dict) else {}),
                    "dir": PLAYER_IMAGES_DIR.relative_to(BASE_DIR).as_posix(),
                    "verified_at": status.get("updated_at"),
                    "total_players": status.get("total_players", 0),
                    "local_players": status.get("local_players", 0),
                    "missing": status.get("missing", 0),
                    "total_local_files": status.get("total_local_files", 0),
                }
                self._write_fifa_player_stats_cache(fifa_player_stats)
                base_payload = dict(payload)
                base_payload["fifaPlayerStats"] = fifa_player_stats
                self.save_results(base_payload)
            self._write_player_image_report(fifa_player_stats, status)
            total = int(status.get("total_players", 0) or 0)
            local = int(status.get("local_players", 0) or 0)
            return {
                "ok": True,
                "fifaPlayerStats": fifa_player_stats if fifa_player_stats.get("players") else {},
                "imageStatus": status,
                "message": f"Verificación de fotos: {local}/{total} jugadores tienen imagen local en {status.get('dir', 'assets/players')}.",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


    def load_fifa_player_stats(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Endpoint exclusivo de Jugadores FIFA.

        Consulta squad + players.json y actualiza solo fifaPlayerStats. No devuelve
        ni sobrescribe fifaTeamStats, porque Equipos FIFA debe mantener sus totales
        oficiales de equipo.
        """
        try:
            payload = payload or {}
            force = bool(payload.get("force", False))
            catalog: Dict[str, Dict[str, str]] = {}
            if isinstance(payload.get("fifaTeamStats"), dict):
                catalog = payload.get("fifaTeamStats", {}).get("catalog") or {}
            if not catalog:
                catalog = self._load_fifa_team_catalog(discover=True)
            fifa_player_stats = self._fetch_fifa_player_stats(force=force, catalog=catalog or {})
            fifa_player_stats = self._merge_fifa_player_stats_payload(fifa_player_stats, payload.get("fifaPlayerStats") or self._read_fifa_player_stats_cache(max_age_seconds=None))
            base_payload = dict(payload)
            base_payload["fifaPlayerStats"] = fifa_player_stats
            # Conserva fifaTeamStats existente si lo había, pero no lo modifica.
            if isinstance(payload.get("fifaTeamStats"), dict):
                base_payload["fifaTeamStats"] = payload.get("fifaTeamStats")
            self.save_results(base_payload)
            return {"ok": bool(fifa_player_stats.get("ok")), "fifaPlayerStats": fifa_player_stats, "error": fifa_player_stats.get("error")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _team_discipline_from_fifa(self, fifa_stats: Dict[str, Any]) -> Dict[str, Any]:
        rows = fifa_stats.get("teams", []) if isinstance(fifa_stats, dict) else []
        yellow = []
        red = []
        for item in rows or []:
            team = item.get("team") or self._team_from_code(item.get("code", ""))
            code = item.get("code") or TEAM_CODES.get(team, team[:3].upper())
            yellow.append({"team": team, "code": code, "value": int(item.get("yellow", 0) or 0), "source": item.get("source", "FIFA Team Stats"), "kind": "yellow"})
            total_red = int(item.get("red", 0) or 0)
            if not total_red:
                total_red = int(item.get("directRed", 0) or 0) + int(item.get("indirectRed", 0) or 0)
            red.append({"team": team, "code": code, "value": total_red, "source": item.get("source", "FIFA Team Stats"), "kind": "red"})
        yellow.sort(key=lambda x: (-int(x.get("value", 0)), str(x.get("team", ""))))
        red.sort(key=lambda x: (-int(x.get("value", 0)), str(x.get("team", ""))))
        return {
            "ok": True,
            "yellow": yellow,
            "red": red,
            "sources": fifa_stats.get("sources", []) if isinstance(fifa_stats, dict) else [],
            "notes": fifa_stats.get("notes", []) if isinstance(fifa_stats, dict) else [],
            "updated_at": fifa_stats.get("updated_at", time.strftime("%Y-%m-%d %H:%M:%S")) if isinstance(fifa_stats, dict) else time.strftime("%Y-%m-%d %H:%M:%S"),
            "source_type": "FIFA Team Stats",
        }

    def _merge_team_discipline(self, primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
        """Combina disciplina: primary (FIFA) tiene prioridad; fallback (AS) completa equipos faltantes."""
        merged = {"ok": True, "yellow": [], "red": [], "sources": [], "notes": [], "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "source_type": "FIFA + AS fallback"}
        for kind in ("yellow", "red"):
            by_code: Dict[str, Dict[str, Any]] = {}
            for src in (fallback, primary):
                for item in (src or {}).get(kind, []) or []:
                    code = str(item.get("code") or TEAM_CODES.get(str(item.get("team", "")), "")).upper()
                    if not code:
                        team = self._normalize_team_from_text(str(item.get("team", "")))
                        code = TEAM_CODES.get(team, "")
                    if not code:
                        continue
                    # al iterar fallback primero y primary después, FIFA pisa el valor de AS.com.
                    by_code[code] = dict(item)
                    by_code[code]["code"] = code
            merged[kind] = sorted(by_code.values(), key=lambda x: (-int(x.get("value", 0) or 0), str(x.get("team", ""))))
        for src in (primary, fallback):
            merged["sources"].extend((src or {}).get("sources", []) or [])
            merged["notes"].extend((src or {}).get("notes", []) or [])
        merged["sources"] = list(dict.fromkeys([str(x) for x in merged["sources"] if x]))[:16]
        merged["notes"] = list(dict.fromkeys([str(x) for x in merged["notes"] if x]))[:12]
        return merged

    def _fetch_as_team_discipline(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {"ok": True, "yellow": [], "red": [], "sources": [], "notes": [], "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        errors: List[str] = []
        for kind, url in AS_TEAM_DISCIPLINE_URLS.items():
            try:
                raw = fetch_url(url, timeout=12)
                rows = self._parse_as_team_rank(raw, kind, url)
                result[kind] = rows
                result["sources"].append(url)
                result["notes"].append(f"AS.com {('amarillas' if kind == 'yellow' else 'rojas')}: {len(rows)} equipos leídos.")
            except Exception as exc:
                errors.append(f"{kind}: {exc}")
        if not result["yellow"] and not result["red"]:
            result["ok"] = False
            result["error"] = "; ".join(errors) if errors else "No se encontraron filas de disciplina por equipos en AS.com"
        elif errors:
            result["notes"].append("Advertencias: " + "; ".join(errors))
        return result

    def _apply_team_discipline_to_stats(self, stats: Dict[str, Dict[str, Any]], discipline: Dict[str, Any]) -> None:
        if not isinstance(discipline, dict):
            return
        for kind, stat_key in (("yellow", "yellow"), ("red", "red")):
            for item in discipline.get(kind, []) or []:
                team = self._normalize_team_from_text(str(item.get("team", "") or ""))
                if not team:
                    continue
                code = TEAM_CODES.get(team, team[:3].upper())
                if team not in stats:
                    stats[team] = {
                        "team": team, "code": code, "pj": 0, "pg": 0, "pe": 0, "pp": 0,
                        "gf": 0, "gc": 0, "dg": 0, "pts": 0, "yellow": 0, "red": 0,
                        "goals_detail": 0, "assists": 0,
                    }
                try:
                    value = int(item.get("value", 0) or 0)
                except Exception:
                    value = 0
                # AS.com es fuente agregada por equipo: reemplaza el dato de disciplina, no lo suma,
                # para evitar duplicar tarjetas detectadas por jugador o por reportes.
                stats[team][stat_key] = max(0, value)

    def _load_ranking(self) -> Dict[str, Dict[str, Any]]:
        ranking = dict(FALLBACK_RANKING)
        manual_file = DATA_DIR / "ranking_fifa_manual.json"
        if manual_file.exists():
            try:
                manual = json.loads(manual_file.read_text(encoding="utf-8"))
                for code, value in manual.items():
                    ranking[code.upper()] = value
            except Exception:
                pass
        return ranking

    def _team_stats(self, matches: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}

        def ensure(team: str) -> Dict[str, Any]:
            code = TEAM_CODES.get(team, team[:3].upper())
            if team not in stats:
                stats[team] = {
                    "team": team, "code": code, "pj": 0, "pg": 0, "pe": 0, "pp": 0,
                    "gf": 0, "gc": 0, "dg": 0, "pts": 0, "yellow": 0, "red": 0, "goals_detail": 0,
                }
            return stats[team]

        for m in matches:
            h, a = m.get("h"), m.get("a")
            if not h or not a:
                continue
            hs, as_ = ensure(h), ensure(a)
            hg, ag = m.get("hg"), m.get("ag")
            if hg is None or ag is None:
                continue
            try:
                hg_i, ag_i = int(hg), int(ag)
            except Exception:
                continue
            hs["pj"] += 1; as_["pj"] += 1
            hs["gf"] += hg_i; hs["gc"] += ag_i
            as_["gf"] += ag_i; as_["gc"] += hg_i
            if hg_i > ag_i:
                hs["pg"] += 1; hs["pts"] += 3; as_["pp"] += 1
            elif hg_i < ag_i:
                as_["pg"] += 1; as_["pts"] += 3; hs["pp"] += 1
            else:
                hs["pe"] += 1; as_["pe"] += 1; hs["pts"] += 1; as_["pts"] += 1

            events = m.get("events", {}) or {}
            for side, team_stats in (("h", hs), ("a", as_)):
                team_stats["yellow"] += self._count_event_text(events.get(f"{side}Yellow", ""))
                team_stats["red"] += self._count_event_text(events.get(f"{side}Red", ""))
                team_stats["goals_detail"] += self._count_event_text(events.get(f"{side}Scorers", ""))

        for s in stats.values():
            s["dg"] = s["gf"] - s["gc"]
        return stats

    @staticmethod
    def _count_event_text(text: Any) -> int:
        if not text:
            return 0
        if isinstance(text, list):
            return len(text)
        return len([p for p in re.split(r"[,;\n]+", str(text)) if p.strip()])

    def _apply_player_events_to_stats(self, stats: Dict[str, Dict[str, Any]], player_events: Dict[str, Any]) -> None:
        if not isinstance(player_events, dict):
            return
        for kind, stat_key in (("yellow", "yellow"), ("red", "red"), ("goals", "goals_detail"), ("assists", "assists")):
            for item in player_events.get(kind, []) or []:
                team = self._normalize_team_from_text(str(item.get("team", "") or ""))
                if not team:
                    continue
                code = TEAM_CODES.get(team, team[:3].upper())
                if team not in stats:
                    stats[team] = {
                        "team": team, "code": code, "pj": 0, "pg": 0, "pe": 0, "pp": 0,
                        "gf": 0, "gc": 0, "dg": 0, "pts": 0, "yellow": 0, "red": 0,
                        "goals_detail": 0, "assists": 0,
                    }
                try:
                    count = int(item.get("count", 1) or 1)
                except Exception:
                    count = 1
                stats[team][stat_key] = stats[team].get(stat_key, 0) + max(1, count)

    def _rank_contenders(self, stats: Dict[str, Dict[str, Any]], ranking: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for team, s in stats.items():
            code = s["code"]
            rank_info = ranking.get(code, {"rank": 120, "points": 1200})
            rank = int(rank_info.get("rank", 120))
            rank_score = max(10, 100 - min(rank, 120) * 0.75)
            pj = max(1, int(s["pj"]))
            ppg = s["pts"] / pj
            gfpg = s["gf"] / pj
            gcpg = s["gc"] / pj
            win_rate = s["pg"] / pj
            result_score = min(100, max(0, ppg / 3 * 45 + win_rate * 25 + max(-10, s["dg"]) * 4 + gfpg * 8 - gcpg * 4 + 25))
            discipline_penalty = min(30, s.get("yellow", 0) * 1.2 + s.get("red", 0) * 5)
            discipline_score = max(0, 100 - discipline_penalty)
            out.append({
                **s,
                "rank": rank,
                "ranking_points": rank_info.get("points"),
                "ppg": round(ppg, 2),
                "gfpg": round(gfpg, 2),
                "gcpg": round(gcpg, 2),
                "result_score": round(result_score, 2),
                "ranking_score": round(rank_score, 2),
                "discipline_score": round(discipline_score, 2),
            })
        out.sort(key=lambda x: (x["result_score"], x["ranking_score"]), reverse=True)
        return out

    def _injury_news_signals(self, candidates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        signals: Dict[str, Dict[str, Any]] = {}
        for item in candidates:
            code = item["code"]
            team = item["team"]
            q = urllib.parse.quote(f'"{team}" World Cup 2026 injury injured doubt suspended red card')
            url = f"https://news.google.com/rss/search?q={q}&hl=es-419&gl=PE&ceid=PE:es-419"
            headlines: List[str] = []
            risk = 0
            try:
                xml_text = http_get(url, timeout=7)
                root = ET.fromstring(xml_text)
                for title in root.findall(".//item/title")[:12]:
                    text = (title.text or "").strip()
                    if text:
                        headlines.append(text)
                headlines = self._dedupe_headlines(headlines, limit=5)
                for text in headlines:
                    low = text.lower()
                    if any(w in low for w in ["injury", "injured", "lesion", "lesión", "doubt", "out", "suspended", "sancionado", "expulsado"]):
                        risk += 18
                risk = min(100, risk)
            except Exception:
                headlines = []
                risk = 0
            signals[code] = {"risk": risk, "headlines": headlines}
        return signals

