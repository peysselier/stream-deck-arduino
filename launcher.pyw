import ctypes
import glob
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

import pystray
from PIL import Image, ImageTk

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(SCRIPT_DIR, "script.py")
LOCK_FILE = os.path.join(SCRIPT_DIR, "launcher.lock")
LOGO_FILE = os.path.join(SCRIPT_DIR, "logo.png")

# ──────────────────────────────────────────
# PALETTE
# ──────────────────────────────────────────
COLOR_BG_WINDOW = "#1a1a1a"
COLOR_BG_TOPBAR = "#212121"
COLOR_BG_LOGS = "#0d0d0d"
COLOR_TEXT_MAIN = "#e8e6e3"
COLOR_TEXT_LOGS = "#d4d0c8"
COLOR_ACCENT = "#c9620a"
COLOR_ACCENT_HOVER = "#d4732b"
COLOR_STATUS_ON_BG = "#2d6a2d"
COLOR_STATUS_ON_FG = "#90ee90"
COLOR_STATUS_OFF_BG = "#6a2d2d"
COLOR_STATUS_OFF_FG = "#ff9090"
COLOR_BORDER = "#2e2e2e"
COLOR_BUTTON_BG = "#2a2a2a"
COLOR_BUTTON_ACTIVE = "#3a3a3a"
COLOR_LABEL_MUTED = "#888888"


# ──────────────────────────────────────────
# UTILITAIRES SYSTÈME (verrou, tray, DWM)
# ──────────────────────────────────────────
def is_pid_running(pid):
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def acquire_single_instance_lock():
    """Retourne True si on a obtenu le verrou (aucune autre instance active)."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE) as f:
                old_pid = int(f.read().strip())
            if is_pid_running(old_pid):
                return False
        except (ValueError, OSError):
            pass
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    return True


def release_single_instance_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def load_tray_icon_image():
    """Charge logo.png ou un .ico présent dans le dossier du projet, sinon génère un carré vert."""
    if os.path.exists(LOGO_FILE):
        try:
            return Image.open(LOGO_FILE)
        except Exception:
            pass
    ico_files = glob.glob(os.path.join(SCRIPT_DIR, "*.ico"))
    if ico_files:
        try:
            return Image.open(ico_files[0])
        except Exception:
            pass
    img = Image.new("RGB", (64, 64), "green")
    return img


def apply_dark_titlebar(window):
    """Active le mode sombre de la barre de titre native (Windows 10/11)."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
    except Exception:
        pass


def apply_rounded_corners(window):
    """Coins arrondis natifs (Windows 11) avec repli SetWindowRgn (Windows 10).

    Retourne True si le repli SetWindowRgn est utilisé (nécessite un réajustement
    de la région à chaque redimensionnement de la fenêtre).
    """
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        # Windows 11 : préférence de coin arrondi gérée nativement par le DWM.
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
            ctypes.sizeof(ctypes.c_int),
        )
        if result == 0:
            return False  # succès, rien d'autre à faire
    except Exception:
        hwnd = None

    # Windows 10 (ou échec ci-dessus) : on découpe la fenêtre avec un rectangle
    # à coins arrondis. Doit être réappliqué à chaque redimensionnement.
    try:
        if hwnd is None:
            hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        _apply_round_region(hwnd, window.winfo_width(), window.winfo_height())
        return True
    except Exception:
        return False


def _apply_round_region(hwnd, width, height, radius=12):
    region = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius, radius)
    ctypes.windll.user32.SetWindowRgn(hwnd, region, True)


# ──────────────────────────────────────────
# WIDGETS À COINS ARRONDIS (Canvas)
# ──────────────────────────────────────────
def round_rectangle(canvas, x1, y1, x2, y2, r=8, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2,
        x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def make_separator(parent, bg=COLOR_BG_WINDOW, line_color=COLOR_BORDER):
    """Ligne de séparation dessinée sur un Canvas (remplace un Frame de 1px)."""
    canvas = tk.Canvas(parent, height=1, bg=bg, highlightthickness=0)

    def redraw(event):
        canvas.delete("all")
        canvas.create_line(0, 0, event.width, 0, fill=line_color)

    canvas.bind("<Configure>", redraw)
    return canvas


class RoundedButton(tk.Canvas):
    """Bouton à coins arrondis dessiné sur Canvas, avec effet hover."""

    def __init__(self, parent, text, command=None, bg=COLOR_BUTTON_BG, hover=COLOR_BUTTON_ACTIVE,
                 fg=COLOR_TEXT_MAIN, font=("Segoe UI", 9), radius=8, padx=14, pady=6,
                 parent_bg=COLOR_BG_TOPBAR):
        font_obj = tkfont.Font(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        width = font_obj.measure(text) + padx * 2
        height = font_obj.metrics("linespace") + pady * 2

        super().__init__(parent, width=width, height=height, bg=parent_bg,
                         highlightthickness=0, cursor="hand2")

        self.text = text
        self.command = command
        self.bg_color = bg
        self.hover_color = hover
        self.fg_color = fg
        self.font = font
        self.radius = radius
        self.w = width
        self.h = height

        self._redraw(self.bg_color)

        self.bind("<Enter>", lambda e: self._redraw(self.hover_color))
        self.bind("<Leave>", lambda e: self._redraw(self.bg_color))
        self.bind("<Button-1>", self._on_click)

    def _redraw(self, color):
        self.delete("all")
        round_rectangle(self, 1, 1, self.w - 1, self.h - 1, r=self.radius, fill=color, outline=color)
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=self.fg_color, font=self.font)

    def _on_click(self, event):
        if self.command:
            self.command()

    def set_colors(self, bg, hover):
        self.bg_color = bg
        self.hover_color = hover
        self._redraw(self.bg_color)


class RoundedBadge(tk.Canvas):
    """Badge pilule à coins arrondis (rayon 12px) pour le statut."""

    def __init__(self, parent, text, bg, fg, font=("Segoe UI", 9, "bold"), radius=12,
                 padx=10, pady=2, parent_bg=COLOR_BG_WINDOW):
        self.font = font
        self.radius = radius
        self.padx = padx
        self.pady = pady

        font_obj = tkfont.Font(family=font[0], size=font[1], weight=font[2] if len(font) > 2 else "normal")
        height = font_obj.metrics("linespace") + pady * 2

        super().__init__(parent, height=height, bg=parent_bg, highlightthickness=0)
        self.h = height
        self.set_state(text, bg, fg)

    def set_state(self, text, bg, fg):
        font_obj = tkfont.Font(family=self.font[0], size=self.font[1],
                               weight=self.font[2] if len(self.font) > 2 else "normal")
        width = font_obj.measure(text) + self.padx * 2
        self.config(width=width)
        self.w = width

        self.delete("all")
        round_rectangle(self, 1, 1, self.w - 1, self.h - 1, r=self.radius, fill=bg, outline=bg)
        self.create_text(self.w / 2, self.h / 2, text=text, fill=fg, font=self.font)


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Stream Deck")
        self.root.geometry("750x500")
        self.root.minsize(500, 350)
        self.root.configure(bg=COLOR_BG_WINDOW)

        apply_dark_titlebar(self.root)

        # Icône de la fenêtre / barre des tâches
        self.window_icon = None
        if os.path.exists(LOGO_FILE):
            try:
                icon_img = Image.open(LOGO_FILE).resize((32, 32), Image.LANCZOS)
                self.window_icon = ImageTk.PhotoImage(icon_img)
                self.root.iconphoto(True, self.window_icon)
            except Exception:
                self.window_icon = None

        # Coins arrondis (natifs sur Windows 11, repli SetWindowRgn sur Windows 10)
        self._round_corners_fallback = apply_rounded_corners(self.root)
        if self._round_corners_fallback:
            self.root.bind("<Configure>", self._on_resize_round_corners)

        self.process = None
        self.log_queue = queue.Queue()
        self.reader_thread = None
        self.tray_icon = None

        # ──────────────────────────────────
        # HEADER
        # ──────────────────────────────────
        header = tk.Frame(self.root, bg=COLOR_BG_TOPBAR, height=60)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        # Titre (à gauche)
        left_frame = tk.Frame(header, bg=COLOR_BG_TOPBAR)
        left_frame.pack(side=tk.LEFT, padx=16)

        tk.Label(
            left_frame,
            text="Stream Deck",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_TEXT_MAIN,
            bg=COLOR_BG_TOPBAR,
        ).pack(side=tk.LEFT)

        # Boutons (à droite)
        button_frame = tk.Frame(header, bg=COLOR_BG_TOPBAR)
        button_frame.pack(side=tk.RIGHT, padx=16)

        self.start_button = RoundedButton(
            button_frame, "Démarrer", command=self.start_process,
            bg=COLOR_BUTTON_BG, hover=COLOR_BUTTON_ACTIVE, parent_bg=COLOR_BG_TOPBAR,
        )
        self.restart_button = RoundedButton(
            button_frame, "Redémarrer", command=self.restart_process,
            bg=COLOR_BUTTON_BG, hover=COLOR_BUTTON_ACTIVE, parent_bg=COLOR_BG_TOPBAR,
        )
        self.stop_button = RoundedButton(
            button_frame, "Arrêter", command=self.stop_process,
            bg=COLOR_BUTTON_BG, hover=COLOR_BUTTON_ACTIVE, parent_bg=COLOR_BG_TOPBAR,
        )

        self.stop_button.pack(side=tk.LEFT, padx=4)
        self.restart_button.pack(side=tk.LEFT, padx=4)
        self.start_button.pack(side=tk.LEFT, padx=4)

        # Séparateur
        make_separator(self.root, bg=COLOR_BG_WINDOW, line_color=COLOR_BORDER).pack(fill=tk.X, side=tk.TOP)

        # ──────────────────────────────────
        # BANDEAU STATUT
        # ──────────────────────────────────
        status_frame = tk.Frame(self.root, bg=COLOR_BG_WINDOW)
        status_frame.pack(fill=tk.X, side=tk.TOP, padx=12, pady=6)

        tk.Label(
            status_frame, text="Statut :", font=("Segoe UI", 9), fg=COLOR_LABEL_MUTED, bg=COLOR_BG_WINDOW
        ).pack(side=tk.LEFT)

        self.status_badge = RoundedBadge(
            status_frame, "Arrêté", bg=COLOR_STATUS_OFF_BG, fg=COLOR_STATUS_OFF_FG,
            parent_bg=COLOR_BG_WINDOW,
        )
        self.status_badge.pack(side=tk.LEFT, padx=8)

        # ──────────────────────────────────
        # ZONE DE LOGS
        # ──────────────────────────────────
        log_frame = tk.Frame(self.root, bg=COLOR_BG_WINDOW)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        self.log_canvas = tk.Canvas(log_frame, bg=COLOR_BG_WINDOW, highlightthickness=0)
        self.log_canvas.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.Vertical.TScrollbar",
            background=COLOR_BUTTON_BG,
            troughcolor=COLOR_BG_LOGS,
            bordercolor=COLOR_BG_LOGS,
            arrowcolor=COLOR_TEXT_MAIN,
            width=8,
        )
        style.map(
            "Dark.Vertical.TScrollbar",
            background=[("active", COLOR_BUTTON_ACTIVE)],
        )

        log_inner = tk.Frame(self.log_canvas, bg=COLOR_BG_LOGS)

        scrollbar = ttk.Scrollbar(log_inner, orient=tk.VERTICAL, style="Dark.Vertical.TScrollbar")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.log_area = tk.Text(
            log_inner,
            state="disabled",
            bg=COLOR_BG_LOGS,
            fg=COLOR_TEXT_LOGS,
            font=("Consolas", 9),
            bd=0,
            highlightthickness=0,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            insertbackground=COLOR_TEXT_LOGS,
        )
        self.log_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_area.yview)

        self._log_inner_window = self.log_canvas.create_window(8, 8, anchor="nw", window=log_inner)
        self.log_canvas.bind("<Configure>", self._redraw_log_background)

        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        # ─── Icône système (tray) ───
        self.start_tray_icon()

        # Lancement automatique au démarrage
        self.start_process()

        # Démarre le polling de la queue de logs
        self.root.after(100, self.poll_log_queue)

    # ─── Zone de logs : fond arrondi ───
    def _redraw_log_background(self, event):
        self.log_canvas.delete("bg")
        round_rectangle(
            self.log_canvas, 0, 0, event.width, event.height, r=8,
            fill=COLOR_BG_LOGS, outline=COLOR_BG_LOGS, tags="bg",
        )
        inset = 8
        self.log_canvas.coords(self._log_inner_window, inset, inset)
        self.log_canvas.itemconfig(
            self._log_inner_window,
            width=max(event.width - 2 * inset, 0),
            height=max(event.height - 2 * inset, 0),
        )

    # ─── Coins arrondis (repli Windows 10) ───
    def _on_resize_round_corners(self, event):
        if event.widget is not self.root:
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            _apply_round_region(hwnd, event.width, event.height)
        except Exception:
            pass

    # ─── Gestion du processus ───
    def start_process(self):
        if self.process and self.process.poll() is None:
            return  # déjà en cours

        self.process = subprocess.Popen(
            [sys.executable, "-u", TARGET_SCRIPT],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )

        self.reader_thread = threading.Thread(target=self.read_output, daemon=True)
        self.reader_thread.start()

        self.set_status(True)
        self.append_log("[Launcher] script.py démarré.\n")

    def read_output(self):
        proc = self.process
        try:
            for line in proc.stdout:
                self.log_queue.put(line)
        except Exception:
            pass
        finally:
            proc.wait()
            self.log_queue.put(None)  # signale la fin du processus

    def stop_process(self):
        if not self.process or self.process.poll() is not None:
            self.set_status(False)
            return

        self.append_log("[Launcher] Arrêt en cours...\n")
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.append_log("[Launcher] Le script ne répond pas, arrêt forcé.\n")
            self.process.kill()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

        self.set_status(False)
        self.append_log("[Launcher] Script arrêté.\n")

    def restart_process(self):
        self.append_log("[Launcher] Redémarrage...\n")
        self.stop_process()
        self.start_process()

    # ─── UI ───
    def set_status(self, running):
        if running:
            self.status_badge.set_state("En cours", COLOR_STATUS_ON_BG, COLOR_STATUS_ON_FG)
            self.start_button.set_colors(COLOR_BUTTON_BG, COLOR_BUTTON_ACTIVE)
        else:
            self.status_badge.set_state("Arrêté", COLOR_STATUS_OFF_BG, COLOR_STATUS_OFF_FG)
            self.start_button.set_colors(COLOR_ACCENT, COLOR_ACCENT_HOVER)

    def append_log(self, text):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, text)
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line is None:
                    self.set_status(False)
                else:
                    if line and "[SERIE reçu] Etats:" in line:
                        continue
                    self.append_log(line)
        except queue.Empty:
            pass
        self.root.after(100, self.poll_log_queue)

    # ─── Icône système (tray) ───
    def start_tray_icon(self):
        menu = pystray.Menu(
            pystray.MenuItem("Afficher", self.show_window),
            pystray.MenuItem("Quitter", self.quit_app),
        )
        self.tray_icon = pystray.Icon(
            "stream_deck_launcher",
            load_tray_icon_image(),
            "Stream Deck Launcher",
            menu,
        )
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        self.root.after(0, self._show_window)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self):
        self.root.withdraw()

    def quit_app(self, icon=None, item=None):
        self.root.after(0, self._quit_app)

    def _quit_app(self):
        self.stop_process()
        if self.tray_icon:
            self.tray_icon.stop()
        release_single_instance_lock()
        self.root.destroy()


if __name__ == "__main__":
    if not acquire_single_instance_lock():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "Stream Deck Launcher",
            "Le launcher est déjà en cours d'exécution (voir l'icône dans la barre des tâches système).",
        )
        sys.exit(0)

    root = tk.Tk()
    app = LauncherApp(root)
    root.mainloop()
