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
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests
from flask import Flask, Response, jsonify, make_response, request, send_from_directory, session

# Importa toda la lógica existente sin usar archivos BAT ni consola local.
import backend as fixture_backend

BASE_DIR: Path = fixture_backend.BASE_DIR
HTML_FILE: Path = fixture_backend.HTML_FILE
api = fixture_backend.AppApi()

app = Flask(__name__, static_folder=None)
app.config["JSON_AS_ASCII"] = False
# Sesión de edición: solo usuarios autenticados pueden guardar o actualizar datos.
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "fixture-mundial-2026-web-session-v105")
APP_LOGIN_USER = os.environ.get("APP_LOGIN_USER", "vglasinovich")
APP_LOGIN_PASSWORD = os.environ.get("APP_LOGIN_PASSWORD", "vicglasi061290")


# Persistencia durable opcional con Supabase/Postgres.
# Si estas variables existen en Render, la app guarda ahí en lugar de depender
# del disco temporal de Render. Si no existen, conserva el JSON local como fallback.
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_TABLE = (os.environ.get("SUPABASE_TABLE") or "app_state").strip()
APP_STATE_KEY = (os.environ.get("APP_STATE_KEY") or "fixture_mundial_2026").strip()


def _supabase_enabled() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY and SUPABASE_TABLE and APP_STATE_KEY)


def _supabase_headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _supabase_endpoint(query: str = "") -> str:
    return f"{SUPABASE_URL}/rest/v1/{SUPABASE_TABLE}{query}"


def _merge_payload_preserving_good_data(payload: Dict[str, Any], existing: Dict[str, Any] | None) -> Dict[str, Any]:
    """Evita que una respuesta parcial de FIFA reduzca datos ya buenos."""
    payload = dict(payload or {})
    existing = existing if isinstance(existing, dict) else {}
    try:
        if isinstance(payload.get("fifaTeamStats"), dict) and isinstance(existing.get("fifaTeamStats"), dict):
            payload["fifaTeamStats"] = api._merge_fifa_team_stats(payload.get("fifaTeamStats") or {}, existing.get("fifaTeamStats") or {})
        if isinstance(payload.get("fifaPlayerStats"), dict) and isinstance(existing.get("fifaPlayerStats"), dict):
            payload["fifaPlayerStats"] = api._merge_fifa_player_stats_payload(payload.get("fifaPlayerStats") or {}, existing.get("fifaPlayerStats") or {})
    except Exception:
        # Si por alguna razón el merge protector falla, no se bloquea el guardado completo.
        pass
    return payload


def _supabase_load() -> Dict[str, Any]:
    if not _supabase_enabled():
        return {"ok": False, "storage": "local", "error": "Supabase no configurado"}
    try:
        url = _supabase_endpoint(f"?key=eq.{APP_STATE_KEY}&select=key,data,updated_at&limit=1")
        r = requests.get(url, headers=_supabase_headers(), timeout=20)
        if r.status_code >= 400:
            return {"ok": False, "storage": "supabase", "error": r.text, "status_code": r.status_code}
        rows = r.json() if r.text else []
        if rows:
            data = rows[0].get("data")
            return {"ok": True, "data": data, "path": f"Supabase:{SUPABASE_TABLE}/{APP_STATE_KEY}", "storage": "supabase", "updated_at": rows[0].get("updated_at")}
        return {"ok": True, "data": None, "path": f"Supabase:{SUPABASE_TABLE}/{APP_STATE_KEY}", "storage": "supabase", "empty": True}
    except Exception as exc:
        return {"ok": False, "storage": "supabase", "error": str(exc)}


def _supabase_save(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _supabase_enabled():
        return {"ok": False, "storage": "local", "error": "Supabase no configurado"}
    existing_res = _supabase_load()
    existing = existing_res.get("data") if existing_res.get("ok") else None
    payload = _merge_payload_preserving_good_data(payload or {}, existing)
    payload["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    body = {"key": APP_STATE_KEY, "data": payload, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        r = requests.post(
            _supabase_endpoint("?on_conflict=key"),
            headers=_supabase_headers({"Prefer": "resolution=merge-duplicates,return=representation"}),
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            timeout=30,
        )
        if r.status_code >= 400:
            return {"ok": False, "storage": "supabase", "error": r.text, "status_code": r.status_code}
        # Backup local temporal para diagnóstico. La fuente durable es Supabase.
        try:
            api.save_results(payload)
        except Exception:
            pass
        return {"ok": True, "path": f"Supabase:{SUPABASE_TABLE}/{APP_STATE_KEY}", "storage": "supabase", "saved_at": payload["saved_at"]}
    except Exception as exc:
        return {"ok": False, "storage": "supabase", "error": str(exc)}


def _persistent_load(payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if _supabase_enabled():
        res = _supabase_load()
        if res.get("ok") and res.get("data"):
            return res
        # Si Supabase aún está vacío, se intenta leer el JSON local como respaldo inicial.
        local = api.load_results(payload or {})
        if local.get("ok") and local.get("data"):
            local["storage"] = "local_fallback"
            local["path"] = local.get("path") or "JSON local"
            local["message"] = "Supabase configurado pero vacío; se cargó respaldo local. Presiona Guardar con sesión iniciada para migrarlo."
            return local
        return res
    local = api.load_results(payload or {})
    local["storage"] = "local"
    return local


def _persistent_save(payload: Dict[str, Any]) -> Dict[str, Any]:
    if _supabase_enabled():
        res = _supabase_save(payload or {})
        if res.get("ok"):
            return res
        # Si falla Supabase, no se pierde la operación: se guarda en JSON local temporal.
        local = api.save_results(payload or {})
        local["storage"] = "local_fallback"
        local["warning"] = "No se pudo guardar en Supabase; quedó en JSON temporal de Render."
        local["supabase_error"] = res.get("error")
        return local
    local = api.save_results(payload or {})
    local["storage"] = "local"
    return local


def _json(payload: Dict[str, Any], status: int = 200) -> Response:
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "no-store"
    return response


def _is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def _auth_payload() -> Dict[str, Any]:
    return {"ok": True, "authenticated": _is_authenticated(), "user": session.get("user") if _is_authenticated() else None}


def _auth_required() -> Response | None:
    if _is_authenticated():
        return None
    return _json({"ok": False, "auth_required": True, "error": "Debes iniciar sesión para registrar o actualizar datos."}, 401)


@app.after_request
def add_common_headers(response: Response) -> Response:
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type, Authorization")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    # El HTML principal no se cachea; assets sí pueden cachearse.
    return response


def _serve_html() -> Response:
    html = HTML_FILE.read_text(encoding="utf-8")
    # v139: no inyectar el estado completo en el HTML.
    # El estado puede incluir planteles/jugadores y crecer varios MB; cargarlo en el HTML
    # duplica memoria en Chrome y puede provocar Out of Memory al abrir Análisis.
    # La app lo solicita después por /api/load.
    state = None
    boot = (
        "<script>"
        "window.__APP_MODE__='web';"
        "window.__INITIAL_STATE__ = " + json.dumps(state, ensure_ascii=False) + ";"
        "window.__AUTH__ = " + json.dumps(_auth_payload(), ensure_ascii=False) + ";"
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
    "load": lambda p: _persistent_load(p),
    "cache_flags": lambda p: api.cache_flags(p),
    "player_image_status": lambda p: api.player_image_status(p),
    "player_image_log": lambda p: api.player_image_log(p),
    "player_image_sources_manual": lambda p: api.player_image_sources_manual(p),
    "player_image_manual_download_status": lambda p: api.player_image_manual_download_status(p),
}

PUBLIC_POST_ACTIONS = {"player_image_status", "player_image_log", "player_image_manual_download_status"}

POST_MAP: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "save": _persistent_save,
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


@app.route("/api/session", methods=["GET"])
def api_session() -> Response:
    return _json(_auth_payload())


@app.route("/api/login", methods=["POST", "OPTIONS"])
def api_login() -> Response:
    if request.method == "OPTIONS":
        return _json({"ok": True})
    data = _payload()
    user = str(data.get("username") or data.get("user") or "").strip()
    password = str(data.get("password") or "")
    if user == APP_LOGIN_USER and password == APP_LOGIN_PASSWORD:
        session["authenticated"] = True
        session["user"] = APP_LOGIN_USER
        return _json({"ok": True, "authenticated": True, "user": APP_LOGIN_USER})
    session.clear()
    return _json({"ok": False, "authenticated": False, "error": "Usuario o contraseña incorrectos."}, 401)


@app.route("/api/logout", methods=["POST", "OPTIONS"])
def api_logout() -> Response:
    if request.method == "OPTIONS":
        return _json({"ok": True})
    session.clear()
    return _json({"ok": True, "authenticated": False})


@app.route("/api/status", methods=["GET"])
def api_status() -> Response:
    return _json({
        "ok": True,
        "mode": "web",
        "backend": "flask",
        "authenticated": _is_authenticated(),
        "user": session.get("user") if _is_authenticated() else None,
        "data_file": str(fixture_backend.DATA_FILE),
        "backup_file": str(fixture_backend.LOCAL_DATA_FILE),
        "storage": "supabase" if _supabase_enabled() else "local",
        "supabase_configured": _supabase_enabled(),
        "supabase_table": SUPABASE_TABLE if _supabase_enabled() else None,
        "app_state_key": APP_STATE_KEY if _supabase_enabled() else None,
        "flags_dir": str(fixture_backend.FLAGS_DIR),
        "player_images_dir": str(fixture_backend.PLAYER_IMAGES_DIR),
    })



@app.route("/api/storage/status", methods=["GET"])
def api_storage_status() -> Response:
    res = _persistent_load({})
    return _json({
        "ok": True,
        "storage": "supabase" if _supabase_enabled() else "local",
        "supabase_configured": _supabase_enabled(),
        "table": SUPABASE_TABLE if _supabase_enabled() else None,
        "key": APP_STATE_KEY if _supabase_enabled() else None,
        "has_data": bool(res.get("data")),
        "loaded_from": res.get("storage"),
        "path": res.get("path"),
        "message": res.get("message"),
        "error": res.get("error"),
    })


@app.route("/api/storage/migrate", methods=["POST", "OPTIONS"])
def api_storage_migrate() -> Response:
    if request.method == "OPTIONS":
        return _json({"ok": True})
    blocked = _auth_required()
    if blocked is not None:
        return blocked
    if not _supabase_enabled():
        return _json({"ok": False, "error": "Supabase no configurado en Render."}, 400)
    local = api.load_results({})
    data = local.get("data")
    if not data:
        return _json({"ok": False, "error": "No se encontró data local para migrar."}, 404)
    saved = _supabase_save(data)
    status = 200 if saved.get("ok") else 500
    return _json(saved, status)


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
                if key not in PUBLIC_POST_ACTIONS:
                    blocked = _auth_required()
                    if blocked is not None:
                        return blocked
                return _json(fn(_payload()))
        return _json({"ok": False, "error": f"Ruta API no encontrada: {key}"}, 404)
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)}, 500)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
