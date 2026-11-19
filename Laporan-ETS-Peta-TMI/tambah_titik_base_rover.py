# Jalankan di QGIS: Plugins > Python Console, lalu ketik:
# exec(open(r"D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\LAPORAN ETS (2)\QGIS\tambah_titik_base_rover.py", encoding="utf-8").read())

import os
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsMarkerSymbol, QgsPalLayerSettings, QgsTextFormat, QgsTextBufferSettings,
    QgsVectorLayerSimpleLabeling,
)
from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QColor, QFont
from qgis.utils import iface

CSV = r"D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\LAPORAN ETS (2)\DATA\TMI_Base-Rover Laksa.csv"
NAMA_LAYER = "Lokasi Data Magnetik (Base-Rover)"

uri = (QUrl.fromLocalFile(CSV).toString()
       + "?type=csv&delimiter=,&encoding=UTF-8&detectTypes=yes&geomType=point"
       + "&xField=UTM%20X&yField=UTM%20Y&crs=EPSG:32749"
       + "&watchFile=yes&spatialIndex=yes")

proj = QgsProject.instance()
for lyr in proj.mapLayersByName(NAMA_LAYER):
    proj.removeMapLayer(lyr.id())

layer = QgsVectorLayer(uri, NAMA_LAYER, "delimitedtext")
if not layer.isValid():
    raise RuntimeError("Layer CSV tidak valid, cek path: " + CSV)

# Nama kolom pertama bisa terbawa BOM (\ufeff) dari CSV
day_field = next(f.name() for f in layer.fields() if f.name().lstrip("\ufeff") == "DAY")

warna = {"DAY 3": "#e41a1c", "DAY 4": "#377eb8", "DAY 5": "#4daf4a"}
kategori = []
for day in sorted(layer.uniqueValues(layer.fields().indexOf(day_field))):
    sym = QgsMarkerSymbol.createSimple({
        "name": "circle", "size": "2.4",
        "color": warna.get(day, "#ff7f00"),
        "outline_color": "black", "outline_width": "0.3",
    })
    kategori.append(QgsRendererCategory(day, sym, day))
layer.setRenderer(QgsCategorizedSymbolRenderer(day_field, kategori))

# Label nama titik
fmt = QgsTextFormat()
fmt.setFont(QFont("Arial"))
fmt.setSize(7)
buf = QgsTextBufferSettings()
buf.setEnabled(True)
buf.setSize(0.8)
buf.setColor(QColor("white"))
fmt.setBuffer(buf)
lbl = QgsPalLayerSettings()
lbl.fieldName = "Nama_titik"
lbl.setFormat(fmt)
lbl.placement = QgsPalLayerSettings.OverPoint
lbl.yOffset = -2.5
layer.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
layer.setLabelsEnabled(True)

# Taruh paling atas di Layers panel
proj.addMapLayer(layer, False)
proj.layerTreeRoot().insertLayer(0, layer)

iface.mapCanvas().setExtent(iface.mapCanvas().mapSettings().layerExtentToOutputExtent(layer, layer.extent()))
iface.mapCanvas().refresh()
print(f"OK: {layer.featureCount()} titik dimuat ke '{NAMA_LAYER}'")
