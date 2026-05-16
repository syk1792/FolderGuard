"""
FolderGuard - 폴더 실수 삭제 방지 프로그램
"""

import os
import json
import threading
import subprocess
from tkinter import filedialog, messagebox
import customtkinter as ctk

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".folderguard.json")
PIN_PREFIX    = "! "

PURPLE        = "#5a46b4"
PURPLE_LIGHT  = "#7c6ee6"
PURPLE_BG     = "#f0edff"
PURPLE_BORDER = "#d4cef5"
TEXT_DARK     = "#2d2250"
TEXT_MID      = "#6b5fa8"
TEXT_MUTED    = "#a09ac0"
GREEN         = "#22c55e"
WHITE         = "#ffffff"


class FolderGuardApp:
    def __init__(self):
        self.folders = []
        self.tray_icon = None
        self._load()
        self._build_ui()

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

    def _build_ui(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("FolderGuard")
        self.root.geometry("460x720")
        self.root.resizable(False, False)
        self.root.configure(fg_color="#f4f2fb")

        # 헤더
        hdr = ctk.CTkFrame(self.root, fg_color=PURPLE, corner_radius=0, height=80)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        hdr_inner = ctk.CTkFrame(hdr, fg_color="transparent")
        hdr_inner.pack(fill="both", expand=True, padx=22, pady=14)

        icon_box = ctk.CTkFrame(hdr_inner, fg_color="#7259c9", corner_radius=13, width=50, height=50)
        icon_box.pack(side="left")
        icon_box.pack_propagate(False)
        ctk.CTkLabel(icon_box, text="FG", font=ctk.CTkFont(size=16, weight="bold"),
                     text_color=WHITE).place(relx=0.5, rely=0.5, anchor="center")

        txt_box = ctk.CTkFrame(hdr_inner, fg_color="transparent")
        txt_box.pack(side="left", padx=14)
        ctk.CTkLabel(txt_box, text="FolderGuard",
                     font=ctk.CTkFont(size=20, weight="bold"), text_color=WHITE).pack(anchor="w")
        ctk.CTkLabel(txt_box, text="소중한 폴더를 실수로부터 보호해요",
                     font=ctk.CTkFont(size=12), text_color="#c5bcf0").pack(anchor="w")

        # 본문
        body = ctk.CTkFrame(self.root, fg_color=WHITE, corner_radius=0)
        body.pack(fill="both", expand=True)

        pad = ctk.CTkFrame(body, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=22, pady=16)

        # 폴더 추가 버튼
        ctk.CTkButton(
            pad, text="  +  보호할 폴더 선택하기",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PURPLE_BG, text_color=PURPLE_LIGHT,
            hover_color="#e6e0ff",
            border_width=2, border_color=PURPLE_BORDER,
            corner_radius=13, height=54,
            command=self._add_folder
        ).pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(pad, text="보호 중인 폴더",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

        self.list_frame = ctk.CTkScrollableFrame(pad, fg_color="transparent", height=190)
        self.list_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkFrame(pad, fg_color=PURPLE_BORDER, height=1).pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(pad, text="설정",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 8))

        self.opt_delete = ctk.BooleanVar(value=True)
        self.opt_pin    = ctk.BooleanVar(value=True)
        self.opt_tray   = ctk.BooleanVar(value=True)

        opt_row = ctk.CTkFrame(pad, fg_color="transparent")
        opt_row.pack(fill="x", pady=(0, 14))
        opt_row.columnconfigure((0, 1, 2), weight=1)

        self._opt_card(opt_row, "삭제 방지",  "실수로\n못 지우게",   self.opt_delete, 0)
        self._opt_card(opt_row, "상단 고정",  "탐색기\n맨 위 표시", self.opt_pin,    1)
        self._opt_card(opt_row, "트레이 상주","백그라운드\n보호",    self.opt_tray,   2)

        btn_row = ctk.CTkFrame(pad, fg_color="transparent")
        btn_row.pack(fill="x")
        btn_row.columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row, text="보호 해제",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PURPLE_BG, text_color=PURPLE_LIGHT,
            hover_color="#e6e0ff",
            border_width=2, border_color=PURPLE_BORDER,
            corner_radius=12, height=50,
            command=self._release_all
        ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

        ctk.CTkButton(
            btn_row, text="✓  적용하기",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=PURPLE, hover_color="#4a3494",
            corner_radius=12, height=50,
            command=self._apply
        ).grid(row=0, column=1, padx=(6, 0), sticky="ew")

        # 상태바
        bar = ctk.CTkFrame(self.root, fg_color=PURPLE_BG, corner_radius=0, height=40)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        bar_inner = ctk.CTkFrame(bar, fg_color="transparent")
        bar_inner.pack(fill="both", expand=True, padx=22)

        self.status_lbl = ctk.CTkLabel(bar_inner, text="● 보호 중인 폴더 없음",
                                        font=ctk.CTkFont(size=13), text_color=TEXT_MID)
        self.status_lbl.pack(side="left", pady=10)

        ctk.CTkLabel(bar_inner, text="v1.0", font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED).pack(side="right", pady=10)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh()
        self.root.mainloop()

    def _opt_card(self, parent, title, desc, var, col):
        frame = ctk.CTkFrame(parent, fg_color=PURPLE_BG, corner_radius=12,
                             border_width=2, border_color=PURPLE_BORDER)
        frame.grid(row=0, column=col, padx=4, sticky="nsew")
        ctk.CTkCheckBox(frame, text="", variable=var, width=20,
                         fg_color=PURPLE_LIGHT, hover_color=PURPLE,
                         checkmark_color=WHITE, border_color=PURPLE_BORDER).pack(pady=(12, 4))
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=13, weight="bold"),
                     text_color="#4a3d8a", justify="center").pack()
        ctk.CTkLabel(frame, text=desc, font=ctk.CTkFont(size=11),
                     text_color=TEXT_MUTED, justify="center").pack(pady=(2, 12))

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
            text=f"● {count}개 폴더 보호 중입니다" if count else "● 보호 중인 폴더 없음"
        )

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
        right.pack(side="right", padx=(8, 0))
        if folder.get("protected"):
            ctk.CTkLabel(right, text="보호중",
                         font=ctk.CTkFont(size=11, weight="bold"),
                         text_color=GREEN).pack(pady=(0, 4))
        ctk.CTkButton(right, text="X", width=32, height=32,
                       fg_color=WHITE, text_color="#c4b8e8",
                       hover_color="#ffe4e4", border_width=1, border_color=PURPLE_BORDER,
                       corner_radius=8, font=ctk.CTkFont(size=12, weight="bold"),
                       command=lambda i=idx: self._remove(i)).pack()

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
                new = self._pin(path)
                if new != path:
                    folder["path"] = new
                    folder["pinned"] = True
            done += 1
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
                folder["path"] = self._unpin(folder["path"])
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

    def _protect(self, path):
        try:
            user = os.environ.get("USERNAME", "")
            r = subprocess.run(["icacls", path, "/deny", f"{user}:(D,DC)"],
                               capture_output=True, text=True)
            return r.returncode == 0
        except Exception as e:
            messagebox.showerror("오류", f"보호 적용 실패:\n{e}")
            return False

    def _unprotect(self, path):
        try:
            user = os.environ.get("USERNAME", "")
            subprocess.run(["icacls", path, "/remove:d", user], capture_output=True, text=True)
        except Exception:
            pass

    def _pin(self, path):
        parent, name = os.path.dirname(path), os.path.basename(path)
        if not name.startswith(PIN_PREFIX):
            new_path = os.path.join(parent, PIN_PREFIX + name)
            try:
                os.rename(path, new_path)
                return new_path
            except Exception:
                pass
        return path

    def _unpin(self, path):
        parent, name = os.path.dirname(path), os.path.basename(path)
        if name.startswith(PIN_PREFIX):
            new_path = os.path.join(parent, name[len(PIN_PREFIX):])
            try:
                os.rename(path, new_path)
                return new_path
            except Exception:
                pass
        return path

    def _start_tray(self):
        if self.tray_icon or not TRAY_AVAILABLE:
            return
        img = Image.new("RGBA", (64, 64), (90, 70, 180, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(124, 110, 230, 255))
        menu = pystray.Menu(
            pystray.MenuItem("FolderGuard 열기", self._show_window, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self._quit),
        )
        self.tray_icon = pystray.Icon("FolderGuard", img, "FolderGuard 실행 중", menu)
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
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()


if __name__ == "__main__":
    FolderGuardApp()
