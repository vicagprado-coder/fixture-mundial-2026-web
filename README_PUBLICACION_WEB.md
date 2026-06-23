# Fixture Mundial 2026 - Versión Web Publicable

Esta versión convierte el aplicativo local en una app web Python publicable.

## Qué mantiene

- Fixture, tablas, terceros, clasificados/eliminados y rondas.
- Regla FIFA de desempate directo / victoria olímpica.
- Primer lugar asegurado, Top 2, mejores terceros y eliminados matemáticos.
- Equipos FIFA, jugadores FIFA y análisis del posible campeón.
- Actualización a FIFA desde el botón correspondiente.
- Guardado de resultados mediante backend Python.

## Archivos principales

- `web_app.py`: entrada web para hosting.
- `backend.py`: lógica del sistema.
- `app_mundial_2026.html`: interfaz.
- `requirements.txt`: dependencias para hosting.
- `Procfile`: comando para plataformas tipo Render/Railway.
- `render.yaml`: configuración lista para Render.

## Ejecutar local como web

```bash
pip install -r requirements.txt
python web_app.py
```

Abrir:

```text
http://127.0.0.1:10000
```

## Publicar en Render

1. Crear repositorio en GitHub.
2. Subir todos los archivos de esta carpeta.
3. En Render, crear `New Web Service` desde el repositorio.
4. Usar:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn web_app:app --workers 1 --threads 8 --timeout 180
```

5. Variable recomendada:

```text
FIXTURE_DATA_DIR=/tmp/fixture_mundial_2026
```

## Nota sobre persistencia

En hosting gratuito, el guardado en archivos puede reiniciarse si la plataforma reconstruye o reinicia el servicio. Para una publicación permanente, conviene conectar una base de datos gratuita como Supabase/PostgreSQL o usar disco persistente si el hosting lo permite.

## Diferencia contra la versión PC

- No se incluyen `.bat` en esta versión limpia.
- El botón `Cerrar` en web no apaga el servidor; solo sirve como cierre/retorno visual.
- El backend queda activo para que la app siga disponible por link.


## v104 - Rondas en español y mayúsculas

- Los equipos en la sección Rondas se muestran en español y en mayúsculas.
- Si el valor interno viene en inglés, por ejemplo `Germany`, se visualiza como `ALEMANIA`.
- Al guardar una ronda, el equipo se normaliza internamente para mantener la lógica de ganadores y avance.


## Versión v105 - sesión de edición

La web queda en modo visualización para cualquier visitante. Solo al iniciar sesión se habilitan acciones de registro o actualización: guardar marcadores, actualizar FIFA/análisis, cargar cruces, editar rondas, reiniciar rondas y guardar datos.

Para mayor seguridad en Render, puedes definir variables de entorno:

- `APP_LOGIN_USER`
- `APP_LOGIN_PASSWORD`
- `SECRET_KEY`

Si no se definen, la app usa las credenciales configuradas por defecto para esta entrega.


## v106 - Protección de estadísticas FIFA

- La actualización ya no reduce equipos ni jugadores si FIFA devuelve una respuesta parcial.
- Se prueban todas las variantes de slug configuradas para resolver IdTeam.
- El guardado del backend conserva el último dato bueno de FIFA cuando el navegador/API trae menos datos.


## v107
- Corrige la vista Rondas: se definió correctamente `lock` en los cruces eliminatorios.
- En modo lectura, los inputs de rondas quedan deshabilitados; con sesión iniciada se habilitan.
