import fitz
import pandas as pd
import re
import numpy as np
from datetime import datetime

def read_pdf (pdf_path):
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

def delete_first_data(df):
    i = 0
    while i < len(df):
        if re.match(r'(\d{4}\.\d{2}\.\d{2})', str(df.loc[i, 'Línea'])):
            break
        else:
            i += 1
    data = df.head(i-1)
    df = df.iloc[i-1:]
    df = df.reset_index(drop=True)
    return data, df

def search_data_buttom(search_data, data):
    results = []
    for item in search_data:
        indexes = data.index[(data['Línea'] == item) & (data['Página'] == 1)].tolist()
        for idx in indexes:
            if idx + 1 < len(data):
                results.append(data.iloc[idx + 1]['Línea'])
    return results
    
def search_data_top(search_data, data):
    results = []
    for item in search_data:
        indexes = data.index[(data['Línea'] == item) & (data['Página'] == 1)].tolist()
        for idx in indexes:
            if idx + 1 < len(data):
                results.append(data.iloc[idx - 1]['Línea'])
    return results

def delete_and_clean_data(df):
    df = df[~df.apply(lambda row: row.astype(str).str.strip().isin(["Totals for Invoice", "Invoice Value", "+/- MMV", "Exchange", "Entered Value"])).any(axis=1)]
    df = df.reset_index(drop=True)
    return df
                     
def delete_for_index (df, inferior_limit, superior_limit, type):
    if type == "awb":
        regex = r'[A-Z][A-Za-z0-9]{7,12}'
    elif type == "cbp form":
        regex = r'CBP Form \d+ \(\d{1,2}/\d{2}\)'

    indexes = set()
    for i in range(len(df)):
        value = str(df.loc[i, 'Línea'])
        if re.fullmatch(regex, value):
            for j in range(i + inferior_limit, i + superior_limit):
                if j < len(df):
                    indexes.add(j)
    df = df.drop(index=indexes).reset_index(drop=True)
    return df

def delete_range(df, column, value, start, end):
    pattern = r"^\$\d+\.\d+$"
    n_index = df[df[column] == value].index
    indexes_to_drop = set()
    
    for idx in n_index:
        for i in range(idx - start, idx + end):
            if i in df.index:
                cell_value = str(df.loc[i, column])
                if not re.match(pattern, cell_value):
                    indexes_to_drop.add(i)

    df = df.drop(index=indexes_to_drop).reset_index(drop=True)
    return df

def create_new_dataframe (df):
    final = pd.DataFrame(columns=['HAWB', 'INVOICE VALUE', 'DESCRIPTION', 'TYPE DUTIES', 'GUIDE', 'STEMS', 'ENTERED VALUE', 'RATES', 'DUTIES'])
    i = 0

    while i < len(df) - 1:
        val1 = str(df['Línea'].iloc[i])
        if i == len(df) - 2:
            val2 = str(df['Línea'].iloc[i + 1])
        elif i < len(df) - 5:
            val2 = str(df['Línea'].iloc[i + 1])
            val3 = str(df['Línea'].iloc[i + 2])
            val4 = str(df['Línea'].iloc[i + 3])
            val5 = str(df['Línea'].iloc[i + 4])
            val6 = str(df['Línea'].iloc[i + 5])
        elif i == len(df) - 5:
            val2 = str(df['Línea'].iloc[i + 1])
            val3 = str(df['Línea'].iloc[i + 2])

        if re.match(r'(\d{4}\.\d{2}\.\d{2})', val2) and re.match(r'1 KG', val3):
            new_row = {
                'DESCRIPTION': val1,
                'TYPE DUTIES': 'DUTTIES TARIFFES',
                'GUIDE': val2,
                'STEMS': val3,
                'RATES': val4,
                'DUTIES': val5,
            }
            final = pd.concat([final, pd.DataFrame([new_row])], ignore_index=True)
            i += 5
        elif re.search(r'(\d{4}\.\d{2}\.\d{4})+', val2):
            new_row = {
                'DESCRIPTION': val1,
                'TYPE DUTIES': 'DUTTIES',
                'GUIDE': val2,
                'STEMS': val3,
                'ENTERED VALUE': val4,
                'RATES': val5,
                'DUTIES': val6,
            }
            final = pd.concat([final, pd.DataFrame([new_row])], ignore_index=True)
            i += 6
        elif re.match(r'499 - Merchandise Processing Fee', val1):
            new_row = {
                'DESCRIPTION': val1,
                'TYPE DUTIES': 'OTHER CHARGES',
                'RATES': val2,
                'DUTIES': val3,
            }
            final = pd.concat([final, pd.DataFrame([new_row])], ignore_index=True)
            i += 3
        elif re.match(r'^[A-Z][A-Za-z0-9]{7,12}$', val1):
            if not final.empty:
                final.at[len(final) - 1, 'HAWB'] = val1
                final.at[len(final) - 1, 'INVOICE VALUE'] = val2
            i += 2
        else:
            i+=1
    return final

def insert_new_columns(final, filer_code, import_date, export_date, total_entered_value, duty, other, awb):
    actual_date = datetime.today().strftime("%d/%m/%Y")
    final.insert(0, 'PROCESS DATE (dd/mm/yyyy)', actual_date)
    final.insert(1, 'ENTRY NUMBER', filer_code)
    month, day, year = import_date.split("/")
    import_date = f"{day}/{month}/{year}"
    final.insert(2, 'IMPORT DATE (dd/mm/yyyy)', import_date)
    month, day, year = export_date.split("/")
    export_date = f"{day}/{month}/{year}"
    final.insert(3, 'EXPORT DATE (dd/mm/yyyy)', export_date)
    final.insert(4, 'TOTAL ENTERED VALUE', total_entered_value)
    final.insert(5, 'TOTAL DUTY', duty)
    final.insert(6, 'TOTAL OTHER FEES', other)
    guide_1 = awb.split(",")[0].strip()
    final.insert(7, 'MAWB', guide_1)
    return final

def format_columns (text):
    text = re.sub(r'\$', '', text)
    text = re.sub(r'USD', '', text)
    text = re.sub(r'NO', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_line(desc):
    if 'Merchandise Processing Fee' in desc:
        return '', desc
    match = re.match(r'^(\d{3})\s+(.*)', desc)
    if match:
        return match.group(1), match.group(2)
    else:
        return '', desc

def columns_to_numeric(final, columnas_a_convertir):
    for col in columnas_a_convertir:
        final[col] = final[col].astype(str).str.replace(',', '', regex=False)
        final[col] = pd.to_numeric(final[col], errors='coerce').fillna('')
    return final

def fill_columns(final):
    final['STEMS'] = final['STEMS'].where(~final['STEMS'].str.contains('KG', case=False, na=False), np.nan)
    final['HAWB'] = final['HAWB'][::-1].ffill()[::-1]
    final['INVOICE VALUE'] = final['INVOICE VALUE'][::-1].ffill()[::-1]
    final = final.fillna("")
    return final

def clean_columns(final):
    # FORMATEO DE COLUMNAS
    final['TOTAL ENTERED VALUE'] = final['TOTAL ENTERED VALUE'].apply(format_columns)
    final['TOTAL DUTY'] = final['TOTAL DUTY'].apply(format_columns)
    final['TOTAL OTHER FEES'] = final['TOTAL OTHER FEES'].apply(format_columns)
    final['INVOICE VALUE'] = final['INVOICE VALUE'].apply(format_columns)
    final['STEMS'] = final['STEMS'].apply(format_columns)
    final['ENTERED VALUE'] = final['ENTERED VALUE'].apply(format_columns)
    final['DUTIES'] = final['DUTIES'].apply(format_columns)
    # FORMATEAR GUIDE
    final['TYPE'] = final['GUIDE'].apply(lambda x: 'A~' if x.startswith('A~') else np.nan)
    final['GUIDE'] = final['GUIDE'].apply(lambda x: x[3:].strip() if x.startswith('A~') else x)

    # FORMATEAR DESCRIPTION
    final[['LINE', 'DESCRIPTION']] = final['DESCRIPTION'].apply(lambda x: pd.Series(extract_line(x)))
    # RELLENAR LINES
    final['LINE'] = final['LINE'].replace(r'^\s*$', np.nan, regex=True)
    final['LINE'] = final['LINE'].ffill()

    # CONVERSION A NÚMEROS
    final = columns_to_numeric(final, ['TOTAL ENTERED VALUE', 'TOTAL DUTY', 'TOTAL OTHER FEES', 'INVOICE VALUE', 'STEMS', 'ENTERED VALUE', 'DUTIES'])
    final = final.fillna("")
    return final

def process_pdf(pdf_path):
    try:
        df = read_pdf(pdf_path)
        data, df = delete_first_data(df)
        data_buttom = ['1. Filer Code/Entry Number', '11. Import Date', '12. B/L or AWB Number', '15. Export Date', '37. Duty' , '39. Other']
        data_top = ['35. Total Entered Value']
        result_buttom = search_data_buttom(data_buttom, data)
        filer_code, import_date, awb, export_date, duty, other = result_buttom
        result_top = search_data_top(data_top, data)
        total_entered_value = result_top[0]
        df = delete_and_clean_data(df)
        df = delete_range(df, 'Línea', 'N', 2, 1)
        df = delete_range(df, 'Línea', '1. Filer Code/Entry Number', 2, 28)
        df = delete_for_index(df, 2, 4, "awb")
        df = delete_for_index(df, 0, 2, "cbp form")
        final = create_new_dataframe(df)
        final = insert_new_columns(final, filer_code, import_date, export_date, total_entered_value, duty, other, awb)
        final = fill_columns(final)
        final = clean_columns(final)
        return final, import_date, filer_code, awb
    except ValueError:
        return None