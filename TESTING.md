# Checklist de pruebas — ShineAndBright SupplyPro → Jobber

Ejecutar antes de cada deploy a producción.

---

## 1. Extracción de SupplyPro

- [ ] El app carga sin errores en Streamlit Cloud
- [ ] Click en "Exportar órdenes" conecta a SupplyPro y extrae la tabla
- [ ] La tabla muestra las columnas: Client Name, Job title Final, Full Property Address, total, Start Date
- [ ] Los valores de `Client Name` están normalizados (LGI Homes, DRB Group, Lennar Homes)
- [ ] Los valores de `total` tienen formato `$X,XXX.XX`
- [ ] Las fechas tienen formato `MM/DD/YYYY`
- [ ] No aparecen filas con `nan` o datos vacíos en columnas clave

## 2. Tabla editable

- [ ] La columna "Subir" (checkbox) aparece al inicio, todas marcadas por default
- [ ] Se puede editar cualquier celda de texto (cliente, título, dirección, total, fecha)
- [ ] Al editar una celda y hacer click en otro botón, los cambios persisten
- [ ] Se puede desmarcar filas individualmente
- [ ] Si hay un total inválido (ej. "n/a"), aparece advertencia en amarillo indicando la fila
- [ ] Las métricas (total órdenes, clientes únicos, total $) se actualizan al editar
- [ ] Los botones "Descargar CSV" y "Descargar Excel" generan archivos con los datos editados (sin columna Subir)

## 3. OAuth con Jobber

- [ ] La sidebar muestra "No conectado a Jobber" antes de conectar
- [ ] Click en "Conectar con Jobber" redirige a la pantalla de autorización de Jobber
- [ ] Después de autorizar, el app muestra "✅ Conectado como [nombre cuenta]"
- [ ] "🧪 Probar conexión" muestra un toast con el nombre de la cuenta
- [ ] "Desconectar" limpia los tokens y vuelve al estado "No conectado"
- [ ] Después de desconectar, reconectar vuelve a funcionar correctamente
- [ ] Si se reinicia el app (Reboot en Streamlit Cloud), la sesión persiste (tokens en SQLite)

## 4. Subida a Jobber

- [ ] El botón "📤 Subir a Jobber (N)" solo aparece si hay tokens y filas marcadas
- [ ] La barra de progreso avanza por cada orden procesada
- [ ] El texto de estado muestra la orden que se está procesando
- [ ] Los builders existentes (LGI Homes, DRB Group, Lennar Homes) son encontrados, no duplicados
- [ ] Si una dirección ya existe como Property del cliente, se reutiliza
- [ ] Si una dirección es nueva, se crea como Property y se usa
- [ ] Cada Job se crea en Jobber con:
  - [ ] Cliente correcto
  - [ ] Título = Job title Final
  - [ ] Property = dirección de la orden
  - [ ] Line item con monto correcto (sin símbolos, número)
  - [ ] Fecha de inicio correcta (formato ISO8601)
- [ ] Al terminar, las filas subidas se marcan en la columna "Ya subido" y se desmarcan de "Subir"
- [ ] Si se vuelve a hacer click en "Subir", las filas ya subidas no se procesan de nuevo

## 5. Reporte de subida

- [ ] El reporte muestra todas las órdenes procesadas con ✅/❌
- [ ] Las órdenes exitosas tienen número de Job y link funcional a Jobber
- [ ] Las órdenes fallidas muestran el mensaje de error específico
- [ ] "Descargar reporte" genera un CSV con el resumen
- [ ] Si hay fallidas, el botón "Reintentar fallidas" reactiva solo esas filas para reintentar

## 6. i18n

- [ ] Toggle 🇪🇸/🇬🇧 en la sidebar cambia todos los textos visibles
- [ ] Los textos de error y éxito también cambian de idioma
- [ ] El idioma persiste si se extrae y luego se sube

## 7. Móvil

- [ ] En pantalla de ~375px, las columnas de métricas se apilan verticalmente
- [ ] Los botones son accesibles con el dedo (no se superponen)
- [ ] La tabla es scrolleable horizontalmente

## 8. QuickBooks Online (end-to-end, una vez conectado)

- [ ] En Jobber, la integración con QBO está activa con opción "Push Invoice when marked sent"
- [ ] Crear una Invoice desde un Job en Jobber
- [ ] Marcar esa Invoice como "sent"
- [ ] Confirmar que la Invoice aparece en QuickBooks Online (puede tardar 1-2 min)

---

## Notas de versión

| Fecha      | Versión | Cambios |
|------------|---------|---------|
| 2026-04-17 | 1.0.0   | Release inicial — extracción + tabla editable + subida a Jobber |
