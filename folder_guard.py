"""
FolderGuard v2.0 - 완성본
- 핸들 방식 삭제 방지
- 탐색기 즐겨찾기 고정
- 트레이 상주
- 중복 실행 방지
- 드래그 앤 드롭
- 부팅 시 자동 실행
- PC 재시작 후에도 자동 보호 복구
"""

import os
import sys
import json
import threading
import subprocess
import ctypes
import ctypes.wintypes
import tempfile
import atexit
import winreg
from tkinter import filedialog, messagebox
import customtkinter as ctk

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# ── 상수 ──────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".folderguard.json")
LOCK_FILE     = os.path.join(tempfile.gettempdir(), "folderguard.lock")
APP_NAME      = "FolderGuard"
REG_KEY       = r"Software\Microsoft\Windows\CurrentVersion\Run"

PURPLE        = "#5a46b4"
PURPLE_LIGHT  = "#7c6ee6"
PURPLE_BG     = "#f0edff"
PURPLE_BORDER = "#d4cef5"
TEXT_DARK     = "#2d2250"
TEXT_MID      = "#6b5fa8"
TEXT_MUTED    = "#a09ac0"
GREEN         = "#22c55e"
WHITE         = "#ffffff"


# ── 중복 실행 방지 ────────────────────────────────────
def is_already_running():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    atexit.register(lambda: os.remove(LOCK_FILE) if os.path.exists(LOCK_FILE) else None)
    return False


class FolderGuardApp:
    def __init__(self):
        self.folders  = []
        self.tray_icon = None
        self._handles  = {}
        self._load()
        self._restore_protection()  # PC 재시작 후 자동 보호 복구
        self._build_ui()

    # ── 저장/불러오기 ─────────────────────────────────
    def _load(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.folders = json.load(f).get("folders", [])
        except Exception:
            self.folders = []

    def _save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"folders": self.folders}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── PC 재시작 후 보호 자동 복구 ───────────────────
    def _restore_protection(self):
        for folder in self.folders:
            if folder.get("protected") and os.path.exists(folder["path"]):
                self._protect(folder["path"])
            if folder.get("pinned") and os.path.exists(folder["path"]):
                self._pin(folder["path"])

    # ── 부팅 자동 실행 ────────────────────────────────
    def _set_autostart(self, enable: bool):
        try:
            exe = sys.executable if not getattr(sys, 'frozen', False) else sys.executable
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

    def _get_autostart(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception:
            return False

    # ── UI ────────────────────────────────────────────
    def _build_ui(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        if DND_AVAILABLE:
            self.root = TkinterDnD.Tk()
            self.root.configure(bg="#f4f2fb")
        else:
            self.root = ctk.CTk()
            self.root.configure(fg_color="#f4f2fb")

        self.root.title(APP_NAME)
        self.root.geometry("460x760")
        self.root.resizable(False, False)

        self._make_header()
        self._make_body()
        self._make_statusbar()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh()

        # 트레이 자동 시작 (보호 중인 폴더 있으면)
        if any(f.get("protected") for f in self.folders) and TRAY_AVAILABLE:
            self._start_tray()

        self.root.mainloop()

    def _make_header(self):
        hdr = ctk.CTkFrame(self.root, fg_color=PURPLE, corner_radius=0, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        row = ctk.CTkFrame(hdr, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=22, pady=14)
        icon_box = ctk.CTkFrame(row, fg_color="#7259c9", corner_radius=13, width=50, height=50)
        icon_box.pack(side="left")
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="FG", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=WHITE).place(relx=0.5, rely=0.5, anchor="center")
        txt = ctk.CTkFrame(row, fg_color="transparent")
        txt.pack(side="left", padx=14)
        ctk.CTkLabel(txt, text="FolderGuard",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(txt, text="소중한 폴더를 실수로부터 보호해요",
                     font=ctk.CTkFont(size=12), text_color="#c5bcf0").pack(anchor="w")

    def _make_body(self):
        body = ctk.CTkFrame(self.root, fg_color=WHITE, corner_radius=0)
        body.pack(fill="both", expand=True)
        pad = ctk.CTkFrame(body, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=16)

        # 폴더 추가 버튼
        self.drop_btn = ctk.CTkButton(
            pad, text="  +  클릭해서 폴더 선택  |  여기에 폴더 끌어다 놓기",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=PURPLE_BG, text_color=PURPLE_LIGHT,
            hover_color="#e6e0ff", border_width=2, border_color=PURPLE_BORDER,
            corner_radius=13, height=58, command=self._add_folder)
        self.drop_btn.pack(fill="x", pady=(0, 14))

        if DND_AVAILABLE:
            self.drop_btn.drop_target_register(DND_FILES)
            self.drop_btn.dnd_bind("<<Drop>>", self._on_drop)

        ctk.CTkLabel(pad, text="보호 중인 폴더",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(pad, fg_color="transparent", height=200)
        self.list_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkFrame(pad, fg_color=PURPLE_BORDER, height=1).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(pad, text="설정",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

        self.opt_delete   = ctk.BooleanVar(value=True)
        self.opt_pin      = ctk.BooleanVar(value=True)
        self.opt_tray     = ctk.BooleanVar(value=True)
        self.opt_autostart = ctk.BooleanVar(value=self._get_autostart())

        opt_row = ctk.CTkFrame(pad, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 10))
        opt_row.columnconfigure((0,1,2,3), weight=1)

        self._opt_card(opt_row, "삭제 방지",   "실수로\n못 지우게",      self.opt_delete,   0)
        self._opt_card(opt_row, "즐겨찾기",    "탐색기 왼쪽\n고정",      self.opt_pin,      1)
        self._opt_card(opt_row, "트레이 상주", "백그라운드\n보호",        self.opt_tray,     2)
        self._opt_card(opt_row, "자동 실행",   "PC 켤 때\n자동 시작",    self.opt_autostart, 3)

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x")
        btn_row.columnconfigure((0,1), weight=1)

        ctk.CTkButton(btn_row, text="보호 해제",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=PURPLE_BG, text_color=PURPLE_LIGHT,
                      hover_color="#e6e0ff", border_width=2, border_color=PURPLE_BORDER,
                      corner_radius=12, height=50, command=self._release_all
                      ).grid(row=0, column=0, padx=(0,6), sticky="ew")

        ctk.CTkButton(btn_row, text="✓  적용하기",
                      font=ctk.CTkFont(size=15, weight="bold"),
                      fg_color=PURPLE, hover_color="#4a3494",
                      corner_radius=12, height=50, command=self._apply
                      ).grid(row=0, column=1, padx=(6,0), sticky="ew")

    def _opt_card(self, parent, title, desc, var, col):
        frame = ctk.CTkFrame(parent, fg_color=PURPLE_BG, corner_radius=12,
                             border_width=2, border_color=PURPLE_BORDER)
        frame.grid(row=0, column=col, padx=3, sticky="nsew")
        ctk.CTkCheckBox(frame, text="", variable=var, width=20,
                         fg_color=PURPLE_LIGHT, hover_color=PURPLE,
                         checkmark_color=WHITE, border_color=PURPLE_BORDER).pack(pady=(10,4))
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#4a3d8a", justify="center").pack()
        ctk.CTkLabel(frame, text=desc, font=ctk.CTkFont(size=10),
                     text_color=TEXT_MUTED, justify="center").pack(pady=(2,10))

    def _make_statusbar(self):
        bar = ctk.CTkFrame(self.root, fg_color=PURPLE_BG, corner_radius=0, height=40)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=22)
        self.status_lbl = ctk.CTkLabel(inner, text="● 보호 중인 폴더 없음",
                                        font=ctk.CTkFont(size=13), text_color=TEXT_MID)
        self.status_lbl.pack(side="left", pady=10)
        ctk.CTkLabel(inner, text="v2.0", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(side="right", pady=10)

    # ── 목록 갱신 ─────────────────────────────────────
    def _refresh(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        if not self.folders:
            ctk.CTkLabel(self.list_frame,
                         text="아직 보호 중인 폴더가 없어요\n위 버튼을 눌러 추가해 보세요",
                         font=ctk.CTkFont(size=13), text_color="#c0b8e0",
                         justify="center").pack(pady=20)
        else:
            for i, folder in enumerate(self.folders):
                self._folder_card(folder, i)
        count = sum(1 for f in self.folders if f.get("protected"))
        self.status_lbl.configure(
            text=f"● {count}개 폴더 보호 중입니다" if count else "● 보호 중인 폴더 없음")

    def _folder_card(self, folder, idx):
        card = ctk.CTkFrame(self.list_frame, fg_color=PURPLE_BG, corner_radius=12,
                            border_width=2, border_color=PURPLE_BORDER)
        card.pack(fill="x", pady=4)
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=12, pady=10)
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        name = os.path.basename(folder["path"])
        ctk.CTkLabel(info, text=f"[폴더]  {name}",
                     font=ctk.CTkFont(size=14, weight="bold"),
                     text_color=TEXT_DARK, anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=folder["path"],
                     font=ctk.CTkFont(size=10), text_color=TEXT_MUTED, anchor="w").pack(anchor="w")
        right = ctk.CTkFrame(row, fg_color="transparent")
        right.pack(side="right", padx=(8,0))
        if folder.get("protected"):
            ctk.CTkLabel(right, text="● 보호중",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=GREEN).pack(pady=(0,4))
        ctk.CTkButton(right, text="X", width=32, height=32,
                       fg_color=WHITE, text_color="#c4b8e8",
                       hover_color="#ffe4e4", border_width=1, border_color=PURPLE_BORDER,
                       corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
                       command=lambda i=idx: self._remove(i)).pack()

    # ── 액션 ──────────────────────────────────────────
    def _on_drop(self, event):
        raw = event.data.strip()
        paths = [p.strip("{}") for p in raw.split("} {")] if raw.startswith("{") else raw.split()
        for path in paths:
            path = os.path.normpath(path.strip('"'))
            if os.path.isdir(path) and not any(f["path"] == path for f in self.folders):
                self.folders.append({"path": path, "original_name": os.path.basename(path),
                                     "protected": False, "pinned": False})
        self._save()
        self._refresh()

    def _add_folder(self):
        path = filedialog.askdirectory(title="보호할 폴더를 선택하세요")
        if not path:
            return
        path = os.path.normpath(path)
        if any(f["path"] == path for f in self.folders):
            messagebox.showinfo("안내", "이미 목록에 있는 폴더예요.")
            return
        self.folders.append({"path": path, "original_name": os.path.basename(path),
                              "protected": False, "pinned": False})
        self._save()
        self._refresh()

    def _apply(self):
        if not self.folders:
            messagebox.showinfo("안내", "보호할 폴더를 먼저 추가해주세요.")
            return
        done = 0
        for folder in self.folders:
            path = folder["path"]
            if not os.path.exists(path):
                continue
            if self.opt_delete.get() and not folder.get("protected"):
                if self._protect(path):
                    folder["protected"] = True
            if self.opt_pin.get() and not folder.get("pinned"):
                self._pin(path)
                folder["pinned"] = True
            done += 1
        # 부팅 자동 실행 설정
        self._set_autostart(self.opt_autostart.get())
        self._save()
        self._refresh()
        if self.opt_tray.get() and TRAY_AVAILABLE:
            self._start_tray()
        messagebox.showinfo("완료", f"{done}개 폴더에 보호를 적용했어요!")

    def _release_all(self):
        if not self.folders:
            messagebox.showinfo("안내", "보호 중인 폴더가 없어요.")
            return
        if not messagebox.askyesno("보호 해제", "모든 폴더의 보호를 해제할까요?"):
            return
        for folder in self.folders:
            if folder.get("protected"):
                self._unprotect(folder["path"])
                folder["protected"] = False
            if folder.get("pinned"):
                self._unpin(folder["path"])
                folder["pinned"] = False
        self._save()
        self._refresh()
        messagebox.showinfo("완료", "모든 보호가 해제됐어요.")

    def _remove(self, idx):
        folder = self.folders[idx]
        if folder.get("protected"):
            self._unprotect(folder["path"])
        if folder.get("pinned"):
            self._unpin(folder["path"])
        self.folders.pop(idx)
        self._save()
        self._refresh()

    # ── 보호 (핸들 방식) ──────────────────────────────
    def _protect(self, path):
        try:
            if path in self._handles:
                return True
            GENERIC_READ               = 0x80000000
            FILE_SHARE_READ            = 0x00000001
            FILE_SHARE_WRITE           = 0x00000002
            FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
            OPEN_EXISTING              = 3
            handle = ctypes.windll.kernel32.CreateFileW(
                path, GENERIC_READ,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS, None)
            INVALID_HANDLE = ctypes.wintypes.HANDLE(-1).value
            if handle == INVALID_HANDLE:
                raise Exception("핸들을 열 수 없어요.")
            self._handles[path] = handle
            return True
        except Exception as e:
            messagebox.showerror("오류", f"보호 적용 실패:\n{e}")
            return False

    def _unprotect(self, path):
        handle = self._handles.pop(path, None)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)

    # ── 즐겨찾기 고정 ─────────────────────────────────
    def _pin(self, path):
        try:
            ps = f'powershell -WindowStyle Hidden -Command "$s=(New-Object -Com Shell.Application).NameSpace(\\"{path}\\"); $s.Self.InvokeVerb(\\"pintohome\\")"'
            subprocess.run(ps, capture_output=True, shell=True)
        except Exception:
            pass
        return path

    def _unpin(self, path):
        try:
            ps = f'powershell -WindowStyle Hidden -Command "$s=(New-Object -Com Shell.Application).NameSpace(\\"{path}\\"); $s.Self.InvokeVerb(\\"unpinfromhome\\")"'
            subprocess.run(ps, capture_output=True, shell=True)
        except Exception:
            pass
        return path

    # ── 트레이 ────────────────────────────────────────
    def _start_tray(self):
        if self.tray_icon or not TRAY_AVAILABLE:
            return
        img = Image.new("RGBA", (64, 64), (90, 70, 180, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(124, 110, 230, 255))
        menu = pystray.Menu(
            pystray.MenuItem("FolderGuard 열기", self._show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self._quit))
        self.tray_icon = pystray.Icon(APP_NAME, img, f"{APP_NAME} 실행 중", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_window(self, *_):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def _on_close(self):
        if self.opt_tray.get() and TRAY_AVAILABLE:
            self.root.withdraw()
            self._start_tray()
        else:
            self._quit()

    def _quit(self, *_):
        for handle in self._handles.values():
            ctypes.windll.kernel32.CloseHandle(handle)
        self._handles.clear()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()


if __name__ == "__main__":
    if is_already_running():
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_NAME, "FolderGuard가 이미 실행 중이에요!\n트레이 아이콘을 확인해주세요.")
        root.destroy()
    else:
        FolderGuardApp()
