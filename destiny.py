import pdfplumber
import pandas as pd
from datetime import datetime

def extraer_titulos(pdf_path):
    titulos = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            tablas_detectadas = pagina.find_tables()
            areas_tablas = [tabla.bbox for tabla in tablas_detectadas]
            caracteres = pagina.chars
            caracteres_fuera_tablas = [
                char for char in caracteres
                if not any(x0 <= char["x0"] <= x1 and top <= char["top"] <= bottom for x0, top, x1, bottom in areas_tablas)
            ]
            caracteres_fuera_tablas.sort(key=lambda c: (round(c['top']), c['x0']))
            linea_actual, top_actual = [], None
            tolerancia = 3
            for char in caracteres_fuera_tablas:
                if top_actual is None or abs(char['top'] - top_actual) <= tolerancia:
                    linea_actual.append(char['text'])
                    top_actual = char['top']
                else:
                    linea_texto = ''.join(linea_actual).strip()
                    if linea_texto:
                        titulos.append([linea_texto])
                    linea_actual = [char['text']]
                    top_actual = char['top']
            if linea_actual:
                linea_texto = ''.join(linea_actual).strip()
                if linea_texto:
                    titulos.append([linea_texto])
    titulos = pd.DataFrame(titulos)
    return titulos.iloc[7:].reset_index(drop=True)

def extraer_tablas(pdf_path):
    filas = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            tablas = pagina.extract_tables()
            for tabla in tablas:
                for fila in tabla:
                    filas.append(fila)
    return pd.DataFrame(filas)

def combinar_titulos_tablas(titulos, tablas):
    contenido_final = []
    idx_titulo = 0
    if idx_titulo < len(titulos):
        contenido_final.append([titulos.iloc[idx_titulo, 0]])
        idx_titulo += 1
    for idx, fila in tablas.iterrows():
        fila = fila.tolist()
        if len(fila) > 1 and isinstance(fila[1], str) and "HAWB" in fila[1]:
            continue
        contenido_final.append(fila)
        if (len(fila) > 6 and str(fila[6]).strip() == "Subtotal 2") or \
           (len(fila) > 0 and str(fila[0]).strip() == "Subtotal 2"):
            if idx_titulo < len(titulos):
                contenido_final.append([titulos.iloc[idx_titulo, 0]])
                idx_titulo += 1
    num_columnas = max(len(fila) for fila in contenido_final)
    contenido_final = [fila + [""] * (num_columnas - len(fila)) for fila in contenido_final]
    df_final = pd.DataFrame(contenido_final)
    df_final.insert(0, 'CLIENTE', '')
    lista_titulos = titulos[0].astype(str).str.strip().tolist()
    cliente_actual = ""
    for idx, row in df_final.iterrows():
        primera_columna = str(row.iloc[1]).strip()
        if primera_columna in lista_titulos:
            cliente_actual = primera_columna
        df_final.at[idx, 'CLIENTE'] = cliente_actual
    df_final = df_final[~df_final.iloc[:,1].isin(lista_titulos)].reset_index(drop=True)
    columnas_finales = ["CLIENT", "HAWB", "EXPORTER", "FB", "PIECES", "WEIGHT (Kg)", "FREIGHT ($)", "DUTY ($)", "OTHER CHARGES"]
    df_final.columns = columnas_finales
    return df_final
    
def convertir_columnas_a_numerico(df):
    columnas_a_convertir = df.columns[3:8] 
    for col in columnas_a_convertir:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

def procesar_pdf(pdf_path, v1, rates):
    try:
        titulos = extraer_titulos(pdf_path)
        tablas = extraer_tablas(pdf_path)

        metadatos = tablas.head(4)
        tablas = tablas.iloc[4:].fillna("")
        inv_number = metadatos.iloc[1, 0]
        inv_date = metadatos.iloc[1, 1]
        month, day, year = inv_date.split("/")
        inv_date = f"{year}-{month}-{day}"
        inv_awb = metadatos.iloc[3, 0].replace("-", "").replace(" ", "")
        guide = inv_awb[:3]
        if guide in rates:
            v2, v3 = rates[guide]
        else:
            v2 = 1.76
            v3 = 1.86
        tablas = tablas.iloc[:, :-1]
        df_final = combinar_titulos_tablas(titulos, tablas)

        df_final = df_final[~df_final.apply(lambda x: x.astype(str).str.strip().isin(["Subtotal 1", "Subtotal 2"])).any(axis=1)]
        df_final = df_final[~df_final.apply(lambda fila: fila.astype(str).str.strip().isin(["HAWB", "EXPORTER", "FB", "PIECES", "WEIGHT (Kg)", "FREIGHT ($)", "DUTY ($)", "OTHER CHARGES"])).any(axis=1)]
        df_final = df_final.reset_index(drop=True)
        df_final = convertir_columnas_a_numerico(df_final)
        df_final['OTHER CHARGES'] = df_final['WEIGHT (Kg)'].astype(float).round(0) * v1
        df_final['CHECKED FREIGHT ($)'] = df_final['FREIGHT ($)']  

        mask = df_final['CLIENT'].str.contains('WFM', na=False)
        df_final.loc[mask, 'CHECKED FREIGHT ($)'] = (
            df_final.loc[mask, 'FREIGHT ($)'] / v3 * v2
        ).round(2)

        df_final['TOTAL CHARGES'] = df_final['CHECKED FREIGHT ($)'].astype(float) + df_final['OTHER CHARGES']
        df_final['TOTAL CHARGES'] = df_final['TOTAL CHARGES'].round(2)
        col = df_final.pop("CHECKED FREIGHT ($)")
        df_final.insert(7, 'BASE RATE', df_final['CLIENT'].apply(lambda x: v2 if 'WFM' in str(x) else v3))
        df_final.insert(8, "CHECKED FREIGHT ($)", col)
        fecha_actual = datetime.today().strftime("%Y-%m-%d")
        df_final.insert(0, 'PROCESS DATE', fecha_actual)
        df_final.insert(1, 'NUMBER', inv_number)
        df_final.insert(2, 'DATE', inv_date)
        df_final.insert(3, 'AWB MASTER', inv_awb)
        return df_final, inv_date, inv_number, inv_awb
    except Exception as e:
        return None

