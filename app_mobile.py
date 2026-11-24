"""
MedRemind Mobile - Pengingat Minum Obat
Versi Android (Kivy + KivyMD)

Install dependensi:
  pip install kivy kivymd plyer

Build APK (di Linux/WSL/Google Colab):
  pip install buildozer
  buildozer android debug
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.properties import StringProperty, ListProperty, BooleanProperty, NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.switch import Switch
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, RoundedRectangle, Rectangle

try:
    from plyer import notification
    PLYER_OK = True
except Exception:
    PLYER_OK = False

# ─── Konstanta ───────────────────────────────────────────────
DAFTAR_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
HARI_MAP = {0: "Senin", 1: "Selasa", 2: "Rabu", 3: "Kamis",
            4: "Jumat", 5: "Sabtu", 6: "Minggu"}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_JADWAL  = os.path.join(BASE_DIR, "jadwal_obat.json")
FILE_RIWAYAT = os.path.join(BASE_DIR, "riwayat_minum.json")

# Warna tema
C_BG      = (0.055, 0.090, 0.165, 1)   # navy gelap
C_CARD    = (1, 1, 1, 1)
C_GREEN   = (0.063, 0.725, 0.506, 1)
C_BLUE    = (0.012, 0.518, 0.780, 1)
C_RED     = (0.863, 0.149, 0.149, 1)
C_AMBER   = (0.961, 0.620, 0.043, 1)
C_GRAY    = (0.396, 0.467, 0.541, 1)
C_TEXT    = (0.059, 0.090, 0.161, 1)
C_LIGHT   = (0.973, 0.980, 0.988, 1)


def get_hari_ini():
    return HARI_MAP[datetime.now().weekday()]


def hex_color(r, g, b, a=1):
    return (r, g, b, a)


# ─── Fungsi Data ─────────────────────────────────────────────
def muat_data():
    obat = []
    riwayat = []
    if os.path.exists(FILE_JADWAL):
        try:
            with open(FILE_JADWAL, encoding="utf-8") as f:
                obat = json.load(f)
        except Exception:
            obat = []
    # Normalisasi field lama
    for item in obat:
        item.setdefault("sesi_pagi_aktif", True)
        item.setdefault("jam_pagi", item.get("jam", "08:00"))
        item.setdefault("sesi_siang_aktif", False)
        item.setdefault("jam_siang", "13:00")
        item.setdefault("sesi_sore_aktif", False)
        item.setdefault("jam_sore", "19:00")
        item.setdefault("hari_tipe", "Setiap Hari")
        item.setdefault("hari_aktif", list(DAFTAR_HARI))
        item.setdefault("terakhir_minum_sesi", {})
        item.setdefault("stok", 30)
        item.setdefault("satuan", "Tablet")
        item.setdefault("kurangi_per_minum", 1)
        item.setdefault("aturan", "Sesudah Makan")
        item.setdefault("catatan", "-")
        item.setdefault("dosis", "1 Tablet")

    if os.path.exists(FILE_RIWAYAT):
        try:
            with open(FILE_RIWAYAT, encoding="utf-8") as f:
                riwayat = json.load(f)
        except Exception:
            riwayat = []
    return obat, riwayat


def simpan_jadwal(obat):
    with open(FILE_JADWAL, "w", encoding="utf-8") as f:
        json.dump(obat, f, ensure_ascii=False, indent=4)


def simpan_riwayat(riwayat):
    with open(FILE_RIWAYAT, "w", encoding="utf-8") as f:
        json.dump(riwayat, f, ensure_ascii=False, indent=4)


# ─── Widget Pembantu ─────────────────────────────────────────
class RoundedButton(Button):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ""
        self._btn_color = kw.get("btn_color", C_BLUE)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self._btn_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])


class CardBox(BoxLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.bind(pos=self._draw, size=self._draw)

    def _draw(self, *a):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])


class SectionLabel(Label):
    def __init__(self, **kw):
        kw.setdefault("bold", True)
        kw.setdefault("color", C_TEXT)
        kw.setdefault("halign", "left")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("height", dp(30))
        super().__init__(**kw)
        self.bind(size=lambda *a: setattr(self, "text_size", (self.width, None)))


# ─── Popup Alarm ─────────────────────────────────────────────
class AlarmPopup(Popup):
    def __init__(self, app_ref, item, sesi_key, sesi_nama, jam_target, **kw):
        super().__init__(**kw)
        self.app_ref  = app_ref
        self.item     = item
        self.sesi_key = sesi_key
        self.sesi_nama = sesi_nama
        self.jam_target = jam_target

        self.title = f"⏰ ALARM MINUM OBAT"
        self.size_hint = (0.9, 0.75)
        self.auto_dismiss = False

        stok = item.get("stok", 0)
        satuan = item.get("satuan", "Tablet")
        kurangi = item.get("kurangi_per_minum", 1)
        sisa_est = max(0, stok - kurangi)

        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        # Header merah
        hdr = BoxLayout(size_hint_y=None, height=dp(55))
        with hdr.canvas.before:
            Color(*C_RED)
            Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: hdr.canvas.before.clear() or
                 (hdr.canvas.before.__enter__() or True) and
                 setattr(hdr, "_redraw", True))
        hdr_lbl = Label(text=f"⏰  {sesi_nama}  •  {jam_target}",
                        bold=True, font_size=dp(16), color=(1, 1, 1, 1))
        hdr.add_widget(hdr_lbl)
        root.add_widget(hdr)

        # Info obat
        info = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_y=None, height=dp(180))
        def row(label, value, vc=(0.1, 0.1, 0.1, 1)):
            r = BoxLayout(size_hint_y=None, height=dp(30))
            r.add_widget(Label(text=label, bold=True, color=C_GRAY,
                               size_hint_x=0.42, halign="right",
                               text_size=(dp(130), None), valign="middle"))
            r.add_widget(Label(text=value, color=vc,
                               halign="left", text_size=(dp(200), None),
                               valign="middle"))
            return r

        info.add_widget(row("Nama Obat:", item["nama"], C_BLUE))
        info.add_widget(row("Dosis:", item.get("dosis", "-")))
        info.add_widget(row("Aturan:", item.get("aturan", "-"), C_GREEN))
        stok_txt = f"⚠ {stok} {satuan} → {sisa_est} sesudah minum" if stok <= 5 else f"{stok} {satuan} → {sisa_est} sesudah"
        stok_clr = C_RED if stok <= 0 else (C_AMBER if stok <= 5 else C_GREEN)
        info.add_widget(row("Sisa Stok:", stok_txt, stok_clr))
        root.add_widget(info)

        # Tombol
        btn_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(50))

        btn_minum = RoundedButton(text="✔ SUDAH DIMINUM", btn_color=C_GREEN,
                                  color=(1, 1, 1, 1), bold=True, font_size=dp(14))
        btn_minum.bind(on_release=self.on_minum)

        btn_tunda = RoundedButton(text=f"⏰ Tunda {app_ref.snooze_menit}m", btn_color=C_AMBER,
                                  color=(1, 1, 1, 1), font_size=dp(13))
        btn_tunda.bind(on_release=self.on_snooze)

        btn_lewat = RoundedButton(text="✖ Lewati", btn_color=C_GRAY,
                                  color=(1, 1, 1, 1), font_size=dp(13))
        btn_lewat.bind(on_release=self.on_lewat)

        btn_row.add_widget(btn_minum)
        btn_row.add_widget(btn_tunda)
        btn_row.add_widget(btn_lewat)
        root.add_widget(btn_row)

        self.content = root
        self._play_sound()

    def _play_sound(self):
        def _beep():
            try:
                import winsound
                for _ in range(3):
                    winsound.Beep(1200, 300)
                    time.sleep(0.2)
                    winsound.Beep(1500, 300)
                    time.sleep(0.4)
            except Exception:
                pass
        threading.Thread(target=_beep, daemon=True).start()

    def on_minum(self, *a):
        self.dismiss()
        self.app_ref.catat_minum(self.item["id"], self.sesi_key, self.sesi_nama)

    def on_snooze(self, *a):
        self.dismiss()
        key = (self.item["id"], self.sesi_key)
        target = datetime.now() + timedelta(minutes=self.app_ref.snooze_menit)
        self.app_ref.snooze_list[key] = (target, self.sesi_nama, self.jam_target)
        self.app_ref.show_snack(f"Ditunda {self.app_ref.snooze_menit} menit: {self.item['nama']} ({self.sesi_nama})")

    def on_lewat(self, *a):
        self.dismiss()


# ─── Popup Tambah/Edit Obat ───────────────────────────────────
class FormObatPopup(Popup):
    def __init__(self, app_ref, item=None, **kw):
        super().__init__(**kw)
        self.app_ref = app_ref
        self.item = item   # None = tambah baru
        self.title = "✏ Edit Obat" if item else "➕ Tambah Obat Baru"
        self.size_hint = (0.95, 0.92)
        self.auto_dismiss = False

        scroll = ScrollView()
        root = BoxLayout(orientation="vertical", padding=dp(14),
                         spacing=dp(10), size_hint_y=None)
        root.bind(minimum_height=root.setter("height"))

        def field(label, hint="", text=""):
            root.add_widget(SectionLabel(text=label))
            tf = TextInput(hint_text=hint, text=text, multiline=False,
                           size_hint_y=None, height=dp(44),
                           padding=[dp(10), dp(10)])
            root.add_widget(tf)
            return tf

        self.ent_nama   = field("Nama Obat *", "cth: Paracetamol",
                                item["nama"] if item else "")
        self.ent_dosis  = field("Dosis", "cth: 1 Tablet",
                                item.get("dosis", "1 Tablet") if item else "1 Tablet")
        self.ent_stok   = field("Stok Saat Ini", "cth: 30",
                                str(item.get("stok", 30)) if item else "30")
        self.ent_kurang = field("Kurang Tiap Minum", "cth: 1",
                                str(item.get("kurangi_per_minum", 1)) if item else "1")

        # Satuan
        root.add_widget(SectionLabel(text="Satuan"))
        self.sp_satuan = Spinner(values=["Tablet", "Kapsul", "Sendok", "Bungkus", "ml", "Sachet"],
                                 text=item.get("satuan", "Tablet") if item else "Tablet",
                                 size_hint_y=None, height=dp(44))
        root.add_widget(self.sp_satuan)

        # Aturan
        root.add_widget(SectionLabel(text="Aturan Minum"))
        self.sp_aturan = Spinner(
            values=["Sesudah Makan", "Sebelum Makan", "Bersama Makan",
                    "Saat Makan Malam", "Kapan Saja"],
            text=item.get("aturan", "Sesudah Makan") if item else "Sesudah Makan",
            size_hint_y=None, height=dp(44))
        root.add_widget(self.sp_aturan)

        # ── Sesi Waktu ──
        root.add_widget(SectionLabel(text="─── Waktu Minum (Sesi) ───"))

        def sesi_row(label, aktif_key, jam_key, default_aktif, default_jam):
            aktif_val = item.get(aktif_key, default_aktif) if item else default_aktif
            jam_val   = item.get(jam_key,   default_jam)   if item else default_jam
            row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
            sw = Switch(active=aktif_val, size_hint_x=None, width=dp(60))
            lbl = Label(text=label, color=C_TEXT, size_hint_x=0.4, halign="left")
            lbl.bind(size=lambda *a: setattr(lbl, "text_size", (lbl.width, None)))
            tf = TextInput(text=jam_val, hint_text="JJ:MM", multiline=False,
                           size_hint_x=0.3, height=dp(44), padding=[dp(8), dp(8)])
            row.add_widget(sw)
            row.add_widget(lbl)
            row.add_widget(tf)
            root.add_widget(row)
            return sw, tf

        self.sw_pagi,  self.tf_jam_pagi  = sesi_row("🌅 Pagi",      "sesi_pagi_aktif",  "jam_pagi",  True,  "07:00")
        self.sw_siang, self.tf_jam_siang = sesi_row("☀ Siang",      "sesi_siang_aktif", "jam_siang", False, "13:00")
        self.sw_sore,  self.tf_jam_sore  = sesi_row("🌙 Sore/Malam", "sesi_sore_aktif",  "jam_sore",  False, "19:00")

        # ── Pilih Hari ──
        root.add_widget(SectionLabel(text="─── Jadwal Hari ───"))
        self.sp_hari_tipe = Spinner(values=["Setiap Hari", "Pilih Hari Tertentu"],
                                    text=item.get("hari_tipe", "Setiap Hari") if item else "Setiap Hari",
                                    size_hint_y=None, height=dp(44))
        root.add_widget(self.sp_hari_tipe)

        # Checkbox hari
        hari_aktif_saved = item.get("hari_aktif", list(DAFTAR_HARI)) if item else list(DAFTAR_HARI)
        self.hari_grid = GridLayout(cols=4, size_hint_y=None, height=dp(90), spacing=dp(4))
        self.hari_checks = {}
        for h in DAFTAR_HARI:
            tb = ToggleButton(text=h[:3], state="down" if h in hari_aktif_saved else "normal",
                              size_hint_y=None, height=dp(38), font_size=dp(12))
            self.hari_checks[h] = tb
            self.hari_grid.add_widget(tb)
        root.add_widget(self.hari_grid)

        # Catatan
        self.ent_catatan = field("Catatan (opsional)", "cth: Minum dengan air hangat",
                                 item.get("catatan", "") if item else "")

        # Tombol Simpan / Batal
        btn_row = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        btn_simpan = RoundedButton(text="💾 SIMPAN", btn_color=C_GREEN,
                                   color=(1, 1, 1, 1), bold=True)
        btn_batal  = RoundedButton(text="✖ Batal", btn_color=C_GRAY,
                                   color=(1, 1, 1, 1))
        btn_simpan.bind(on_release=self.on_simpan)
        btn_batal.bind(on_release=lambda *a: self.dismiss())
        btn_row.add_widget(btn_simpan)
        btn_row.add_widget(btn_batal)
        root.add_widget(btn_row)

        scroll.add_widget(root)
        self.content = scroll

    def on_simpan(self, *a):
        nama = self.ent_nama.text.strip()
        if not nama:
            self.app_ref.show_snack("❌ Nama obat tidak boleh kosong!")
            return

        pagi_aktif  = self.sw_pagi.active
        siang_aktif = self.sw_siang.active
        sore_aktif  = self.sw_sore.active

        if not (pagi_aktif or siang_aktif or sore_aktif):
            self.app_ref.show_snack("❌ Aktifkan minimal 1 sesi waktu minum!")
            return

        def valid_jam(s):
            try:
                datetime.strptime(s.strip(), "%H:%M"); return True
            except ValueError:
                return False

        for aktif, jam, label in [
            (pagi_aktif, self.tf_jam_pagi.text, "Pagi"),
            (siang_aktif, self.tf_jam_siang.text, "Siang"),
            (sore_aktif, self.tf_jam_sore.text, "Sore/Malam")
        ]:
            if aktif and not valid_jam(jam):
                self.app_ref.show_snack(f"❌ Format jam {label} harus JJ:MM (cth: 07:30)")
                return

        hari_tipe = self.sp_hari_tipe.text
        hari_aktif = [h for h in DAFTAR_HARI if self.hari_checks[h].state == "down"]
        if hari_tipe == "Pilih Hari Tertentu" and not hari_aktif:
            self.app_ref.show_snack("❌ Pilih minimal 1 hari!")
            return
        if hari_tipe == "Setiap Hari":
            hari_aktif = list(DAFTAR_HARI)

        try:    stok = max(0, int(self.ent_stok.text.strip()))
        except: stok = 30
        try:    kurangi = max(1, int(self.ent_kurang.text.strip()))
        except: kurangi = 1

        jam_utama = (self.tf_jam_pagi.text if pagi_aktif
                     else self.tf_jam_siang.text if siang_aktif
                     else self.tf_jam_sore.text)

        data = {
            "nama": nama,
            "jam": jam_utama.strip(),
            "dosis": self.ent_dosis.text.strip() or "1 Tablet",
            "stok": stok,
            "satuan": self.sp_satuan.text,
            "kurangi_per_minum": kurangi,
            "aturan": self.sp_aturan.text,
            "catatan": self.ent_catatan.text.strip() or "-",
            "sesi_pagi_aktif": pagi_aktif,
            "jam_pagi": self.tf_jam_pagi.text.strip(),
            "sesi_siang_aktif": siang_aktif,
            "jam_siang": self.tf_jam_siang.text.strip(),
            "sesi_sore_aktif": sore_aktif,
            "jam_sore": self.tf_jam_sore.text.strip(),
            "hari_tipe": hari_tipe,
            "hari_aktif": hari_aktif,
            "terakhir_minum": "",
            "terakhir_minum_sesi": self.item.get("terakhir_minum_sesi", {}) if self.item else {},
        }

        if self.item:
            data["id"] = self.item["id"]
            idx = next((i for i, o in enumerate(self.app_ref.daftar_obat)
                        if o["id"] == self.item["id"]), None)
            if idx is not None:
                self.app_ref.daftar_obat[idx] = data
        else:
            data["id"] = (max(o["id"] for o in self.app_ref.daftar_obat) + 1
                          if self.app_ref.daftar_obat else 1)
            self.app_ref.daftar_obat.append(data)

        simpan_jadwal(self.app_ref.daftar_obat)
        self.app_ref.refresh_all()
        self.dismiss()
        self.app_ref.show_snack(f"✅ Obat '{nama}' berhasil disimpan!")


# ─── Screen Dashboard ─────────────────────────────────────────
class DashboardScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(name="dashboard", **kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        with self.canvas.before:
            Color(*C_LIGHT)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self.bg_rect, "pos", self.pos),
                  size=lambda *a: setattr(self.bg_rect, "size", self.size))

        root = BoxLayout(orientation="vertical")

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(70), padding=[dp(16), dp(10)])
        with hdr.canvas.before:
            Color(*C_BG)
            self._hdr_rect = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: setattr(self._hdr_rect, "pos", hdr.pos),
                 size=lambda *a: setattr(self._hdr_rect, "size", hdr.size))

        self.lbl_salam   = Label(text="Selamat Pagi 🌅", font_size=dp(18), bold=True,
                                 color=(1, 1, 1, 1), size_hint_x=0.6, halign="left")
        self.lbl_salam.bind(size=lambda *a: setattr(self.lbl_salam, "text_size",
                                                    (self.lbl_salam.width, None)))
        self.lbl_jam     = Label(text="--:--", font_size=dp(22), bold=True,
                                 color=(1, 1, 1, 1), size_hint_x=0.4, halign="right")
        hdr.add_widget(self.lbl_salam)
        hdr.add_widget(self.lbl_jam)
        root.add_widget(hdr)

        # Kartu Statistik
        stat_row = BoxLayout(size_hint_y=None, height=dp(80),
                             padding=[dp(10), dp(8)], spacing=dp(8))
        self.card_total = self._stat_card("Total\nObat", "0", C_BLUE)
        self.card_sudah = self._stat_card("Sesi\nSelesai", "0", C_GREEN)
        self.card_belum = self._stat_card("Sesi\nTersisa", "0", C_AMBER)
        self.card_stok  = self._stat_card("Stok\nMenipis", "0", C_RED)
        for c in [self.card_total, self.card_sudah, self.card_belum, self.card_stok]:
            stat_row.add_widget(c)
        root.add_widget(stat_row)

        # Label jadwal berikut
        self.lbl_next = Label(text="⏰ Memuat...", size_hint_y=None, height=dp(30),
                              color=C_BLUE, font_size=dp(13), halign="center")
        root.add_widget(self.lbl_next)

        # List sesi hari ini
        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                  padding=[dp(10), dp(4)], size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)

        self.add_widget(root)

    def _stat_card(self, label, nilai, warna):
        card = BoxLayout(orientation="vertical", padding=dp(6))
        with card.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda *a: card.canvas.before.clear() or
                  setattr(card, "_redraw", True))

        lbl_v = Label(text=nilai, font_size=dp(20), bold=True,
                      color=warna, halign="center")
        lbl_l = Label(text=label, font_size=dp(10), color=C_GRAY,
                      halign="center")
        card.add_widget(lbl_v)
        card.add_widget(lbl_l)
        card._val_lbl = lbl_v
        return card

    def refresh(self):
        now = datetime.now()
        h = now.hour
        self.lbl_jam.text = now.strftime("%H:%M")
        if 4 <= h < 11:   self.lbl_salam.text = "Selamat Pagi 🌅"
        elif 11 <= h < 15: self.lbl_salam.text = "Selamat Siang ☀"
        elif 15 <= h < 18: self.lbl_salam.text = "Selamat Sore 🌤"
        else:              self.lbl_salam.text = "Selamat Malam 🌙"

        hari_tgl  = now.strftime("%Y-%m-%d")
        hari_nama = get_hari_ini()
        daftar_obat = self.app_ref.daftar_obat

        total = len(daftar_obat)
        stok_menipis = sum(1 for o in daftar_obat if o.get("stok", 0) <= 5)

        jadwal = []
        sesi_selesai = 0
        jadwal_berikut = "--:--"

        for item in daftar_obat:
            hari_tipe  = item.get("hari_tipe", "Setiap Hari")
            hari_aktif = item.get("hari_aktif", list(DAFTAR_HARI))
            if hari_tipe == "Pilih Hari Tertentu" and hari_nama not in hari_aktif:
                continue

            terakhir = item.get("terakhir_minum_sesi", {}).get(hari_tgl, [])
            for sesi_key, sesi_nama, aktif_key, jam_key in [
                ("pagi",  "🌅 Pagi",       "sesi_pagi_aktif",  "jam_pagi"),
                ("siang", "☀ Siang",       "sesi_siang_aktif", "jam_siang"),
                ("sore",  "🌙 Sore/Malam", "sesi_sore_aktif",  "jam_sore"),
            ]:
                if not item.get(aktif_key, False):
                    continue
                jam = item.get(jam_key, "08:00")
                done = sesi_key in terakhir
                if done:
                    sesi_selesai += 1
                else:
                    if jam > now.strftime("%H:%M") and (jadwal_berikut == "--:--" or jam < jadwal_berikut):
                        jadwal_berikut = f"{jam} — {item['nama']} ({sesi_nama})"
                jadwal.append({
                    "id": item["id"],
                    "sesi_key": sesi_key,
                    "sesi_nama": sesi_nama,
                    "jam": jam,
                    "nama": item["nama"],
                    "dosis": item.get("dosis", "-"),
                    "stok": item.get("stok", 0),
                    "satuan": item.get("satuan", "Tablet"),
                    "done": done,
                })

        jadwal.sort(key=lambda x: x["jam"])
        total_sesi = len(jadwal)
        sisa = total_sesi - sesi_selesai

        self.card_total._val_lbl.text = str(total)
        self.card_sudah._val_lbl.text = str(sesi_selesai)
        self.card_belum._val_lbl.text = str(sisa)
        self.card_stok._val_lbl.text  = str(stok_menipis)

        if jadwal_berikut == "--:--" and total_sesi > 0:
            jadwal_berikut = "🎉 Semua sesi hari ini selesai!"
        self.lbl_next.text = f"⏰ Jadwal Berikut: {jadwal_berikut}"

        # Rebuild list
        self.list_box.clear_widgets()
        for row in jadwal:
            self._add_jadwal_item(row)

    def _add_jadwal_item(self, row):
        done = row["done"]
        stok = row["stok"]
        satuan = row["satuan"]

        card = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=dp(90), padding=dp(8), spacing=dp(4))
        with card.canvas.before:
            Color(0.95, 1.0, 0.95, 1) if done else Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
        card.bind(pos=lambda *a, c=card, d=done: self._redraw_card(c, d),
                  size=lambda *a, c=card, d=done: self._redraw_card(c, d))

        top = BoxLayout()
        status = "✅ Selesai" if done else "⏳ Belum"
        clr_s  = C_GREEN if done else C_AMBER

        nama_lbl = Label(text=f"[b]{row['nama']}[/b]  {row['sesi_nama']}",
                         markup=True, color=C_TEXT, halign="left", size_hint_x=0.65)
        nama_lbl.bind(size=lambda *a: setattr(nama_lbl, "text_size", (nama_lbl.width, None)))
        jam_lbl  = Label(text=f"🕐 {row['jam']}", color=C_BLUE, halign="right",
                         size_hint_x=0.35)
        top.add_widget(nama_lbl)
        top.add_widget(jam_lbl)

        bot = BoxLayout(spacing=dp(6))
        stok_txt = f"❌ Habis" if stok <= 0 else (f"⚠ {stok} {satuan}" if stok <= 5 else f"📦 {stok} {satuan}")
        stok_clr = C_RED if stok <= 0 else (C_AMBER if stok <= 5 else C_GRAY)
        stok_lbl = Label(text=stok_txt, color=stok_clr, font_size=dp(12), halign="left")
        stat_lbl = Label(text=status, color=clr_s, font_size=dp(12), bold=True, halign="right")

        if not done:
            btn = RoundedButton(text="✔ Minum", btn_color=C_GREEN,
                                color=(1, 1, 1, 1), font_size=dp(12),
                                size_hint_x=None, width=dp(90))
            obat_id  = row["id"]
            sesi_key = row["sesi_key"]
            sesi_nama = row["sesi_nama"]
            btn.bind(on_release=lambda *a, oid=obat_id, sk=sesi_key, sn=sesi_nama:
                     self.app_ref.catat_minum(oid, sk, sn))
            bot.add_widget(btn)

        bot.add_widget(stok_lbl)
        bot.add_widget(stat_lbl)

        card.add_widget(top)
        card.add_widget(bot)
        self.list_box.add_widget(card)

    def _redraw_card(self, card, done):
        card.canvas.before.clear()
        with card.canvas.before:
            Color(0.93, 1.0, 0.95, 1) if done else Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])


# ─── Screen Kelola ────────────────────────────────────────────
class KelolaScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(name="kelola", **kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(16), dp(10)])
        with hdr.canvas.before:
            Color(*C_BG)
            r = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: setattr(r, "pos", hdr.pos),
                 size=lambda *a: setattr(r, "size", hdr.size))
        hdr.add_widget(Label(text="💊 Kelola Obat", font_size=dp(18), bold=True,
                             color=(1, 1, 1, 1), halign="left"))
        btn_tambah = RoundedButton(text="➕ Tambah", btn_color=C_GREEN,
                                   color=(1, 1, 1, 1), size_hint_x=None, width=dp(100))
        btn_tambah.bind(on_release=lambda *a: self._open_form(None))
        hdr.add_widget(btn_tambah)
        root.add_widget(hdr)

        # List obat
        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(6),
                                  padding=[dp(10), dp(8)], size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def _open_form(self, item):
        FormObatPopup(self.app_ref, item=item).open()

    def refresh(self):
        self.list_box.clear_widgets()
        for item in self.app_ref.daftar_obat:
            self._add_item_card(item)

        if not self.app_ref.daftar_obat:
            self.list_box.add_widget(Label(
                text="Belum ada obat.\nTekan ➕ Tambah untuk menambahkan.",
                color=C_GRAY, halign="center", size_hint_y=None, height=dp(80)))

    def _add_item_card(self, item):
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                         height=dp(110), padding=dp(10), spacing=dp(4))
        with card.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])
        card.bind(pos=lambda *a, c=card: self._redraw_card(c),
                  size=lambda *a, c=card: self._redraw_card(c))

        # Baris nama & stok
        r1 = BoxLayout(size_hint_y=None, height=dp(30))
        nama_lbl = Label(text=f"[b]{item['nama']}[/b]", markup=True,
                         color=C_TEXT, halign="left", size_hint_x=0.65)
        nama_lbl.bind(size=lambda *a: setattr(nama_lbl, "text_size", (nama_lbl.width, None)))
        stok = item.get("stok", 0)
        sat  = item.get("satuan", "Tablet")
        stok_clr = C_RED if stok <= 0 else (C_AMBER if stok <= 5 else C_GREEN)
        stok_lbl = Label(text=f"📦 {stok} {sat}", color=stok_clr,
                         halign="right", size_hint_x=0.35)
        r1.add_widget(nama_lbl)
        r1.add_widget(stok_lbl)

        # Baris jadwal sesi
        sesi_parts = []
        if item.get("sesi_pagi_aktif"):  sesi_parts.append(f"🌅{item.get('jam_pagi','07:00')}")
        if item.get("sesi_siang_aktif"): sesi_parts.append(f"☀{item.get('jam_siang','13:00')}")
        if item.get("sesi_sore_aktif"):  sesi_parts.append(f"🌙{item.get('jam_sore','19:00')}")
        sesi_str = "  |  ".join(sesi_parts) or "-"

        hari = item.get("hari_tipe", "Setiap Hari")
        if hari == "Pilih Hari Tertentu":
            ha = item.get("hari_aktif", [])
            hari = ", ".join(h[:3] for h in DAFTAR_HARI if h in ha)

        r2 = Label(text=f"⏰ {sesi_str}  •  📅 {hari}",
                   color=C_GRAY, font_size=dp(12), halign="left",
                   size_hint_y=None, height=dp(24))
        r2.bind(size=lambda *a: setattr(r2, "text_size", (r2.width, None)))

        # Baris tombol
        r3 = BoxLayout(spacing=dp(6), size_hint_y=None, height=dp(36))
        btn_edit = RoundedButton(text="✏ Edit", btn_color=C_AMBER,
                                 color=(1, 1, 1, 1), font_size=dp(12))
        btn_hapus = RoundedButton(text="🗑 Hapus", btn_color=C_RED,
                                  color=(1, 1, 1, 1), font_size=dp(12))
        btn_edit.bind(on_release=lambda *a, it=item: self._open_form(it))
        btn_hapus.bind(on_release=lambda *a, it=item: self._konfirm_hapus(it))
        r3.add_widget(btn_edit)
        r3.add_widget(btn_hapus)

        card.add_widget(r1)
        card.add_widget(r2)
        card.add_widget(r3)
        self.list_box.add_widget(card)

    def _redraw_card(self, card):
        card.canvas.before.clear()
        with card.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(10)])

    def _konfirm_hapus(self, item):
        popup = Popup(title="Konfirmasi Hapus", size_hint=(0.8, 0.3))
        box = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        box.add_widget(Label(text=f"Hapus '{item['nama']}'?", color=C_TEXT))
        btn_row = BoxLayout(spacing=dp(8), size_hint_y=None, height=dp(44))
        btn_ya = RoundedButton(text="✔ Hapus", btn_color=C_RED, color=(1, 1, 1, 1))
        btn_tdk = RoundedButton(text="✖ Batal", btn_color=C_GRAY, color=(1, 1, 1, 1))
        btn_ya.bind(on_release=lambda *a: (
            self.app_ref.daftar_obat.remove(item),
            simpan_jadwal(self.app_ref.daftar_obat),
            self.app_ref.refresh_all(),
            popup.dismiss(),
            self.app_ref.show_snack(f"🗑 '{item['nama']}' dihapus.")
        ))
        btn_tdk.bind(on_release=lambda *a: popup.dismiss())
        btn_row.add_widget(btn_ya)
        btn_row.add_widget(btn_tdk)
        box.add_widget(btn_row)
        popup.content = box
        popup.open()


# ─── Screen Riwayat ──────────────────────────────────────────
class RiwayatScreen(Screen):
    def __init__(self, app_ref, **kw):
        super().__init__(name="riwayat", **kw)
        self.app_ref = app_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical")

        hdr = BoxLayout(size_hint_y=None, height=dp(60), padding=[dp(16), dp(10)])
        with hdr.canvas.before:
            Color(*C_BG)
            r = Rectangle(pos=hdr.pos, size=hdr.size)
        hdr.bind(pos=lambda *a: setattr(r, "pos", hdr.pos),
                 size=lambda *a: setattr(r, "size", hdr.size))
        hdr.add_widget(Label(text="📋 Riwayat Minum Obat", font_size=dp(18),
                             bold=True, color=(1, 1, 1, 1)))
        btn_bersih = RoundedButton(text="🗑 Hapus", btn_color=C_RED,
                                   color=(1, 1, 1, 1), size_hint_x=None, width=dp(80))
        btn_bersih.bind(on_release=self._bersihkan)
        hdr.add_widget(btn_bersih)
        root.add_widget(hdr)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", spacing=dp(5),
                                  padding=[dp(10), dp(8)], size_hint_y=None)
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        root.add_widget(self.scroll)
        self.add_widget(root)

    def refresh(self):
        self.list_box.clear_widgets()
        riwayat = list(reversed(self.app_ref.riwayat_minum))
        if not riwayat:
            self.list_box.add_widget(Label(text="Belum ada riwayat.", color=C_GRAY,
                                           size_hint_y=None, height=dp(60), halign="center"))
            return
        for log in riwayat:
            card = BoxLayout(orientation="vertical", size_hint_y=None,
                             height=dp(80), padding=dp(8), spacing=dp(2))
            with card.canvas.before:
                Color(1, 1, 1, 1)
                RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            card.bind(pos=lambda *a, c=card: self._redraw(c),
                      size=lambda *a, c=card: self._redraw(c))

            r1 = BoxLayout()
            r1.add_widget(Label(text=f"[b]{log.get('nama','-')}[/b]  {log.get('sesi','')}",
                                markup=True, color=C_TEXT, halign="left"))
            r1.add_widget(Label(text=log.get("waktu", "-")[:16],
                                color=C_GRAY, font_size=dp(11), halign="right"))
            r2 = BoxLayout()
            r2.add_widget(Label(text=f"💊 {log.get('dosis','-')}  •  📦 Sisa: {log.get('sisa_stok','-')}",
                                color=C_BLUE, font_size=dp(12), halign="left"))
            r2.add_widget(Label(text=f"✅ Tepat Waktu", color=C_GREEN,
                                font_size=dp(11), halign="right"))
            card.add_widget(r1)
            card.add_widget(r2)
            self.list_box.add_widget(card)

    def _redraw(self, card):
        card.canvas.before.clear()
        with card.canvas.before:
            Color(1, 1, 1, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])

    def _bersihkan(self, *a):
        self.app_ref.riwayat_minum = []
        simpan_riwayat([])
        self.refresh()
        self.app_ref.show_snack("🗑 Riwayat telah dihapus.")


# ─── Navigasi Bawah ──────────────────────────────────────────
class NavBar(BoxLayout):
    def __init__(self, app_ref, **kw):
        super().__init__(size_hint_y=None, height=dp(58),
                         spacing=dp(2), **kw)
        self.app_ref = app_ref
        with self.canvas.before:
            Color(*C_BG)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *a: setattr(self._rect, "pos", self.pos),
                  size=lambda *a: setattr(self._rect, "size", self.size))

        tabs = [
            ("🏠 Beranda", "dashboard"),
            ("💊 Kelola",  "kelola"),
            ("📋 Riwayat", "riwayat"),
        ]
        self.btns = {}
        for label, name in tabs:
            btn = Button(text=label, background_color=(0, 0, 0, 0),
                         background_normal="", color=(0.6, 0.7, 0.9, 1),
                         font_size=dp(13), bold=False)
            btn.bind(on_release=lambda *a, n=name: app_ref.go_screen(n))
            self.add_widget(btn)
            self.btns[name] = btn

    def set_active(self, name):
        for n, b in self.btns.items():
            b.color = (1, 1, 1, 1) if n == name else (0.6, 0.7, 0.9, 1)
            b.bold = (n == name)


# ─── Aplikasi Utama ───────────────────────────────────────────
class MedRemindApp(App):
    title = "MedRemind - Pengingat Obat"

    def build(self):
        Window.clearcolor = C_LIGHT

        self.daftar_obat, self.riwayat_minum = muat_data()
        self.snooze_list = {}       # {(obat_id, sesi_key): (target_dt, sesi_nama, jam)}
        self.notif_set   = set()    # {(obat_id, sesi_key, tgl, jam)}
        self.snooze_menit = 5

        root = BoxLayout(orientation="vertical")

        # Screen manager
        self.sm = ScreenManager(transition=SlideTransition())
        self.scr_dash    = DashboardScreen(app_ref=self)
        self.scr_kelola  = KelolaScreen(app_ref=self)
        self.scr_riwayat = RiwayatScreen(app_ref=self)
        self.sm.add_widget(self.scr_dash)
        self.sm.add_widget(self.scr_kelola)
        self.sm.add_widget(self.scr_riwayat)

        # Navbar
        self.navbar = NavBar(app_ref=self)

        root.add_widget(self.sm)
        root.add_widget(self.navbar)

        # Jadwalkan refresh & alarm
        Clock.schedule_interval(self._tick, 1)       # update jam setiap detik
        Clock.schedule_interval(self._check_alarm, 4) # cek alarm setiap 4 detik

        self.go_screen("dashboard")
        return root

    def go_screen(self, name):
        self.sm.current = name
        self.navbar.set_active(name)
        self.refresh_all()

    def refresh_all(self):
        self.scr_dash.refresh()
        self.scr_kelola.refresh()
        self.scr_riwayat.refresh()

    def catat_minum(self, obat_id, sesi_key, sesi_nama):
        item = next((o for o in self.daftar_obat if o["id"] == obat_id), None)
        if not item:
            return

        hari_ini = datetime.now().strftime("%Y-%m-%d")
        waktu_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        stok_lama = item.get("stok", 0)
        kurangi   = item.get("kurangi_per_minum", 1)
        stok_baru = max(0, stok_lama - kurangi)
        satuan    = item.get("satuan", "Tablet")

        item["stok"] = stok_baru
        item["terakhir_minum"] = hari_ini
        sesi_dict = item.setdefault("terakhir_minum_sesi", {})
        if hari_ini not in sesi_dict:
            sesi_dict[hari_ini] = []
        if sesi_key not in sesi_dict[hari_ini]:
            sesi_dict[hari_ini].append(sesi_key)

        # Hapus dari snooze jika ada
        self.snooze_list.pop((obat_id, sesi_key), None)

        simpan_jadwal(self.daftar_obat)

        self.riwayat_minum.append({
            "obat_id": obat_id,
            "nama": item["nama"],
            "sesi": sesi_nama,
            "dosis": item.get("dosis", "-"),
            "sisa_stok": f"{stok_baru} {satuan}",
            "aturan": item.get("aturan", "-"),
            "waktu": waktu_str,
        })
        simpan_riwayat(self.riwayat_minum)
        self.refresh_all()

        if stok_baru == 0:
            self.show_snack(f"❌ Stok '{item['nama']}' HABIS! Segera beli lagi.")
        elif stok_baru <= 5:
            self.show_snack(f"⚠ Sisa stok '{item['nama']}' tinggal {stok_baru} {satuan}!")
        else:
            self.show_snack(f"✅ {item['nama']} ({sesi_nama}) dicatat diminum. Sisa: {stok_baru} {satuan}")

    def _tick(self, dt):
        """Update jam di dashboard setiap detik"""
        if self.sm.current == "dashboard":
            now = datetime.now()
            self.scr_dash.lbl_jam.text = now.strftime("%H:%M")

    def _check_alarm(self, dt):
        now        = datetime.now()
        jam_skrg   = now.strftime("%H:%M")
        hari_tgl   = now.strftime("%Y-%m-%d")
        hari_nama  = get_hari_ini()

        # Cek jadwal reguler
        for item in self.daftar_obat:
            hari_tipe  = item.get("hari_tipe", "Setiap Hari")
            hari_aktif = item.get("hari_aktif", list(DAFTAR_HARI))
            if hari_tipe == "Pilih Hari Tertentu" and hari_nama not in hari_aktif:
                continue

            terakhir = item.get("terakhir_minum_sesi", {}).get(hari_tgl, [])

            for sesi_key, sesi_nama, aktif_key, jam_key in [
                ("pagi",  "🌅 Pagi",       "sesi_pagi_aktif",  "jam_pagi"),
                ("siang", "☀ Siang",       "sesi_siang_aktif", "jam_siang"),
                ("sore",  "🌙 Sore/Malam", "sesi_sore_aktif",  "jam_sore"),
            ]:
                if not item.get(aktif_key, False):
                    continue
                jam_sesi = item.get(jam_key, "08:00")
                if jam_skrg == jam_sesi and sesi_key not in terakhir:
                    kunci = (item["id"], sesi_key, hari_tgl, jam_skrg)
                    if kunci not in self.notif_set:
                        self.notif_set.add(kunci)
                        self._tampilkan_alarm(item, sesi_key, sesi_nama, jam_sesi)

        # Cek snooze
        done_keys = []
        for key, val in list(self.snooze_list.items()):
            target_dt, sesi_nama, jam_target = val
            if now >= target_dt:
                done_keys.append(key)
                obat_id, sesi_key = key
                item = next((o for o in self.daftar_obat if o["id"] == obat_id), None)
                if item:
                    terakhir = item.get("terakhir_minum_sesi", {}).get(hari_tgl, [])
                    if sesi_key not in terakhir:
                        self._tampilkan_alarm(item, sesi_key, sesi_nama, jam_target)
        for k in done_keys:
            self.snooze_list.pop(k, None)

    def _tampilkan_alarm(self, item, sesi_key, sesi_nama, jam_target):
        # Notifikasi sistem (Android)
        if PLYER_OK:
            try:
                notification.notify(
                    title=f"⏰ Minum Obat: {item['nama']}",
                    message=f"{sesi_nama} • {jam_target} — {item.get('dosis','')}",
                    app_name="MedRemind",
                    timeout=10,
                )
            except Exception:
                pass
        # Pop-up di dalam app
        AlarmPopup(app_ref=self, item=item, sesi_key=sesi_key,
                   sesi_nama=sesi_nama, jam_target=jam_target).open()

    def show_snack(self, msg):
        """Tampilkan pesan singkat di bawah layar (seperti Snackbar)"""
        popup = Popup(title="", separator_height=0,
                      size_hint=(0.9, None), height=dp(60),
                      background="", background_color=(0, 0, 0, 0),
                      pos_hint={"center_x": 0.5, "y": 0.04})
        lbl = Label(text=msg, color=(1, 1, 1, 1), halign="center", bold=True,
                    font_size=dp(13))
        with lbl.canvas.before:
            Color(0.1, 0.1, 0.15, 0.95)
            RoundedRectangle(pos=lbl.pos, size=lbl.size, radius=[dp(10)])
        lbl.bind(pos=lambda *a: lbl.canvas.before.clear() or
                 setattr(lbl, "_rd", True))
        popup.content = lbl
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2.5)


if __name__ == "__main__":
    MedRemindApp().run()
