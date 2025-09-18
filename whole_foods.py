import fitz
import pandas as pd
import re
from datetime import datetime, timedelta
import os
import sys
from typing import Optional, Tuple

# Determinar la ruta base según si es ejecutable o script
base_dir = (
    os.path.dirname(sys.executable)
    if getattr(sys, 'frozen', False)
    else os.path.dirname(os.path.abspath(__file__))  
)

excel_path = os.path.join(base_dir, "WFM TRUCK-FECHAS.xlsx")

try:
    RULES = pd.read_excel(excel_path, sheet_name=["CH ROBINSON", "ELITE"])
    RULES_CH = RULES['CH ROBINSON']
    RULES_EMI = RULES['ELITE']
except Exception as e:
    print(f"No se pudo leer el archivo de reglas: {e}")
    RULES = pd.DataFrame() 

def read_pdf (pdf_path):
    """
    Lee un archivo PDF y lo convierte en un DataFrame de pandas donde cada línea
    de texto del PDF se representa como una fila, junto con el número de página.

    Parámetros:
    pdf_path : str
        Ruta completa al archivo PDF que se desea leer.

    Retorno:
    pd.DataFrame
        DataFrame con dos columnas:
        - 'Página': número de página (empezando en 1).
        - 'Línea': contenido de texto de cada línea no vacía.

    Notas:
    - Se ignoran las líneas vacías.
    - Cada página se procesa en orden.
    - Se utiliza PyMuPDF (fitz) para extraer el texto.
    """
    pdf = fitz.open(pdf_path)
    lines = []
    for page_number in range(len(pdf)):
        page = pdf[page_number]
        text = page.get_text()
        page_lines = text.split('\n')
        for line in page_lines:
            if line.strip():
                lines.append({'Página': page_number + 1, 'Línea': line})
    df = pd.DataFrame(lines)
    return df

def delete_for_index(df, inferior_limit, superior_limit, pattern):
    """
    Elimina filas de un DataFrame alrededor de aquellas que coinciden con un patrón específico.

    Parámetros:
        df (pd.DataFrame): DataFrame con la columna 'Texto'.
        inferior_limit (int): Número de filas a eliminar antes de la coincidencia.
        superior_limit (int): Número de filas a eliminar después de la coincidencia.

    Retorna:
        pd.DataFrame: DataFrame con las filas eliminadas.
    """
    indexes_to_delete = set()

    # Recorremos todas las filas del DataFrame
    for i, value in df['Línea'].astype(str).items():
        # Patrón regex: "dd/mm/aa hh:mm AM/PM Page X ofY"
        if re.search(pattern, value):
            # Agregamos índices en el rango seguro
            start = max(i - inferior_limit, 0)
            end = min(i + superior_limit, len(df))
            indexes_to_delete.update(range(start, end))

    # Eliminamos las filas y reiniciamos índices
    df_clean = df.drop(index=indexes_to_delete).reset_index(drop=True)
    return df_clean

def create_new_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Procesa el DataFrame agrupado por páginas.
    Los metadatos de la página (PH, COOLER, PO, etc.) se extraen una sola vez
    y se asignan a todas las filas generadas en esa página.
    """
    final = pd.DataFrame(columns=[
        'PH ORDER', 'PH SHIP TO', 'COOLER', 'PO', 'LOAD DATE', 'DELIVERY DATE', 'DAY DELIVERY DATE', 'SHIP TO DATE', 'DAY SHIP TO', 'MIAMI DATE', 'DAY MIAMI', 'SHIP TO','DESTINATION',
        'ID', 'QUANTITY', 'DESCRIPTION', 'QUALITY',
        'PRICE 1', 'PRICE 2', 'PRICE 3', 'PRICE 4'
    ])

    for page, df_page in df.groupby("Página"):
        df_page = df_page.reset_index(drop=True)
        linea = df_page.loc[8, "Línea"]
        match = re.search(r"Cooler:\s*([^ ]+)", linea)
        resultado = match.group(1) if match else linea
        page_data = {
            "PH ORDER": df_page.loc[5, "Línea"],
            "PH SHIP TO": df_page.loc[7, "Línea"],
            "COOLER": resultado,
            "PO": df_page.loc[0, "Línea"],
            "LOAD DATE": df_page.loc[6, "Línea"],
            "DELIVERY DATE": df_page.loc[3, "Línea"],
            "SHIP TO": df_page.loc[4, "Línea"] + df_page.loc[2, "Línea"],
            "DESTINATION": df_page.loc[1, "Línea"],
            "PAGE": page
        }

        i = 0
        while i < len(df_page) - 3:
            value = str(df_page['Línea'].iloc[i])

            if re.fullmatch(r"\d{9}", value):  # detecta ID de 9 dígitos
                if i >= 3 and str(df_page['Línea'].iloc[i - 3]) == "Temp Recorder":
                    new_row = {
                        **page_data,  # hereda los datos de la página
                        'ID': value,
                        'QUANTITY': str(df_page['Línea'].iloc[i + 1]),
                        'DESCRIPTION': "Temp Recorder",
                        'PRICE 1': str(df_page['Línea'].iloc[i - 2]),
                        'PRICE 2': str(df_page['Línea'].iloc[i + 2]),
                        'PRICE 3': str(df_page['Línea'].iloc[i - 1]),
                        'PRICE 4': str(df_page['Línea'].iloc[i + 3])
                    }
                    final = pd.concat([final, pd.DataFrame([new_row])], ignore_index=True)
                    i += 3
                elif i >= 5:
                    new_row = {
                        **page_data,
                        'ID': value,
                        'QUANTITY': str(df_page['Línea'].iloc[i + 1]),
                        'DESCRIPTION': str(df_page['Línea'].iloc[i - 5]) + " " + str(df_page['Línea'].iloc[i - 4]),
                        'QUALITY': str(df_page['Línea'].iloc[i - 3]),
                        'PRICE 1': str(df_page['Línea'].iloc[i - 2]),
                        'PRICE 2': str(df_page['Línea'].iloc[i + 2]),
                        'PRICE 3': str(df_page['Línea'].iloc[i - 1]),
                        'PRICE 4': str(df_page['Línea'].iloc[i + 3])
                    }
                    final = pd.concat([final, pd.DataFrame([new_row])], ignore_index=True)
                    i += 3
                else:
                    i += 1
            else:
                i += 1

    return final

def format_columns (text):
    """
    Limpia y formatea un texto de una columna específica.

    1. Elimina el símbolo de dólar `$`.
    2. Elimina el prefijo 'Ph:' (por ejemplo, en números de teléfono).
    3. Reemplaza múltiples espacios en blanco por un solo espacio.
    4. Elimina espacios en blanco al inicio y al final.

    Parámetros:
    text : str
        Texto a limpiar y formatear.

    Retorno:
    str
        Texto limpio y formateado.
    """
    text = re.sub(r'\$', '', text)
    text = re.sub(r'Ph:', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def return_ship_day_ch_robinson(rules: pd.DataFrame, destination: str, delivery_day: str) -> str:
    """
    Retorna el 'SHIP DAY' como string según 'DESTINATION' y 'DELIVERY DAYS'.
    Si no hay coincidencias, retorna None.
    """
    filtered = rules.loc[
        (rules['DESTINATION'].str.lower() == destination.lower()) &
        (rules['DELIVERY DAYS'].str.lower() == delivery_day.lower()),
        'SHIP DAY'
    ]
    if not filtered.empty:
        return str(filtered.iloc[0])
    return None

def return_ship_day_elite(rules: pd.DataFrame, destination: str, delivery_day: str) -> Optional[Tuple[str, str]]:
    """
    Retorna una tupla con ('SHIP DAY {i}', 'MIA {i}') según coincidencia parcial en 'ELITE TO WHOLE FOODS'
    y coincidencia exacta en cualquier columna 'DELIVERY DAY {i}'.
    Si no hay coincidencias, retorna None.
    """
    delivery_day = delivery_day.strip().lower()
    destination = destination.lower()
    delivery_columns = []
    for col in rules.columns:
        match = re.match(r"DELIVERY DAY (\d+)", col.upper())
        if match:
            i = int(match.group(1))
            delivery_columns.append((i, col))
    for _, row in rules.iterrows():
        elite_field = str(row.get('ELITE TO WHOLE FOODS', '')).lower()
        if destination in elite_field:
            for i, col in delivery_columns:
                day_value = str(row.get(col, '')).lower()
                if delivery_day == day_value:
                    ship_day_key = f"SHIP DATE {i}"
                    ship_day = str(row.get(ship_day_key, ''))
                    mia_key = f"MIA {i}"
                    mia = str(row.get(mia_key, ''))
                    return ship_day, mia
    return None

def get_previous_weekday(target_day: str, base_date_str: str, date_format: str = "%m/%d/%y") -> Optional[str]:
    """
    Returns the most recent date within the past 7 days that matches the target weekday.
    - target_day: weekday name in English (e.g., 'Tuesday')
    - base_date_str: reference date in 'MM/DD/YYYY' format
    """
    weekdays = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6
    }
    base_date = datetime.strptime(base_date_str, date_format)
    target_index = weekdays[target_day.strip().capitalize()]
    for i in range(0, 7):
        candidate = base_date - timedelta(days=i)
        if candidate.weekday() == target_index:
            return candidate.strftime(date_format)
    return None

def apply_date(df: pd.DataFrame, insert_col: str, day_col: str, base_date_col:str) -> pd.DataFrame:
    df[insert_col] = df.apply(
        lambda row: get_previous_weekday(row[day_col], row[base_date_col]) if row[day_col] and row[base_date_col] else '',
        axis=1
    )
    return df

def process_pdf (pdf_path):
    df = read_pdf(pdf_path)
    patterns = [
        {"pattern": r"Page\s+(?P<pagina>\d+)\s+of\s+(?P<total>\d+)", "inferior": 4, "superior": 2},
        {"pattern": r"Transnational Cargo", "inferior": 1, "superior": 3},
        {"pattern": r"Purchase Order", "inferior": 0, "superior": 1},
        {"pattern": r"Ship To", "inferior": 0, "superior": 1},
        {"pattern": r"Bill Tor", "inferior": 0, "superior": 1},
        {"pattern": r"Pickup #:", "inferior": 0, "superior": 1},
        {"pattern": r"Fax:", "inferior": 0, "superior": 1},
        {"pattern": r"Delivery Type:", "inferior": 0, "superior": 3},
        {"pattern": r"PO #:", "inferior": 0, "superior": 3},
        {"pattern": r"(?:Ph|Phone):\s*(?P<telefono>\d{10})", "inferior": 1, "superior": 2},
        {"pattern": r"Delivery Date:", "inferior": 0, "superior": 1},
        {"pattern": r"Bill To", "inferior": 0, "superior": 1},
        {"pattern": r"External PO:", "inferior": 0, "superior": 2},
        {"pattern": r"Totals", "inferior": 0, "superior": 7},
    ]
    for item in patterns:
        df = delete_for_index(df, item["inferior"], item["superior"], item["pattern"])
    df = create_new_dataframe(df)
    df['PRICE 3'] = df['PRICE 3'].apply(format_columns)
    df['PRICE 4'] = df['PRICE 4'].apply(format_columns)
    df['PH ORDER'] = df['PH ORDER'].apply(format_columns)
    df['PH SHIP TO'] = df['PH SHIP TO'].apply(format_columns)
    df = df.fillna('')
    price_cols = ['PRICE 1', 'PRICE 2', 'PRICE 3', 'PRICE 4']
    for col in price_cols:
        df[col] = df[col].str.replace(',', '').astype(float)
    df['QUANTITY'] = pd.to_numeric(df['QUANTITY'], errors='coerce', downcast='integer')
    for idx, row in df.iterrows():
        fecha_str = row['DELIVERY DATE']
        fecha_obj = datetime.strptime(fecha_str, "%m/%d/%y")
        day_name = fecha_obj.strftime("%A")
        address = row['DESTINATION']
        destination = address.rsplit(' ', 1)[0]
        destination_without_coma = address.split(',')[0].strip()
        if row.get('COOLER') == 'CHFL':
            ship_day_name = return_ship_day_ch_robinson(RULES_CH, destination, day_name)
            df.loc[idx, 'DAY SHIP TO'] = str(ship_day_name).capitalize() if ship_day_name else ""
        elif row.get('COOLER') == 'EMI':
            result = return_ship_day_elite(RULES_EMI, destination_without_coma, day_name)
            if result:
                ship_day_name, miami_day_name = result
                df.loc[idx, 'DAY SHIP TO'] = str(ship_day_name).capitalize() if ship_day_name else ""
                df.loc[idx, 'DAY MIAMI'] = str(miami_day_name).capitalize() if miami_day_name else ""
            else:
                df.loc[idx, 'DAY SHIP TO'] = ""
                df.loc[idx, 'DAY MIAMI'] = ""
        else:
            df.loc[idx, 'DAY SHIP TO'] = ""
        df.loc[idx, 'DAY DELIVERY DATE'] = str(day_name)
    df = apply_date(df, 'SHIP TO DATE', 'DAY SHIP TO', 'DELIVERY DATE')
    df = apply_date(df, 'MIAMI DATE', 'DAY MIAMI', 'SHIP TO DATE')
    actual_date = datetime.today().strftime("%m/%d/%Y")
    df.insert(0, 'PROCESS DATE', actual_date)
    return df