import os
import re
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
from tkinter import ttk
import ctypes
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# ----------------------
# Ocultar consola en Windows
# ----------------------
try:
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
except Exception:
    pass

# ----------------------
# Rutas y archivos
# ----------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
RAW_CSV      = os.path.join(BASE_DIR, "ordenes_extraidas.csv")
SHINE_DIR    = os.path.join(BASE_DIR, "Shine")
APEX_DIR     = os.path.join(BASE_DIR, "Apex")
LICENSE_PATH = os.path.join(os.getenv('APPDATA', BASE_DIR), "supplypro_license.txt")

# ----------------------
# Credenciales y licencias
# ----------------------
CREDENTIALS = {
    'ShineAndBright': {'mode':'single', 'account':('programmer01','Shineandbright')},
    'Apex':           {'mode':'single', 'account':('ProgrammerApex','Apex1216')}
}
VALID_LICENSE_KEYS = ["X30XH3-S9JH34","TU-LLAVE-2"]

# ----------------------
# Mapas de reglas ShineAndBright
# ----------------------
shine_task_map = {
    'Interior Cleaning Draw 1 Base':'ROUGH CLEAN', 
    'Interior Cleaning Draw 2 Final':'ROUGH RECLEAN',
    'Interior Reclean 1':'FINAL CLEAN', 
    'Interior Reclean 2':'RECLEAN', 
    'Interior Reclean 3':'RECLEAN',
    'Pressure Washing Draw 2':'REWASH', 
    'Pressure Washing Draw 3':'REWASH', 
    'Pressure Washing':'FIRST WASH',
    'Cleaning - Pre-Paint Clean':'ROUGH CLEAN', 
    'Cleaning - Rough Clean':'ROUGH RECLEAN',
    'Cleaning - Final Clean':'FINAL CLEAN', 
    'Cleaning - Final QA Clean':'QA CLEAN',
    'Cleaning - Quality Assurance Clean':'QA CLEAN', 
    'Cleaning - TLC Re-Clean':'TLC RECLEAN',
    'Cleaning - Pressure Wash Home':'FIRST WASH', 
    'Cleaning - Re-Wash Home':'REWASH',
    'Cleaning - Brick Clean':'BRICK CLEAN', 
    'Rough Clean':'ROUGH CLEAN', 
    'Final Clean':'FINAL CLEAN',
    'Quality Re-Walk':'QA CLEAN', 
    'Interior Clean Touch Up #1':'TOUCH UP',
    'Interior Clean Touch Up #2':'TOUCH UP', 
    'Power Wash':'FIRST WASH',
    'Celebration Walk Clean':'TLC RECLEAN'
}
shine_client_map = {
    r'^LGI Homes.*':    'LGI Homes',
    r'^DRB Group.*':    'DRB Group',
    r'^Lennar Homes.*': 'Lennar Homes'
}

shine_subdivision_map = {
    '5536 Lakeside Glen Lake Series 40s':'Lakeside Glen 40s',
    '5537 Lakeside Glen Lake Series 50s':'Lakeside Glen 50s',
    'GAL - Bell Farm 50 - 2487260':'Bell Farm 50',
    'GAL - Bell Farm 60 - 2487360':'Bell Farm 60',
    'GAL - Creekside Cottages Dream - 2489260':'Creekside Cottages Dream',
    'GAL - Elizabeth - - 2485160':'Elizabeth Arbor',
    'GAL - Elizabeth - Chase Det Gar - 2485060':'Elizabeth Chase Det Gar',
    'GAL - Elizabeth - Enclave - 2485460':'Elizabeth Enclave',
    'GAL - Elizabeth - Meadows - 2485360':'Elizabeth Meadows',
    'GAL - Elizabeth - Trinity - 2484960':'Elizabeth Trinity',
    'GAL - Elizabeth - Walk - 2487160':'Elizabeth Walk',
    'GAL - Estates at New Town - 2902460':'Estates at New Town',
    'GAL - Legacy Ridge Dream - 2489960':'Legacy Ridge Dream',
    'GAL - Shannon Woods Meadows - 2486560':'Shannon Woods Meadows',
    'GAL - Shannon Woods Walk Enclave - 2486460':'Shannon Woods Walk Enclave',
    'GAL - Sullivan Farm - 2487960':'Sullivan Farm'
}

apex_instruction_regex = [
    (r"Pour Mono Slab.*\(408205\).*", "Pour Mono Slab"),
    (r"Concrete Labor - Pour Mono Slab.*\(408205\).*", "Pour Mono Slab"),
    (r"Concrete Labor - City Walk.*\(457610\).*", "City Walk"),
    (r"Concrete Labor - Flatwork/ Drives and Walks.*\(457601\).*", "Flatwork/ Drives and Walks"),
    (r"Concrete Labor - Prep and Dig Footing.*", "Prep and Dig Footing"),
    (r"Concrete Labor - Set Forms.*", "Set Forms"),
    (r"Concrete Labor - Mono Slab Prep.*", "Mono Slab Prep"),
    (r"Flooring - Check Slab for Flooring.*", "Check Slab for Flooring"),
    (r"Concrete Labor - Grind Slab for Flooring.*", "Grind Slab for Flooring")
]

# ----------------------
# Licenciamiento
# ----------------------
def check_license():
    if os.path.exists(LICENSE_PATH):
        return True
    root = tk.Tk(); root.withdraw()
    valid = [k.upper() for k in VALID_LICENSE_KEYS]
    while True:
        key = simpledialog.askstring("Licencia","Ingresa tu llave:",parent=root)
        if key is None:
            messagebox.showinfo("Licencia","No ingresaste clave. Cerrando.")
            root.destroy()
            return False
        val = key.strip().upper()
        if val in valid:
            os.makedirs(os.path.dirname(LICENSE_PATH), exist_ok=True)
            with open(LICENSE_PATH,'w') as f: f.write(val)
            root.destroy()
            return True
        messagebox.showerror("Licencia inválida","Intenta nuevamente.")

# ----------------------
# Obtener credenciales
# ----------------------
def get_credentials(cfg):
    return CREDENTIALS[cfg]['account']

# ----------------------
# Extracción de órdenes
# ----------------------
def exportar_ordenes(cfg):
    driver = None
    try:
        path = ChromeDriverManager().install()
        service = Service(path)
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        user,pwd = get_credentials(cfg)
        driver.get('https://www.hyphensolutions.com/MH2Supply/Login.asp')
        wait.until(EC.presence_of_element_located((By.ID,'user_name'))).send_keys(user)
        driver.find_element(By.ID,'password').send_keys(pwd)
        driver.find_element(By.CSS_SELECTOR,"input[type='submit']").click()
        time.sleep(5)

        wait.until(EC.element_to_be_clickable((By.LINK_TEXT,'Newly Received Orders'))).click()
        wait.until(EC.presence_of_element_located((By.NAME,'ref_epo_filter')))
        Select(driver.find_element(By.NAME,'ref_epo_filter')).select_by_visible_text('Show All Except EPOs')
        time.sleep(5)

        th = driver.find_element(By.XPATH,"//th[contains(normalize-space(.),'Builder')]")
        tbl = th.find_element(By.XPATH,'./ancestor::table')
        df = pd.read_html(tbl.get_attribute('outerHTML'))[0]
        df.to_csv(RAW_CSV, index=False, encoding='utf-8-sig')

        # Cerrar sesión
        try:
            driver.find_element(By.LINK_TEXT, "Sign Out").click()
            time.sleep(2)
        except Exception:
            pass

    except Exception as e:
        messagebox.showerror('Error extracción', str(e))
    finally:
        if driver:
            driver.quit()

# ----------------------
# Transformación de órdenes
# ----------------------
def transformar_ordenes(cfg):
    try:
        raw = pd.read_csv(RAW_CSV, header=None, dtype=str, encoding='utf-8-sig')
        sub = raw.iloc[57:-4].reset_index(drop=True) if len(raw)>61 else raw.copy()
        headers = [str(x).strip().replace('\n',' ') for x in sub.iloc[0]]
        df = sub.iloc[1:].copy()
        df.columns = headers
        df = df.applymap(lambda v: str(v).strip().replace('\n',' '))

        # Renombrar y eliminar irrelevantes
        df.rename(columns={
            'Builder Order #':'Number order',
            'Account':'Client Name',
            'Subdivision':'Job title',
            'Lot / Block Plan/Elv/Swing':'lote number',
            'Job Address':'Job Address',
            'Task Task Filter':'instruction',
            'Total Excl Tax':'total',
            'Request Acknowledged Actual':'Start Date'
        }, inplace=True)
        drop_cols = [c for c in df.columns if any(x in c for x in ['Supplier Order','Order Status','Builder Status'])]
        df.drop(columns=drop_cols, inplace=True)

        # Fecha única
        df['Start Date'] = df['Start Date'].apply(
            lambda x: re.search(r"\d{1,2}/\d{1,2}/\d{4}", x).group(0)
                      if re.search(r"\d{1,2}/\d{1,2}/\d{4}", x) else ''
        )

        # Full Property Address sin subdividir y quitar Lennar Options from CRM
        df['Full Property Address'] = df['Job Address']\
            .str.replace("Lennar Options from CRM","", regex=False)\
            .str.strip()
        df.drop(columns=['Job Address'], inplace=True)

        # Limpieza de Client Name
        df['Client Name'] = df['Client Name'].apply(
            lambda x: next((rep for pat,rep in shine_client_map.items() if re.match(pat,x)), x)
        )

        # Limpieza de instruction y Shine map
        df['instruction'] = df['instruction']\
            .str.replace(r"\s*[\(\[].*?[\)\]]", "", regex=True)\
            .str.strip()
        df['instruction'] = df['instruction'].apply(lambda x: shine_task_map.get(x, x))
        if cfg=='Apex':
            df['instruction'] = df['instruction'].str.replace(r'^Concrete Labor -\s*', '', regex=True)
            for pattern, repl in apex_instruction_regex:
                df['instruction'] = df['instruction'].str.replace(pattern, repl, regex=True)

        # Limpieza de Job title
        df['job_title_clean'] = df['Job title']\
            .str.replace(r'^GAL\s*-\s*', '', regex=True)\
            .str.replace(r'\s*-\s*\d+$', '', regex=True)\
            .str.strip()

        # Lote number previo a /
        df['lote number'] = df['lote number'].str.partition('/')[0].str.strip()

        # Construir Job title Final
        df['Job title Final'] = df.apply(
            lambda r: f"{r['instruction']} / LOT {r['lote number']} / {r['job_title_clean']} / {r['Number order']}",
            axis=1
        )

        # Filtrado de filas inválidas
        df = df[
            df['Number order'].notna() &
            df['Number order'].str.strip().ne('') &
            (df['Number order'].str.lower()!='nan')
        ]

        # Seleccionar finales y eliminar nan
        final = df[['Client Name','Job title Final','Full Property Address','total','Start Date']]
        final = final[~final.apply(lambda row: row.astype(str).str.lower().eq('nan').any(), axis=1)]

        out_dir = SHINE_DIR if cfg=='ShineAndBright' else APEX_DIR
        os.makedirs(out_dir, exist_ok=True)
        final.to_csv(os.path.join(out_dir,'ordenes_jobber.csv'), index=False, encoding='utf-8-sig')

    except Exception as e:
        messagebox.showerror('Error transformación', str(e))

# ----------------------
# Placeholders GUI
# ----------------------
def importar_a_jobber():   messagebox.showinfo('Importar a Jobber','Función pendiente')
def importar_a_quickbox(): messagebox.showinfo('Importar a Quickbox','Función pendiente')

# ----------------------
# Interfaz gráfica
# ----------------------
if __name__=='__main__':
    if not check_license(): sys.exit(0)

    root = tk.Tk()
    root.title('SupplyPro Extractor')
    root.geometry('400x380')

    tk.Label(root, text='SupplyPro Extractor', font=('Arial',16,'bold')).pack(pady=10)

    config_var = tk.StringVar(value='ShineAndBright')
    tk.Radiobutton(root, text='ShineAndBright',     variable=config_var, value='ShineAndBright').pack(anchor='w')
    tk.Radiobutton(root, text='Apex Constructions', variable=config_var, value='Apex').pack(anchor='w')

    progreso = ttk.Progressbar(root, mode='indeterminate')

    def run_export():
        progreso.pack(fill='x', padx=20, pady=5)
        progreso.start(10)
        root.update_idletasks()
        exportar_ordenes(config_var.get())
        transformar_ordenes(config_var.get())
        progreso.stop()
        progreso.pack_forget()
        messagebox.showinfo('Éxito','Operación completada')

    tk.Button(root, text='Exportar órdenes de SupplyPro', command=run_export,
              bg='#00C2FF', fg='white', height=2, width=30).pack(pady=5)
    tk.Button(root, text='Importar a Jobber',     command=importar_a_jobber,
              bg='#00C2FF', fg='white', height=2, width=30).pack(pady=5)
    tk.Button(root, text='Importar a Quickbox',    command=importar_a_quickbox,
              bg='#00C2FF', fg='white', height=2, width=30).pack(pady=5)

    tk.Label(root, text='By FroDev', font=('Arial',8)).place(x=10, y=360)
    root.mainloop()
