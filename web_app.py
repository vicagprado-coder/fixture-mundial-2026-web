# -*- coding: utf-8 -*-
"""Versión web publicable del Fixture Mundial 2026.

Este archivo expone el aplicativo como una aplicación WSGI/Flask para
publicarla en Render, Railway, Fly.io, PythonAnywhere u otro hosting Python.

Start command sugerido:
    gunicorn web_app:app --workers 1 --threads 8 --timeout 180
"""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Callable, Dict

from flask import Flask, Response, jsonify, make_response, request, send_from_directory

# Importa toda la lógica existente sin usar archivos BAT ni consola local.
import backend as fixture_backend

BASE_DIR: Path = fixture_backend.BASE_DIR
HTML_FILE: Path = fixture_backend.HTML_FILE
api = fixture_backend.AppApi()

app = Flask(__name__, static_folder=None)
app.config["JSON_AS_ASCII"] = False


def _json(payload: Dict[str, Any], status: int = 200) -> Response:
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.after_request
def add_common_headers(response: Response) -> Response:
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    # El HTML principal no se cachea; assets sí pueden cachearse.
    return response


def _serve_html() -> Response:
    html = HTML_FILE.read_text(encoding="utf-8")
    try:
        state = api.load_results().get("data")
    except Exception:
        state = None
    boot = (
        "<script>"
        "window.__APP_MODE__='web';"
        "window.__INITIAL_STATE__ = " + json.dumps(state, ensure_ascii=False) + ";"
        "</script>"
    )
    if "</head>" in html:
        html = html.replace("</head>", boot + "\n</head>", 1)
    else:
        html = boot + html
    response = make_response(html)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/", methods=["GET"])
@app.route("/app_mundial_2026.html", methods=["GET"])
def index() -> Response:
    return _serve_html()


@app.route("/health", methods=["GET"])
def health() -> Response:
    return _json({"ok": True, "mode": "web", "app": fixture_backend.APP_TITLE})


@app.route("/assets/<path:filename>", methods=["GET"])
def assets(filename: str) -> Response:
    return send_from_directory(BASE_DIR / "assets", filename)


@app.route("/data/<path:filename>", methods=["GET"])
def data_files(filename: str) -> Response:
    return send_from_directory(BASE_DIR / "data", filename)


@app.route("/<path:filename>", methods=["GET"])
def root_files(filename: str) -> Response:
    """Compatibilidad con rutas locales antiguas.

    Algunas referencias históricas apuntaban a /logo_mundial_2026.webp o
    /fondo_total_mundial_2026.jpg. Primero se buscan en BASE_DIR y luego en assets.
    """
    safe = filename.strip("/")
    if not safe or ".." in safe.split("/"):
        return _json({"ok": False, "error": "Ruta inválida"}, 400)
    direct = BASE_DIR / safe
    if direct.exists() and direct.is_file():
        return send_from_directory(BASE_DIR, safe)
    asset = BASE_DIR / "assets" / safe
    if asset.exists() and asset.is_file():
        return send_from_directory(BASE_DIR / "assets", safe)
    return _json({"ok": False, "error": "Archivo no encontrado"}, 404)


def _payload() -> Dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    raw = request.get_data(as_text=True) or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


GET_MAP: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "load": lambda p: api.load_results(p),
    "cache_flags": lambda p: api.cache_flags(p),
    "player_image_status": lambda p: api.player_image_status(p),
    "player_image_log": lambda p: api.player_image_log(p),
    "player_image_sources_manual": lambda p: api.player_image_sources_manual(p),
    "player_image_manual_download_status": lambda p: api.player_image_manual_download_status(p),
}

POST_MAP: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "save": api.save_results,
    "analyze_full": api.analyze_full,
    "analyze": api.analyze_internet,
    "sync": api.sync_from_internet,
    "player_stats": api.load_player_stats,
    "fifa_team_stats": api.load_fifa_team_stats,
    "fifa_player_stats": api.load_fifa_player_stats,
    "cache_player_images": api.cache_player_images,
    "player_image_save": api.player_image_save,
    "player_image_attempt_log": api.player_image_attempt_log,
    "player_image_status": api.player_image_status,
    "player_image_log": api.player_image_log,
    "player_image_sources_manual": api.player_image_sources_manual,
    "player_image_manual_download_start": api.player_image_manual_download_start,
    "player_image_manual_download_status": api.player_image_manual_download_status,
    "search_events": api.search_match_events,
    "cache_flags": api.cache_flags,
}


@app.route("/api/status", methods=["GET"])
def api_status() -> Response:
    return _json({
        "ok": True,
        "mode": "web",
        "backend": "flask",
        "data_file": str(fixture_backend.DATA_FILE),
        "backup_file": str(fixture_backend.LOCAL_DATA_FILE),
        "flags_dir": str(fixture_backend.FLAGS_DIR),
        "player_images_dir": str(fixture_backend.PLAYER_IMAGES_DIR),
    })


@app.route("/api/close", methods=["POST", "OPTIONS"])
def api_close() -> Response:
    # En hosting web NO se debe apagar el servidor. El botón puede cerrar la pestaña
    # desde el navegador, pero el backend debe seguir vivo para otros usuarios.
    if request.method == "OPTIONS":
        return _json({"ok": True})
    return _json({"ok": True, "mode": "web", "message": "Modo web: puedes cerrar la pestaña; el servidor queda activo."})


@app.route("/api/<path:name>", methods=["GET", "POST", "OPTIONS"])
def api_routes(name: str) -> Response:
    if request.method == "OPTIONS":
        return _json({"ok": True})
    key = name.strip("/")
    try:
        if request.method == "GET":
            fn = GET_MAP.get(key)
            if fn:
                return _json(fn({}))
        elif request.method == "POST":
            fn = POST_MAP.get(key)
            if fn:
                return _json(fn(_payload()))
        return _json({"ok": False, "error": f"Ruta API no encontrada: {key}"}, 404)
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)}, 500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
