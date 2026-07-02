# CONTEXT.md — ShineAndBright SupplyPro → Jobber

Documento de contexto para sesiones futuras de Claude Code.  
Última actualización: 2026-04-17

---

## ¿Qué es este proyecto?

**ShineAndBright** es una empresa de limpieza de casas nuevas en construcción (post-construction cleaning). Sus clientes son builders (constructoras) que les asignan trabajos a través de **SupplyPro**, una plataforma legacy de gestión de órdenes de trabajo para subcontratistas de construcción.

El equipo de ShineAndBright recibe órdenes en SupplyPro y las necesita en **Jobber** (su sistema de gestión de trabajos) para crear Jobs, luego convertirlos en Invoices, y que esas Invoices lleguen a **QuickBooks Online** para facturación.

**El problema:** Antes del proyecto, el flujo era 100% manual:
1. Alguien entraba a SupplyPro, exportaba un CSV a mano
2. Subía ese CSV a Jobber usando la función de importar órdenes
3. Convertía cada orden a invoice manualmente
4. Mandaba las invoices a QuickBooks a mano

**La solución:** Esta app automatiza todo excepto el paso de conversión a invoice (que el equipo hace manualmente en Jobber para poder ajustar precios antes de facturar).

---

## Flujo final automatizado

```
SupplyPro (web scraping)
        ↓
  Tabla editable en el app
  (el equipo revisa y ajusta)
        ↓
  Click "Subir a Jobber"
        ↓
  Jobs creados en Jobber via API GraphQL
        ↓
  El equipo convierte Jobs → Invoices en Jobber
  (ajustan precios si hace falta)
        ↓
  Jobber sync nativa → QuickBooks Online
  (solo cuando el equipo marca la invoice como "sent")
```

**Importante:** QuickBooks Online NO se toca con código. La sincronización es 100% nativa de Jobber (integración one-way Jobber→QBO). El admin de Jobber activa esa integración una sola vez.

---

## Stack técnico

| Componente | Tecnología |
|---|---|
| Frontend / UI | Streamlit (Python) |
| Deploy | Streamlit Cloud |
| Repo | GitHub: https://github.com/FroDev-CR/WorkSyncExtractor |
| App URL | https://worksyncextractor.streamlit.app |
| Scraping SupplyPro | Playwright (browser headless) |
| API Jobber | GraphQL REST — `POST https://api.getjobber.com/api/graphql` |
| Auth Jobber | OAuth 2.0 Authorization Code Grant |
| Token storage | SQLite local (`jobber_tokens.db`, ignorado en git) |
| i18n | Módulo propio, español por default, toggle a inglés |

---

## Clientes de ShineAndBright (builders)

Solo hay 3 builders activos. Ya existen en Jobber — **nunca crear duplicados**:

| Nombre en SupplyPro | Nombre normalizado en Jobber |
|---|---|
| `LGI Homes *` | `LGI Homes` |
| `DRB Group *` | `DRB Group` |
| `Lennar Homes *` | `Lennar Homes` |

El mapeo está en `config.py → SHINE_CLIENT_MAP`.

---

## Estructura de archivos

```
/
├── app.py                  — UI Streamlit + flujo OAuth callback + upload logic
├── scraper.py              — Playwright scraper para SupplyPro (NO MODIFICAR LÓGICA)
├── transformer.py          — Transforma DataFrame crudo (NO MODIFICAR LÓGICA)
├── config.py               — Constantes, mapas de reglas, lee credenciales de st.secrets
├── logger.py               — Logging centralizado (INFO por default, DEBUG con LOG_LEVEL=DEBUG)
├── requirements.txt        — Dependencias Python
├── packages.txt            — Dependencias sistema (Playwright)
├── README.md               — Guía de setup completa
├── TESTING.md              — Checklist de pruebas manual
├── CONTEXT.md              — Este archivo
│
├── jobber/
│   ├── __init__.py
│   ├── storage.py          — SQLite wrapper para tokens OAuth (id=1, una sola cuenta)
│   ├── oauth.py            — OAuth 2.0: build_auth_url, exchange_code, refresh_tokens, handle_callback
│   ├── client.py           — JobberClient: execute(), fetch_account(), enrich_account_info()
│   ├── mutations.py        — Queries/mutations GraphQL como constantes string
│   └── mappers.py          — parse_total, parse_date_iso, parse_address, map_row_to_job_input, validate_row
│
├── i18n/
│   ├── __init__.py         — Helper t(key, **kwargs), lee st.session_state.lang
│   ├── es.py               — Diccionario de strings en español
│   └── en.py               — Diccionario en inglés
│
└── .streamlit/
    ├── config.toml         — Tema visual (primaryColor: #00C2FF)
    ├── post_install.sh     — Instala browsers de Playwright en Streamlit Cloud
    └── secrets.toml.example — Template (el real NO va al repo)
```

---

## Secrets requeridos (Streamlit Cloud → Settings → Secrets)

```toml
SUPPLYPRO_USERNAME = "programmer01"
SUPPLYPRO_PASSWORD = "Shineandbright"

JOBBER_CLIENT_ID     = "1b469383-78e7-4696-8b6c-d027b1db0011"
JOBBER_CLIENT_SECRET = "<rotar en Jobber Developer Center>"
APP_URL              = "https://worksyncextractor.streamlit.app/"
```

> ⚠️ El Client Secret fue expuesto en el chat de desarrollo. Debe rotarse en https://developer.getjobber.com antes de usar en producción.

---

## Jobber API — detalles clave

- **Endpoint:** `POST https://api.getjobber.com/api/graphql`
- **Header versión:** `X-JOBBER-GRAPHQL-VERSION: 2025-01-20`
- **OAuth Callback URL configurado:** `https://worksyncextractor.streamlit.app/`
- **Scopes:** `read_clients`, `write_clients`, `read_jobs`, `write_jobs`, `read_users`
- **Refresh Token Rotation:** ON — cada vez que se refresca, se guarda el NUEVO refresh token (el viejo se invalida)
- **Rate limit:** leaky bucket 10,000 pts, restaura 500/s. Para 40 órdenes son ~120 requests (~360 pts) — sin problema
- **Throttling:** si recibe error `THROTTLED`, el cliente espera y reintenta automáticamente (máx 3 intentos)

### Mutations implementadas en `jobber/mutations.py`
| Constante | Propósito |
|---|---|
| `FIND_CLIENT_QUERY` | Buscar builder por nombre (searchTerm) |
| `CREATE_CLIENT_MUTATION` | Crear builder si no existe (fallback) |
| `FIND_PROPERTY_QUERY` | Listar properties de un cliente |
| `CREATE_PROPERTY_MUTATION` | Crear nueva property/dirección |
| `CREATE_JOB_MUTATION` | Crear Job con clientId, propertyId, lineItems, startAt |
| `ACCOUNT_QUERY` | Obtener nombre e id de la cuenta conectada |

### Flujo de subida por orden
1. `get_or_find_client(name)` — busca en cache local, si no query a Jobber, si no existe lo crea
2. `get_or_create_property(client_id, address)` — busca en cache, si no lista properties del cliente y compara `street1`, si no existe la crea
3. `map_row_to_job_input(row, client_id, property_id)` — construye el dict de atributos para `jobCreate`
4. `client.execute(CREATE_JOB_MUTATION, {"attributes": attributes})` — crea el Job
5. Marca la fila como `Ya subido = True` en `st.session_state.df_editor`

---

## DataFrame — columnas finales de SupplyPro

El scraper + transformer producen estas 5 columnas:

| Columna | Ejemplo | Notas |
|---|---|---|
| `Client Name` | `LGI Homes` | Normalizado por SHINE_CLIENT_MAP |
| `Job title Final` | `ROUGH CLEAN / LOT 1234 / Bell Farm 50 / SP-00001` | Formato: `{instrucción} / LOT {lote} / {subdivisión} / {número orden}` |
| `Full Property Address` | `123 Main St, Austin, TX 78610` | Dirección de la propiedad |
| `total` | `$1,234.56` | String con símbolo y comas — parse con `mappers.parse_total()` |
| `Start Date` | `04/15/2026` | Formato MM/DD/YYYY — convertir con `mappers.parse_date_iso()` |

---

## app.py — flujo de renderizado

El app sigue este orden en cada rerun de Streamlit:

1. `install_playwright()` — cached, solo corre una vez
2. Imports de módulos propios
3. `oauth.handle_callback()` — detecta `?code=` en URL, intercambia por tokens, limpia params
4. **Sidebar:** toggle idioma + estado Jobber (conectado/desconectado + botones)
5. **Main:** botón "Exportar" → spinner → extracción → transformación → inicializar `df_editor`
6. **Tabla editable:** `st.data_editor` con col Subir + validaciones
7. **Botón Subir a Jobber:** solo visible si hay tokens + filas pendientes → setea `trigger_upload` en session_state → `st.rerun()`
8. **Upload loop:** si `trigger_upload` en session_state, procesa todas las filas marcadas
9. **Reporte:** tabla con resultados, links, botón descargar, botón reintentar fallidas

### session_state keys importantes
| Key | Tipo | Propósito |
|---|---|---|
| `lang` | `str` ("es"/"en") | Idioma activo |
| `df_result` | `DataFrame \| None` | Datos crudos extraídos |
| `df_editor` | `DataFrame \| None` | Datos editados con cols Subir/Ya subido |
| `upload_report` | `list \| None` | Resultados del último batch de subida |
| `trigger_upload` | `bool` | Flag para disparar upload en el siguiente rerun |
| `oauth_state` | `str` | State CSRF para validar callback OAuth |
| `jobber_just_connected` | `bool` | Flag para mostrar mensaje de éxito post-OAuth |

---

## Estado del proyecto (2026-04-17)

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Higiene del repo, secrets, estructura | ✅ Completo |
| 1 | i18n ES/EN con toggle en sidebar | ✅ Completo |
| 2 | OAuth Jobber + cliente GraphQL + storage SQLite | ✅ Completo |
| 3 | Tabla editable (`st.data_editor`) + mappers | ✅ Completo |
| 4 | Lógica de subida a Jobber + reporte + reintentar | ✅ Completo |
| 5 | README, TESTING.md, logging centralizado | ✅ Completo |
| **Test end-to-end** | Probar subida real con credenciales Jobber | ⏳ Pendiente |

### Pendiente para test end-to-end
1. Admin conecta con OAuth (ya funciona el redirect, falta confirmar el exchange)
2. Exportar 2-3 órdenes de prueba desde SupplyPro
3. Subir a Jobber y verificar:
   - Jobs creados correctamente en Jobber
   - Cliente correcto (no duplicado)
   - Property correcta (creada o reutilizada)
   - Line item con monto correcto
   - Fecha de inicio correcta
4. **Posibles ajustes de schema GraphQL** — los nombres de campos de `JobCreateAttributes` pueden diferir de lo implementado. Si la API devuelve `userErrors`, revisar y corregir en `mutations.py` y `mappers.py`
5. Verificar integración Jobber → QBO end-to-end (una invoice marcada como "sent" debe llegar a QBO)

---

## Reglas y restricciones del proyecto

- **NO tocar** la lógica de `scraper.py` ni `transformer.py` — funcionan y son frágiles
- **NO usar** la API de QuickBooks — la sync es 100% nativa de Jobber
- **NO hardcodear** credenciales — todo va en `st.secrets` o variables de entorno
- **NO crear clientes duplicados** en Jobber — siempre buscar primero por nombre exacto
- **NO asumir el schema GraphQL** — validar en GraphiQL si algo falla con `userErrors`
- **El `refresh_token` rota** — cada vez que se refresca, el nuevo token DEBE guardarse inmediatamente (el viejo se invalida)
- Al editar en la tabla, los cambios van a `st.session_state.df_editor` — siempre leer de ahí, no de `df_result`

---

## Cómo continuar desde cero en una nueva sesión

1. Leer este archivo
2. Revisar el estado actual del repo: `git log --oneline`
3. Si hay errores de schema en la API de Jobber: abrir `jobber/mutations.py` y `jobber/mappers.py`
4. Si hay errores de UI/lógica: abrir `app.py`
5. Los secrets de Streamlit Cloud están configurados — no tocar salvo para rotar el Client Secret
6. Para probar localmente: `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`, llenar valores, `streamlit run app.py`
