"""Sports Equipment Locker - touchscreen kiosk (Tkinter).
Run:  python kiosk.py        Exit:  Ctrl+Q
"""
import os
import sys
import time
import tkinter as tk
from datetime import datetime

import cv2
from PIL import Image, ImageTk

import camera
import config
import database as db
import hardware

BG, CARD, BTN = "#0f172a", "#1e293b", "#334155"
ACCENT, GREEN, RED = "#38bdf8", "#22c55e", "#ef4444"
TEXT, MUTED, DARK = "#f8fafc", "#94a3b8", "#0f172a"

SCALE = 1.0


def S(n):
    return max(1, int(n * SCALE))


def F(size, weight="normal"):
    return ("Segoe UI", S(size), weight)


def make_button(parent, text, command, bg=BTN, fg=TEXT, size=20, padx=18, pady=10, state="normal"):
    return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                     activebackground=ACCENT, activeforeground=DARK, disabledforeground=MUTED,
                     font=F(size, "bold"), relief="flat", bd=0, cursor="hand2",
                     padx=S(padx), pady=S(pady), state=state)


# ======================================================================
# Reusable widgets
# ======================================================================
class Screen(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        self._jobs = []

    def later(self, ms, fn):
        jid = self.after(ms, fn)
        self._jobs.append(jid)
        return jid

    def on_leave(self):
        for j in self._jobs:
            try:
                self.after_cancel(j)
            except Exception:
                pass
        self._jobs = []

    def header(self, title, sub=None):
        tk.Label(self, text=title, font=F(32, "bold"), bg=BG, fg=TEXT).pack(pady=(S(24), 0))
        if sub:
            tk.Label(self, text=sub, font=F(16), bg=BG, fg=MUTED, wraplength=S(1000)).pack(pady=(S(4), S(10)))


class NumPad(tk.Frame):
    def __init__(self, parent, max_len):
        super().__init__(parent, bg=BG)
        self.max_len = max_len
        self.value = ""
        self.display = tk.Label(self, font=("Consolas", S(34), "bold"), bg=CARD, fg=ACCENT,
                                padx=S(20), pady=S(8))
        self.display.pack(pady=(0, S(12)))
        grid = tk.Frame(self, bg=BG)
        grid.pack()
        keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "CLR", "0", "⌫"]
        for i, k in enumerate(keys):
            r, c = divmod(i, 3)
            b = make_button(grid, k, lambda key=k: self.press(key), size=24, padx=26, pady=10,
                            bg=BTN if k.isdigit() else "#475569")
            b.grid(row=r, column=c, padx=S(5), pady=S(5), sticky="nsew")
            grid.columnconfigure(c, weight=1, uniform="np")
        self.refresh()

    def press(self, key):
        if key == "CLR":
            self.value = ""
        elif key == "⌫":
            self.value = self.value[:-1]
        elif len(self.value) < self.max_len:
            self.value += key
        self.refresh()

    def refresh(self):
        slots = list(self.value) + ["_"] * (self.max_len - len(self.value))
        self.display.config(text=" ".join(slots))


class OnScreenKeyboard(tk.Frame):
    ROWS = ["QWERTYUIOP", "ASDFGHJKLÑ", "ZXCVBNM.,-'"]

    def __init__(self, parent, var, max_len=60):
        super().__init__(parent, bg=BG)
        self.var, self.max_len = var, max_len
        for r, row in enumerate(self.ROWS):
            for c, ch in enumerate(row):
                make_button(self, ch, lambda k=ch: self.press(k), size=16, padx=4, pady=5
                            ).grid(row=r, column=c, sticky="nsew", padx=S(3), pady=S(3))
        for c in range(10):
            self.columnconfigure(c, weight=1, uniform="k")
        make_button(self, "SPACE", lambda: self.press(" "), size=14, padx=4, pady=5
                    ).grid(row=3, column=0, columnspan=6, sticky="nsew", padx=S(3), pady=S(3))
        make_button(self, "⌫", self.back, size=14, padx=4, pady=5, bg="#475569"
                    ).grid(row=3, column=6, columnspan=2, sticky="nsew", padx=S(3), pady=S(3))
        make_button(self, "CLEAR", lambda: self.var.set(""), size=14, padx=4, pady=5, bg="#475569"
                    ).grid(row=3, column=8, columnspan=2, sticky="nsew", padx=S(3), pady=S(3))

    def press(self, ch):
        if len(self.var.get()) < self.max_len:
            self.var.set(self.var.get() + ch)

    def back(self):
        self.var.set(self.var.get()[:-1])


class ChoiceGroup(tk.Frame):
    def __init__(self, parent, options, columns=3, initial=""):
        super().__init__(parent, bg=BG)
        self.value = ""
        self.buttons = {}
        for i, opt in enumerate(options):
            b = make_button(self, opt, lambda o=opt: self.select(o), size=13, padx=6, pady=6)
            b.grid(row=i // columns, column=i % columns, sticky="nsew", padx=S(3), pady=S(3))
            self.buttons[opt] = b
        for c in range(columns):
            self.columnconfigure(c, weight=1, uniform="c")
        if initial in options:
            self.select(initial)

    def select(self, opt):
        self.value = opt
        for o, b in self.buttons.items():
            b.config(bg=ACCENT if o == opt else BTN, fg=DARK if o == opt else TEXT)


# ======================================================================
# Screens
# ======================================================================
class HomeScreen(Screen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        tk.Label(self, text="SPORTS EQUIPMENT LOCKER", font=F(40, "bold"), bg=BG, fg=TEXT).pack(pady=(S(60), S(6)))
        tk.Label(self, text="Touch an option to begin", font=F(20), bg=BG, fg=MUTED).pack()
        row = tk.Frame(self, bg=BG)
        row.pack(expand=True, fill="both", padx=S(60), pady=S(40))
        row.columnconfigure((0, 1), weight=1, uniform="h")
        row.rowconfigure(0, weight=1)
        make_button(row, "BORROW", app.start_borrow, bg=GREEN, fg="#052e16", size=44
                    ).grid(row=0, column=0, sticky="nsew", padx=S(20))
        make_button(row, "RETURN", app.start_return, bg=ACCENT, fg=DARK, size=44
                    ).grid(row=0, column=1, sticky="nsew", padx=S(20))


class StudentNumberScreen(Screen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Borrow", "Enter your student number")
        self.pad = NumPad(self, config.STUDENT_NUMBER_LENGTH)
        self.pad.pack(pady=S(6))
        self.msg = tk.Label(self, text="", font=F(16, "bold"), bg=BG, fg=RED)
        self.msg.pack(pady=S(6))
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(8))
        make_button(row, "BACK", app.go_home, size=20, padx=40).pack(side="left", padx=S(10))
        make_button(row, "ENTER", self.submit, bg=GREEN, fg="#052e16", size=20, padx=60).pack(side="left", padx=S(10))

    def submit(self):
        sn = self.pad.value
        if len(sn) != config.STUDENT_NUMBER_LENGTH:
            self.msg.config(text=f"Please enter all {config.STUDENT_NUMBER_LENGTH} digits.")
            return
        student = db.get_student(sn)
        self.app.session["student_number"] = sn
        if db.student_is_complete(student):
            self.app.session["student"] = student
            self.app.show(SelectItemsScreen)
        else:
            self.app.show(RegisterScreen, student_number=sn, existing=student)


class RegisterScreen(Screen):
    def __init__(self, parent, app, student_number, existing=None):
        super().__init__(parent, app)
        existing = existing or {}
        self.sn = student_number
        self.header("Quick Registration", f"Student number: {student_number}  -  fill in your details, then continue")

        self.name_var = tk.StringVar(value=(existing.get("name") or "").upper())
        tk.Label(self, text="Full name", font=F(14), bg=BG, fg=MUTED).pack(anchor="w", padx=S(60))
        tk.Label(self, textvariable=self.name_var, font=F(22, "bold"), bg=CARD, fg=ACCENT, anchor="w",
                 padx=S(14), pady=S(6)).pack(fill="x", padx=S(60), pady=(0, S(6)))

        mid = tk.Frame(self, bg=BG)
        mid.pack(fill="x", padx=S(60))
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)
        left = tk.Frame(mid, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, S(10)))
        tk.Label(left, text="Department", font=F(14), bg=BG, fg=MUTED).pack(anchor="w")
        self.dept = ChoiceGroup(left, config.DEPARTMENTS, columns=3, initial=existing.get("department", ""))
        self.dept.pack(fill="x")
        right = tk.Frame(mid, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        tk.Label(right, text="Year level", font=F(14), bg=BG, fg=MUTED).pack(anchor="w")
        self.year = ChoiceGroup(right, config.YEAR_LEVELS, columns=2, initial=existing.get("year_level", ""))
        self.year.pack(fill="x")

        OnScreenKeyboard(self, self.name_var).pack(fill="x", padx=S(60), pady=S(8))
        self.msg = tk.Label(self, text="", font=F(14, "bold"), bg=BG, fg=RED)
        self.msg.pack()
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(4))
        make_button(row, "CANCEL", app.go_home, size=18, padx=40).pack(side="left", padx=S(10))
        make_button(row, "SAVE & CONTINUE", self.save, bg=GREEN, fg="#052e16", size=18, padx=40
                    ).pack(side="left", padx=S(10))

    def save(self):
        name = " ".join(self.name_var.get().split()).title()
        if len(name) < 3:
            self.msg.config(text="Please enter your full name.")
        elif not self.dept.value:
            self.msg.config(text="Please choose your department.")
        elif not self.year.value:
            self.msg.config(text="Please choose your year level.")
        else:
            db.save_student(self.sn, name, self.dept.value, self.year.value)
            self.app.session["student"] = db.get_student(self.sn)
            self.app.show(SelectItemsScreen)


class SelectItemsScreen(Screen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        student = app.session["student"]
        first = (student["name"].split() or [""])[0].title()
        self.header(f"Hi, {first}!", "Choose the item(s) you want to borrow. You can borrow more than one.")
        self.avail = {a["item_name"]: a for a in db.availability()}
        old = app.session.get("cart", {})
        self.cart = {k: min(v, self.avail[k]["available"]) for k, v in old.items() if k in self.avail}
        self.cart = {k: v for k, v in self.cart.items() if v > 0}

        grid = tk.Frame(self, bg=BG)
        grid.pack(expand=True, fill="both", padx=S(40), pady=S(6))
        cols = 3
        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="t")
        self.qty_labels = {}
        for i, (name, a) in enumerate(self.avail.items()):
            r, c = divmod(i, cols)
            grid.rowconfigure(r, weight=1)
            tile = tk.Frame(grid, bg=CARD)
            tile.grid(row=r, column=c, sticky="nsew", padx=S(8), pady=S(8))
            tk.Label(tile, text=name, font=F(24, "bold"), bg=CARD, fg=TEXT).pack(pady=(S(14), 0))
            tk.Label(tile, text=f"Available: {a['available']} of {a['total']}", font=F(14), bg=CARD,
                     fg=GREEN if a["available"] else RED).pack()
            ctl = tk.Frame(tile, bg=CARD)
            ctl.pack(pady=S(10))
            enabled = "normal" if a["available"] else "disabled"
            make_button(ctl, "−", lambda n=name: self.change(n, -1), size=22, padx=22, pady=4, state=enabled
                        ).pack(side="left", padx=S(8))
            lbl = tk.Label(ctl, text="0", font=F(28, "bold"), bg=CARD, fg=ACCENT, width=2)
            lbl.pack(side="left")
            self.qty_labels[name] = lbl
            make_button(ctl, "+", lambda n=name: self.change(n, +1), size=22, padx=22, pady=4, state=enabled
                        ).pack(side="left", padx=S(8))

        self.summary = tk.Label(self, text="", font=F(16, "bold"), bg=BG, fg=TEXT, wraplength=S(1000))
        self.summary.pack(pady=S(4))
        self.msg = tk.Label(self, text="", font=F(14, "bold"), bg=BG, fg=RED)
        self.msg.pack()
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(10))
        make_button(row, "BACK", app.go_home, size=20, padx=40).pack(side="left", padx=S(10))
        make_button(row, "CONTINUE", self.go_next, bg=GREEN, fg="#052e16", size=20, padx=60).pack(side="left", padx=S(10))
        self.refresh()

    def change(self, name, delta):
        cur = self.cart.get(name, 0)
        new = max(0, min(self.avail[name]["available"], cur + delta))
        if new:
            self.cart[name] = new
        else:
            self.cart.pop(name, None)
        self.refresh()

    def refresh(self):
        for n, lbl in self.qty_labels.items():
            lbl.config(text=str(self.cart.get(n, 0)))
        if self.cart:
            self.summary.config(text="Selected: " + ", ".join(f"{q} x {n}" for n, q in self.cart.items()))
        else:
            self.summary.config(text="No item selected yet")

    def go_next(self):
        if not self.cart:
            self.msg.config(text="Please select at least one item.")
            return
        self.app.session["cart"] = dict(self.cart)
        if config.SKIP_CAMERA_FOR_TESTING:
            self.app.finish_borrow("")
        else:
            self.app.show(CameraScreen)


def _make_cascade():
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


_cascade = None


def detect_faces(frame):
    global _cascade
    if _cascade is None:
        _cascade = _make_cascade()
    gray = cv2.equalizeHist(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    return list(_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)))


class CameraScreen(Screen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Face Capture",
                    f"Tap CAPTURE, then look at the camera. You get {config.CAPTURE_COUNTDOWN} seconds to pose.")
        self.preview = tk.Label(self, bg="black")
        self.preview.pack(pady=S(6))
        self.status = tk.Label(self, text="Starting camera...", font=F(18, "bold"), bg=BG, fg=MUTED)
        self.status.pack(pady=S(4))
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(8))
        self.back_btn = make_button(row, "BACK", self.go_back, size=20, padx=40)
        self.back_btn.pack(side="left", padx=S(10))
        self.cap_btn = make_button(row, "CAPTURE", self.start_countdown, bg=GREEN, fg="#052e16", size=20,
                                   padx=60, state="disabled")
        self.cap_btn.pack(side="left", padx=S(10))

        self.cap = None
        self.faces = []
        self.last_check = 0
        self.counting = False
        self.remaining = 0
        self.open_camera()

    def open_camera(self):
        self.status.config(text="Starting camera...", fg=MUTED)
        self.update_idletasks()
        cap, info = camera.find_camera()
        if cap is None:
            self.status.config(text=info, fg=RED)
            return
        self.cap = cap
        self.cam_info = info
        self.cap_btn.config(state="normal")
        self.loop()

    def loop(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if ok:
            display = cv2.flip(frame, 1)
            h, w = display.shape[:2]
            if time.time() - self.last_check > 0.4:
                self.last_check = time.time()
                self.faces = detect_faces(frame)
                if not self.counting:
                    if self.faces:
                        self.status.config(text="Person detected - ready", fg=GREEN)
                    else:
                        self.status.config(text="No person detected", fg=RED)
            for (x, y, fw, fh) in self.faces:
                x2 = w - x - fw      # mirror the box to match the flipped preview
                cv2.rectangle(display, (x2, y), (x2 + fw, y + fh), (0, 200, 0), 3)
            if self.counting:
                cv2.putText(display, str(self.remaining), (w // 2 - 40, h // 2 + 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10)
            pw = S(640)
            ph = int(pw * h / w)
            img = Image.fromarray(cv2.cvtColor(display, cv2.COLOR_BGR2RGB)).resize((pw, ph))
            photo = ImageTk.PhotoImage(img)
            self.preview.configure(image=photo)
            self.preview.image = photo
        self.later(30, self.loop)

    def start_countdown(self):
        if self.counting or self.cap is None:
            return
        self.counting = True
        self.remaining = config.CAPTURE_COUNTDOWN
        self.cap_btn.config(state="disabled")
        self.back_btn.config(state="disabled")
        self.status.config(text="Get ready...", fg=ACCENT)
        self.later(1000, self.tick)

    def tick(self):
        self.remaining -= 1
        if self.remaining > 0:
            self.later(1000, self.tick)
        else:
            self.take_photo()

    def take_photo(self):
        frame, faces = None, []
        for _ in range(5):
            ok, f = self.cap.read()
            if ok:
                frame = f
                faces = detect_faces(f)
                if faces:
                    break
            time.sleep(0.1)
        if frame is None or not faces:
            self.counting = False
            self.cap_btn.config(state="normal")
            self.back_btn.config(state="normal")
            self.status.config(text="No person detected - nothing was captured. Please try again.", fg=RED)
            return
        fname = f"{self.app.session['student_number']}_{datetime.now():%Y%m%d_%H%M%S}.jpg"
        cv2.imwrite(os.path.join(config.CAPTURE_DIR, fname), frame)
        self.release()
        self.app.finish_borrow(fname)

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def go_back(self):
        self.app.show(SelectItemsScreen)

    def on_leave(self):
        super().on_leave()
        self.release()


class OtpDisplayScreen(Screen):
    def __init__(self, parent, app, txns):
        super().__init__(parent, app)
        self.txns = txns
        self.header("Your OTP codes", "Record each code. You need the matching OTP to return that item.")
        grid = tk.Frame(self, bg=BG)
        grid.pack(expand=True, fill="both", padx=S(50), pady=S(6))
        cols = 1 if len(txns) <= 4 else 2
        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="o")
        for i, t in enumerate(txns):
            r, c = divmod(i, cols)
            grid.rowconfigure(r, weight=1)
            card = tk.Frame(grid, bg=CARD)
            card.grid(row=r, column=c, sticky="nsew", padx=S(8), pady=S(6))
            otp = t["otp"][:3] + " " + t["otp"][3:]
            tk.Label(card, text=otp, font=("Consolas", S(40), "bold"), bg=CARD, fg=ACCENT
                     ).pack(side="left", padx=S(24), pady=S(10))
            tk.Label(card, text=f"{t['item_name']}\nCompartment {t['compartment_no']}",
                     font=F(20, "bold"), bg=CARD, fg=TEXT, justify="left").pack(side="left", padx=S(10))
        make_button(self, "OK - I RECORDED MY OTP", self.confirm, bg=GREEN, fg="#052e16", size=22, padx=60, pady=14
                    ).pack(pady=S(16))

    def confirm(self):
        lines = []
        for t in self.txns:
            try:
                hardware.open_compartment(t["item_name"], t["compartment_no"])
                hardware.set_sim_present(t["item_name"], t["compartment_no"], False)
            except Exception as e:
                print("[HW] error:", e)
            lines.append(f"{t['item_name']} - Compartment {t['compartment_no']}")
        self.app.show(MessageScreen, title="Compartments opening",
                      body="Please take your item(s):\n\n" + "\n".join(lines) + "\n\nThank you!",
                      color=GREEN, seconds=8)


class MessageScreen(Screen):
    def __init__(self, parent, app, title, body, color=GREEN, seconds=6, next_cls=None):
        super().__init__(parent, app)
        self.next_cls = next_cls or HomeScreen
        tk.Label(self, text=title, font=F(36, "bold"), bg=BG, fg=color).pack(pady=(S(80), S(20)))
        tk.Label(self, text=body, font=F(22), bg=BG, fg=TEXT, justify="center", wraplength=S(1000)).pack()
        make_button(self, "DONE", self.finish, size=22, padx=60).pack(pady=S(40))
        self.later(seconds * 1000, self.finish)

    def finish(self):
        self.app.show(self.next_cls)


class ReturnOtpScreen(Screen):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self.header("Return an item", "Enter the 6-digit OTP you received when you borrowed")
        self.pad = NumPad(self, 6)
        self.pad.pack(pady=S(6))
        self.msg = tk.Label(self, text="", font=F(16, "bold"), bg=BG, fg=RED)
        self.msg.pack(pady=S(6))
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(8))
        make_button(row, "BACK", app.go_home, size=20, padx=40).pack(side="left", padx=S(10))
        make_button(row, "ENTER", self.submit, bg=GREEN, fg="#052e16", size=20, padx=60).pack(side="left", padx=S(10))

    def submit(self):
        if len(self.pad.value) != 6:
            self.msg.config(text="Please enter all 6 digits.")
            return
        txn = db.find_active_by_otp(self.pad.value)
        if not txn:
            self.msg.config(text="Invalid OTP, or it was already used.")
            self.pad.press("CLR")
            return
        self.app.show(ReturnProcessScreen, txn=txn)


class ReturnProcessScreen(Screen):
    def __init__(self, parent, app, txn):
        super().__init__(parent, app)
        self.txn = txn
        item, no = txn["item_name"], txn["compartment_no"]
        self.header(f"{item} - Compartment {no}", f"Borrowed by {txn.get('name') or txn['student_number']} "
                                                  f"on {txn['borrowed_at']}")
        self.status = tk.Label(self, text="", font=F(24, "bold"), bg=BG, fg=ACCENT, wraplength=S(1000))
        self.status.pack(pady=S(40))
        self.sim_btn = None
        if config.SIMULATE_HARDWARE:
            self.sim_btn = make_button(self, "[SIMULATION]  Item placed inside the compartment", self.sim_place,
                                       bg="#7c3aed", size=16, padx=30)
            self.sim_btn.pack(pady=S(10))
        row = tk.Frame(self, bg=BG)
        row.pack(pady=S(20))
        make_button(row, "CANCEL", app.go_home, size=18, padx=40).pack(side="left", padx=S(10))
        self.retry_btn = make_button(row, "TRY AGAIN", self.retry, bg=GREEN, fg="#052e16", size=18, padx=40)

        hardware.set_sim_present(item, no, False)   # item is currently out
        try:
            hardware.open_compartment(item, no)
        except Exception as e:
            print("[HW] error:", e)
        self.seen = 0
        self.start_wait()

    def start_wait(self):
        self.deadline = time.time() + config.RETURN_TIMEOUT_SECONDS
        self.seen = 0
        self.retry_btn.pack_forget()
        self.status.config(text="Compartment is open.\nPlace the item inside and close the door.", fg=ACCENT)
        self.later(400, self.poll)

    def sim_place(self):
        hardware.set_sim_present(self.txn["item_name"], self.txn["compartment_no"], True)

    def poll(self):
        t = self.txn
        try:
            present = hardware.item_present(t["item_name"], t["compartment_no"])
        except Exception as e:
            print("[HW] sensor error:", e)
            present = False
        self.seen = self.seen + 1 if present else 0
        if self.seen >= 2:   # present on 2 consecutive checks = stable
            returned_at = db.complete_return(t["id"])
            self.app.show(MessageScreen, title="Item returned!",
                          body=f"{t['item_name']} - Compartment {t['compartment_no']}\nReturned at {returned_at}\n\nThank you!",
                          color=GREEN, seconds=6)
        elif time.time() > self.deadline:
            self.status.config(text="Item not detected in the compartment.\nPlease place it inside, then try again.",
                               fg=RED)
            self.retry_btn.pack(side="left", padx=S(10))
        else:
            self.later(400, self.poll)

    def retry(self):
        self.start_wait()


# ======================================================================
# Application
# ======================================================================
class KioskApp(tk.Tk):
    def __init__(self):
        global SCALE
        super().__init__()
        self.title("Sports Equipment Locker")
        self.configure(bg=BG)
        SCALE = max(0.6, min(self.winfo_screenwidth() / 1280, self.winfo_screenheight() / 800))
        self.attributes("-fullscreen", True)
        self.bind_all("<Control-q>", self.quit_app)
        self.bind_all("<Control-Q>", self.quit_app)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.current = None
        self.session = {}
        self.show(HomeScreen)

    def show(self, screen_cls, **kwargs):
        if self.current is not None:
            self.current.on_leave()
            self.current.destroy()
        self.current = screen_cls(self.container, self, **kwargs)
        self.current.pack(fill="both", expand=True)

    def go_home(self):
        self.session = {}
        self.show(HomeScreen)

    def start_borrow(self):
        self.session = {"cart": {}}
        self.show(StudentNumberScreen)

    def start_return(self):
        self.session = {}
        self.show(ReturnOtpScreen)

    def finish_borrow(self, photo):
        try:
            txns = db.create_borrow(self.session["student_number"], self.session["cart"], photo)
        except ValueError as e:
            self.show(MessageScreen, title="Sorry", body=str(e) + "\nPlease choose again.",
                      color=RED, seconds=4, next_cls=SelectItemsScreen)
            return
        self.show(OtpDisplayScreen, txns=txns)

    def quit_app(self, event=None):
        if self.current is not None:
            self.current.on_leave()
        self.destroy()


if __name__ == "__main__":
    db.init_db()
    KioskApp().mainloop()