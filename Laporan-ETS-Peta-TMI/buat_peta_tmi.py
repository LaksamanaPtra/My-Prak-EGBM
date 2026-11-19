# -*- coding: utf-8 -*-
"""
buat_peta_tmi.py — Pembuat project QGIS 4.2.3 peta anomali magnetik (TMI)
Praktikum EGBM — Laksamana Putra Yulistiono (5017251036)

Cara menjalankan
----------------
1) Standalone (Command Prompt):
     "C:\\OSGeo4W\\bin\\python-qgis.bat" "<ROOT>\\QGIS\\buat_peta_tmi.py"
2) Dari QGIS Python Console:
     exec(open(r"<ROOT>\\QGIS\\buat_peta_tmi.py", encoding="utf-8").read())

Skrip membuat (untuk tiap dataset) di ROOT\\QGIS\\<DATASET>\\ :
  - Peta_<Dataset>.qgz (4 print layout), titik_ukur.gpkg, kontur_TMI.gpkg,
    Selisih_MC-Kriging.tif (Raster Calculator)
  - output\\<PREFIX>_0x_*.png (300 dpi), output\\statistik_grid.csv, output\\log_proses.txt
Data asli (DATA, TUTORIAL) hanya dibaca, tidak pernah diubah.
"""
import os
import csv
import math
import datetime
import urllib.request

# Jangan biarkan GDAL menulis berkas .aux.xml di samping grid asli (folder TUTORIAL)
os.environ["GDAL_PAM_ENABLED"] = "NO"

import numpy as np
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
gdal.SetConfigOption("GDAL_PAM_ENABLED", "NO")

from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsVectorLayer, QgsRasterLayer, QgsFeature, QgsField, QgsFields, QgsGeometry, QgsPointXY,
    QgsVectorFileWriter, QgsRectangle, QgsStyle, QgsColorRampShader, QgsRasterShader,
    QgsSingleBandPseudoColorRenderer, QgsBilinearRasterResampler, QgsColorRampLegendNodeSettings,
    QgsMarkerSymbol, QgsLineSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer,
    QgsRuleBasedRenderer, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling, QgsPrintLayout, QgsLayoutItemPage, QgsLayoutItemMap,
    QgsLayoutItemMapGrid, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemScaleBar,
    QgsLayoutItemPicture, QgsLayoutItemShape, QgsLayoutPoint, QgsLayoutSize, QgsLayoutExporter,
    QgsLegendStyle, QgsFillSymbol, QgsSingleSymbolRenderer, QgsLayoutMeasurement,
    QgsMapLayerLegendUtils, QgsBasicNumericFormat, QgsHueSaturationFilter,
)
from qgis.PyQt.QtCore import Qt, QMetaType, QSizeF
from qgis.PyQt.QtGui import QColor, QFont, QPainter

ROOT = r"D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\LAPORAN ETS (2)"
EPSG = "EPSG:32749"
MM = Qgis.LayoutUnit.Millimeters
XYZ_URL = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"          # Google Satellite (peta desain)
XYZ_TERRAIN_URL = "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}"  # Google Terrain (peta TMI/selisih)
SUMBER = ("Sumber data: Praktikum EGBM; gridding Oasis montaj 2026.1.1; "
          "diolah oleh Laksamana Putra Yulistiono (5017251036)")
TEKS_CRS = "Sistem koordinat: WGS 84 / UTM Zona 49S"
DAY_COLORS = ["#e41a1c", "#2b83ba", "#33a02c", "#ff7f00", "#984ea3"]

CONFIGS = [
    dict(
        key="ROVER-ROVER", prefix="RR", project_name="Peta_Rover-Rover",
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
        contour_interval=50,
    ),
    dict(
        key="BASE-ROVER", prefix="BR", project_name="Peta_Base-Rover",
        subtitle="Konfigurasi Base-Rover, Telaga Ngebel, Ponorogo",
        periode="11, 13, dan 14 Agustus 2026",
        points_csv=os.path.join(ROOT, "DATA", "TMI_Base-Rover Laksa.csv"),
        day_field="DAY", name_field="Nama_titik", x_field="UTM X", y_field="UTM Y",
        z_field="Z", tmi_field="TMI", expected_n=74,
        bases=[("Base station", 111.638979, -7.795342, "EPSG:4326")],
        base_note="Base station: 111,638979° BT; 7,795342° LS.",
        grid_krig=os.path.join(ROOT, "TUTORIAL", "BASE-ROVER", "base-rover_TMI_Kriging_SurferV7.grd"),
        grid_mc=os.path.join(ROOT, "TUTORIAL", "BASE-ROVER", "base-rover_TMI_MC_SurferV7.grd"),
        contour_interval=100,
    ),
]


# ----------------------------------------------------------------------------- util
def ceil_to(v, step):
    return math.ceil(v / step) * step


def fmt_id(v, dec=0):
    """Format angka gaya Indonesia: titik ribuan, koma desimal."""
    s = f"{v:,.{dec}f}"
    return s.replace(",", "#").replace(".", ",").replace("#", ".")


def text_format(size, bold=False, color="black", buffer=None):
    f = QFont("Arial")
    f.setBold(bold)
    tf = QgsTextFormat()
    tf.setFont(f)
    tf.setSize(size)
    tf.setColor(QColor(color))
    if buffer:
        b = QgsTextBufferSettings()
        b.setEnabled(True)
        b.setSize(buffer[0])
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
    ds = None
    return arr, valid, gt, nd


def bilinear_sample(arr, valid, gt, x, y):
    """Sampling bilinear pada simpul grid (pusat sel). None jika di luar/NoData."""
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
    steps = [2500 * i for i in range(1, 41)] + [5000 * i for i in range(21, 41)]
    for s in steps:
        if s >= need:
            return s
    return ceil_to(need, 10000)


# ----------------------------------------------------------------------------- data
def build_point_gpkg(cfg, gpkg, log):
    with open(cfg["points_csv"], encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != cfg["expected_n"]:
        raise RuntimeError(f"[{cfg['key']}] Jumlah titik terbaca {len(rows)}, seharusnya {cfg['expected_n']}. BERHENTI.")
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
            tr = QgsCoordinateTransform(QgsCoordinateReferenceSystem(bcrs), crs, QgsProject.instance())
            p = tr.transform(p)
            log(f"Base '{name}' {bx}, {by} ({bcrs}) -> {p.x():.2f}, {p.y():.2f} ({EPSG})")
        f = QgsFeature(bfields)
        f.setAttributes([name, p.x(), p.y()])
        f.setGeometry(QgsGeometry.fromPointXY(p))
        bfeats.append(f)

    for lname, flds, fts, mode in [("titik_ukur", fields, feats, QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile),
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
    return rows


def make_contours(grid_path, gpkg, layer_name, interval, log):
    ds = gdal.OpenEx(grid_path, gdal.OF_RASTER | gdal.OF_READONLY)
    band = ds.GetRasterBand(1)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(32749)
    drv = ogr.GetDriverByName("GPKG")
    out = drv.Open(gpkg, 1) if os.path.exists(gpkg) else drv.CreateDataSource(gpkg)
    lyr = out.CreateLayer(layer_name, srs, ogr.wkbLineString, options=["OVERWRITE=YES"])
    lyr.CreateField(ogr.FieldDefn("ID", ogr.OFTInteger))
    lyr.CreateField(ogr.FieldDefn("ELEV", ogr.OFTReal))
    opts = [f"LEVEL_INTERVAL={interval}", "LEVEL_BASE=0", "ID_FIELD=0", "ELEV_FIELD=1"]
    if band.GetNoDataValue() is not None:
        opts.append(f"NODATA={band.GetNoDataValue()}")
    gdal.ContourGenerateEx(band, lyr, options=opts)
    n = lyr.GetFeatureCount()
    out = None
    ds = None
    log(f"Kontur {layer_name}: {n} garis (interval {interval} nT)")


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


# ----------------------------------------------------------------------------- simbologi
def style_pseudocolor(layer, vmin, vmax, ramp_name, invert):
    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    if invert:
        ramp.invert()
    sh = QgsColorRampShader(vmin, vmax, ramp, QgsColorRampShader.Type.Interpolated,
                            Qgis.ShaderClassificationMethod.Continuous)
    sh.classifyColorRamp()
    sh.setClip(False)
    ls = QgsColorRampLegendNodeSettings()
    ls.setUseContinuousLegend(True)
    ls.setSuffix(" nT")
    sh.setLegendSettings(ls)
    rs = QgsRasterShader()
    rs.setRasterShaderFunction(sh)
    ren = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, rs)
    ren.setClassificationMin(vmin)
    ren.setClassificationMax(vmax)
    layer.setRenderer(ren)
    layer.resampleFilter().setZoomedInResampler(QgsBilinearRasterResampler())
    layer.resampleFilter().setZoomedOutResampler(QgsBilinearRasterResampler())
    # dipadukan dengan relief Google Terrain di bawahnya (gaya project TUTORIAL\QGIS\MC BASE-ROVER.qgz)
    layer.setBlendMode(QPainter.CompositionMode.CompositionMode_Multiply)
    layer.triggerRepaint()


def make_xyz(url, name, log, grayscale_opacity=None):
    """Layer XYZ; None jika tile tidak bisa diunduh. grayscale_opacity -> grayscale 'By average' + opacity."""
    try:
        tile = url.replace("{x}", "0").replace("{y}", "0").replace("{z}", "0")
        urllib.request.urlopen(tile, timeout=15).read()
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


def style_contours(layer):
    root = QgsRuleBasedRenderer.Rule(None)
    for label, filt, color, width, pen in [
        ("Kontur 0 nT", '"ELEV" = 0', "#000000", 0.6, "solid"),
        ("Kontur positif", '"ELEV" > 0', "#000000", 0.26, "solid"),
        ("Kontur negatif (putus-putus)", '"ELEV" < 0', "#000000", 0.26, "dash"),
    ]:
        sym = QgsLineSymbol.createSimple({"line_color": color, "line_width": str(width), "line_style": pen})
        root.appendChild(QgsRuleBasedRenderer.Rule(sym, 0, 0, filt, label))
    layer.setRenderer(QgsRuleBasedRenderer(root))
    pal = QgsPalLayerSettings()
    pal.isExpression = True
    # label hanya pada kontur yang panjangnya > 1000 m, mengikuti lengkung garis
    pal.fieldName = 'if($length > 1000, to_int("ELEV"), NULL)'
    pal.placement = Qgis.LabelPlacement.Curved
    pal.lineSettings().setPlacementFlags(Qgis.LabelLinePlacementFlag.OnLine)
    # buffer tipis agar tanda minus tidak tertutup garis kontur yang ditimpa label
    pal.setFormat(text_format(7, color="#323232", buffer=(0.4, "white")))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


def style_points_by_day(layer, day_field, name_field):
    days = sorted({f[day_field] for f in layer.getFeatures()},
                  key=lambda d: int("".join(ch for ch in d if ch.isdigit()) or 0))
    counts = {d: 0 for d in days}
    for f in layer.getFeatures():
        counts[f[day_field]] += 1
    cats = []
    for i, d in enumerate(days):
        sym = QgsMarkerSymbol.createSimple({"name": "circle", "color": DAY_COLORS[i % len(DAY_COLORS)],
                                            "outline_color": "white", "outline_width": "0.3", "size": "2.4"})
        num = "".join(ch for ch in d if ch.isdigit())
        cats.append(QgsRendererCategory(d, sym, f"Hari ke-{num} ({counts[d]} titik)"))
    layer.setRenderer(QgsCategorizedSymbolRenderer(day_field, cats))
    pal = QgsPalLayerSettings()
    pal.fieldName = name_field
    pal.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    pal.dist = 0.4
    pal.setFormat(text_format(4.5, color="white", buffer=(0.45, "black")))
    try:
        pal.placementSettings().setOverlapHandling(Qgis.LabelOverlapHandling.AllowOverlapIfRequired)
    except Exception:
        pass
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)
    return days, counts


def style_points_black(layer):
    layer.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
        {"name": "circle", "color": "black", "outline_style": "no", "size": "1.5"})))


def style_base(layer):
    layer.setRenderer(QgsSingleSymbolRenderer(QgsMarkerSymbol.createSimple(
        {"name": "star", "color": "#ffd700", "outline_color": "black", "outline_width": "0.35", "size": "5.5"})))
    pal = QgsPalLayerSettings()
    pal.fieldName = "NAMA"
    pal.placement = Qgis.LabelPlacement.OrderedPositionsAroundPoint
    pal.dist = 1.5
    pal.setFormat(text_format(7, bold=True, color="#ffd700", buffer=(0.6, "black")))
    layer.setLabeling(QgsVectorLayerSimpleLabeling(pal))
    layer.setLabelsEnabled(True)


# ----------------------------------------------------------------------------- layout
def add_label(layout, text, x, y, w, h, tf, halign=Qt.AlignmentFlag.AlignLeft,
              valign=Qt.AlignmentFlag.AlignTop):
    lbl = QgsLayoutItemLabel(layout)
    lbl.setText(text)
    lbl.setTextFormat(tf)
    lbl.setHAlign(halign)
    lbl.setVAlign(valign)
    layout.addLayoutItem(lbl)
    lbl.attemptMove(QgsLayoutPoint(x, y, MM))
    lbl.attemptResize(QgsLayoutSize(w, h, MM))
    return lbl


def make_layout(project, name, title, subtitle, map_layers, legend_entries, extent,
                info_lines, legend_title="LEGENDA"):
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName(name)
    layout.pageCollection().page(0).setPageSize("A4", QgsLayoutItemPage.Orientation.Landscape)

    # bingkai halaman
    frame = QgsLayoutItemShape(layout)
    frame.setShapeType(QgsLayoutItemShape.Shape.Rectangle)
    frame.setSymbol(QgsFillSymbol.createSimple({"color": "255,255,255,0", "outline_color": "black",
                                                "outline_width": "0.5"}))
    layout.addLayoutItem(frame)
    frame.attemptMove(QgsLayoutPoint(5, 4, MM))
    frame.attemptResize(QgsLayoutSize(287, 202, MM))

    add_label(layout, title, 8, 6, 281, 8, text_format(15, bold=True), Qt.AlignmentFlag.AlignHCenter)
    add_label(layout, subtitle, 8, 14.5, 281, 6, text_format(10.5), Qt.AlignmentFlag.AlignHCenter)

    # peta — ukuran bingkai menyesuaikan ekstent pada skala bulat
    AX, AY, AW, AH = 20, 29, 180, 166
    need = max(extent.width() / (AW / 1000.0), extent.height() / (AH / 1000.0))
    scale = nice_scale(need)
    fw = min(AW, extent.width() * 1000.0 / scale)
    fh = min(AH, extent.height() * 1000.0 / scale)
    fx = AX + (AW - fw) / 2.0
    fy = AY + (AH - fh) / 2.0
    m = QgsLayoutItemMap(layout)
    m.setCrs(QgsCoordinateReferenceSystem(EPSG))
    layout.addLayoutItem(m)
    m.attemptMove(QgsLayoutPoint(fx, fy, MM))
    m.attemptResize(QgsLayoutSize(fw, fh, MM))
    m.setLayers(map_layers)
    m.setKeepLayerSet(True)
    m.zoomToExtent(extent)
    m.setScale(scale)
    m.setFrameEnabled(True)
    m.setFrameStrokeWidth(QgsLayoutMeasurementMM(0.3))

    interval = 500 if scale <= 40000 else 1000
    g = QgsLayoutItemMapGrid("Grid UTM", m)
    m.grids().addGrid(g)
    g.setIntervalX(interval)
    g.setIntervalY(interval)
    g.setStyle(QgsLayoutItemMapGrid.GridStyle.Cross)
    g.setCrossLength(2.0)
    g.setGridLineWidth(0.2)
    g.setFrameStyle(QgsLayoutItemMapGrid.FrameStyle.Zebra)
    g.setFrameWidth(1.2)
    g.setAnnotationEnabled(True)
    g.setAnnotationFormat(QgsLayoutItemMapGrid.AnnotationFormat.Decimal)
    g.setAnnotationPrecision(0)
    g.setAnnotationTextFormat(text_format(6))
    g.setAnnotationFrameDistance(0.8)
    S = QgsLayoutItemMapGrid.BorderSide
    D = QgsLayoutItemMapGrid.DisplayMode
    for side in (S.Left, S.Right, S.Top, S.Bottom):
        g.setAnnotationPosition(QgsLayoutItemMapGrid.AnnotationPosition.OutsideMapFrame, side)
    g.setAnnotationDirection(QgsLayoutItemMapGrid.AnnotationDirection.Vertical, S.Left)
    g.setAnnotationDirection(QgsLayoutItemMapGrid.AnnotationDirection.Vertical, S.Right)
    g.setAnnotationDirection(QgsLayoutItemMapGrid.AnnotationDirection.Horizontal, S.Top)
    g.setAnnotationDirection(QgsLayoutItemMapGrid.AnnotationDirection.Horizontal, S.Bottom)
    g.setAnnotationDisplay(D.LatitudeOnly, S.Left)
    g.setAnnotationDisplay(D.LatitudeOnly, S.Right)
    g.setAnnotationDisplay(D.LongitudeOnly, S.Top)
    g.setAnnotationDisplay(D.LongitudeOnly, S.Bottom)
    m.updateBoundingRect()

    # panel kanan
    PX, PW = 211, 76
    lg = QgsLayoutItemLegend(layout)
    layout.addLayoutItem(lg)
    lg.setTitle(legend_title)
    lg.setLinkedMap(m)
    lg.setAutoUpdateModel(False)
    root = lg.model().rootGroup()
    root.removeAllChildren()
    for lyr, title in legend_entries:
        node = root.addLayer(lyr)
        node.setCustomProperty("legend/title-label", title)
        if isinstance(lyr, QgsRasterLayer):
            # buang simpul "Band 1", sisakan bar warna kontinu dan perbesar
            QgsMapLayerLegendUtils.setLegendNodeOrder(node, [1])
            QgsMapLayerLegendUtils.setLegendNodeSymbolSize(node, 1, QSizeF(6, 32))
            lg.model().refreshLayerLegend(node)
    lg.rstyle(QgsLegendStyle.Style.Title).setTextFormat(text_format(10, bold=True))
    lg.rstyle(QgsLegendStyle.Style.Subgroup).setTextFormat(text_format(8, bold=True))
    lg.rstyle(QgsLegendStyle.Style.SymbolLabel).setTextFormat(text_format(7.5))
    lg.rstyle(QgsLegendStyle.Style.Subgroup).setMargin(QgsLegendStyle.Side.Top, 2.5)
    lg.setSymbolHeight(4)
    lg.setSymbolWidth(6)
    lg.setFrameEnabled(True)
    lg.setBoxSpace(2.5)
    lg.attemptMove(QgsLayoutPoint(PX, AY, MM))
    lg.setMaximumSymbolSize(6)
    lg.setWrapString("|")

    # blok panah utara + skala dan teks keterangan ditaruh tetap di bagian bawah panel;
    # legenda (atas) dibatasi agar tidak melewati y = 124 mm
    info_h = 40
    info_y = AY + AH - info_h
    y = info_y - 27

    # panah utara + skala
    add_label(layout, "U", PX, y, 12, 5, text_format(10, bold=True), Qt.AlignmentFlag.AlignHCenter)
    na = QgsLayoutItemPicture(layout)
    na.setPicturePath(os.path.join(QgsApplication.pkgDataPath(), "svg", "arrows", "NorthArrow_01.svg"),
                      Qgis.PictureFormat.SVG)
    na.setSvgFillColor(QColor("black"))
    na.setSvgStrokeColor(QColor("black"))
    layout.addLayoutItem(na)
    na.attemptMove(QgsLayoutPoint(PX + 1, y + 5, MM))
    na.attemptResize(QgsLayoutSize(10, 16, MM))
    na.setLinkedMap(m)

    total_m = 40.0 * scale / 1000.0
    seg = min([100, 200, 250, 500, 1000, 2000, 2500, 5000], key=lambda s: abs(2 * s - total_m))
    sb = QgsLayoutItemScaleBar(layout)
    sb.setStyle("Single Box")
    layout.addLayoutItem(sb)
    sb.setLinkedMap(m)
    sb.setUnits(Qgis.DistanceUnit.Meters)
    sb.setUnitLabel("m")
    sb.setMapUnitsPerScaleBarUnit(1.0)
    sb.setSegmentSizeMode(Qgis.ScaleBarSegmentSizeMode.Fixed)
    sb.setNumberOfSegments(2)
    sb.setNumberOfSegmentsLeft(0)
    sb.setUnitsPerSegment(seg)
    sb.setHeight(2.0)
    sb.setTextFormat(text_format(7))
    nf = QgsBasicNumericFormat()
    nf.setShowThousandsSeparator(True)
    nf.setThousandsSeparator(".")
    nf.setDecimalSeparator(",")
    nf.setNumberDecimalPlaces(0)
    sb.setNumericFormat(nf)
    sb.attemptMove(QgsLayoutPoint(PX + 18, y + 6, MM))
    sb.refreshItemSize()
    add_label(layout, f"Skala 1 : {fmt_id(scale)}", PX + 18, y + 16, PW - 18, 5, text_format(8))
    y_after = y + 22

    # teks keterangan (rata bawah panel)
    info = "\n".join(info_lines + [TEKS_CRS, SUMBER])
    add_label(layout, info, PX, info_y, PW, info_h, text_format(6.5), valign=Qt.AlignmentFlag.AlignBottom)
    project.layoutManager().addLayout(layout)
    layout.refresh()
    lg.adjustBoxSize()
    lg_bottom = lg.pos().y() + lg.rect().height()
    if lg_bottom > y - 2:
        print(f"PERINGATAN: legenda '{name}' (bawah {lg_bottom:.1f} mm) bisa menimpa panah utara (y={y:.1f} mm)")
    return layout, scale, interval, dict(legend_bottom=lg_bottom, info_top=info_y, y_after=y_after)


def export_png(layout, path):
    exp = QgsLayoutExporter(layout)
    st = QgsLayoutExporter.ImageExportSettings()
    st.dpi = 300
    res = exp.exportToImage(path, st)
    if res != QgsLayoutExporter.ExportResult.Success:
        raise RuntimeError(f"Ekspor gagal ({res}): {path}")


# ----------------------------------------------------------------------------- utama
def build_project(cfg):
    ds_dir = os.path.join(ROOT, "QGIS", cfg["key"])
    out_dir = os.path.join(ds_dir, "output")
    os.makedirs(out_dir, exist_ok=True)
    log_lines = []

    def log(msg):
        print(f"[{cfg['prefix']}] {msg}")
        log_lines.append(msg)

    log(f"Mulai {datetime.datetime.now():%Y-%m-%d %H:%M:%S} — {cfg['key']}")
    crs = QgsCoordinateReferenceSystem(EPSG)
    project = QgsProject()
    project.setCrs(crs)
    project.setTitle(cfg["project_name"].replace("_", " "))

    # 1. titik ukur + base
    gpkg = os.path.join(ds_dir, "titik_ukur.gpkg")
    build_point_gpkg(cfg, gpkg, log)
    pts_day = QgsVectorLayer(f"{gpkg}|layername=titik_ukur", "Titik ukur (per hari)", "ogr")
    pts_blk = QgsVectorLayer(f"{gpkg}|layername=titik_ukur", "Titik ukur", "ogr")
    base = QgsVectorLayer(f"{gpkg}|layername=base_station", "Base station", "ogr")
    for l in (pts_day, pts_blk, base):
        if not l.isValid():
            raise RuntimeError(f"Layer {l.name()} tidak valid")
    if pts_day.featureCount() != cfg["expected_n"]:
        raise RuntimeError(f"Jumlah fitur {pts_day.featureCount()} != {cfg['expected_n']}. BERHENTI.")
    log(f"Titik ukur: {pts_day.featureCount()} fitur; base: {base.featureCount()} fitur")

    # 2. grid
    grids = {}
    for key, path, nm in [("krig", cfg["grid_krig"], "Anomali TMI – Kriging"),
                          ("mc", cfg["grid_mc"], "Anomali TMI – Minimum Curvature")]:
        rl = QgsRasterLayer(path, nm, "gdal")
        if not rl.isValid():
            raise RuntimeError(f"Grid gagal terbaca: {path}. BERHENTI.")
        rl.setCrs(crs)
        if rl.crs().authid() != EPSG:
            raise RuntimeError(f"CRS grid {nm} = {rl.crs().authid()}")
        if not rl.extent().intersects(pts_day.extent()):
            raise RuntimeError(f"Ekstent grid {nm} tidak tumpang-tindih dengan titik ukur")
        inside = sum(1 for f in pts_day.getFeatures() if rl.extent().contains(f.geometry().asPoint()))
        log(f"Grid {nm}: {rl.width()}x{rl.height()} sel, CRS {rl.crs().authid()}, "
            f"ekstent {rl.extent().toString(1)}; titik di dalam ekstent: {inside}/{pts_day.featureCount()}")
        grids[key] = rl

    # 3. selisih (Raster Calculator)
    diff_tif = os.path.join(ds_dir, "Selisih_MC-Kriging.tif")
    raster_difference(grids["mc"], grids["krig"], diff_tif, project)
    diff = QgsRasterLayer(diff_tif, "Selisih MC − Kriging", "gdal")
    if not diff.isValid():
        raise RuntimeError("Raster selisih tidak valid")
    diff.setCrs(crs)

    # 4. statistik + rentang warna
    arrs = {k: read_grid(p) for k, p in [("krig", cfg["grid_krig"]), ("mc", cfg["grid_mc"]), ("diff", diff_tif)]}
    exp_valid = arrs["krig"][1] & arrs["mc"][1]
    if int(arrs["diff"][1].sum()) != int(exp_valid.sum()) or (arrs["diff"][1] != exp_valid).any():
        raise RuntimeError("Mask NoData selisih tidak sama dengan irisan sel valid Kriging & MC")
    log(f"Selisih: {int(arrs['diff'][1].sum())} sel valid (= irisan sel valid Kriging dan MC)")
    comb = np.concatenate([arrs["krig"][0][arrs["krig"][1]], arrs["mc"][0][arrs["mc"][1]]])
    p98 = float(np.percentile(np.abs(comb), 98))
    R = ceil_to(p98, 50)
    dvals = arrs["diff"][0][arrs["diff"][1]]
    p98d = float(np.percentile(np.abs(dvals), 98))
    Sd = ceil_to(p98d, 25)
    log(f"R: P98(|Kriging ∪ MC|) = {p98:.2f} nT -> R = ±{R} nT")
    log(f"S: P98(|MC − Kriging|) = {p98d:.2f} nT -> S = ±{Sd} nT")

    pts = [(f[cfg["x_field"]], f[cfg["y_field"]], f[cfg["tmi_field"]]) for f in pts_day.getFeatures()]
    stats_rows = []
    for key, label, fname in [("krig", "Kriging", cfg["grid_krig"]), ("mc", "Minimum Curvature", cfg["grid_mc"]),
                              ("diff", "Selisih (MC - Kriging)", diff_tif)]:
        a, v, gt, _ = arrs[key]
        vals = a[v]
        row = dict(dataset=cfg["key"], grid=label, berkas=os.path.basename(fname),
                   min_nT=f"{vals.min():.3f}", max_nT=f"{vals.max():.3f}", mean_nT=f"{vals.mean():.3f}",
                   std_nT=f"{vals.std():.3f}", n_sel_valid=int(v.sum()),
                   rms_residual_nT="", n_titik_residual="", n_titik_luar_grid="",
                   rentang_warna_nT=f"±{Sd}" if key == "diff" else f"±{R}")
        if key != "diff":
            res = []
            for x, y, t in pts:
                g = bilinear_sample(a, v, gt, x, y)
                if g is not None:
                    res.append(t - g)
            res = np.array(res)
            row["rms_residual_nT"] = f"{math.sqrt(np.mean(res ** 2)):.3f}"
            row["n_titik_residual"] = len(res)
            row["n_titik_luar_grid"] = len(pts) - len(res)
            log(f"RMS residual {label}: {row['rms_residual_nT']} nT ({len(res)} titik, "
                f"{len(pts) - len(res)} titik di luar/tepi grid)")
        stats_rows.append(row)
    stats_csv = os.path.join(out_dir, "statistik_grid.csv")
    with open(stats_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(stats_rows[0].keys()))
        w.writeheader()
        w.writerows(stats_rows)

    # 5. kontur
    kgpkg = os.path.join(ds_dir, "kontur_TMI.gpkg")
    make_contours(cfg["grid_krig"], kgpkg, "kontur_kriging", cfg["contour_interval"], log)
    make_contours(cfg["grid_mc"], kgpkg, "kontur_mc", cfg["contour_interval"], log)
    con_k = QgsVectorLayer(f"{kgpkg}|layername=kontur_kriging", "Kontur TMI – Kriging", "ogr")
    con_m = QgsVectorLayer(f"{kgpkg}|layername=kontur_mc", "Kontur TMI – Minimum Curvature", "ogr")

    # 6. basemap: Satellite untuk peta desain; Terrain grayscale (average) 70 % untuk peta TMI/selisih
    basemap = make_xyz(XYZ_URL, "Google Satellite", log)
    terrain = make_xyz(XYZ_TERRAIN_URL, "Google Terrain (grayscale)", log, grayscale_opacity=0.7)

    # 7. simbologi
    style_pseudocolor(grids["krig"], -R, R, "RdBu", True)
    style_pseudocolor(grids["mc"], -R, R, "RdBu", True)
    style_pseudocolor(diff, -Sd, Sd, "PuOr", True)
    style_contours(con_k)
    style_contours(con_m)
    days, counts = style_points_by_day(pts_day, cfg["day_field"], cfg["name_field"])
    style_points_black(pts_blk)
    style_base(base)

    layers_top_down = [base, pts_day, pts_blk, con_k, con_m, grids["krig"], grids["mc"], diff]
    layers_top_down += [l for l in (terrain, basemap) if l]
    for l in reversed(layers_top_down):
        project.addMapLayer(l)
    root = project.layerTreeRoot()
    for i, l in enumerate(layers_top_down):  # urutkan atas → bawah
        node = root.findLayer(l.id())
        clone = node.clone()
        root.insertChildNode(i, clone)
        root.removeChildNode(node)
    for l in (pts_blk, con_m, grids["mc"], diff) + ((basemap,) if basemap else ()):
        root.findLayer(l.id()).setItemVisibilityChecked(False)

    # 8. layout — ekstent dilonggarkan 300 m agar konteks relief di sekitar grid terlihat
    ext = QgsRectangle(grids["krig"].extent())
    ext.combineExtentWith(pts_day.extent())
    ext.combineExtentWith(base.extent())
    ext = ext.buffered(300)

    bg = [terrain] if terrain else []
    bg_note = (["Warna dipadukan (multiply) dengan relief Google Terrain grayscale 70 %; "
                "warna peta sedikit lebih gelap daripada bar legenda."] if terrain
               else ["Citra latar Google Terrain tidak tersedia (gagal dimuat)."])
    tmi_note = [f"Interval kontur: {cfg['contour_interval']} nT (kontur 0 nT tebal, kontur negatif putus-putus; "
                "label pada kontur > 1000 m).",
                f"Rentang warna: −{R} s.d. +{R} nT (sama untuk Kriging dan Minimum Curvature)."] + bg_note
    desain_info = [f"Jumlah titik ukur: {pts_day.featureCount()}; waktu akuisisi: {cfg['periode']}.",
                   cfg["base_note"],
                   "Citra latar: Google Satellite." if basemap else "Citra latar: tidak tersedia (gagal dimuat)."]
    pfx = cfg["prefix"]
    specs = [
        (f"{pfx}_01_Desain_Akuisisi", "01 Desain Akuisisi", "PETA DESAIN AKUISISI DATA MAGNETIK",
         [base, pts_day] + ([basemap] if basemap else []),
         [(pts_day, "Titik ukur"), (base, "Base station")], desain_info),
        (f"{pfx}_02_TMI_Kriging", "02 TMI Kriging", "PETA ANOMALI MAGNETIK TOTAL (TMI) – KRIGING",
         [pts_blk, con_k, grids["krig"]] + bg,
         [(grids["krig"], "Anomali TMI (nT)"), (con_k, "Kontur TMI (nT)"), (pts_blk, "Titik ukur")], tmi_note),
        (f"{pfx}_03_TMI_MC", "03 TMI Minimum Curvature", "PETA ANOMALI MAGNETIK TOTAL (TMI) – MINIMUM CURVATURE",
         [pts_blk, con_m, grids["mc"]] + bg,
         [(grids["mc"], "Anomali TMI (nT)"), (con_m, "Kontur TMI (nT)"), (pts_blk, "Titik ukur")], tmi_note),
        (f"{pfx}_04_Selisih_MC-Kriging", "04 Selisih MC - Kriging",
         "PETA SELISIH ANOMALI TMI (MINIMUM CURVATURE − KRIGING)",
         [pts_blk, diff] + bg,
         [(diff, "Selisih MC − Kriging (nT)"), (pts_blk, "Titik ukur")],
         ["Selisih = grid Minimum Curvature − grid Kriging (Raster Calculator); sel NoData pada salah satu grid tetap NoData.",
          f"Rentang warna: −{Sd} s.d. +{Sd} nT (P98 |selisih|)."] + bg_note),
    ]
    pngs = []
    for fname, lname, title, mlayers, lentries, info in specs:
        layout, scale, interval, geo = make_layout(project, lname, title, cfg["subtitle"], mlayers, lentries, ext, info)
        png = os.path.join(out_dir, fname + ".png")
        export_png(layout, png)
        pngs.append(png)
        log(f"Layout '{lname}': skala 1:{scale}, grid {interval} m, legenda s.d. y={geo['legend_bottom']:.1f} mm, "
            f"teks info mulai y={geo['info_top']:.1f} mm -> {os.path.basename(png)} "
            f"({os.path.getsize(png) / 1024:.0f} KB)")

    qgz = os.path.join(ds_dir, cfg["project_name"] + ".qgz")
    if not project.write(qgz):
        raise RuntimeError(f"Gagal menyimpan project: {project.error()}")
    log(f"Project disimpan: {qgz}")
    with open(os.path.join(out_dir, "log_proses.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    return dict(R=R, S=Sd, p98=p98, p98d=p98d, stats=stats_rows, pngs=pngs, qgz=qgz,
                basemap=basemap is not None, terrain=terrain is not None, log=log_lines)


def main():
    standalone = QgsApplication.instance() is None
    app = None
    if standalone:
        # platform offscreen tidak memuat font Windows -> teks jadi kotak; arahkan ke folder font
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
        QgsApplication.setPrefixPath(os.environ.get("QGIS_PREFIX_PATH", r"C:\OSGeo4W\apps\qgis"), True)
        app = QgsApplication([], True)
        app.initQgis()
    hasil = {}
    try:
        for cfg in CONFIGS:
            hasil[cfg["key"]] = build_project(cfg)
    finally:
        if standalone:
            app.exitQgis()
    for k, h in hasil.items():
        print(f"== {k}: R = ±{h['R']} nT, S = ±{h['S']} nT, satellite = {h['basemap']}, terrain = {h['terrain']}")
    return hasil


def QgsLayoutMeasurementMM(v):
    return QgsLayoutMeasurement(v, MM)


HASIL = main()
