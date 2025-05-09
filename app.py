import customtkinter as ctk
from tkinter import filedialog, messagebox
import paperless
import pandas as pd
import destiny
import sys
import os
import json

def select_files():
    files = filedialog.askopenfilenames(
        title="Selecciona los archivos PDF",
        filetypes=[("Archivos PDF", "*.pdf")]
    )
    if not files:
        return []
    return files

def process_destiny_pdfs(files, v1, rates):
    try:
        all_dataFrames = []
        inv_dates = []

        for file in files:
            try:
                df, inv_date, inv_number, inv_awb = destiny.procesar_pdf(file, v1, rates)
                all_dataFrames.append(df)
                inv_dates.append(inv_date)
            except Exception as e:
                print(e)
                messagebox.showerror("Error", f"Error al procesar el archivo")
                return

        if len(all_dataFrames) > 1:
            min_inv_date = min(inv_dates)
            max_inv_date = max(inv_dates)
            output_filename = f"{min_inv_date}-{max_inv_date}.xlsx"
        else:
            output_filename = f"{inv_awb}-{inv_date}-{inv_number}.xlsx"

        combined_df = pd.concat(all_dataFrames, ignore_index=True)
        combined_df = combined_df.sort_values(by='AWB MASTER', key=lambda col: col.str[:3].astype(int)).reset_index(drop=True)
        combined_df.to_excel(output_filename, index=False)
        messagebox.showinfo("Éxito", f"Archivo guardado como: {output_filename}")

    except Exception as e:
        messagebox.showerror("Error", f"Error al procesar los archivos")

def proccess_paperless_pdfs(files):
    try:
        # List to store all DataFrames
        all_dataframes = []
        import_dates = []

        for file in files:
            try:
                df, import_date, filer_code, awb = paperless.process_pdf(file)
                filer_code = filer_code.replace("-","")
                import_date = import_date.replace("/","-")
                all_dataframes.append(df)
                import_dates.append(import_date)
            except:
                messagebox.showerror("Error", f"Error al procesar el archivo")
                return
                
        if len(all_dataframes) > 1:
            min_import_date = min(import_dates)
            max_import_date = max(import_dates)
            output_filename = f"{min_import_date}-{max_import_date}.xlsx"
        else:
            output_filename = f"{filer_code}-{import_date}-{awb}.xlsx"
            
        combined_df = pd.concat(all_dataframes, ignore_index=True)

        combined_df.to_excel(output_filename, index=False)
        messagebox.showinfo("Éxito", f"Archivo guardado como: {output_filename}")

    except Exception as e:
        messagebox.showerror("Error", "Error al procesar los archivos")

def create_interface():
    # Window configuration
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("green")
    window = ctk.CTk()
    window.geometry("400x220")
    window.title("BellaFlor")

    # Get background color
    bg_color = window.cget("fg_color")

    label_title = ctk.CTkLabel(window, text="Procesamiento de Facturas", font=("Arial", 16))
    label_title.pack(pady=10)

    combobox = ctk.CTkComboBox(window, values=['Destiny', 'Duties'])
    combobox.pack(pady=10)

    content_frame = ctk.CTkFrame(window, fg_color=bg_color)
    content_frame.pack(pady=10, padx=20, fill="both", expand=True)

    def combobox_callback(option):
        for widget in content_frame.winfo_children():
            widget.destroy()

        if option == "Destiny":
            input = ctk.CTkEntry(content_frame, placeholder_text="Flete = 0.02")
            input.pack(pady=5)
            def on_submit():
                value = float(input.get()) if input.get().strip() else 0.02
                files = select_files()
                if not files:
                    return
                if getattr(sys, 'frozen', False):
                    base_dir = os.path.dirname(sys.executable)
                else:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(base_dir, "rates.json")
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        rates = json.load(f)
                except Exception as e:
                    messagebox.showerror("Error", f"❌ No se pudo leer el archivo rates.json:\n{e}")
                    return None
                process_destiny_pdfs(files, value, rates)
            button = ctk.CTkButton(content_frame, text="Seleccionar archivos", command=on_submit)
            button.pack(pady=5)

        elif option == "Duties":
            def on_submit():
                files = select_files()
                if not files:
                    return
                proccess_paperless_pdfs(files)
            button = ctk.CTkButton(content_frame, text="Seleccionar archivos", command=on_submit)
            button.pack(pady=5)

    combobox.configure(command=combobox_callback)
    window.mainloop()

if __name__ == "__main__":
    create_interface()
