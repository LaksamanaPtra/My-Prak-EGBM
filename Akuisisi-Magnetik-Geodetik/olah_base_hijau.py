"""Olah 'Datasheet Pengukuran Lapangan Base Hijau.xlsx' -> format '..._Koreksi Rover-Rover.xlsx' (sheet Koreksi + TMI).
usage: python olah_base_hijau.py SRC.xlsx OUT.xlsx
BASE1 di bawah: isi bacaan base awal (jam, menit, detik, signal, PPM). Kosong = baris disiapkan untuk diisi manual.
"""
import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

SRC, OUT = sys.argv[1], sys.argv[2]
# base awal (dari screenshot user, 18-Okt-2026): (signal, jam, menit, detik, ppm)
BASE1 = [(9, 15, 27, 50, 44935.9), (6, 15, 28, 45, 44935.0), (9, 15, 29, 21, 44935.1)]
BASE1_IGRF = 44443.8   # nilai IGRF yg tertulis di screenshot base awal (tidak dipakai di rumus)
BASE1_COORD = (697948.02, 9194462.94, 4.49)   # UTM X, UTM Y, Elevasi (m) dari screenshot base awal
BASE1_GPS = "GPS: 7.284 S, 112.793 E"
BASE1_ROWS = len(BASE1) if BASE1 else 5
DATE = "18-Okt-2026"

# ---------------- baca datasheet lapangan
src = openpyxl.load_workbook(SRC).active
blocks, cur = [], None
for r in range(8, src.max_row + 1):
    v = [src.cell(r, c).value for c in range(1, 13)]
    if all(x is None for x in v):
        continue
    if v[0] is not None and (cur is None or str(v[0]) != cur["name"]):
        cur = {"name": str(v[0]), "x": v[6], "y": v[7], "z": v[8], "igrf": v[10], "rows": [], "note": []}
        blocks.append(cur)
    jam = v[3]
    if cur["name"] == "37" and jam == 3:          # ditulis format 12 jam -> 15 (jam 3 sore)
        jam = 15
        if "jam 3 -> 15 (sore)" not in cur["note"]:
            cur["note"].append("jam 3 -> 15 (sore)")
    cur["rows"].append({"sig": v[2], "h": jam, "m": v[4], "s": v[5], "ppm": v[9]})
base2 = [b for b in blocks if b["name"].lower().startswith("base")][0]
stations = [b for b in blocks if b is not base2]

# ---------------- koreksi transkripsi sesuai foto kertas lapangan: (stasiun, iterasi ke-) -> nilai di kertas
PAPER_FIX = {
    ("37", 7): {"ppm": 45144.2},   # xlsx 45140.2 (digit ke-5 di kertas = 4, bukan 0)
    ("35", 4): {"s": 13},          # xlsx 16:19:23
    ("35", 11): {"s": 56},         # xlsx 16:24:26 (hanya 1 detik setelah iterasi 10)
    ("34", 1): {"m": 26},          # xlsx 16:28:16
    ("34", 2): {"ppm": 46410.3},   # xlsx 46410.9
}
for b in blocks:
    for i, d in enumerate(b["rows"], 1):
        for k, v in PAPER_FIX.get((b["name"], i), {}).items():
            b["note"].append(f"it{i} {k}: {d[k]} -> {v}")
            d[k] = v

# ---------------- koordinat: di kertas kolom UTM X/Y berisi lintang (S) / bujur (E) derajat, elevasi dalam km
from pyproj import Transformer
COORD_FIX = {"36": (7.283, 112.794)}      # kertas: 7,283 / 112,794 (xlsx salah ketik 7.253 / 112.754)
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32749", always_xy=True)   # WGS84 -> UTM 49S
for b in blocks:
    if b["name"] in COORD_FIX:
        b["x"], b["y"] = COORD_FIX[b["name"]]
        b["note"].append("koord. dikoreksi sesuai kertas")
    lat, lon = -abs(b["x"]), b["y"]
    b["note"].append(f"GPS: {abs(lat):.3f} S, {lon:.3f} E")
    e, n = to_utm.transform(lon, lat)
    b["x"], b["y"], b["z"] = round(e, 1), round(n, 1), round(b["z"] * 1000, 1)   # elevasi km -> m

# ---------------- gaya (sama dgn file referensi)
F = "Aptos Narrow"
thin = Side(style="thin")
BD = Border(left=thin, right=thin, top=thin, bottom=thin)
HDR = PatternFill("solid", fgColor="FFD966")
BLUE = PatternFill("solid", fgColor="DBE9F7")
YEL = PatternFill("solid", fgColor="FFF2CC")
CEN = Alignment(horizontal="center", vertical="center", wrap_text=True)
WIDTH = dict(A=11.43, B=7.29, C=6.57, D=4.57, E=6.29, F=5.86, G=17.71, H=22.71, I=12.5, J=13.5, K=8.5,
             L=16.57, M=30.86, N=10.5, O=14.57, P=15.0, Q=16.0, R=24)

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Koreksi Base Hijau"
for k, w in WIDTH.items():
    ws.column_dimensions[k].width = w


def put(r, c, v, bold=False, fill=None):
    x = ws.cell(r, c, v)
    x.font = Font(name=F, size=12, bold=bold)
    x.alignment = CEN
    x.border = BD
    if fill:
        x.fill = fill
    return x


def box(r1, r2, c1, c2, fill=None):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            x = ws.cell(r, c)
            x.border = BD
            x.alignment = CEN
            x.font = Font(name=F, size=12, bold=x.font.b)
            if fill:
                x.fill = fill


ws.merge_cells("A1:R3")
put(1, 1, "DATA PENGUKURAN METODE MAGNETIK - ROVER ROVER", bold=True)
box(1, 3, 1, 18)
for r, (a, b) in zip((4, 5, 6), (("KELOMPOK", "DEKLINASI"), ("OPERATOR", "INKLINASI"), ("CUACA", "DATE"))):
    put(r, 1, a, bold=True); ws.merge_cells(f"B{r}:F{r}"); put(r, 2, None)
    put(r, 9, b, bold=True); ws.merge_cells(f"J{r}:R{r}"); put(r, 10, DATE if b == "DATE" else None)
    box(r, r, 1, 18)
heads = ["Stasiun", "Datum", "Signal", "Waktu", None, None, "Detik Pengukuran", "Detik Pengukuran Base", "UTM X", "UTM Y",
         "Elevasi", "Pembacaan PPM", "Rata-rata Pembacaan PPM Base", "IGRF", "Koreksi Harian", "Anomali Bersih", "TMI", "Keterangan"]
for c, h in enumerate(heads, 1):
    put(7, c, h, bold=True, fill=HDR)
    if c not in (4, 5, 6):
        ws.merge_cells(start_row=7, start_column=c, end_row=8, end_column=c)
for c, h in zip((4, 5, 6), ("Jam", "Menit", "Detik")):
    put(8, c, h, bold=True, fill=HDR)
ws.merge_cells("D7:F7")
box(7, 8, 1, 18, HDR)

MERGE_ST = "ABIJKNQ"          # kolom yg di-merge per blok stasiun (seperti referensi)
MERGE_BASE = "ABHIJKMNOPQ"    # kolom yg di-merge per blok base


def merge_cols(r1, r2, cols):
    if r2 > r1:
        for col in cols:
            ws.merge_cells(f"{col}{r1}:{col}{r2}")


row = 9
# ---------------- Base 1 (awal)
B1r1, B1r2 = row, row + BASE1_ROWS - 1
for i in range(BASE1_ROWS):
    r = row + i
    vals = BASE1[i] if i < len(BASE1) else (None, None, None, None, None)
    for c, v in zip((3, 4, 5, 6, 12), vals):
        put(r, c, v, fill=BLUE if BASE1 else YEL)
    put(r, 7, f'=IF(D{r}="","",(D{r}*3600)+(E{r}*60)+F{r})', fill=BLUE)
put(B1r1, 1, "Base 1", fill=BLUE)
put(B1r1, 8, f'=IFERROR(AVERAGE(G{B1r1}:G{B1r2}),"")', fill=BLUE)
b1x, b1y, b1z = BASE1_COORD if BASE1 else (base2["x"], base2["y"], base2["z"])
for c, v in ((9, b1x), (10, b1y), (11, b1z), (14, BASE1_IGRF if BASE1 else base2["igrf"])):
    put(B1r1, c, v, fill=BLUE)
put(B1r1, 13, f'=IFERROR(AVERAGE(L{B1r1}:L{B1r2}),"")', fill=BLUE)
put(B1r1, 18, BASE1_GPS if BASE1 else "ISI DATA BASE AWAL (kuning)", fill=BLUE)
box(B1r1, B1r2, 1, 18, BLUE)
for r in range(B1r1, B1r2 + 1):
    for c in (3, 4, 5, 6, 12):
        if not BASE1:
            ws.cell(r, c).fill = YEL
merge_cols(B1r1, B1r2, "ABHIJKMNOPQ")
row = B1r2 + 1

# ---------------- stasiun (posisi Base 2 dihitung dulu untuk rumus koreksi harian)
B2r1 = row + sum(len(s["rows"]) for s in stations)
B2r2 = B2r1 + len(base2["rows"]) - 1
sec = lambda h, m, x: h * 3600 + m * 60 + x
if BASE1:
    t1 = sum(sec(*b[1:4]) for b in BASE1) / len(BASE1); b1 = sum(b[4] for b in BASE1) / len(BASE1)
    t2 = sum(sec(d["h"], d["m"], d["s"]) for d in base2["rows"]) / len(base2["rows"])
    b2 = sum(d["ppm"] for d in base2["rows"]) / len(base2["rows"])
anom = lambda d, s: (d["ppm"] - s["igrf"] - (sec(d["h"], d["m"], d["s"]) - t1) / (t2 - t1) * (b2 - b1)) if BASE1 else d["ppm"]
H1, H2, M1, M2 = f"$H${B1r1}", f"$H${B2r1}", f"$M${B1r1}", f"$M${B2r1}"
tmi_cells = []
for s in stations:
    r1 = row
    rr = list(range(r1, r1 + len(s["rows"])))
    for r, d in zip(rr, s["rows"]):
        for c, v in zip((3, 4, 5, 6, 12), (d["sig"], d["h"], d["m"], d["s"], d["ppm"])):
            put(r, c, v)
        put(r, 7, f"=(D{r}*3600)+(E{r}*60)+F{r}")
        put(r, 15, f'=IFERROR((G{r}-{H1})/({H2}-{H1})*({M2}-{M1}),"")')
        put(r, 16, f'=IF(O{r}="","",L{r}-$N${r1}-O{r})')
    put(r1, 1, s["name"])
    for c, v in ((9, s["x"]), (10, s["y"]), (11, s["z"]), (14, s["igrf"])):
        put(r1, c, v)
    # 3 anomali paling berdekatan (pakai nilai anomali sebenarnya bila base awal ada)
    ppm = [(anom(d, s), r) for d, r in zip(s["rows"], rr)]
    if len(ppm) <= 3:
        pick = [r for _, r in ppm]
    else:
        srt = sorted(ppm)
        best = min(range(len(srt) - 2), key=lambda i: srt[i + 2][0] - srt[i][0])
        pick = sorted(r for _, r in srt[best:best + 3])
    put(r1, 17, '=IFERROR(AVERAGE(' + ",".join(f"P{r}" for r in pick) + '),"")')
    put(r1, 18, "; ".join(s["note"]) or None)
    box(r1, rr[-1], 1, 18)
    merge_cols(r1, rr[-1], MERGE_ST + "R")
    tmi_cells.append((s, r1))
    row = rr[-1] + 1

# ---------------- Base 2 (akhir)
assert row == B2r1
for i, d in enumerate(base2["rows"]):
    r = B2r1 + i
    for c, v in zip((3, 4, 5, 6, 12), (d["sig"], d["h"], d["m"], d["s"], d["ppm"])):
        put(r, c, v, fill=BLUE)
    put(r, 7, f"=(D{r}*3600)+(E{r}*60)+F{r}", fill=BLUE)
put(B2r1, 1, "Base 2", fill=BLUE)
put(B2r1, 8, f"=AVERAGE(G{B2r1}:G{B2r2})", fill=BLUE)
for c, v in ((9, base2["x"]), (10, base2["y"]), (11, base2["z"]), (14, base2["igrf"])):
    put(B2r1, c, v, fill=BLUE)
put(B2r1, 13, f"=AVERAGE(L{B2r1}:L{B2r2})", fill=BLUE)
put(B2r1, 18, "; ".join(base2["note"]), fill=BLUE)
box(B2r1, B2r2, 1, 18, BLUE)
merge_cols(B2r1, B2r2, MERGE_BASE + "R")
for r in range(B1r1, B2r2 + 1):
    ws.row_dimensions[r].height = 14.25
    for c in (9, 10, 11):
        ws.cell(r, c).number_format = "0.00"
    for c in (8, 13, 14, 15, 16, 17):
        ws.cell(r, c).number_format = "0.0" if c in (8, 14) else "0.000"
ws.sheet_view.zoomScale = 70

# ---------------- sheet TMI
t = wb.create_sheet("TMI")
for c, (h, w) in enumerate((("HARI", 13), ("NAMA_TITIK", 13), ("UTM_X", 13), ("UTM_Y", 13), ("Z", 13), ("TMI", 13)), 1):
    t.cell(1, c, h).font = Font(name=F, bold=True)
    t.column_dimensions[chr(64 + c)].width = w
sh = f"'{ws.title}'"
for i, (s, r1) in enumerate(tmi_cells, 2):
    t.cell(i, 1, DATE); t.cell(i, 2, s["name"])
    for c, col in ((3, "I"), (4, "J"), (5, "K"), (6, "Q")):
        t.cell(i, c, f"={sh}!{col}{r1}")
    for c in range(1, 7):
        t.cell(i, c).font = Font(name=F)
wb.save(OUT)
print("saved", OUT, "| Base1 rows", B1r1, B1r2, "| Base2 rows", B2r1, B2r2,
      "| stations", [(s["name"], r) for s, r in tmi_cells])
