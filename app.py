import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading, json, sys, os

import paperless
import destiny
import pandas as pd

# ---------- SELECCIONAR PDF ----------
def select_files() -> tuple[str]:
    return filedialog.askopenfilenames(
        title="Selecciona los archivos PDF",
        filetypes=[("Archivos PDF", "*.pdf")]
    )

# ---------- PROCESAMIENTO ­DESTINY ----------
def process_destiny_pdfs(files, v1, rates, on_progress=None):
    all_dfs, inv_dates = [], []

    for i, file in enumerate(files, start=1):
        try:
            df, inv_date, inv_number, inv_awb = destiny.procesar_pdf(file, v1, rates)
            all_dfs.append(df)
            inv_dates.append(inv_date)
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar {os.path.basename(file)}")
            return
        if on_progress: on_progress(i)

    output_filename = (f"{min(inv_dates)}-{max(inv_dates)}.xlsx"
                       if len(all_dfs) > 1
                       else f"{inv_awb}-{inv_date}-{inv_number}.xlsx")

    (pd.concat(all_dfs, ignore_index=True)
       .sort_values(by='AWB MASTER',
                    key=lambda c: c.str[:3].astype(int))
       .reset_index(drop=True)
       .to_excel(output_filename, index=False))

    messagebox.showinfo("Éxito", f"Archivo guardado como:\n{output_filename}")

# ---------- PROCESAMIENTO DUTTIES ----------
def process_paperless_pdfs(files, on_progress=None):
    all_dfs, import_dates = [], []

    for i, file in enumerate(files, start=1):
        try:
            df, import_date, filer_code, awb = paperless.process_pdf(file)
            import_dates.append(import_date := import_date.replace("/", "-"))
            filer_code = filer_code.replace("-", "")
            all_dfs.append(df)
        except Exception as e:
            messagebox.showerror("Error", f"Error al procesar {os.path.basename(file)}")
            return
        if on_progress: on_progress(i)

    output_filename = (f"{min(import_dates)}-{max(import_dates)}.xlsx"
                       if len(all_dfs) > 1
                       else f"{filer_code}-{import_date}-{awb}.xlsx")

    pd.concat(all_dfs, ignore_index=True).to_excel(output_filename, index=False)
    messagebox.showinfo("Éxito", f"Archivo guardado como:\n{output_filename}")

# ---------- BARRA DE PROGRESO ----------
def run_with_progress(task_fn, files, *args):
    total = len(files)
    if total == 0:
        return 

    # content_frame.pack_forget()
    progress_bar.pack(fill="x", padx=40)
    percent_label.pack()

    progress_bar.set(0)
    percent_var.set("0 %")

    def advance(done):
        frac = done / total
        progress_bar.set(frac)            
        percent_var.set(f"{int(frac*100)} %")

    def worker():
        try:
            task_fn(files, *args, on_progress=advance)
        finally:                         
            progress_bar.set(0)
            percent_var.set("")
            progress_bar.pack_forget()
            percent_label.pack_forget()
            content_frame.pack(pady=10, padx=20, fill="both", expand=True)

    threading.Thread(target=worker, daemon=True).start()

# ---------- INTERFAZ PRINCIPAL ----------
def create_interface():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("green")

    window = ctk.CTk()
    window.geometry("400x240")
    window.title("BellaFlor")
    window.resizable(False, False)

    ctk.CTkLabel(window, text="Procesamiento de Facturas",
                 font=("Arial", 16)).pack(pady=10)

    combobox = ctk.CTkComboBox(window, values=['Destiny', 'Duties'])
    combobox.pack(pady=10)

    global progress_bar, percent_var, percent_label, content_frame
    progress_bar = ctk.CTkProgressBar(window, mode="determinate")
    percent_var = ctk.StringVar()
    percent_label = ctk.CTkLabel(window, textvariable=percent_var,
                                font=("Arial", 12))
    content_frame = ctk.CTkFrame(window,
                                 fg_color=window.cget("fg_color"))
    content_frame.pack(pady=10, padx=20, fill="both", expand=True)

    def combobox_callback(option):
        for w in content_frame.winfo_children():
            w.destroy()

        if option == "Destiny":
            entry = ctk.CTkEntry(content_frame,
                                 placeholder_text="Flete = 0.02")
            entry.pack(pady=5)

            def on_submit():
                v1 = float(entry.get()) if entry.get().strip() else 0.02
                files = select_files()
                if not files:
                    return
                base_dir = (os.path.dirname(sys.executable)
                            if getattr(sys, 'frozen', False)
                            else os.path.dirname(os.path.abspath(__file__)))
                try:
                    with open(os.path.join(base_dir, "rates.json"),
                              encoding="utf-8") as f:
                        rates = json.load(f)
                except Exception as e:
                    messagebox.showerror("Error",
                        f"No se pudo leer rates.json")
                    return
                run_with_progress(process_destiny_pdfs, files, v1, rates)

            ctk.CTkButton(content_frame, text="Seleccionar archivos",
                          command=on_submit).pack(pady=5)

        elif option == "Duties":
            def on_submit():
                files = select_files()
                run_with_progress(process_paperless_pdfs, files)
            ctk.CTkButton(content_frame, text="Seleccionar archivos",
                          command=on_submit).pack(pady=5)

    combobox.configure(command=combobox_callback)
    window.mainloop()

# ---------- EJECUCIÓN ----------
if __name__ == "__main__":
    create_interface()
