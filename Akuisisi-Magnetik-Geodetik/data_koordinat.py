"""Tugas Geodetik 3: Data Koordinat (Lon, Lat, UTM X, UTM Y, h, N, H) -> xlsx.
Sumber: lat/lon/h dari NRTK BIG (via Geoid_Decimal SRGI), N & H dari SRGI INAGEOID2020 v2, UTM 49S dihitung pyproj."""
import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pyproj import Transformer

SRC, OUT = sys.argv[1], sys.argv[2]
import win32com.client as w32  # baca .xls lewat Excel
xl = w32.Dispatch("Excel.Application"); xl.DisplayAlerts = False
wbx = xl.Workbooks.Open(SRC, 0, True); sh = wbx.Sheets("decimal")
pts = []
r = 2
while sh.Cells(r, 1).Value:
    pts.append([sh.Cells(r, c).Value for c in range(1, 8)])
    r += 1
wbx.Close(False); xl.Quit()

tf = Transformer.from_crs("EPSG:4326", "EPSG:32749", always_xy=True)   # WGS84 -> UTM 49S


def dms(v, pos, neg):
    a = abs(v); d = int(a); m = int((a - d) * 60); s = (a - d - m / 60) * 3600
    return f"{d}° {m}' {s:.4f}\" {pos if v >= 0 else neg}"


F = "Times New Roman"
thin = Side(style="thin")
BD = Border(left=thin, right=thin, top=thin, bottom=thin)
CEN = Alignment(horizontal="center", vertical="center", wrap_text=True)
HDR = PatternFill("solid", fgColor="1F4E78")

wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Data Koordinat"
ws.merge_cells("A1:J1"); ws["A1"] = "DATA KOORDINAT TITIK PENGUKURAN GEODETIK (GNSS ComNav T300) - 18 OKTOBER 2026"
ws["A1"].font = Font(name=F, bold=True, size=13); ws["A1"].alignment = CEN
ws.merge_cells("A2:J2")
ws["A2"] = "Datum WGS84 | Proyeksi UTM Zona 49S | Geoid INAGEOID2020 v2 | H = h - N"
ws["A2"].font = Font(name=F, italic=True); ws["A2"].alignment = CEN
heads = [("No", 5), ("Nama Titik", 11), ("Longitude (°)", 15), ("Latitude (°)", 15), ("UTM X / Easting (m)", 16),
         ("UTM Y / Northing (m)", 17), ("Ellipsoid Height / h (m)", 15), ("Geoid Undulation / N (m)", 15),
         ("Orthometric Height / H (m)", 16), ("Ketelitian Geoid (m)", 12)]
for c, (h, w) in enumerate(heads, 1):
    x = ws.cell(4, c, h); x.font = Font(name=F, bold=True, color="FFFFFF"); x.fill = HDR; x.alignment = CEN; x.border = BD
    ws.column_dimensions[chr(64 + c)].width = w
ws.row_dimensions[4].height = 45
fmts = [None, None, "0.000000000", "0.000000000", "0.000", "0.000", "0.0000", "0.000", "0.000", "0.000"]
for i, (name, lat, lon, h, N, H, acc) in enumerate(pts):
    e, n = tf.transform(lon, lat)
    row = [i + 1, name, lon, lat, round(e, 3), round(n, 3), h, N, H, acc]
    for c, v in enumerate(row, 1):
        x = ws.cell(5 + i, c, v); x.font = Font(name=F); x.alignment = CEN; x.border = BD
        if fmts[c - 1]: x.number_format = fmts[c - 1]
    print(name, lat, lon, dms(lat, "N", "S"), dms(lon, "E", "W"), round(e, 3), round(n, 3), h, N, H)
nr = 5 + len(pts) + 1
notes = ["Keterangan:",
         "- Longitude, Latitude (WGS84) & Ellipsoid Height: hasil post-processing NRTK BIG (nrtk.big.go.id), solution type Code.",
         "- Geoid Undulation (N) & Orthometric Height (H): hasil SRGI BIG (srgi.big.go.id), model INAGEOID2020 versi 2.",
         "- UTM X / UTM Y: konversi Latitude-Longitude WGS84 ke UTM Zona 49S (EPSG:32749).",
         "- Latitude negatif = Lintang Selatan."]
for k, t in enumerate(notes):
    ws.cell(nr + k, 1, t).font = Font(name=F, bold=(k == 0), italic=(k > 0), size=10)
ws.freeze_panes = "A5"
wb.save(OUT); print("saved", OUT)
