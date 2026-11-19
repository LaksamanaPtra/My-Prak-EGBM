import os
from qgis.core import *
from qgis.PyQt.QtGui import QColor,QFont
from qgis.PyQt.QtCore import Qt
p=QgsProject.instance();out=os.path.dirname(p.fileName())
a=p.mapLayersByName('Area Akuisisi')[0];t=p.mapLayersByName('Titik Gravity')[0]
d=p.mapLayersByName('DEMNAS 1608-41 | Elevasi UTM 49S (10 m)')[0]
l=QgsPrintLayout(p);l.initializeDefaults();l.setName('DEMNAS - A4 Landscape')
l.pageCollection().pages()[0].setPageSize(QgsLayoutSize(297,210))
def place(item,x,y,w,h):
 l.addLayoutItem(item);item.attemptMove(QgsLayoutPoint(x,y));item.attemptResize(QgsLayoutSize(w,h));return item
def label(text,x,y,w,h,size=9,bold=False,center=False):
 i=QgsLayoutItemLabel(l);i.setText(text);i.setFont(QFont('Times New Roman',size,QFont.Weight.Bold if bold else QFont.Weight.Normal));i.setVAlign(Qt.AlignmentFlag.AlignVCenter)
 if center:i.setHAlign(Qt.AlignmentFlag.AlignHCenter)
 return place(i,x,y,w,h)
def box(x,y,w,h):
 i=QgsLayoutItemShape(l);i.setShapeType(QgsLayoutItemShape.Rectangle);i.setSymbol(QgsFillSymbol.createSimple({'color':'255,255,255,0','outline_color':'0,0,0,255','outline_width':'0.25'}));return place(i,x,y,w,h)
box(3,3,291,204)
m=QgsLayoutItemMap(l);place(m,12,10,198,190);m.setCrs(p.crs());m.setLayers([t,a,d]);m.setKeepLayerSet(True);e=QgsRectangle(a.extent());e.scale(1.32);m.zoomToExtent(e);m.setFrameEnabled(True)
grid=m.grid();grid.setEnabled(True);grid.setCrs(p.crs());grid.setIntervalX(250);grid.setIntervalY(250);grid.setStyle(QgsLayoutItemMapGrid.Solid)
grid.setLineSymbol(QgsLineSymbol.createSimple({'line_color':'65,65,65,100','line_width':'0.12'}));grid.setAnnotationEnabled(True);grid.setAnnotationPrecision(0);grid.setAnnotationFont(QFont('Times New Roman',7));grid.setAnnotationFrameDistance(1)
for side in [QgsLayoutItemMapGrid.Left,QgsLayoutItemMapGrid.Right]:grid.setAnnotationDirection(QgsLayoutItemMapGrid.VerticalDescending,side)
box(217,10,70,190)
for y,h in [(10,20),(30,34),(64,17),(81,66),(147,36),(183,17)]:box(217,y,70,h)
label('PETA ELEVASI DEMNAS\nAREA AKUISISI GRAVITY\nSumur Welut dan Sekitarnya',218,11,68,18,10,True,True)
n=QgsLayoutItemPicture(l);place(n,246,33,12,13);n.setPicturePath('C:/OSGeo4W/apps/qgis/svg/arrows/NorthArrow_04.svg')
label('N',247,30,10,4,7,True,True)
label('Skala 1 : '+format(round(m.scale()),','),218,46,68,5,8,False,True)
s=QgsLayoutItemScaleBar(l);s.setStyle('Single Box');s.setLinkedMap(m);s.applyDefaultSize();s.setUnits(Qgis.DistanceUnit.Meters);s.setUnitsPerSegment(100);s.setNumberOfSegments(2);s.setNumberOfSegmentsLeft(0);s.setUnitLabel('m');s.setHeight(1.6);s.setFont(QFont('Times New Roman',7));place(s,236,53,40,7)
label('Proyeksi       : UTM zona 49S\nSistem grid  : Meter (EPSG:32749)\nDatum          : WGS 84 / tinggi EGM2008',218,65,68,15,8)
label('LEGENDA',219,82,66,6,10,True)
leg=QgsLayoutItemLegend(l);leg.setTitle('');leg.setLinkedMap(m);leg.setAutoUpdateModel(False)
lr=leg.model().rootGroup();lr.removeAllChildren()
for layer,name in [(t,'Titik gravity'),(a,'Area akuisisi'),(d,'Elevasi (m)')]:
 node=lr.addLayer(layer);node.setUseLayerName(False);node.setName(name)
leg.setStyleFont(QgsLegendStyle.Subgroup,QFont('Times New Roman',8));leg.setStyleFont(QgsLegendStyle.SymbolLabel,QFont('Times New Roman',8));leg.setBoxSpace(1);place(leg,219,90,65,40)
label('Sumber: DEMNAS BIG 1608-41; area dan titik\nakuisisi. Grid hasil reproyeksi: 10 m.\nPeta elevasi, belum merupakan hasil TC.',219,132,66,13,7)
label('Inset Peta',218,147,68,5,9,True,True)
im=QgsLayoutItemMap(l);place(im,225,154,54,21);im.setCrs(p.crs());im.setLayers([a,d]);im.setKeepLayerSet(True);im.zoomToExtent(d.extent());im.setFrameEnabled(True)
ov=QgsLayoutItemMapOverview('Lokasi yang dipetakan',im);im.overviews().addOverview(ov);ov.setLinkedMap(m);ov.setFrameSymbol(QgsFillSymbol.createSimple({'color':'255,0,0,0','outline_color':'255,0,0,255','outline_width':'0.4'}))
label('Kotak merah: lokasi yang dipetakan',219,176,66,5,7,False,True)
label('Dibuat oleh\nLaksamana Putra Yulistiono\n5017251036',218,184,68,15,8,False,True)
p.layoutManager().addLayout(l);p.write()
ex=QgsLayoutExporter(l);s=QgsLayoutExporter.ImageExportSettings();s.dpi=300
print('PNG',ex.exportToImage(os.path.join(out,'Peta_DEMNAS_A4_Landscape.png'),s))
s.dpi=110;print('PREVIEW',ex.exportToImage(os.path.join(out,'preview_demnas_a4.png'),s))
print('QPT',l.saveAsTemplate(os.path.join(out,'Layout_DEMNAS_A4.qpt'),QgsReadWriteContext()))
iface.openLayoutDesigner(l)
