# ✨ ShineAndBright — SupplyPro → Jobber

Extrae órdenes de trabajo de SupplyPro automáticamente, permite revisarlas y editarlas, y las sube directo a Jobber como Jobs. La sincronización con QuickBooks Online la hace Jobber de forma nativa.

**App:** https://worksyncextractor.streamlit.app  
**Repo:** https://github.com/FroDev-CR/WorkSyncExtractor

---

## Flujo de trabajo

```
SupplyPro → Extracción → Tabla editable → Subir a Jobber → Jobs en Jobber
                                                                    ↓
                                                      (integración nativa)
                                                                    ↓
                                                         QuickBooks Online
```

1. El equipo abre el app y hace click en **Exportar órdenes de SupplyPro**
2. El app extrae las órdenes nuevas (~30–60 s)
3. El equipo revisa y edita la tabla (cliente, título, dirección, monto, fecha)
4. Marca las órdenes a subir y hace click en **Subir a Jobber**
5. El app crea un Job en Jobber por cada orden seleccionada
6. El equipo convierte los Jobs en Invoices en Jobber y las ajusta si es necesario
7. Jobber sincroniza las invoices marcadas como "sent" a QuickBooks Online automáticamente

---

## Setup inicial

### 1. Crear el app en Jobber Developer Center

1. Ve a https://developer.getjobber.com y entra con tu cuenta de Jobber
2. Haz click en **Create App**
3. Completa los campos:
   - **App Name:** ShineAndBright SupplyPro Sync
   - **Description:** Sincronización automática de órdenes SupplyPro → Jobber
   - **OAuth Callback URL:** `https://worksyncextractor.streamlit.app/`
   - **Scopes:** marca `read_clients`, `write_clients`, `read_jobs`, `write_jobs`, `read_users`
   - **Refresh Token Rotation:** ON (recomendado, es el default)
4. Guarda. Copia el **Client ID** y el **Client Secret**

### 2. Configurar secrets en Streamlit Cloud

1. Ve a https://share.streamlit.io
2. Encuentra el app **WorkSyncExtractor** → botón **⋮** → **Settings** → **Secrets**
3. Pega el siguiente bloque (reemplaza los valores):

```toml
SUPPLYPRO_USERNAME = "programmer01"
SUPPLYPRO_PASSWORD = "TU_PASSWORD_SUPPLYPRO"

JOBBER_CLIENT_ID     = "TU_CLIENT_ID"
JOBBER_CLIENT_SECRET = "TU_CLIENT_SECRET"
APP_URL              = "https://worksyncextractor.streamlit.app/"
```

4. Haz click en **Save** — el app se reinicia automáticamente

### 3. Conectar Jobber (una sola vez)

1. Abre el app
2. En la sidebar, haz click en **🔗 Conectar con Jobber**
3. Authoriza el app en la pantalla de Jobber
4. Serás redirigido de vuelta al app — la sidebar mostrará **✅ Conectado como [cuenta]**
5. Haz click en **🧪 Probar conexión** para confirmar

Los tokens se guardan en SQLite (`jobber_tokens.db`) y se renuevan automáticamente. Si el app se re-deploya desde cero, el admin necesita reconectar — toma ~30 segundos.

### 4. Activar integración Jobber → QuickBooks Online

Esta es la única configuración que se hace en Jobber directamente. Solo se hace una vez.

1. En Jobber, ve a **Settings** → **Apps** → **QuickBooks Online** → **Connect**
2. Autoriza la conexión con tu cuenta de QBO
3. En la configuración de la integración, selecciona la opción:
   **"Push Invoice when marked sent"**
   (esto da tiempo al equipo para ajustar la invoice antes de que llegue a QBO)
4. Guarda

A partir de ese momento, cada vez que el equipo marque una invoice como "sent" en Jobber, llegará automáticamente a QuickBooks Online.

---

## Estructura del proyecto

```
/
├── app.py                    — UI Streamlit principal
├── scraper.py                — Extracción de órdenes desde SupplyPro (Playwright)
├── transformer.py            — Limpieza y transformación de datos
├── config.py                 — Constantes y mapas de reglas (sin credenciales)
├── requirements.txt
├── packages.txt              — Dependencias del sistema (Playwright)
├── jobber/
│   ├── storage.py            — Persistencia de tokens OAuth en SQLite
│   ├── oauth.py              — Flujo OAuth 2.0 con Jobber
│   ├── client.py             — Cliente GraphQL con retry y refresh automático
│   ├── mutations.py          — Queries y mutations GraphQL como constantes
│   └── mappers.py            — Mapeo de filas del DataFrame a variables GraphQL
├── i18n/
│   ├── __init__.py           — Helper t() para internacionalización
│   ├── es.py                 — Strings en español
│   └── en.py                 — Strings en inglés
└── .streamlit/
    ├── secrets.toml.example  — Template de secrets (no contiene valores reales)
    └── config.toml           — Tema visual
```

---

## Desarrollo local

```bash
# Clonar
git clone https://github.com/FroDev-CR/WorkSyncExtractor.git
cd WorkSyncExtractor

# Instalar dependencias
pip install -r requirements.txt
playwright install chromium

# Configurar secrets locales
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Editar secrets.toml con los valores reales

# Correr
streamlit run app.py
```

> El archivo `secrets.toml` está en `.gitignore` y nunca debe subirse al repo.

---

## Troubleshooting

### "No conectado a Jobber" después de reconectar
El refresh token se invalida cuando el app es desconectado manualmente en Jobber.  
→ Haz click en **Desconectar** en la sidebar y luego vuelve a conectar.

### Error "Invalid refresh token"
El token fue invalidado (desconexión manual, cambio de Client Secret, o re-autorización de scopes).  
→ Haz click en **Desconectar** y completa el flujo OAuth de nuevo.

### El app no encuentra el cliente en Jobber
Los 4 builders (LGI Homes, DRB Group, Lennar Homes) deben existir en Jobber con ese nombre exacto.  
Si no existen, el app los creará automáticamente la primera vez.

### Error al crear una Property
La dirección extraída de SupplyPro puede tener formato inconsistente.  
→ Edita la dirección en la tabla antes de subir.

### Playwright no inicia en Streamlit Cloud
El `post_install.sh` instala los browsers automáticamente.  
Si falla, ve a Manage App → **Reboot** en Streamlit Cloud.

### El app se ve lento al extraer
SupplyPro usa un sistema legacy — la extracción con Playwright tarda ~45-90 s. Es normal.

---

## Rate limits de Jobber

- Máximo 2500 requests / 5 minutos por app+cuenta
- Leaky bucket de 10,000 puntos, restaura 500/segundo
- Para 40 órdenes: ~120 requests (~360 puntos) — bien dentro del límite
- El cliente GraphQL maneja throttling automáticamente con retry + backoff

---

## Seguridad

- Las credenciales de SupplyPro y los tokens de Jobber **nunca** se commitean al repo
- Los tokens OAuth se guardan localmente en `jobber_tokens.db` (en `.gitignore`)
- El Client Secret de Jobber vive solo en Streamlit Cloud Secrets
- Si el Client Secret es comprometido, rotarlo en Jobber Developer Center e inmediatamente actualizar el secret en Streamlit Cloud
