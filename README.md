# Fixture Mundial 2026 - Versión Web Limpia v102

Esta carpeta contiene solo los archivos necesarios para publicar la versión web del sistema.

## Archivos incluidos

- `web_app.py`: entrada Flask/WSGI para hosting.
- `backend.py`: lógica del sistema, consultas FIFA, guardado, jugadores, análisis y rondas.
- `app_mundial_2026.html`: interfaz web.
- `requirements.txt`: dependencias de producción.
- `Procfile`: comando para Render/Railway.
- `render.yaml`: configuración sugerida para Render.
- `assets/`: imágenes y recursos visuales.
- `data/`: archivos de soporte iniciales.
- `FOTOS.txt`: fuente manual de URLs para fotos de jugadores.
- `README_PUBLICACION_WEB.md`: pasos de publicación.

## Qué se retiró

- Auditorías históricas `AUDITORIA_*.md`.
- Archivos `.bat` de ejecución local Windows.
- Archivos de versión PC/local como `requirements-local.txt`, `estructura.txt`, `README_COMPLETO_v86.txt` y scripts auxiliares locales.

## Ejecutar localmente como web

```bash
pip install -r requirements.txt
python web_app.py
```

Abrir:

```text
http://127.0.0.1:10000
```

## Publicar en Render

Build Command:

```text
pip install -r requirements.txt
```

Start Command:

```text
gunicorn web_app:app --workers 1 --threads 8 --timeout 180
```

Variable recomendada:

```text
FIXTURE_DATA_DIR=/tmp/fixture_mundial_2026
```

Para persistencia real en producción, usar un disco persistente o base de datos externa.
