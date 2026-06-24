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


## v103 - Corrección rondas / clasificados

- La sección Rondas carga cruces FIFA aunque la fase de grupos no esté completa.
- Si un equipo ya aseguró el 1.º lugar o Top 2 por regla FIFA/desempate directo, se detecta para los cruces.
- Los cupos todavía no definidos quedan como posiciones pendientes.
- El paquete se mantiene limpio, sin auditorías ni archivos locales .bat.


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


## v108
- Persistencia durable con Supabase/PostgreSQL.
- Fallback a JSON local si Supabase no está configurado o falla.
- Protección para no reducir estadísticas FIFA/planteles con respuestas parciales.
- Endpoints nuevos: `/api/storage/status` y `/api/storage/migrate`.


## v109 - Corrección actualización JSON FIFA

- Se corrigió el parser del endpoint `fdh-api.fifa.com/v1/stats/season/.../team/...json` para aceptar lista de listas, lista de objetos, claves directas y estructuras anidadas.
- El botón de actualización forzada agrega un parámetro temporal para evitar caché intermedio.
- La posesión ahora acepta valores `0.435` y también `43.5` sin multiplicar dos veces.
- Después de actualizar FIFA, inicia sesión y presiona **Guardar** para persistir los datos en Supabase.


## v110 - Corrección TEAM_CODES

- Se corrigió el error `TEAM_CODES is not defined` que bloqueaba la actualización de Equipos/Jugadores FIFA.
- Se mantiene la persistencia en Supabase y la protección contra respuestas parciales de FIFA.
- Después de desplegar, usar Ctrl+F5, iniciar sesión, ejecutar Actualizar FIFA + análisis y presionar Guardar.


## v111 - Fechas en rondas eliminatorias
- Se agregaron fecha y hora referencial en Perú para Ronda de 32, Ronda de 16, Cuartos, Semifinales, 3er puesto y Final.
- Las fechas se muestran dentro de cada tarjeta M73-M104 en la sección Rondas.


## v112 - Rondas por secciones

- La sección Rondas ahora se muestra de arriba hacia abajo por secciones.
- Cada etapa tiene su propio bloque: Ronda de 32, Ronda de 16, Cuartos, Semifinales, 3er puesto y Final.
- Se mantiene fecha y hora referencial por partido, login, Supabase y bloqueo de edición.
