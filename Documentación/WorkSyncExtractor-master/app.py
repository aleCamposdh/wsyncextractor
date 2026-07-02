"""
SupplyPro Extractor - Versión Web con Streamlit
"""
import streamlit as st
import pandas as pd
from io import BytesIO
import subprocess
import sys
from pathlib import Path

# Instalar Playwright browsers en primera ejecución
@st.cache_resource
def install_playwright():
    """Instala los navegadores de Playwright si no están instalados"""
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True
        )
    except Exception as e:
        st.warning(f"Nota: {str(e)}")

# Instalar Playwright al inicio
install_playwright()

from config import CREDENTIALS
from scraper import ejecutar_extraccion
from transformer import transformar_ordenes


# Configuración de la página
st.set_page_config(
    page_title="SupplyPro Extractor",
    page_icon="📦",
    layout="centered"
)

# Inicializar estado de sesión
if 'df_result' not in st.session_state:
    st.session_state.df_result = None


def main_page():
    """Página principal de la aplicación"""
    st.title("📦 SupplyPro Extractor")
    st.markdown("### Extracción automática de órdenes")
    {MongoDataBaseNotsupported}
{StreamlitNotsupported} {RepositoryNotsupported}
    
    # Selector de configuración
    config = st.radio(
        "Selecciona la empresa:",
        ["ShineAndBright", "Apex"],
        horizontal=True
    )

    st.markdown("---")

    # Botón principal de extracción
    if st.button("🚀 Exportar órdenes de SupplyPro", type="primary", use_container_width=True):
        with st.spinner(f"Extrayendo órdenes de {config}..."):
            try:
                # Obtener credenciales automáticamente
                creds = CREDENTIALS[config]
                username = creds['username']
                password = creds['password']

                # Extraer datos
                st.info("⏳ Conectando a SupplyPro...")
                df_raw = ejecutar_extraccion(username, password)

                # Transformar datos
                st.info("⚙️ Procesando órdenes...")
                df_final = transformar_ordenes(df_raw, config)

                # Verificar si hay órdenes válidas
                if len(df_final) == 0:
                    st.warning(f"⚠️ No se encontraron órdenes válidas para {config}. Es posible que no haya órdenes pendientes en este momento.")
                    st.session_state.df_result = None
                else:
                    # Guardar resultado
                    st.session_state.df_result = df_final
                    st.session_state.config_name = config
                    st.success(f"✅ ¡Operación completada! Se encontraron {len(df_final)} órdenes.")

            except Exception as e:
                st.error(f"❌ Error en la extracción: {str(e)}")
                st.info("💡 Intenta nuevamente en unos segundos. Si el error persiste, contacta al administrador.")

    # Mostrar resultados si existen
    if st.session_state.df_result is not None:
        st.markdown("---")
        st.markdown("### 📊 Resultados")

        df = st.session_state.df_result

        # Mostrar preview
        st.dataframe(df, use_container_width=True, height=400)

        # Estadísticas rápidas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total órdenes", len(df))
        with col2:
            st.metric("Clientes únicos", df['Client Name'].nunique())
        with col3:
            try:
                # Intentar calcular el total limpiando el formato de moneda
                total_amount = df['total'].str.replace('$', '').str.replace(',', '').astype(float).sum()
                st.metric("Total $", f"${total_amount:,.2f}")
            except (ValueError, AttributeError):
                # Si no se puede convertir, mostrar "N/A"
                st.metric("Total $", "N/A")

        # Botones de descarga
        st.markdown("### 💾 Descargar")

        col1, col2 = st.columns(2)

        with col1:
            # Descargar CSV
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="📥 Descargar CSV",
                data=csv,
                file_name=f"ordenes_{st.session_state.config_name}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col2:
            # Descargar Excel
            buffer = BytesIO()
            df.to_excel(buffer, index=False, engine='openpyxl')
            buffer.seek(0)
            st.download_button(
                label="📥 Descargar Excel",
                data=buffer,
                file_name=f"ordenes_{st.session_state.config_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # Información adicional en expander
    with st.expander("ℹ️ Cómo usar esta aplicación"):
        st.markdown("""
        **Pasos:**
        1. Selecciona la empresa (ShineAndBright o Apex)
        2. Haz clic en "Exportar órdenes de SupplyPro"
        3. Espera a que se extraigan y procesen las órdenes
        4. Descarga el archivo CSV o Excel

        **Nota:** La extracción es automática, no necesitas ingresar credenciales.
        """)

    # Footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: gray;'>Desarrollado por FroDev</p>",
        unsafe_allow_html=True
    )


# Mostrar página principal
main_page()
