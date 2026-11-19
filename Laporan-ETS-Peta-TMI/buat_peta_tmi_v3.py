# -*- coding: utf-8 -*-
"""
buat_peta_tmi_v3.py — layout gaya peta referensi (QGIS 4.2.3)
Praktikum Eksplorasi Gaya Berat Magnetik (EGBM) — Laksamana Putra Yulistiono (5017251036)

Data, simbologi, rentang warna dan kontur sama dengan v2; yang berubah hanya layout:
  - BR dan RR sama-sama A4 landscape; bingkai ganda; kotak judul di atas peta
  - panel kanan berkotak: institusi (logo ITS) & pembuat | utara & skala | legenda |
    lokasi penelitian (inset OSM + grid derajat) | keterangan | sumber data
  - grid UTM garis abu-abu tipis tiap 500 m, label koordinat di keempat sisi
  - teks >= 6 pt bila gambar disisipkan selebar 16 cm; judul >= 1,6 x teks
  - 10 peta: 01 desain, 02 Kriging, 03 MC, 04 selisih, 05 TMI raw MC

Cara menjalankan
  Standalone : "C:\\OSGeo4W\\bin\\python-qgis.bat" "<ROOT>\\QGIS\\buat_peta_tmi_v3.py"
  QGIS Python Console : exec(open(r"<ROOT>\\QGIS\\buat_peta_tmi_v3.py", encoding="utf-8").read())
  Sebagian peta saja: environment TMI_V3_RENDER=BR_02 (atau daftar dipisah koma); default ALL.

Hasil hanya ditulis ke ROOT\\QGIS\\<DATASET>\\output_v3\\ dan ROOT\\QGIS\\<DATASET>\\Peta_<Dataset>_v3.qgz.
TUTORIAL, DATA, SURFER, output lama dan output_v2 hanya dibaca.
"""
import os
import csv
import math
import datetime
import urllib.request

os.environ["GDAL_PAM_ENABLED"] = "NO"     # jangan tulis .aux.xml di samping grid sumber
os.environ["SHAPE_RESTORE_SHX"] = "NO"    # jangan pernah membuat .shx di folder SURFER

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")
gdal.SetConfigOption("SHAPE_RESTORE_SHX", "NO")

from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsVectorFileWriter, QgsRectangle, QgsStyle, QgsColorRampShader, QgsRasterShader,
    QgsSingleBandPseudoColorRenderer, QgsBilinearRasterResampler, QgsRasterDataProvider,
    QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
    QgsRuleBasedRenderer, QgsSingleSymbolRenderer, QgsPalLayerSettings, QgsTextFormat,
    QgsTextBufferSettings, QgsTextMaskSettings, QgsSymbolLayerReference, QgsVectorLayerSimpleLabeling,
    QgsPrintLayout, QgsLayoutItem, QgsLayoutItemPage, QgsLayoutItemMap, QgsLayoutItemMapGrid,
    QgsLayoutItemMapOverview, QgsLayoutItemLabel, QgsLayoutItemScaleBar, QgsLayoutItemPicture,
    QgsLayoutItemShape, QgsLayoutItemPolyline, QgsLayoutItemMarker, QgsLayoutPoint, QgsLayoutSize,
    QgsLayoutMeasurement, QgsLayoutExporter, QgsHueSaturationFilter, QgsBasicNumericFormat,
    QgsGradientFillSymbolLayer, QgsSimpleFillSymbolLayer,
)
from qgis.PyQt.QtCore import Qt, QMetaType, QPointF
from qgis.PyQt.QtGui import QColor, QFont, QPainter, QPolygonF, QFontMetricsF, QImage

ROOT = r"D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\LAPORAN ETS (2)"
EPSG = "EPSG:32749"
MM = Qgis.LayoutUnit.Millimeters
WORD_WIDTH_MM = 160.0          # lebar gambar di Word
MIN_PT_AT_WORD = 6.0           # ukuran minimum teks pada lebar 16 cm (keputusan v3)
LOGO_ITS = os.path.join(ROOT, "zLOGO ITS", "Lambang ITS.png")
PANEL_W = 82.0                 # lebar panel kanan (mm)
OUT_DIR_NAME = "output_v3"
URL_SAT = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
URL_TERRAIN = "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}"
URL_OSM = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
JATIM_LONLAT = (110.85, -8.85, 114.65, -6.70)   # extent inset Jawa Timur (lon/lat)
NAMA = "Laksamana Putra Yulistiono (5017251036)"
TEKS_GRIDDING = ("Gridding: Oasis montaj 2026.1.1 (Kriging/Minimum Curvature); kontur: Surfer 23; "
                 "layout: QGIS 4.2.3.")
TEKS_CRS = "Sistem koordinat: WGS 84 / UTM Zona 49S."
DAY_COLORS = ["#e41a1c", "#2b83ba", "#33a02c", "#ff7f00", "#984ea3"]
GRID_INTERVAL = 500
DATA_MARGIN_M = 50             # margin minimal di sekitar data saat memilih skala

RENDER = os.environ.get("TMI_V3_RENDER", "ALL").upper()

CONFIGS = [
    dict(
        key="BASE-ROVER", prefix="BR", project_name="Peta_Base-Rover_v3", orientation="landscape",
        subtitle="Konfigurasi Base-Rover, Telaga Ngebel, Ponorogo",
        periode="11, 13, dan 14 Agustus 2026",
        points_csv=os.path.join(ROOT, "DATA", "TMI_Base-Rover Laksa.csv"),
        day_field="DAY", name_field="Nama_titik", x_field="UTM X", y_field="UTM Y",
        z_field="Z", tmi_field="TMI", expected_n=74,
        bases=[("Base station", 111.638979, -7.795342, "EPSG:4326")],
        base_note="Base station: 111,638979° BT; 7,795342° LS.",
        grid_krig=os.path.join(ROOT, "TUTORIAL", "BASE-ROVER", "base-rover_TMI_Kriging_SurferV7.grd"),
        grid_mc=os.path.join(ROOT, "TUTORIAL", "BASE-ROVER", "base-rover_TMI_MC_SurferV7.grd"),
        kontur_krig=os.path.join(ROOT, "SURFER", "BR_Kontur_Kriging.shp"),
        kontur_mc=os.path.join(ROOT, "SURFER", "BR_Kontur_MC.shp"),
        grid_range=dict(krig=(-1199.3, 1056.4), mc=(-1548.9, 1046.6)),
        contour_interval=100, diff_interval=100,
        R=1600, ticks=[-1600, -800, 0, 800, 1600],
        S=500, diff_ticks=[-500, -250, 0, 250, 500],
        # ambang $length label kontur per peta (m); dinaikkan bertahap hanya untuk peta yang padat
        label_min_length={"02": 1000, "03": 1000, "04": 1000, "05": 1000},
        raw=dict(  # peta 05: TMI raw (sebelum koreksi diurnal), Minimum Curvature
            grid=os.path.join(ROOT, "TUTORIAL", "RAW", "BASE ROVER", "raw_base-rover_TMI_RAW_SurferV7.grd"),
            csv=os.path.join(ROOT, "DATA", "TMI_RAW_Base-Rover.csv"), tmi_field="TMI_RAW",
            kontur=os.path.join(ROOT, "SURFER", "BR_Kontur_RAW_MC.shp"),
            geom=(49, 26, 99, 567462, 9137613),
            stats=(-1406.12, 1159.59, 129.58, 1255),
            label_min_length=1000,
        ),
    ),
    dict(
        key="ROVER-ROVER", prefix="RR", project_name="Peta_Rover-Rover_v3", orientation="landscape",
        subtitle="Konfigurasi Rover-Rover, Sumbermanjing Wetan, Malang",
        periode="3–6 Agustus 2025",
        points_csv=os.path.join(ROOT, "DATA", "DATA_TMI_Rover-Rover_D1_D4.csv"),
        day_field="HARI", name_field="NAMA_TITIK", x_field="UTM_X", y_field="UTM_Y",
        z_field="Z", tmi_field="TMI", expected_n=86,
        bases=[("Base D-1", 684689.0, 9078345.0, EPSG),
               ("Base D-2", 684074.0, 9077531.0, EPSG),
               ("Base D-3", 684734.7, 9079236.0, EPSG)],
        base_note="Base D-4 tidak ditampilkan (koordinat tidak valid).",
        grid_krig=os.path.join(ROOT, "TUTORIAL", "ROVER-ROVER", "rover-rover_TMI_Kriging_SurverV7.grd"),
        grid_mc=os.path.join(ROOT, "TUTORIAL", "ROVER-ROVER", "rover-rover_TMI_MC_SurverV7.grd"),
        kontur_krig=os.path.join(ROOT, "SURFER", "RR_Kontur_Kriging.shp"),
        kontur_mc=os.path.join(ROOT, "SURFER", "RR_Kontur_MC.shp"),
        grid_range=dict(krig=(-574.9, 422.2), mc=(-817.4, 446.3)),
        contour_interval=50, diff_interval=50,
        R=900, ticks=[-900, -600, -300, 0, 300, 600, 900],
        S=175, diff_ticks=[-175, -100, 0, 100, 175],
        label_min_length={"02": 1000, "03": 1000, "04": 1000, "05": 1000},
        raw=dict(
            grid=os.path.join(ROOT, "TUTORIAL", "RAW", "ROVER ROVER", "raw_rover-rover_TMI_RAW_SurferV7.grd"),
            csv=os.path.join(ROOT, "DATA", "TMI_RAW_Rover-Rover.csv"), tmi_field="TMI_RAW",
            kontur=os.path.join(ROOT, "SURFER", "RR_Kontur_RAW_MC.shp"),
            geom=(32, 47, 88, 683032, 9077547),
            stats=(-802.57, 448.70, -42.77, 1391),
            label_min_length=1000,
        ),
    ),
]

STAT_KEYS = ["min_nT", "max_nT", "mean_nT", "std_nT", "n_sel_valid",
             "rms_residual_nT", "n_titik_residual", "n_titik_luar_grid"]


# ============================================================================ util umum
def ceil_to(v, step):
    return math.ceil(v / step - 1e-9) * step


def fmt_id(v, dec=0):
    s = f"{v:,.{dec}f}"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def fmt_tick(v):
    return f"{v:g}".replace("-", "−")


_METRIC_IMG = None


def _metric_device():
    global _METRIC_IMG
    if _METRIC_IMG is None:
        _METRIC_IMG = QImage(8, 8, QImage.Format.Format_ARGB32)
        dpm = int(round(300 / 0.0254))
        _METRIC_IMG.setDotsPerMeterX(dpm)
        _METRIC_IMG.setDotsPerMeterY(dpm)
    return _METRIC_IMG


def font_metrics(size, bold=False):
    f = QFont("Arial")
    f.setPointSizeF(size)
    f.setBold(bold)
    return QFontMetricsF(f, _metric_device())


def text_w(text, size, bold=False):
    """Lebar teks (mm) pada ukuran font (pt)."""
    return font_metrics(size, bold).horizontalAdvance(text) / 300.0 * 25.4


def line_h(size, bold=False):
    return font_metrics(size, bold).lineSpacing() / 300.0 * 25.4


def wrap(text, width_mm, size, bold=False):
    out = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = (cur + " " + word).strip()
            if cur and text_w(trial, size, bold) > width_mm:
                out.append(cur)
                cur = word
            else:
                cur = trial
        out.append(cur)
    return out


class FontLog:
    """Mencatat semua ukuran font layout untuk laporan ukuran terkecil."""
    def __init__(self):
        self.sizes = []

    def add(self, size, what):
        self.sizes.append((size, what))
        return size


def text_format(size, bold=False, color="black", buffer=None):
    f = QFont("Arial")
    f.setBold(bold)
    tf = QgsTextFormat()
    tf.setFont(f)
    tf.setSize(size)
    tf.setSizeUnit(Qgis.RenderUnit.Points)
    tf.setColor(QColor(color))
    if buffer:
        b = QgsTextBufferSettings()
        b.setEnabled(True)
        b.setSize(buffer[0])
        b.setSizeUnit(Qgis.RenderUnit.Millimeters)
        b.setColor(QColor(buffer[1]))
        tf.setBuffer(b)
    return tf


def read_grid(path):
    ds = gdal.OpenEx(path, gdal.OF_RASTER | gdal.OF_READONLY)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray().astype(np.float64)
    nd = band.GetNoDataValue()
    valid = np.isfinite(arr) & (np.abs(arr) < 1e30)
    if nd is not None:
        valid &= arr != nd
    gt = ds.GetGeoTransform()
    ext = (gt[0], gt[3] + gt[5] * ds.RasterYSize, gt[0] + gt[1] * ds.RasterXSize, gt[3])
    ds = None
    return arr, valid, gt, nd, ext


def bilinear_sample(arr, valid, gt, x, y):
    c = (x - gt[0]) / gt[1] - 0.5
    r = (y - gt[3]) / gt[5] - 0.5
    c0, r0 = int(math.floor(c)), int(math.floor(r))
    if c0 < 0 or r0 < 0 or c0 + 1 >= arr.shape[1] or r0 + 1 >= arr.shape[0]:
        return None
    if not valid[r0:r0 + 2, c0:c0 + 2].all():
        return None
    dc, dr = c - c0, r - r0
    return ((1 - dc) * (1 - dr) * arr[r0, c0] + dc * (1 - dr) * arr[r0, c0 + 1]
            + (1 - dc) * dr * arr[r0 + 1, c0] + dc * dr * arr[r0 + 1, c0 + 1])


def nice_scale(need):
    s = 2500
    while s < need:
        s += 2500
    return s


# ============================================================================ data
def check_surfer_contours(cfg, log):
    """Pengecekan (a)–(d) shapefile kontur Surfer. Mengembalikan baris tabel; raise bila gagal."""
    rows, ok_all = [], True
    for key, path, grid in [("krig", cfg["kontur_krig"], cfg["grid_krig"]),
                            ("mc", cfg["kontur_mc"], cfg["grid_mc"])]:
        name = os.path.basename(path)
        comps = [os.path.splitext(path)[0] + e for e in (".shp", ".shx", ".dbf")]
        if not all(os.path.exists(c) for c in comps):
            rows.append(f"{name}: (a) GAGAL — komponen .shp/.shx/.dbf tidak lengkap")
            ok_all = False
            continue
        ds = gdal.OpenEx(path, gdal.OF_VECTOR | gdal.OF_READONLY)
        lyr = ds.GetLayer(0)
        z = np.array(sorted({f.GetField("ZLEVEL") for f in lyr}))
        lyr.ResetReading()
        e = lyr.GetExtent()  # xmin, xmax, ymin, ymax
        n = lyr.GetFeatureCount()
        ds = None
        gmin, gmax = cfg["grid_range"][key]
        gext = read_grid(grid)[4]
        iv = cfg["contour_interval"]
        steps = np.unique(np.round(np.diff(z), 6))
        ok_b = z.min() >= gmin and z.max() <= gmax
        ok_c = len(steps) == 1 and abs(steps[0] - iv) < 1e-6
        ok_d = e[0] >= gext[0] and e[1] <= gext[2] and e[2] >= gext[1] and e[3] <= gext[3]
        rows.append(f"{name}: (a) OK {n} garis | (b) {'OK' if ok_b else 'GAGAL'} ZLEVEL {z.min():g}..{z.max():g} "
                    f"(grid {gmin}..{gmax}) | (c) {'OK' if ok_c else 'GAGAL'} interval {list(steps)} | "
                    f"(d) {'OK' if ok_d else 'GAGAL'} extent di dalam grid")
        ok_all &= ok_b and ok_c and ok_d
    for r in rows:
        log("Cek kontur Surfer — " + r)
    if not ok_all:
        raise RuntimeError(f"[{cfg['key']}] Pengecekan shapefile kontur Surfer GAGAL — BERHENTI.")


def build_point_gpkg(cfg, gpkg, log):
    with open(cfg["points_csv"], encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != cfg["expected_n"]:
        raise RuntimeError(f"[{cfg['key']}] Jumlah titik {len(rows)} != {cfg['expected_n']}. BERHENTI.")
    crs = QgsCoordinateReferenceSystem(EPSG)
    fields = QgsFields()
    for name, typ in [(cfg["day_field"], QMetaType.Type.QString), (cfg["name_field"], QMetaType.Type.QString),
                      (cfg["x_field"], QMetaType.Type.Double), (cfg["y_field"], QMetaType.Type.Double),
                      (cfg["z_field"], QMetaType.Type.Double), (cfg["tmi_field"], QMetaType.Type.Double)]:
        fields.append(QgsField(name, typ))
    feats = []
    for r in rows:
        f = QgsFeature(fields)
        x, y = float(r[cfg["x_field"]]), float(r[cfg["y_field"]])
        f.setAttributes([r[cfg["day_field"]].strip(), r[cfg["name_field"]].strip(), x, y,
                         float(r[cfg["z_field"]]), float(r[cfg["tmi_field"]])])
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        feats.append(f)
    bfields = QgsFields()
    bfields.append(QgsField("NAMA", QMetaType.Type.QString))
    bfields.append(QgsField("UTM_X", QMetaType.Type.Double))
    bfields.append(QgsField("UTM_Y", QMetaType.Type.Double))
    bfeats = []
    for name, bx, by, bcrs in cfg["bases"]:
        p = QgsPointXY(bx, by)
        if bcrs != EPSG:
            p = QgsCoordinateTransform(QgsCoordinateReferenceSystem(bcrs), crs, QgsProject.instance()).transform(p)
            log(f"Base '{name}' {bx}, {by} ({bcrs}) -> {p.x():.2f}, {p.y():.2f} ({EPSG})")
        f = QgsFeature(bfields)
        f.setAttributes([name, p.x(), p.y()])
        f.setGeometry(QgsGeometry.fromPointXY(p))
        bfeats.append(f)
    for lname, flds, fts, mode in [
            ("titik_ukur", fields, feats, QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile),
            ("base_station", bfields, bfeats, QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteLayer)]:
        mem = QgsVectorLayer(f"Point?crs={EPSG}", lname, "memory")
        mem.dataProvider().addAttributes(flds.toList())
        mem.updateFields()
        mem.dataProvider().addFeatures(fts)
        opt = QgsVectorFileWriter.SaveVectorOptions()
        opt.driverName = "GPKG"
        opt.layerName = lname
        opt.actionOnExistingFile = mode
        err = QgsVectorFileWriter.writeAsVectorFormatV3(mem, gpkg, QgsProject.instance().transformContext(), opt)
        if err[0] != QgsVectorFileWriter.WriterError.NoError:
            raise RuntimeError(f"Gagal menulis {lname}: {err}")


def raster_difference(mc, krig, out_tif, project):
    from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
    entries = []
    for ref, lyr in [("mc@1", mc), ("krig@1", krig)]:
        e = QgsRasterCalculatorEntry()
        e.ref = ref
        e.raster = lyr
        e.bandNumber = 1
        entries.append(e)
    calc = QgsRasterCalculator('"mc@1" - "krig@1"', out_tif, "GTiff", mc.extent(), mc.crs(),
                               mc.width(), mc.height(), entries, project.transformContext())
    res = calc.processCalculation()
    if res != QgsRasterCalculator.Result.Success:
        raise RuntimeError(f"Raster Calculator gagal: {res} {calc.lastError()}")


def make_diff_contours(tif, gpkg, interval, log):
    ds = gdal.OpenEx(tif, gdal.OF_RASTER | gdal.OF_READONLY)
    band = ds.GetRasterBand(1)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32749)
    drv = ogr.GetDriverByName("GPKG")
    out = drv.Open(gpkg, 1) if os.path.exists(gpkg) else drv.CreateDataSource(gpkg)
    lyr = out.CreateLayer("kontur_selisih", srs, ogr.wkbLineString, options=["OVERWRITE=YES"])
    lyr.CreateField(ogr.FieldDefn("ID", ogr.OFTInteger))
    lyr.CreateField(ogr.FieldDefn("ZLEVEL", ogr.OFTReal))
    opts = [f"LEVEL_INTERVAL={interval}", "LEVEL_BASE=0", "ID_FIELD=0", "ELEV_FIELD=1"]
    if band.GetNoDataValue() is not None:
        opts.append(f"NODATA={band.GetNoDataValue()}")
    gdal.ContourGenerateEx(band, lyr, options=opts)
    n = lyr.GetFeatureCount()
    out = None
    ds = None
    log(f"Kontur selisih (GDAL, interval {interval} nT): {n} garis")
    return n


def compute_stats(cfg, diff_tif, pts):
    arrs = {k: read_grid(p) for k, p in [("krig", cfg["grid_krig"]), ("mc", cfg["grid_mc"]), ("diff", diff_tif)]}
    exp_valid = arrs["krig"][1] & arrs["mc"][1]
    if (arrs["diff"][1] != exp_valid).any():
        raise RuntimeError("Mask NoData selisih tidak sama dengan irisan sel valid Kriging & MC")
    rows = []
    for key, label, fname in [("krig", "Kriging", cfg["grid_krig"]), ("mc", "Minimum Curvature", cfg["grid_mc"]),
                              ("diff", "Selisih (MC - Kriging)", diff_tif)]:
        a, v, gt, _, _ = arrs[key]
        vals = a[v]
        row = dict(dataset=cfg["key"], grid=label, berkas=os.path.basename(fname),
                   min_nT=f"{vals.min():.3f}", max_nT=f"{vals.max():.3f}", mean_nT=f"{vals.mean():.3f}",
                   std_nT=f"{vals.std():.3f}", n_sel_valid=str(int(v.sum())),
                   rms_residual_nT="", n_titik_residual="", n_titik_luar_grid="",
                   rentang_warna_nT=f"±{cfg['S']}" if key == "diff" else f"±{cfg['R']}")
        if key != "diff":
            res = [t - g for x, y, t in pts if (g := bilinear_sample(a, v, gt, x, y)) is not None]
            res = np.array(res)
            row["rms_residual_nT"] = f"{math.sqrt(np.mean(res ** 2)):.3f}"
            row["n_titik_residual"] = str(len(res))
            row["n_titik_luar_grid"] = str(len(pts) - len(res))
        rows.append(row)
    return rows


def compare_with_old_stats(cfg, rows, log):
    old_csv = os.path.join(ROOT, "QGIS", cfg["key"], "output", "statistik_grid.csv")
    with open(old_csv, encoding="utf-8-sig", newline="") as fh:
        old = {r["grid"]: r for r in csv.DictReader(fh)}
    bad = []
    for r in rows:
        o = old.get(r["grid"])
        for k in STAT_KEYS:
            if o is None or str(o[k]) != str(r[k]):
                bad.append(f"{r['grid']}.{k}: lama={None if o is None else o[k]} baru={r[k]}")
    if bad:
        for b in bad:
            log("STATISTIK BERBEDA: " + b)
        raise RuntimeError(f"[{cfg['key']}] Statistik grid berbeda dengan statistik_grid.csv lama — BERHENTI.")
    log(f"Statistik grid identik dengan {os.path.relpath(old_csv, ROOT)} ({len(rows)} grid x {len(STAT_KEYS)} kolom).")


# ============================================================================ simbologi
def style_pseudocolor(layer, vmin, vmax, ramp_name):
    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    ramp.invert()  # biru = rendah, merah = tinggi
    sh = QgsColorRampShader(vmin, vmax, ramp, QgsColorRampShader.Type.Interpolated,
                            Qgis.ShaderClassificationMethod.Continuous)
    sh.classifyColorRamp()
    sh.setClip(False)
    rs = QgsRasterShader()
    rs.setRasterShaderFunction(sh)
    ren = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, rs)
    ren.setClassificationMin(vmin)
    ren.setClassificationMax(vmax)
    layer.setRenderer(ren)
    layer.resampleFilter().setZoomedInResampler(QgsBilinearRasterResampler())
    layer.resampleFilter().setZoomedOutResampler(QgsBilinearRasterResampler())
    # early resampling (di tingkat provider)
    layer.setResamplingStage(Qgis.RasterResamplingStage.Provider)
    layer.dataProvider().setZoomedInResamplingMethod(QgsRasterDataProvider.ResamplingMethod.Bilinear)
    layer.dataProvider().setZoomedOutResamplingMethod(QgsRasterDataProvider.ResamplingMethod.Bilinear)
    layer.setBlendMode(QPainter.CompositionMode.CompositionMode_Multiply)
    return ramp


def make_xyz(url, name, log, grayscale_opacity=None):
    try:
        tile = url.replace("{x}", "0").replace("{y}", "0").replace("{z}", "0")
        req = urllib.request.Request(tile, headers={"User-Agent": "QGIS/4.2.3 praktikum-EGBM"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"CATATAN: basemap {name} gagal dimuat ({e}) — peta dibuat tanpa basemap ini.")
        return None
    uri = "type=xyz&url=" + url.replace("=", "%3D").replace("&", "%26") + "&zmax=19&zmin=0"
    lyr = QgsRasterLayer(uri, name, "wms")
    if not lyr.isValid():
        log(f"CATATAN: layer XYZ {name} tidak valid — peta dibuat tanpa basemap ini.")
        return None
    if grayscale_opacity is not None:
        lyr.hueSaturationFilter().setGrayscaleMode(QgsHueSaturationFilter.GrayscaleMode.GrayscaleAverage)
        lyr.renderer().setOpacity(grayscale_opacity)
    return lyr


CONTOUR_RULES = [  # label, filter, lebar (mm), gaya
    ("Kontur 0 nT", '"ZLEVEL" = 0', 0.6, "solid"),
    ("Kontur positif", '"ZLEVEL" > 0', 0.26, "solid"),
    ("Kontur negatif", '"ZLEVEL" < 0', 0.26, "dash"),
]


def contour_symbol(width, pen):
    return QgsLineSymbol.createSimple({"line_color": "0,0,0,255", "line_width": str(width),
                                       "line_width_unit": "MM", "line_style": pen})


def style_contours(layer, font_pt, min_length):
    root = QgsRuleBasedRenderer.Rule(None)
    for label, filt, width, pen in CONTOUR_RULES:
        root.appendChild(QgsRuleBasedRenderer.Rule(contour_symbol(width, pen), 0, 0, filt, label))
    layer.setRenderer(QgsRuleBasedRenderer(root))
    # label mask 1,5 mm: menyembunyikan garis kontur di bawah label
    masked = []
    for rule in layer.renderer().rootRule().children():
        for sl in rule.symbol().symbolLayers():
            masked.append(QgsSymbolLayerReference(layer.id(), sl.id()))
    tf = text_format(font_pt, color="#202020")
    mask = QgsTextMaskSettings()
    mask.setEnabled(True)
    mask.setSize(1.5)
    mask.setSizeUnit(Qgis.RenderUnit.Millimeters)
    mask.setMaskedSymbolLayers(masked)
    tf.setMask(mask)
    pal = QgsPalLayerSettings()
    pal.isExpression = True
    pal.fieldName = f'if($length > {min_length}, to_int("ZLEVEL"), NULL)'
    pal.placement = Qgis.LabelPlacement.Curved
    pal.lineSettings().setPlacementFlags(Qgis.LabelLinePlacementFlag.OnLine)
    pal.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    pal.setFormat(tf)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


def make_blocking(layer):
    """Fitur layer menjadi obstacle label (tanpa menggambar label sendiri)."""
    pal = QgsPalLayerSettings()
    pal.fieldName = "''"
    pal.isExpression = True
    pal.drawLabels = False
    pal.obstacleSettings().setIsObstacle(True)
    pal.obstacleSettings().setFactor(2.0)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


def day_symbol(i):
    return QgsMarkerSymbol.createSimple({"name": "circle", "color": DAY_COLORS[i % len(DAY_COLORS)],
                                         "outline_color": "white", "outline_width": "0.3", "size": "2.4"})


def point_symbol():
    return QgsMarkerSymbol.createSimple({"name": "circle", "color": "black", "outline_style": "no", "size": "1.5"})


def base_symbol():
    return QgsMarkerSymbol.createSimple({"name": "star", "color": "#ffd700", "outline_color": "black",
                                         "outline_width": "0.35", "size": "5"})


def style_points_by_day(layer, day_field, name_field, font_pt):
    days = sorted({f[day_field] for f in layer.getFeatures()},
                  key=lambda d: int("".join(ch for ch in d if ch.isdigit()) or 0))
    counts = {d: 0 for d in days}
    for f in layer.getFeatures():
        counts[f[day_field]] += 1
    cats, legend = [], []
    for i, d in enumerate(days):
        num = "".join(ch for ch in d if ch.isdigit())
        lbl = f"Hari ke-{num} ({counts[d]} titik)"
        cats.append(QgsRendererCategory(d, day_symbol(i), lbl))
        legend.append(("marker", day_symbol(i), lbl))
    layer.setRenderer(QgsCategorizedSymbolRenderer(day_field, cats))
    pal = QgsPalLayerSettings()
    pal.fieldName = name_field
    pal.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    pal.dist = 0.6
    pal.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.PreventOverlap)
    pal.setFormat(text_format(font_pt, color="black", buffer=(0.8, "white")))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    return legend


def style_base_labeled(layer, font_pt):
    layer.setRenderer(QgsSingleSymbolRenderer(base_symbol()))
    pal = QgsPalLayerSettings()
    pal.fieldName = "NAMA"
    pal.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    pal.dist = 1.5
    pal.setFormat(text_format(font_pt, bold=True, color="#ffd700", buffer=(0.8, "black")))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)

# ============================================================================ elemen layout
class Page:
    def __init__(self, layout, fonts):
        self.layout = layout
        self.fonts = fonts

    def label(self, text, x, y, w, h, size, bold=False, halign=Qt.AlignmentFlag.AlignLeft,
              valign=Qt.AlignmentFlag.AlignTop, what="teks", color="black"):
        self.fonts.add(size, what)
        lbl = QgsLayoutItemLabel(self.layout)
        lbl.setText(text)
        lbl.setTextFormat(text_format(size, bold, color))
        lbl.setHAlign(halign)
        lbl.setVAlign(valign)
        lbl.setMarginX(0)
        lbl.setMarginY(0)
        self.layout.addLayoutItem(lbl)
        lbl.attemptMove(QgsLayoutPoint(x, y, MM))
        lbl.attemptResize(QgsLayoutSize(w, h, MM))
        return lbl

    def text_block(self, text, x, y, w, size, bold=False, what="teks"):
        """Teks dibungkus manual (tinggi pasti). Mengembalikan tinggi (mm)."""
        lines = wrap(text, w, size, bold)
        h = len(lines) * line_h(size, bold)
        self.label("\n".join(lines), x, y, w + 1.0, h + 0.5, size, bold, what=what)
        return h

    def line(self, x1, y1, x2, y2, symbol):
        it = QgsLayoutItemPolyline(QPolygonF([QPointF(x1, y1), QPointF(x2, y2)]), self.layout)
        it.setSymbol(symbol)
        self.layout.addLayoutItem(it)
        return it

    def marker(self, cx, cy, symbol):
        it = QgsLayoutItemMarker(self.layout)
        it.setSymbol(symbol)
        self.layout.addLayoutItem(it)
        it.setReferencePoint(QgsLayoutItem.ReferencePoint.Middle)
        it.attemptMove(QgsLayoutPoint(cx, cy, MM))
        return it

    def rect(self, x, y, w, h, symbol):
        it = QgsLayoutItemShape(self.layout)
        it.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
        it.setSymbol(symbol)
        self.layout.addLayoutItem(it)
        it.attemptMove(QgsLayoutPoint(x, y, MM))
        it.attemptResize(QgsLayoutSize(w, h, MM))
        return it

    def box(self, x, y, w, h, width=0.3):
        return self.rect(x, y, w, h, QgsFillSymbol.createSimple(
            {"color": "255,255,255,0", "outline_color": "black", "outline_width": str(width)}))


def text_lines_h(texts, width, size, bold=False):
    return sum(len(wrap(t, width, size, bold)) for t in texts) * line_h(size, bold)


def colorbar_v(pg, ramp, ticks, title, x, y, F, bar_h):
    """Colour bar tegak bergradasi + tick antara. Tinggi blok = 2*lh + 1,2 + bar_h."""
    lh = line_h(F)
    vmin, vmax = ticks[0], ticks[-1]
    g = QgsGradientFillSymbolLayer()
    g.setGradientColorType(Qgis.GradientColorSource.ColorRamp)
    g.setColorRamp(ramp.clone())
    g.setGradientType(Qgis.GradientType.Linear)
    g.setCoordinateMode(Qgis.SymbolCoordinateReference.Feature)
    g.setReferencePoint1(QPointF(0.5, 1.0))
    g.setReferencePoint2(QPointF(0.5, 0.0))
    outline = QgsSimpleFillSymbolLayer.create({"style": "no", "outline_color": "black", "outline_width": "0.2"})
    tick_sym = QgsLineSymbol.createSimple({"line_color": "black", "line_width": "0.2"})
    pg.label(title, x, y, text_w(title, F, True) + 1.0, lh + 0.5, F, bold=True, what="judul colour bar")
    y0 = y + lh + 1.2 + lh / 2
    bar_w = 5.0
    pg.rect(x, y0, bar_w, bar_h, QgsFillSymbol([g, outline]))
    for t in ticks:
        ty = y0 + bar_h * (vmax - t) / (vmax - vmin)
        pg.line(x + bar_w, ty, x + bar_w + 1.5, ty, tick_sym.clone())
        pg.label(fmt_tick(t), x + bar_w + 2.2, ty - lh / 2, 20, lh + 0.3, F, what="tick colour bar",
                 valign=Qt.AlignmentFlag.AlignVCenter)
    return bar_w + 2.2 + max(text_w(fmt_tick(t), F) for t in ticks)


def colorbar_v_height(F, bar_h):
    return 2 * line_h(F) + 1.2 + bar_h


def legend_rows_h(n, F):
    return n * (max(line_h(F), 5.0) + 1.2)


def legend_items(pg, items, x, y, F):
    lh = line_h(F)
    row = max(lh, 5.0) + 1.2
    sw = 7.0
    for i, (kind, sym, label) in enumerate(items):
        cy = y + i * row + row / 2
        if kind == "line":
            pg.line(x, cy, x + sw, cy, sym)
        else:
            pg.marker(x + sw / 2, cy, sym)
        pg.label(label, x + sw + 2, cy - lh / 2, text_w(label, F) + 2, lh + 0.3, F, what="legenda",
                 valign=Qt.AlignmentFlag.AlignVCenter)
    return len(items) * row


def north_scale_height(F):
    lh = line_h(F)
    return max(lh + 0.5 + 12, (2.0 + lh + 2.0) + 1.0 + lh)


def north_scale_stacked_height(F):
    lh = line_h(F)
    return (lh + 0.5 + 10.0 + 1.5) + (2.0 + lh + 2.0) + 1.0 + lh


def north_and_scale(pg, m, scale, x, y, w, F):
    """Kolom sempit: panah utara di atas, skala batang & skala numerik di bawahnya."""
    lh = line_h(F)
    pg.label("U", x + w / 2 - 5, y, 10, lh + 0.3, F, bold=True, halign=Qt.AlignmentFlag.AlignHCenter,
             what="panah utara")
    na = QgsLayoutItemPicture(pg.layout)
    na.setPicturePath(os.path.join(QgsApplication.pkgDataPath(), "svg", "arrows", "NorthArrow_01.svg"),
                      Qgis.PictureFormat.SVG)
    na.setSvgFillColor(QColor("black"))
    na.setSvgStrokeColor(QColor("black"))
    pg.layout.addLayoutItem(na)
    na.attemptMove(QgsLayoutPoint(x + w / 2 - 3.5, y + lh + 0.5, MM))
    na.attemptResize(QgsLayoutSize(7, 10, MM))
    na.setLinkedMap(m)
    sx, avail = x, w
    y = y + lh + 0.5 + 10.0 + 1.5
    best = None
    for n in (2, 1):
        for seg in (100, 200, 250, 500, 1000, 2000):
            seg_mm = seg * 1000.0 / scale
            labels = [fmt_id(seg * k) for k in range(n)] + [f"{fmt_id(seg * n)} m"]
            ws = [text_w(t, F) for t in labels]
            total = n * seg_mm + ws[-1] / 2 + ws[0] / 2
            fits = total <= avail and all(seg_mm >= (ws[k] + ws[k + 1]) / 2 + 1.5 for k in range(n))
            if fits and (best is None or n * seg > best[0] * best[1]):
                best = (n, seg)
        if best:
            break
    n, seg = best if best else (1, 500)
    sb = QgsLayoutItemScaleBar(pg.layout)
    sb.setStyle("Single Box")
    pg.layout.addLayoutItem(sb)
    sb.setLinkedMap(m)
    sb.setUnits(Qgis.DistanceUnit.Meters)
    sb.setUnitLabel("m")
    sb.setMapUnitsPerScaleBarUnit(1.0)
    sb.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.Fixed)
    sb.setNumberOfSegments(n)
    sb.setNumberOfSegmentsLeft(0)
    sb.setUnitsPerSegment(seg)
    sb.setHeight(2.0)
    sb.setTextFormat(text_format(F))
    pg.fonts.add(F, "skala batang")
    sb.setBoxContentSpace(0)
    nf = QgsBasicNumericFormat()
    nf.setShowThousandsSeparator(True)
    nf.setThousandsSeparator(".")
    nf.setDecimalSeparator(",")
    nf.setNumberDecimalPlaces(0)
    sb.setNumericFormat(nf)
    sb.attemptMove(QgsLayoutPoint(sx, y + 0.5, MM))
    sb.refreshItemSize()
    sb_h = 2.0 + lh + 2.0
    pg.label(f"1 : {fmt_id(scale)}", sx, y + sb_h + 1.0, avail, lh + 0.3, F, what="skala numerik",
             halign=Qt.AlignmentFlag.AlignHCenter)


def inset_map(pg, project, osm, main_map, x, y, w, h, F):
    """Inset Jawa Timur (OSM) + grid derajat 1° (label kiri & bawah) + kotak merah area penelitian."""
    lh = line_h(F)
    mx, mw = x + lh + 1.2, w - lh - 1.2
    mh = h - lh - 1.2
    if osm is None:
        pg.box(mx, y, mw, mh)
        return
    im = QgsLayoutItemMap(pg.layout)
    im.setCrs(QgsCoordinateReferenceSystem(EPSG))
    pg.layout.addLayoutItem(im)
    im.attemptMove(QgsLayoutPoint(mx, y, MM))
    im.attemptResize(QgsLayoutSize(mw, mh, MM))
    im.setLayers([osm])
    im.setKeepLayerSet(True)
    tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem("EPSG:4326"), QgsCoordinateReferenceSystem(EPSG),
                                project)
    im.zoomToExtent(tr.transformBoundingBox(QgsRectangle(*JATIM_LONLAT)))
    im.setFrameEnabled(True)
    im.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, MM))
    g = QgsLayoutItemMapGrid("Grid derajat", im)
    im.grids().addGrid(g)
    g.setCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    g.setIntervalX(2.0)
    g.setIntervalY(2.0)
    g.setStyle(QgsLayoutItemMapGrid.GridStyle.Solid)
    g.setLineSymbol(QgsLineSymbol.createSimple({"line_color": "90,90,90,140", "line_width": "0.1"}))
    g.setAnnotationEnabled(True)
    g.setAnnotationFormat(QgsLayoutItemMapGrid.AnnotationFormat.CustomFormat)
    g.setAnnotationExpression("to_string(abs(@grid_number)) || '°' || "
                              "if(@grid_axis = 'x', 'BT', 'LS')")
    g.setAnnotationTextFormat(text_format(F))
    pg.fonts.add(F, "label inset")
    g.setAnnotationFrameDistance(0.6)
    S = QgsLayoutItemMapGrid.BorderSide
    D = QgsLayoutItemMapGrid.DisplayMode
    g.setAnnotationPosition(QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame, S.Left)
    g.setAnnotationPosition(QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame, S.Bottom)
    g.setAnnotationDirection(QgsLayoutItemMapGrid.AnnotationDirection.Vertical, S.Left)
    g.setAnnotationDisplay(D.LatitudeOnly, S.Left)
    g.setAnnotationDisplay(D.LongitudeOnly, S.Bottom)
    g.setAnnotationDisplay(D.HideAll, S.Right)
    g.setAnnotationDisplay(D.HideAll, S.Top)
    ov = QgsLayoutItemMapOverview("Area penelitian", im)
    im.overviews().addOverview(ov)
    ov.setLinkedMap(main_map)
    ov.setFrameSymbol(QgsFillSymbol.createSimple({"color": "255,0,0,90", "outline_color": "255,0,0,255",
                                                  "outline_width": "0.8"}))


def map_frame(pg, layers, extent_data, x, y, w, h, F):
    """Peta utama: skala bulat; grid garis abu-abu tipis 500 m; label koordinat di 4 sisi; judul sumbu."""
    need = max((extent_data.width() + 2 * DATA_MARGIN_M) / (w / 1000.0),
               (extent_data.height() + 2 * DATA_MARGIN_M) / (h / 1000.0))
    scale = nice_scale(need)
    m = QgsLayoutItemMap(pg.layout)
    m.setCrs(QgsCoordinateReferenceSystem(EPSG))
    pg.layout.addLayoutItem(m)
    m.attemptMove(QgsLayoutPoint(x, y, MM))
    m.attemptResize(QgsLayoutSize(w, h, MM))
    m.setLayers(layers)
    m.setKeepLayerSet(True)
    m.zoomToExtent(extent_data)
    m.setScale(scale)
    m.setFrameEnabled(True)
    m.setFrameStrokeWidth(QgsLayoutMeasurement(0.35, MM))
    g = QgsLayoutItemMapGrid("Grid UTM", m)
    m.grids().addGrid(g)
    g.setIntervalX(GRID_INTERVAL)
    g.setIntervalY(GRID_INTERVAL)
    g.setStyle(QgsLayoutItemMapGrid.GridStyle.Solid)
    g.setLineSymbol(QgsLineSymbol.createSimple({"line_color": "110,110,110,150", "line_width": "0.1"}))
    g.setFrameStyle(QgsLayoutItemMapGrid.FrameStyle.ExteriorTicks)
    g.setFrameWidth(1.2)
    g.setFramePenSize(0.25)
    g.setAnnotationEnabled(True)
    g.setAnnotationFormat(QgsLayoutItemMapGrid.AnnotationFormat.Decimal)
    g.setAnnotationPrecision(0)
    g.setAnnotationTextFormat(text_format(F))
    pg.fonts.add(F, "label koordinat")
    g.setAnnotationFrameDistance(0.8)
    S = QgsLayoutItemMapGrid.BorderSide
    D = QgsLayoutItemMapGrid.DisplayMode
    A = QgsLayoutItemMapGrid.AnnotationDirection
    for side in (S.Left, S.Right, S.Top, S.Bottom):
        g.setAnnotationPosition(QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame, side)
    g.setAnnotationDirection(A.Vertical, S.Left)       # label sumbu Y tegak
    g.setAnnotationDirection(A.Vertical, S.Right)
    g.setAnnotationDirection(A.Horizontal, S.Top)
    g.setAnnotationDirection(A.Horizontal, S.Bottom)
    g.setAnnotationDisplay(D.LatitudeOnly, S.Left)
    g.setAnnotationDisplay(D.LatitudeOnly, S.Right)
    g.setAnnotationDisplay(D.LongitudeOnly, S.Top)
    g.setAnnotationDisplay(D.LongitudeOnly, S.Bottom)
    m.updateBoundingRect()
    lh = line_h(F)
    ann_off = 1.2 + 0.8 + lh + 1.0
    pg.label("Easting (m)", x, y + h + ann_off, w, lh + 0.3, F, halign=Qt.AlignmentFlag.AlignHCenter,
             what="judul sumbu")
    ny = pg.label("Northing (m)", 0, 0, h, lh + 0.3, F, halign=Qt.AlignmentFlag.AlignHCenter, what="judul sumbu")
    cx = x - ann_off - lh / 2
    ny.attemptMove(QgsLayoutPoint(cx - h / 2, y + h / 2 - (lh + 0.3) / 2, MM))
    ny.setItemRotation(-90)
    spacing = GRID_INTERVAL * 1000.0 / scale
    if text_w("9999999", F) + 1.0 > spacing:
        print(f"PERINGATAN: label koordinat ({text_w('9999999', F):.1f} mm) > jarak grid ({spacing:.1f} mm)")
    return m, scale


def make_layout(project, spec, cfg, F, FT, FS, fonts, osm):
    """Layout v3 (gaya referensi): A4 landscape, bingkai ganda, kotak judul di atas peta,
    panel kanan berkotak: institusi & pembuat | utara & skala | legenda | lokasi | keterangan | sumber data."""
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(spec["lname"])
    W, H = 297.0, 210.0
    layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Orientation.Landscape)
    pg = Page(layout, fonts)
    lh = line_h(F)
    lh_t, lh_s = line_h(FT, True), line_h(FS)
    # bingkai ganda
    pg.box(4.0, 4.0, W - 8.0, H - 8.0, 0.6)
    X0, Y0, X1, Y1 = 5.5, 5.5, W - 5.5, H - 5.5
    pg.box(X0, Y0, X1 - X0, Y1 - Y0, 0.25)

    PW = PANEL_W
    PX = X1 - PW
    pad = 1.6
    cw = PW - 2 * pad                     # lebar isi panel

    # ---------------- kotak judul di atas peta
    tw = PX - X0 - 4.0
    title_lines = wrap(spec["title"], tw, FT, True)
    tb_h = 2.0 + len(title_lines) * lh_t + lh_s + 2.0
    pg.box(X0, Y0, PX - X0, tb_h)
    pg.label("\n".join(title_lines), X0 + 2, Y0 + 2.0, tw, len(title_lines) * lh_t + 0.5, FT, True,
             Qt.AlignmentFlag.AlignHCenter, what="judul")
    pg.label(spec["subtitle"], X0 + 2, Y0 + 2.0 + len(title_lines) * lh_t, tw, lh_s + 0.3, FS,
             halign=Qt.AlignmentFlag.AlignHCenter, what="sub-judul")

    # ---------------- peta utama
    side = 1.2 + 0.8 + lh + 1.0          # tick + jarak + label koordinat + celah
    mx = X0 + 1.0 + lh + side             # judul sumbu Y + label kiri
    mw = (PX - 1.5) - side - mx
    my = Y0 + tb_h + side
    mh = (Y1 - 1.0) - lh - side - my      # label bawah + judul sumbu X
    m, scale = map_frame(pg, spec["map_layers"], spec["extent"], mx, my, mw, mh, F)

    # ---------------- panel kanan: ukur tinggi isi tiap kotak
    hdr = lh + 1.0
    logo_sz = 16.0
    inst_lines = ["Departemen Teknik Geofisika", "Institut Teknologi Sepuluh Nopember",
                  "Praktikum Eksplorasi Gaya Berat Magnetik (EGBM)"]
    inst_txt_w = cw - logo_sz - 2.0
    inst_bold = [True, True, False]
    inst_txt_h = sum(text_lines_h([t], inst_txt_w, F, b) for t, b in zip(inst_lines, inst_bold))
    inst_h = max(logo_sz, inst_txt_h)
    maker = f"Dibuat oleh: {NAMA}"
    box1_h = inst_h + 1.5 + text_lines_h([maker], cw, F)
    ns_w = 27.0                           # kolom panah utara + skala di samping inset
    n_items = len(spec["legend"])
    if spec["colorbar"]:
        ramp, ticks, cb_title = spec["colorbar"]
        cb_bar = max(26.0, (len(ticks) - 1) * (lh + 0.6))
        cb_w = 5.0 + 2.2 + max(text_w(fmt_tick(t), F) for t in ticks)
        it_w = max(text_w(l, F) for _, _, l in spec["legend"]) + 9.0
        side_by_side = cb_w + 4.0 + it_w <= cw
        if side_by_side:
            leg_body = max(colorbar_v_height(F, cb_bar), lh + 1.2 + legend_rows_h(n_items, F))
        else:
            leg_body = colorbar_v_height(F, cb_bar) + 1.5 + legend_rows_h(n_items, F)
    else:
        leg_body = legend_rows_h(n_items, F)
    box3_h = hdr + leg_body
    inset_w = cw - ns_w - 2.0
    inset_h = max(north_scale_stacked_height(F), inset_w / 1.6)
    box4_h = hdr + inset_h
    box5_h = hdr + text_lines_h(spec["info"], cw, F)
    box6_h = hdr + text_lines_h(spec["sources"], cw, F)
    heights = [box1_h, box3_h, box4_h, box5_h, box6_h]
    avail = (Y1 - Y0) - len(heights) * 2 * pad
    extra = avail - sum(heights)
    if extra < 0:
        # kurangi tinggi inset lebih dulu (tidak kurang dari kolom utara+skala), lalu laporkan
        cut = min(-extra, inset_h - north_scale_stacked_height(F))
        inset_h -= cut
        heights[2] -= cut
        extra += cut
    if extra < -0.5:
        print(f"PERINGATAN: panel '{spec['lname']}' kelebihan {-extra:.1f} mm")
    add = max(extra, 0.0) / len(heights)

    y = Y0
    boxes = []
    for h in heights:
        bh = h + 2 * pad + add
        boxes.append((y, bh))
        pg.box(PX, y, PW, bh)
        y += bh

    def top(i):
        return boxes[i][0] + pad + add / 2

    cx = PX + pad
    # 1. institusi + pembuat
    y1 = top(0)
    logo = QgsLayoutItemPicture(layout)
    logo.setPicturePath(LOGO_ITS, Qgis.PictureFormat.Raster)
    logo.setResizeMode(QgsLayoutItemPicture.ResizeMode.Zoom)
    layout.addLayoutItem(logo)
    logo.attemptMove(QgsLayoutPoint(cx, y1 + (inst_h - logo_sz) / 2, MM))
    logo.attemptResize(QgsLayoutSize(logo_sz, logo_sz, MM))
    ty = y1 + (inst_h - inst_txt_h) / 2
    for t, b in zip(inst_lines, inst_bold):
        ty += pg.text_block(t, cx + logo_sz + 2.0, ty, inst_txt_w, F, bold=b, what="institusi")
    pg.text_block(maker, cx, y1 + inst_h + 1.5, cw, F, what="pembuat")
    # 2. legenda
    y3 = top(1)
    pg.label("LEGENDA", cx, y3, cw, lh + 0.3, F, bold=True, what="judul legenda")
    y3 += hdr
    if spec["colorbar"]:
        if side_by_side:
            colorbar_v(pg, ramp, ticks, cb_title, cx, y3, F, cb_bar)
            legend_items(pg, spec["legend"], cx + cw - it_w, y3 + lh + 1.2, F)
        else:
            colorbar_v(pg, ramp, ticks, cb_title, cx, y3, F, cb_bar)
            legend_items(pg, spec["legend"], cx, y3 + colorbar_v_height(F, cb_bar) + 1.5, F)
    else:
        legend_items(pg, spec["legend"], cx, y3, F)
    # 3. lokasi penelitian (inset) + panah utara & skala di sampingnya
    y4 = top(2)
    pg.label("LOKASI PENELITIAN", cx, y4, inset_w, lh + 0.3, F, bold=True, what="judul inset")
    inset_map(pg, project, osm, m, cx, y4 + hdr, inset_w, inset_h, F)
    north_and_scale(pg, m, scale, cx + inset_w + 2.0, y4 + (hdr + inset_h - north_scale_stacked_height(F)) / 2,
                    ns_w, F)
    # 4. keterangan
    y5 = top(3)
    pg.label("KETERANGAN", cx, y5, cw, lh + 0.3, F, bold=True, what="judul keterangan")
    y5 += hdr
    for t in spec["info"]:
        y5 += pg.text_block(t, cx, y5, cw, F, what="keterangan")
    # 5. sumber data
    y6 = top(4)
    pg.label("SUMBER DATA", cx, y6, cw, lh + 0.3, F, bold=True, what="judul sumber")
    y6 += hdr
    for t in spec["sources"]:
        y6 += pg.text_block(t, cx, y6, cw, F, what="sumber")

    project.layoutManager().addLayout(layout)
    geo = dict(map_w=mw, map_h=mh, frac=mw / (X1 - X0), panel_extra=extra)
    return layout, scale, geo


def export_png(layout, path):
    exp = QgsLayoutExporter(layout)
    st = QgsLayoutExporter.ImageExportSettings()
    st.dpi = 300
    res = exp.exportToImage(path, st)
    if res != QgsLayoutExporter.ExportResult.Success:
        raise RuntimeError(f"Ekspor gagal ({res}): {path}")


# ============================================================================ TMI raw
def check_raw_inputs(cfg, log):
    """(a) geometri grid raw = grid MC terkoreksi; (b) statistik raw ±0,05 nT; (c) kontur Surfer raw."""
    rc = cfg["raw"]
    arr, valid, gt, _, _ = read_grid(rc["grid"])
    _, _, gt_mc, _, _ = read_grid(cfg["grid_mc"])
    ny, nx = arr.shape
    ox, oy = gt[0] + gt[1] / 2, gt[3] + gt[5] * ny - gt[5] / 2
    e = rc["geom"]
    ok_a = (nx, ny) == e[:2] and abs(gt[1] - e[2]) < 1e-9 and abs(-gt[5] - e[2]) < 1e-9 \
        and abs(ox - e[3]) < 1e-6 and abs(oy - e[4]) < 1e-6 and tuple(gt) == tuple(gt_mc)
    vals = arr[valid]
    s = (vals.min(), vals.max(), vals.mean(), int(valid.sum()))
    t = rc["stats"]
    ok_b = all(abs(s[i] - t[i]) <= 0.05 for i in range(3)) and s[3] == t[3]
    comps = [os.path.splitext(rc["kontur"])[0] + x for x in (".shp", ".shx", ".dbf")]
    if not all(os.path.exists(c) for c in comps):
        raise RuntimeError(f"Shapefile kontur raw tidak lengkap: {rc['kontur']}")
    ds = gdal.OpenEx(rc["kontur"], gdal.OF_VECTOR | gdal.OF_READONLY)
    z = np.array(sorted({f.GetField("ZLEVEL") for f in ds.GetLayer(0)}))
    ds = None
    steps = np.unique(np.round(np.diff(z), 6))
    ok_c = z.min() >= s[0] and z.max() <= s[1] and len(steps) == 1 \
        and abs(steps[0] - cfg["contour_interval"]) < 1e-6
    log(f"Cek raw: (a) {'OK' if ok_a else 'GAGAL'} geometri {nx}x{ny}, {gt[1]:g} m | (b) {'OK' if ok_b else 'GAGAL'} "
        f"min {s[0]:.2f} max {s[1]:.2f} mean {s[2]:.2f} {s[3]} sel | (c) {'OK' if ok_c else 'GAGAL'} ZLEVEL "
        f"{z.min():g}..{z.max():g}")
    if not (ok_a and ok_b and ok_c):
        raise RuntimeError(f"[{cfg['key']}] Pengecekan input TMI raw GAGAL — BERHENTI.")
    return arr, valid, gt


def raw_stats(cfg, arr, valid, gt, out_csv, log):
    rc = cfg["raw"]
    with open(rc["csv"], encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != cfg["expected_n"]:
        raise RuntimeError(f"[{cfg['key']}] Jumlah titik raw {len(rows)} != {cfg['expected_n']}. BERHENTI.")
    res = []
    for r in rows:
        g = bilinear_sample(arr, valid, gt, float(r[cfg["x_field"]]), float(r[cfg["y_field"]]))
        if g is not None:
            res.append(float(r[rc["tmi_field"]]) - g)
    res = np.array(res)
    vals = arr[valid]
    row = dict(dataset=cfg["key"], grid="TMI raw (Minimum Curvature)", berkas=os.path.basename(rc["grid"]),
               min_nT=f"{vals.min():.3f}", max_nT=f"{vals.max():.3f}", mean_nT=f"{vals.mean():.3f}",
               std_nT=f"{vals.std():.3f}", n_sel_valid=str(int(valid.sum())),
               rms_residual_nT=f"{math.sqrt(np.mean(res ** 2)):.3f}", n_titik_residual=str(len(res)),
               n_titik_luar_grid=str(len(rows) - len(res)), rentang_warna_nT=f"±{cfg['R']}")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)
    log(f"Statistik raw: min {row['min_nT']}, max {row['max_nT']}, mean {row['mean_nT']}, std {row['std_nT']}, "
        f"{row['n_sel_valid']} sel; RMS residual {row['rms_residual_nT']} nT ({row['n_titik_residual']} titik)")
    return row


# ============================================================================ utama
def build_project(cfg, render_keys, logbuf):
    ds_dir = os.path.join(ROOT, "QGIS", cfg["key"])
    out_dir = os.path.join(ds_dir, OUT_DIR_NAME)
    os.makedirs(out_dir, exist_ok=True)
    pfx = cfg["prefix"]

    def log(msg):
        print(f"[{pfx}] {msg}")
        logbuf.append(msg)

    page_w = 297.0
    F = math.ceil(MIN_PT_AT_WORD * page_w / WORD_WIDTH_MM * 10 - 1e-9) / 10.0    # dibulatkan ke atas 0,1 pt
    FT = math.ceil(1.6 * F * 10 - 1e-9) / 10.0
    FS = F + 1.0
    fonts = FontLog()
    log(f"Mulai {datetime.datetime.now():%Y-%m-%d %H:%M:%S} — {cfg['key']} (A4 landscape, layout v3)")
    log(f"Font: teks {F} pt, sub-judul {FS} pt, judul {FT} pt; batas minimum {MIN_PT_AT_WORD:g} x "
        f"{page_w:.0f}/160 = {MIN_PT_AT_WORD * page_w / WORD_WIDTH_MM:.2f} pt")

    check_surfer_contours(cfg, log)
    raw_arr, raw_valid, raw_gt = check_raw_inputs(cfg, log)

    crs = QgsCoordinateReferenceSystem(EPSG)
    project = QgsProject()
    project.setCrs(crs)
    project.setTitle(cfg["project_name"].replace("_", " "))

    gpkg = os.path.join(out_dir, "titik_ukur.gpkg")
    build_point_gpkg(cfg, gpkg, log)
    pts_day = QgsVectorLayer(f"{gpkg}|layername=titik_ukur", "Titik ukur (per hari)", "ogr")
    pts_blk = QgsVectorLayer(f"{gpkg}|layername=titik_ukur", "Titik ukur", "ogr")
    base_lbl = QgsVectorLayer(f"{gpkg}|layername=base_station", "Base station (berlabel)", "ogr")
    base_obs = QgsVectorLayer(f"{gpkg}|layername=base_station", "Base station", "ogr")
    for l in (pts_day, pts_blk, base_lbl, base_obs):
        if not l.isValid():
            raise RuntimeError(f"Layer {l.name()} tidak valid")
    if pts_day.featureCount() != cfg["expected_n"]:
        raise RuntimeError(f"Jumlah fitur {pts_day.featureCount()} != {cfg['expected_n']}. BERHENTI.")
    log(f"Titik ukur: {pts_day.featureCount()} fitur; base: {base_obs.featureCount()} fitur")

    grids = {}
    for key, path, nm in [("krig", cfg["grid_krig"], "Anomali TMI – Kriging"),
                          ("mc", cfg["grid_mc"], "Anomali TMI – Minimum Curvature"),
                          ("raw", cfg["raw"]["grid"], "TMI raw – Minimum Curvature")]:
        rl = QgsRasterLayer(path, nm, "gdal")
        if not rl.isValid():
            raise RuntimeError(f"Grid gagal terbaca: {path}. BERHENTI.")
        rl.setCrs(crs)
        grids[key] = rl

    diff_tif = os.path.join(out_dir, "Selisih_MC-Kriging.tif")
    raster_difference(grids["mc"], grids["krig"], diff_tif, project)
    diff = QgsRasterLayer(diff_tif, "Selisih MC − Kriging", "gdal")
    diff.setCrs(crs)

    pts = [(f[cfg["x_field"]], f[cfg["y_field"]], f[cfg["tmi_field"]]) for f in pts_day.getFeatures()]
    stats_rows = compute_stats(cfg, diff_tif, pts)
    compare_with_old_stats(cfg, stats_rows, log)
    with open(os.path.join(out_dir, "statistik_grid.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(stats_rows[0].keys()))
        w.writeheader()
        w.writerows(stats_rows)
    raw_stats(cfg, raw_arr, raw_valid, raw_gt, os.path.join(out_dir, "statistik_grid_raw.csv"), log)

    con_k = QgsVectorLayer(cfg["kontur_krig"], "Kontur TMI – Kriging (Surfer 23)", "ogr")
    con_m = QgsVectorLayer(cfg["kontur_mc"], "Kontur TMI – Minimum Curvature (Surfer 23)", "ogr")
    con_r = QgsVectorLayer(cfg["raw"]["kontur"], "Kontur TMI raw – MC (Surfer 23)", "ogr")
    for l in (con_k, con_m, con_r):
        if not l.isValid():
            raise RuntimeError(f"Shapefile kontur tidak valid: {l.source()}")
        l.setCrs(crs)   # shapefile tanpa .prj: CRS hanya di-set di project
    dgpkg = os.path.join(out_dir, "kontur_selisih.gpkg")
    make_diff_contours(diff_tif, dgpkg, cfg["diff_interval"], log)
    con_d = QgsVectorLayer(f"{dgpkg}|layername=kontur_selisih", "Kontur selisih (nT)", "ogr")
    n_lines = {"02": con_k.featureCount(), "03": con_m.featureCount(), "04": con_d.featureCount(),
               "05": con_r.featureCount()}

    satellite = make_xyz(URL_SAT, "Google Satellite", log)
    terrain = make_xyz(URL_TERRAIN, "Google Terrain (grayscale)", log, grayscale_opacity=0.7)
    osm = make_xyz(URL_OSM, "OpenStreetMap (inset)", log)

    ramp_tmi = style_pseudocolor(grids["krig"], -cfg["R"], cfg["R"], "RdBu")
    style_pseudocolor(grids["mc"], -cfg["R"], cfg["R"], "RdBu")
    style_pseudocolor(grids["raw"], -cfg["R"], cfg["R"], "RdBu")
    ramp_diff = style_pseudocolor(diff, -cfg["S"], cfg["S"], "PuOr")
    F_lbl = F
    thr = cfg["label_min_length"]
    style_contours(con_k, F_lbl, thr["02"])
    style_contours(con_m, F_lbl, thr["03"])
    style_contours(con_d, F_lbl, thr["04"])
    style_contours(con_r, F_lbl, thr["05"])
    for k in ("02", "03", "04", "05"):
        log(f"Ambang label kontur peta {pfx}_{k}: $length > {thr[k]} m")
    day_legend = style_points_by_day(pts_day, cfg["day_field"], cfg["name_field"], F_lbl)
    pts_blk.setRenderer(QgsSingleSymbolRenderer(point_symbol()))
    make_blocking(pts_blk)
    style_base_labeled(base_lbl, F_lbl)
    base_obs.setRenderer(QgsSingleSymbolRenderer(base_symbol()))
    make_blocking(base_obs)

    order = [base_lbl, base_obs, pts_day, pts_blk, con_k, con_m, con_d, con_r,
             grids["krig"], grids["mc"], diff, grids["raw"]]
    order += [l for l in (terrain, satellite, osm) if l]
    for l in reversed(order):
        project.addMapLayer(l)
    root = project.layerTreeRoot()
    for i, l in enumerate(order):
        node = root.findLayer(l.id())
        root.insertChildNode(i, node.clone())
        root.removeChildNode(node)
    for l in (base_lbl, pts_day, con_m, con_d, con_r, grids["mc"], diff, grids["raw"], satellite, osm):
        if l:
            root.findLayer(l.id()).setItemVisibilityChecked(False)

    ext = QgsRectangle(grids["krig"].extent())
    ext.combineExtentWith(pts_day.extent())
    ext.combineExtentWith(base_obs.extent())

    bg = [terrain] if terrain else []
    contour_items = [("line", contour_symbol(w_, p_), lbl) for lbl, _, w_, p_ in CONTOUR_RULES]
    base_label = "Base station" if len(cfg["bases"]) == 1 else "Base station (D-1–D-3)"
    pts_items = [("marker", point_symbol(), "Titik ukur"), ("marker", base_symbol(), base_label)]
    proj = "Proyeksi: WGS 84 / UTM Zona 49S (EPSG:32749)."
    multiply = "Warna dipadukan dengan relief (Multiply)."
    terrain_src = ("Peta dasar: Google Terrain © Google; inset © OpenStreetMap contributors."
                   if terrain else "Peta dasar Google Terrain tidak tersedia (gagal dimuat).")
    grid_src = ("Gridding: Oasis montaj 2026.1.1 (Kriging/Minimum Curvature); kontur: Surfer 23; "
                "layout: QGIS 4.2.3.")
    data_src = "Data titik ukur: Praktikum EGBM (" + cfg["periode"] + ")."
    sub = cfg["subtitle"]
    specs = [
        dict(key="01", fname=f"{pfx}_01_Desain_Akuisisi", lname="01 Desain Akuisisi",
             title="PETA DESAIN AKUISISI DATA MAGNETIK", subtitle=sub,
             map_layers=[base_lbl, pts_day] + ([satellite] if satellite else []), colorbar=None,
             legend=day_legend + [("marker", base_symbol(), base_label)],
             info=[f"Jumlah titik ukur: {pts_day.featureCount()}.", cfg["base_note"], proj],
             sources=[data_src,
                      ("Citra: Google Satellite © Google; inset © OpenStreetMap contributors." if satellite
                       else "Citra Google Satellite tidak tersedia (gagal dimuat)."),
                      "Layout: QGIS 4.2.3."]),
        dict(key="02", fname=f"{pfx}_02_TMI_Kriging", lname="02 TMI Kriging",
             title="PETA ANOMALI MAGNETIK TOTAL (TMI) – KRIGING", subtitle=sub,
             map_layers=[base_obs, pts_blk, con_k, grids["krig"]] + bg,
             colorbar=(ramp_tmi, cfg["ticks"], "Anomali TMI (nT)"), legend=contour_items + pts_items,
             info=[f"Interval kontur: {cfg['contour_interval']} nT.",
                   f"Rentang warna: −{cfg['R']} s.d. +{cfg['R']} nT (sama untuk Kriging, MC, dan raw).",
                   multiply, proj],
             sources=[grid_src, terrain_src]),
        dict(key="03", fname=f"{pfx}_03_TMI_MC", lname="03 TMI Minimum Curvature",
             title="PETA ANOMALI MAGNETIK TOTAL (TMI) – MINIMUM CURVATURE", subtitle=sub,
             map_layers=[base_obs, pts_blk, con_m, grids["mc"]] + bg,
             colorbar=(ramp_tmi, cfg["ticks"], "Anomali TMI (nT)"), legend=contour_items + pts_items,
             info=[f"Interval kontur: {cfg['contour_interval']} nT.",
                   f"Rentang warna: −{cfg['R']} s.d. +{cfg['R']} nT (sama untuk Kriging, MC, dan raw).",
                   multiply, proj],
             sources=[grid_src, terrain_src]),
        dict(key="04", fname=f"{pfx}_04_Selisih_MC-Kriging", lname="04 Selisih MC - Kriging",
             title="PETA SELISIH ANOMALI TMI (MINIMUM CURVATURE − KRIGING)", subtitle=sub,
             map_layers=[base_obs, pts_blk, con_d, diff] + bg,
             colorbar=(ramp_diff, cfg["diff_ticks"], "Selisih MC − Kriging (nT)"), legend=contour_items + pts_items,
             info=["Selisih = MC − Kriging (Raster Calculator).",
                   f"Interval kontur selisih: {cfg['diff_interval']} nT.",
                   f"Rentang warna: −{cfg['S']} s.d. +{cfg['S']} nT.", multiply, proj],
             sources=["Gridding: Oasis montaj 2026.1.1 (Kriging/Minimum Curvature); kontur selisih: GDAL; "
                      "layout: QGIS 4.2.3.", terrain_src]),
        dict(key="05", fname=f"{pfx}_05_TMI_Raw_MC", lname="05 TMI Raw MC",
             title="PETA TMI RAW – MINIMUM CURVATURE",
             subtitle="Sebelum koreksi diurnal · " + sub,
             map_layers=[base_obs, pts_blk, con_r, grids["raw"]] + bg,
             colorbar=(ramp_tmi, cfg["ticks"], "TMI raw (nT)"), legend=contour_items + pts_items,
             info=["TMI raw = PPM − medan referensi, tanpa koreksi diurnal.",
                   f"Interval kontur: {cfg['contour_interval']} nT.",
                   f"Rentang warna: −{cfg['R']} s.d. +{cfg['R']} nT (sama dengan peta terkoreksi).",
                   proj],
             sources=["Gridding: Oasis montaj 2026.1.1 (Minimum Curvature); kontur: Surfer 23; layout: QGIS 4.2.3.",
                      terrain_src]),
    ]
    pngs = []
    for sp in specs:
        sp["extent"] = ext
        layout, scale, geo = make_layout(project, sp, cfg, F, FT, FS, fonts, osm)
        tag = f"{pfx}_{sp['key']}"
        if render_keys != "ALL" and tag not in render_keys:
            continue
        png = os.path.join(out_dir, sp["fname"] + ".png")
        export_png(layout, png)
        pngs.append(png)
        nl = f"; kontur {n_lines[sp['key']]} garis" if sp["key"] in n_lines else ""
        log(f"Layout '{sp['lname']}': skala 1:{scale}, bingkai peta {geo['map_w']:.0f} x {geo['map_h']:.0f} mm "
            f"({geo['frac'] * 100:.1f} % lebar area cetak){nl}; ruang sisa panel {geo['panel_extra']:.1f} mm "
            f"-> {os.path.basename(png)} ({os.path.getsize(png) / 1024:.0f} KB)")
    fmin = min(s for s, _ in fonts.sizes)
    log(f"Ukuran font terkecil di layout: {fmin} pt = {fmin * WORD_WIDTH_MM / page_w:.2f} pt pada lebar 16 cm")
    if render_keys == "ALL":
        qgz = os.path.join(ds_dir, cfg["project_name"] + ".qgz")
        if not project.write(qgz):
            raise RuntimeError(f"Gagal menyimpan project: {project.error()}")
        log(f"Project disimpan: {qgz}")
    with open(os.path.join(out_dir, "log_proses.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(logbuf) + "\n")
    _KEEP.append(project)
    return dict(pngs=pngs, fmin=fmin, page_w=page_w, n_lines=n_lines, thr=thr)


_KEEP = []


def main():
    standalone = QgsApplication.instance() is None
    app = None
    if standalone:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
        QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", r"C:\OSGeo4W\apps\qgis"), True)
        app = QgsApplication([], True)
        app.initQgis()
    render = "ALL" if RENDER == "ALL" else [k.strip() for k in RENDER.split(",")]
    hasil = {}
    try:
        for cfg in CONFIGS:
            if render == "ALL" or any(k.startswith(cfg["prefix"] + "_") for k in render):
                hasil[cfg["key"]] = build_project(cfg, render, [])
    except Exception:
        import traceback
        traceback.print_exc()
        raise
    finally:
        if standalone:
            # keluar langsung setelah semua berkas tertulis (mencegah crash destruktor setelah exitQgis)
            import sys
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0 if hasil else 1)
    return hasil


HASIL = main()
