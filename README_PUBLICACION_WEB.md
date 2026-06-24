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

## v108 - Persistencia durable con Supabase

Esta versión ya no depende únicamente del archivo JSON temporal de Render. Si configuras Supabase, los resultados, rondas, jugadores, estadísticas FIFA y análisis se guardan en una tabla PostgreSQL externa.

### Variables de entorno necesarias en Render

Configura en Render > Environment:

- `SUPABASE_URL`: URL del proyecto Supabase, ejemplo `https://xxxxx.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY`: Service role key del proyecto Supabase
- `SUPABASE_TABLE`: `app_state`
- `APP_STATE_KEY`: `fixture_mundial_2026`
- `APP_LOGIN_USER`: `vglasinovich`
- `APP_LOGIN_PASSWORD`: tu contraseña de edición
- `SECRET_KEY`: cualquier valor largo aleatorio para la sesión Flask

### SQL para crear la tabla en Supabase

Ejecuta esto en Supabase > SQL Editor:

```sql
create table if not exists public.app_state (
  key text primary key,
  data jsonb not null,
  updated_at timestamptz not null default now()
);

alter table public.app_state enable row level security;
```

La app escribe desde el backend usando `SUPABASE_SERVICE_ROLE_KEY`, por eso esa clave solo debe ir en Render como variable de entorno y nunca en el HTML.

### Migración inicial

Después del deploy v108:

1. Abre la web en el mismo navegador donde ya tenías tus resultados.
2. Inicia sesión.
3. Presiona `Guardar` una vez.
4. Ese guardado sube el estado actual a Supabase.
5. Desde ese momento los siguientes usuarios/navegadores cargarán la data desde Supabase.

### Verificación

Abre:

`/api/storage/status`

Debe responder con `storage: supabase`, `supabase_configured: true` y `has_data: true` después del primer guardado.


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
