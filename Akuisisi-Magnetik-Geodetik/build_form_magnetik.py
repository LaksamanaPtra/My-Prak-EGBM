"""Build the magnetic field-acquisition workbook (Rover-Rover + Base-Rover), Excel & Google Sheets compatible.
usage: python build.py OUT.xlsx [--sample]
"""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule
from openpyxl.chart import ScatterChart, Reference, Series
from openpyxl.chart.trendline import Trendline
from openpyxl.utils import get_column_letter as CL

OUT = sys.argv[1]
SAMPLE = "--sample" in sys.argv

F = "Times New Roman"
thin = Side(style="thin", color="999999")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HDR = PatternFill("solid", fgColor="1F4E78")
INP = PatternFill("solid", fgColor="FFF9DB")    # yellow = isi di lapangan
CAL = PatternFill("solid", fgColor="E8F1FB")    # blue = rumus otomatis
RES = PatternFill("solid", fgColor="D9F2D9")    # green = hasil akhir
HLP = PatternFill("solid", fgColor="EEEEEE")    # grey = kolom bantu
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

wb = Workbook()

# ---------------------------------------------------------------- INFO
info = wb.active
info.title = "INFO"
info.column_dimensions["A"].width = 3
info.column_dimensions["B"].width = 30
info.column_dimensions["C"].width = 45
info.column_dimensions["D"].width = 60
info["B2"] = "FORM AKUISISI DATA MAGNETIK (ROVER-ROVER) - EGBM 2026"
info["B2"].font = Font(name=F, bold=True, size=14, color="1F4E78")
fields = [
    ("Kelompok", "", ""),
    ("Operator / Anggota", "", ""),
    ("Tanggal Akuisisi", "", "format dd/mm/yyyy"),
    ("Lokasi", "", "mis. Karang Ploso"),
    ("Cuaca", "", "cerah / berawan / gerimis"),
    ("Alat Magnetometer", "", "mis. PPM Geotron G5 (tulis no. alat)"),
    ("Zona UTM", "49S", "Jawa Timur umumnya 49S"),
    ("Deklinasi (°)", "", "dari NOAA / BGS calculator"),
    ("Inklinasi (°)", "", "dari NOAA / BGS calculator"),
    ("IGRF default (nT)", "", "dipakai bila kolom IGRF per titik kosong"),
    ("Koordinat Titik Base / Referensi (UTM X, Y, Z)", "", "titik ikat rover-rover"),
]
for i, (k, v, note) in enumerate(fields):
    r = 4 + i
    info.cell(r, 2, k).font = Font(name=F, bold=True)
    c = info.cell(r, 3, v)
    c.fill = INP
    c.font = Font(name=F)
    info.cell(r, 4, note).font = Font(name=F, italic=True, color="777777")
    for col in (2, 3):
        info.cell(r, col).border = BORDER
IGRF_DEF = "INFO!$C$13"

guide = [
    "WARNA SEL",
    "Kuning = diisi di lapangan  |  Biru = rumus otomatis (jangan diketik)  |  Hijau = hasil akhir (TMI)",
    "Sheet ROVER-ROVER: kolom A-L (Stasiun s/d Keterangan) SAMA PERSIS dengan Datasheet Pengukuran Lapangan (PDF);",
    "kolom setelahnya (header abu/hijau) dihitung otomatis.",
    "",
    "SHEET ROVER-ROVER (1 alat, kembali ke BASE tiap beberapa titik)",
    "1. Satu baris = satu bacaan PPM. Tulis nama stasiun di SETIAP baris bacaan (copy ke bawah).",
    "2. Bacaan di titik referensi diberi nama yang diawali 'BASE' (mis. BASE, Base1). Urutan: BASE > T1 > T2 > BASE > T3 ... > BASE.",
    "3. Koreksi Harian = (t - t1)/(t2 - t1) x (B2 - B1); t1,B1 = rata-rata waktu & PPM base SEBELUM titik, t2,B2 = base SESUDAH titik.",
    "   Koreksi harian baru muncul setelah bacaan BASE penutup loop diisi.",
    "4. Anomali Bersih = PPM - IGRF - Koreksi Harian.",
    "5. TMI = rata-rata 3 anomali yang nilainya paling berdekatan (otomatis). Untuk memilih manual, isi 1 di kolom 'Pilih'.",
    "6. UTM X/Y, Elevasi & IGRF cukup diisi di bacaan pertama tiap stasiun (baris lain ikut otomatis).",
    "7. Baris BASE berwarna biru otomatis. Cek tabel 'Rekap Base per Loop' di kanan (kolom AI-AK).",
    "8. Mau cetak form kosong? Print sheet ROVER-ROVER: sudah diatur A4 landscape, kolom A-L seperti PDF.",
    "",
    "SHEET REKAP",
    "Tabel siap gridding (X, Y, Z, TMI) untuk Oasis Montaj / Surfer / QGIS. Copy > Paste Values ke file baru / CSV.",
    "",
    "IGRF: https://www.ngdc.noaa.gov/geomag/calculators/magcalc.shtml  (input lokasi & tanggal, model WMMHR/IGRF, Calculate)",
    "      https://geomag.bgs.ac.uk/data_service/models_compass/gma_calc.html",
    "Tip lapangan: catat jam di HP & jam alat (sinkronkan), nama titik, cuaca, & gangguan (kendaraan, pagar besi, kabel) di Keterangan.",
]
r0 = 18
info.cell(r0, 2, "PETUNJUK").font = Font(name=F, bold=True, size=12, color="1F4E78")
for i, t in enumerate(guide):
    c = info.cell(r0 + 1 + i, 2, t)
    c.font = Font(name=F, bold=t.isupper() and t != "", size=11)


# kolom isian lapangan = Datasheet Pengukuran Lapangan (PDF), urutan sama persis
FIELD_COLS = [("Stasiun", 10, "inp"), ("Datum", 9, "inp"), ("Signal", 7, "inp"), ("Jam", 6, "inp"),
              ("Menit", 6, "inp"), ("Detik", 6, "inp"), ("UTM X", 11, "inp"), ("UTM Y", 12, "inp"),
              ("Elevasi", 8, "inp"), ("Pembacaan PPM", 12, "inp"), ("IGRF", 10, "inp"), ("Keterangan", 24, "inp")]
HDR_CAL = PatternFill("solid", fgColor="44546A")
HDR_RES = PatternFill("solid", fgColor="2E7D32")


def header_block(ws, title, last_col=12):
    """Kop seperti PDF: KELOMPOK/OPERATOR/CUACA kiri, DEKLINASI/INKLINASI/DATE kanan (diambil dari INFO)."""
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
    ws["A2"] = title
    ws["A2"].font = Font(name=F, bold=True, size=14)
    ws["A2"].alignment = CENTER
    meta = [("KELOMPOK", "INFO!$C$4"), ("OPERATOR", "INFO!$C$5"), ("CUACA", "INFO!$C$8"),
            ("DEKLINASI", "INFO!$C$11"), ("INKLINASI", "INFO!$C$12"), ("DATE", "INFO!$C$6")]
    for i, (k, ref) in enumerate(meta):
        r = 4 + i % 3
        lab, v0, v1 = (1, 2, 8) if i < 3 else (9, 10, 12)
        ws.cell(r, lab, k).font = Font(name=F, bold=True)
        ws.merge_cells(start_row=r, start_column=v0, end_row=r, end_column=v1)
        c = ws.cell(r, v0, f'=IF({ref}="","",{ref})')
        c.font = Font(name=F)
        if k == "DATE":
            c.number_format = "dd/mm/yyyy"
        for col in range(lab, v1 + 1):
            ws.cell(r, col).border = BORDER


def write_headers(ws, headers, row=8):
    fills = {"inp": HDR, "cal": HDR_CAL, "res": HDR_RES, "hlp": HLP}
    for j, (name, width, kind) in enumerate(headers, 1):
        c = ws.cell(row, j, name)
        c.font = Font(name=F, bold=True, color="FFFFFF" if kind != "hlp" else "000000")
        c.fill = fills[kind]
        c.alignment = CENTER
        c.border = BORDER
        ws.column_dimensions[CL(j)].width = width
    ws.row_dimensions[row].height = 32


def style_body(ws, headers, r1, r2):
    fills = {"inp": INP, "cal": CAL, "res": RES, "hlp": HLP}
    for j, (_, _, kind) in enumerate(headers, 1):
        for r in range(r1, r2 + 1):
            c = ws.cell(r, j)
            c.fill = fills[kind]
            c.border = BORDER
            c.font = Font(name=F, size=11, bold=(kind == "res"), color="777777" if kind == "hlp" else "000000")
            c.alignment = Alignment(horizontal="center")


def tmi_select(val, grp, k, pick, avg3, best, r1, r2):
    """TMI for group k: manual pick > best 3 closest values > mean of all."""
    R = lambda c: f"${c}${r1}:${c}${r2}"
    return (f'IF(COUNTIFS({R(grp)},{k},{R(pick)},1)>0,AVERAGEIFS({R(val)},{R(grp)},{k},{R(pick)},1),'
            f'IF(COUNTIFS({R(grp)},{k},{R(best)},TRUE)>0,AVERAGEIFS({R(avg3)},{R(grp)},{k},{R(best)},TRUE),'
            f'AVERAGEIFS({R(val)},{R(grp)},{k})))')


def closest3_helpers(ws, r, r1, r2, val, grp, first, count, rank, n, spread, avg3, best):
    """Rank each value within its point, then spread/avg of it + next 2 larger values (sorted)."""
    v, g = f"{val}{r}", f"{grp}{r}"
    blk = f"OFFSET(${val}${r1},{first}{r}-1,0,{count}{r},1)"
    ws[f"{first}{r}"] = f'=IF({g}="","",MATCH({g},${grp}${r1}:${grp}${r2},0))'
    ws[f"{count}{r}"] = f'=IF({g}="","",COUNTIF(${grp}${r1}:${grp}${r2},{g}))'
    ws[f"{rank}{r}"] = (f'=IF(OR({g}="",NOT(ISNUMBER({v}))),"",COUNTIFS(${grp}${r1}:${grp}${r2},{g},${val}${r1}:${val}${r2},"<"&{v})'
                        f'+COUNTIFS(${grp}${r1}:{grp}{r},{g},${val}${r1}:{val}{r},{v}))')
    ws[f"{n}{r}"] = f'=IF({g}="","",COUNT({blk}))'
    ws[f"{spread}{r}"] = f'=IF({rank}{r}="","",IF({rank}{r}<={n}{r}-2,SMALL({blk},{rank}{r}+2)-{v},""))'
    ws[f"{avg3}{r}"] = f'=IF({spread}{r}="","",({v}+SMALL({blk},{rank}{r}+1)+SMALL({blk},{rank}{r}+2))/3)'
    ws[f"{best}{r}"] = f'=IF({spread}{r}="",FALSE,COUNTIFS(${grp}${r1}:${grp}${r2},{g},${spread}${r1}:${spread}${r2},"<"&{spread}{r})=0)'


# ---------------------------------------------------------------- RR (rover-rover)
# A..L = persis urutan Datasheet Pengukuran Lapangan (PDF); M..U = hitungan; V..AG = kolom bantu
rr = wb.create_sheet("ROVER-ROVER")
R1, R2 = 9, 808
H = FIELD_COLS + [
     ("Waktu", 10, "cal"), ("Detik Pengukuran", 12, "cal"), ("IGRF dipakai", 11, "cal"),
     ("Detik Base (rata2)", 12, "cal"), ("PPM Base (rata2)", 12, "cal"), ("Koreksi Harian", 11, "cal"),
     ("Anomali Bersih", 11, "cal"), ("Pilih (1)", 7, "inp"), ("TMI", 11, "res"),
     ("ptIdx", 6, "hlp"), ("iter", 5, "hlp"), ("isBase", 7, "hlp"), ("baseNo", 6, "hlp"), ("staIdx", 6, "hlp"),
     ("first", 5, "hlp"), ("count", 5, "hlp"), ("rank", 5, "hlp"), ("n", 4, "hlp"), ("spread", 7, "hlp"),
     ("avg3", 9, "hlp"), ("best", 6, "hlp")]
header_block(rr, "DATA PENGUKURAN METODE MAGNETIK - ROVER ROVER")
write_headers(rr, H)
style_body(rr, H, R1, R2)
T = lambda col, k: f"INDEX(${col}${R1}:${col}$108,{k})"
for r in range(R1, R2 + 1):
    p = r - 1
    rr[f"M{r}"] = f'=IF(OR(A{r}="",D{r}=""),"",TIME(D{r},E{r},F{r}))'
    rr[f"M{r}"].number_format = "hh:mm:ss"
    rr[f"N{r}"] = f'=IF(OR(A{r}="",D{r}=""),"",D{r}*3600+E{r}*60+F{r})'
    rr[f"O{r}"] = (f'=IF(A{r}="","",IF(K{r}<>"",K{r},IF(INDEX($K${R1}:$K${R2},AA{r})<>"",'
                   f'INDEX($K${R1}:$K${R2},AA{r}),IF({IGRF_DEF}="","",{IGRF_DEF}))))')
    rr[f"P{r}"] = f'=IF(AND(X{r}=TRUE,W{r}=1),{T("AJ", f"Y{r}")},"")'
    rr[f"Q{r}"] = f'=IF(AND(X{r}=TRUE,W{r}=1),{T("AK", f"Y{r}")},"")'
    rr[f"R{r}"] = (f'=IF(OR(A{r}="",X{r}<>FALSE,N{r}="",J{r}=""),"",IFERROR((N{r}-{T("AJ", f"Y{r}")})/'
                   f'({T("AJ", f"Y{r}+1")}-{T("AJ", f"Y{r}")})*({T("AK", f"Y{r}+1")}-{T("AK", f"Y{r}")}),""))')
    rr[f"S{r}"] = f'=IF(OR(R{r}="",J{r}="",O{r}=""),"",J{r}-O{r}-R{r})'
    rr[f"U{r}"] = (f'=IF(OR(A{r}="",X{r}<>FALSE,W{r}<>1),"",IFERROR('
                   + tmi_select("S", "V", f"V{r}", "T", "AF", "AG", R1, R2) + ',""))')
    rr[f"N{r}"].number_format = "0"
    rr[f"P{r}"].number_format = "0.0"
    for c in "OQRSU":
        rr[f"{c}{r}"].number_format = "0.00"
    rr[f"V{r}"] = (f'=IF(A{r}="","",IF(A{r}=A{p},V{p},MAX($V${R1 - 1}:V{p})+1))' if r > R1
                   else f'=IF(A{r}="","",1)')
    rr[f"W{r}"] = f'=IF(A{r}="","",COUNTIF($V${R1}:V{r},V{r}))'
    rr[f"X{r}"] = f'=IF(A{r}="","",UPPER(LEFT(TRIM(A{r}),4))="BASE")'
    rr[f"Y{r}"] = f'=IF(A{r}="","",COUNTIFS($X${R1}:X{r},TRUE,$W${R1}:W{r},1))'
    rr[f"Z{r}"] = f'=IF(OR(A{r}="",X{r}<>FALSE),"",COUNTIFS($X${R1}:X{r},FALSE,$W${R1}:W{r},1))'
    closest3_helpers(rr, r, R1, R2, "S", "V", "AA", "AB", "AC", "AD", "AE", "AF", "AG")
    for c in ("AE", "AF"):
        rr[f"{c}{r}"].number_format = "0.00"
rr["AI7"] = "REKAP BASE PER LOOP (otomatis)"
rr["AI7"].font = Font(name=F, bold=True)
for j, (name, w) in enumerate([("Base ke-", 8), ("Detik rata2 (t)", 14), ("PPM rata2 (B)", 14)]):
    c = rr.cell(8, 35 + j, name)
    c.font = Font(name=F, bold=True, color="FFFFFF"); c.fill = HDR_CAL; c.alignment = CENTER; c.border = BORDER
    rr.column_dimensions[CL(35 + j)].width = w
for i in range(100):
    r = R1 + i
    rr[f"AI{r}"] = i + 1
    rr[f"AJ{r}"] = f'=IFERROR(AVERAGEIFS($N${R1}:$N${R2},$Y${R1}:$Y${R2},AI{r},$X${R1}:$X${R2},TRUE),"")'
    rr[f"AK{r}"] = f'=IFERROR(AVERAGEIFS($J${R1}:$J${R2},$Y${R1}:$Y${R2},AI{r},$X${R1}:$X${R2},TRUE),"")'
    for c in ("AI", "AJ", "AK"):
        rr[f"{c}{r}"].fill = CAL; rr[f"{c}{r}"].border = BORDER; rr[f"{c}{r}"].font = Font(name=F)
    rr[f"AJ{r}"].number_format = "0.0"; rr[f"AK{r}"].number_format = "0.000"
rr.freeze_panes = "B9"
rr.page_setup.orientation = "landscape"
rr.page_setup.paperSize = rr.PAPERSIZE_A4
rr.page_setup.fitToWidth = 1
rr.page_setup.fitToHeight = 0
rr.sheet_properties.pageSetUpPr.fitToPage = True
rr.print_area = f"A2:L{R2}"
rr.print_title_rows = "2:8"
rr.column_dimensions.group("V", "AG", hidden=True)
rr.conditional_formatting.add(f"A{R1}:U{R2}", FormulaRule(formula=[f"$X{R1}=TRUE"], fill=PatternFill("solid", fgColor="BDD7EE")))
dv = DataValidation(type="list", formula1='"1"', allow_blank=True)
rr.add_data_validation(dv); dv.add(f"T{R1}:T{R2}")

# ---------------------------------------------------------------- REKAP
rk = wb.create_sheet("REKAP")
rk["A1"] = "REKAP TMI PER TITIK (siap gridding: Oasis Montaj / Surfer / QGIS) - Copy > Paste Values"
rk["A1"].font = Font(name=F, bold=True, size=13, color="1F4E78")
blocks = [(1, "ROVER-ROVER", "'ROVER-ROVER'", R1, R2, "Z", "A", "G", "H", "I", "U")]
for c0, title, sh, a, b, idx, nm, x, y, z, tmi in blocks:
    rk.cell(3, c0, title).font = Font(name=F, bold=True)
    for j, (h, w) in enumerate([("No", 5), ("Titik", 10), ("UTM X", 12), ("UTM Y", 13), ("Z", 9),
                                ("TMI (nT)", 11), ("n bacaan", 8)]):
        c = rk.cell(4, c0 + j, h)
        c.font = Font(name=F, bold=True, color="FFFFFF"); c.fill = HDR; c.alignment = CENTER; c.border = BORDER
        rk.column_dimensions[CL(c0 + j)].width = w
    for i in range(200):
        r = 5 + i
        k = f"{CL(c0)}{r}"
        rk.cell(r, c0, i + 1)
        m = f"MATCH({k},{sh}!${idx}${a}:${idx}${b},0)"
        for j, col in enumerate((nm, x, y, z, tmi), 1):
            ix = f"INDEX({sh}!${col}${a}:${col}${b},{m})"
            rk.cell(r, c0 + j, f'=IFERROR(IF({ix}="","",{ix}),"")')
        rk.cell(r, c0 + 6, f'=IF({CL(c0 + 1)}{r}="","",COUNTIF({sh}!${idx}${a}:${idx}${b},{k}))')
        for j in range(7):
            cc = rk.cell(r, c0 + j)
            cc.border = BORDER; cc.font = Font(name=F, bold=(j == 5)); cc.fill = RES if j == 5 else CAL
        rk.cell(r, c0 + 5).number_format = "0.00"
rk.freeze_panes = "A5"

# ---------------------------------------------------------------- sample data (test only)
if SAMPLE:
    import math
    info["C13"] = 44952
    rows = [("Base", 7, 23, 57, 44963.46667, 44952.2), ("Base", 7, 24, 10, 44963.46667, None),
            ("Base", 7, 24, 15, 44963.46667, None), ("Base", 7, 24, 50, 44963.46667, None), ("Base", 7, 25, 26, 44963.46667, None)]
    rows += [("T118", 7, 48, 25, 45207.6, 44952.2), ("T118", 7, 48, 32, 45208.5, None), ("T118", 7, 48, 59, 45208.7, None),
             ("T118", 7, 50, 9, 45209, None), ("T118", 7, 50, 18, 45209, None)]
    t119 = [(8, 15, 0, 45192.2), (8, 15, 20, 45200), (8, 15, 55, 45196.4), (8, 16, 5, 45185.4), (8, 16, 35, 45196.6),
            (8, 16, 58, 45195.2), (8, 17, 1, 45199.3)]
    rows += [("T119", h, m, s, v, 44956.7 if i == 0 else None) for i, (h, m, s, v) in enumerate(t119)]
    rows += [("Base", 10, 15, 17, 44974.8, None), ("Base", 10, 16, 37, 44974.8, None), ("Base", 10, 17, 23, 44974.8, None),
             ("Base", 10, 17, 47, 44974.8, None), ("Base", 10, 18, 13, 44974.8, None)]
    for i, (n, h, m, s, v, ig) in enumerate(rows):
        r = R1 + i
        rr[f"A{r}"] = n; rr[f"D{r}"] = h; rr[f"E{r}"] = m; rr[f"F{r}"] = s; rr[f"J{r}"] = v
        if ig: rr[f"K{r}"] = ig
    rr["G14"] = 685172; rr["H14"] = 9077775; rr["I14"] = 358

wb.save(OUT)
print("saved", OUT)
