import os
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import queue
import threading
from .downloader import run_download

class NovelDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RanobeLib Downloader")
        self.root.geometry("800x600")
        self.root.resizable(True, True)
        
        # Переменные
        self.novel_url = tk.StringVar()
        self.save_images = tk.BooleanVar(value=True)
        self.output_dir = tk.StringVar(value=os.path.join(os.getcwd(), "output"))
        
        # Очередь для межпоточного общения
        self.log_queue = queue.Queue()
        
        self.create_widgets()
        self.update_logs()
        self.check_output_dir()

    def check_output_dir(self):
        output_dir = self.output_dir.get()
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def create_widgets(self):
        style = ttk.Style()
        style.theme_use("clam")  # Альтернативные темы: "alt", "default", "classic"
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=6)
        style.configure("TCheckbutton", font=("Segoe UI", 10))
        style.configure("TLabelframe.Label", font=("Segoe UI", 11, "bold"))
        style.configure("TEntry", padding=5)
    
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    
        input_frame = ttk.LabelFrame(main_frame, text="🔽 Параметры загрузки")
        input_frame.pack(fill=tk.X, padx=10, pady=10)
    
        url_frame = ttk.Frame(input_frame)
        url_frame.pack(fill=tk.X, padx=5, pady=5)
    
        ttk.Label(url_frame, text="Ссылка на новеллу:").pack(side=tk.LEFT, padx=(0, 5))
        url_entry = ttk.Entry(url_frame, textvariable=self.novel_url, width=70)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
    
        options_frame = ttk.Frame(input_frame)
        options_frame.pack(fill=tk.X, padx=5, pady=5)
    
        img_check = ttk.Checkbutton(
            options_frame, 
            text="Сохранять изображения", 
            variable=self.save_images
        )
        img_check.pack(side=tk.LEFT)
    
        ttk.Label(options_frame, text="Папка сохранения:").pack(side=tk.LEFT, padx=(20, 5))
        dir_entry = ttk.Entry(options_frame, textvariable=self.output_dir, width=40, state='readonly')
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(options_frame, text="📁", width=3, command=self.select_directory).pack(side=tk.LEFT)
    
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=(10, 0))
    
        self.download_btn = ttk.Button(
            btn_frame, 
            text="⬇ Начать загрузку", 
            command=self.start_download,
            width=20
        )
        self.download_btn.pack(pady=5)
    
        log_frame = ttk.LabelFrame(main_frame, text="📋 Прогресс выполнения")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
        self.log_area = scrolledtext.ScrolledText(
            log_frame, 
            state='disabled',
            wrap=tk.WORD,
            font=("Consolas", 10),
            background="#f9f9f9"
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
        self.status_var = tk.StringVar(value="Готов к работе")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=("Segoe UI", 9)
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    

    def select_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.output_dir.set(directory)
            self.check_output_dir()

    def start_download(self):
        url = self.novel_url.get().strip()
        if not url:
            messagebox.showerror("Ошибка", "Введите ссылку на новеллу")
            return
            
        # Очищаем лог
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        
        # Отключить кнопку во время загрузки
        self.download_btn.config(state=tk.DISABLED)
        self.status_var.set("Загрузка начата...")
        
        # Запуск в отдельном потоке
        thread = threading.Thread(
            target=run_download,
            args=(
                url,
                self.save_images.get(),
                self.output_dir.get(),
                self.log_queue
            ),
            daemon=True
        )
        thread.start()

    def update_logs(self):
        # Проверяем очередь сообщений
        while not self.log_queue.empty():
            msg = self.log_queue.get()
            self.log_area.config(state=tk.NORMAL)
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.config(state=tk.DISABLED)
            self.log_area.yview(tk.END)
        
        # Проверяем состояние кнопки
        if self.download_btn['state'] == tk.DISABLED:
            # Если активных потоков нет - включаем кнопку
            if threading.active_count() == 1:
                self.download_btn.config(state=tk.NORMAL)
                self.status_var.set("Готов к работе")
        
        # Повторяем каждые 100мс
        self.root.after(100, self.update_logs)
