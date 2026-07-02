# ----------------------
# Configuración general
# ----------------------

# Credenciales de SupplyPro
CREDENTIALS = {
    'ShineAndBright': {
        'mode': 'single',
        'username': 'programmer01',
        'password': 'Shineandbright'
    },
    'Apex': {
        'mode': 'single',
        'username': 'ProgrammerApex',
        'password': 'Apex1216'
    }
}

# URL de SupplyPro
SUPPLYPRO_URL = 'https://www.hyphensolutions.com/MH2Supply/Login.asp'

# Mapas de reglas ShineAndBright
SHINE_TASK_MAP = {
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

SHINE_CLIENT_MAP = {
    r'^LGI Homes.*':    'LGI Homes',
    r'^DRB Group.*':    'DRB Group',
    r'^Lennar Homes.*': 'Lennar Homes'
}

SHINE_SUBDIVISION_MAP = {
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

# Reglas Apex
APEX_INSTRUCTION_REGEX = [
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
