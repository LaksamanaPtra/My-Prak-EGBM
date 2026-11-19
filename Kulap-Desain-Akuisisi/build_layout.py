import os,json
from qgis.core import *
from qgis.PyQt.QtGui import QColor,QFont
from qgis.PyQt.QtCore import Qt
p=QgsProject.instance()
root=r'D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\KULAP EGBM\DESAIN AKUISISI'
out=os.path.join(root,'Peta_Lokasi_TC')
area=p.mapLayersByName('Area Akuisisi')[0]
ref=p.mapLayersByName('Acuan citra dan batas kecamatan (dari Lokasi.png)')[0]
for name in ['Titik Gravity','Titik Magnetik']:
    layer=QgsVectorLayer(os.path.join(root,name+'.gpkg'),name,'ogr')
    p.addMapLayer(layer);p.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(False)
# Persist true survey area and buffers for subsequent terrain preparation.
g=QgsGeometry(next(area.getFeatures()).geometry())
gpkg=os.path.join(out,'Persiapan_TC.gpkg')
for name,dist in [('Buffer lokal 10 km',10000),('Buffer regional 167 km',167000)]:
    mem=QgsVectorLayer('MultiPolygon?crs=EPSG:32749',name,'memory')
    geom=g.buffer(dist,100);geom.convertToMultiType()
    f=QgsFeature();f.setGeometry(geom);mem.dataProvider().addFeatures([f]);mem.updateExtents()
    opt=QgsVectorFileWriter.SaveVectorOptions();opt.driverName='GPKG';opt.layerName='lokal_10km' if dist==10000 else 'regional_167km'
    if os.path.exists(gpkg):opt.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteLayer
    QgsVectorFileWriter.writeAsVectorFormatV3(mem,gpkg,p.transformContext(),opt)
    layer=QgsVectorLayer(gpkg+'|layername='+opt.layerName,name,'ogr');p.addMapLayer(layer)
    p.layerTreeRoot().findLayer(layer.id()).setItemVisibilityChecked(False)
idx=QgsVectorLayer(os.path.join(out,'DEMNAS_index_BIG.geojson'),'Indeks DEMNAS yang diperlukan','ogr')
idx.setSubsetString('"NAMOBJ" IN (\'1608-41\',\'1608-42\',\'1608-43\',\'1608-44\')');p.addMapLayer(idx);p.layerTreeRoot().findLayer(idx.id()).setItemVisibilityChecked(False)
layout=QgsPrintLayout(p);layout.initializeDefaults();layout.setName('Peta Lokasi Penelitian - TC')
layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(420,297))
def place(item,x,y,w,h):
    layout.addLayoutItem(item);item.attemptMove(QgsLayoutPoint(x,y));item.attemptResize(QgsLayoutSize(w,h));return item
def label(text,x,y,w,h,size=12,bold=False,color='black',center=False):
    item=QgsLayoutItemLabel(layout);item.setText(text);item.setFont(QFont('Arial',size,QFont.Weight.Bold if bold else QFont.Weight.Normal));item.setFontColor(QColor(color))
    if center:item.setHAlign(Qt.AlignmentFlag.AlignHCenter)
    item.setVAlign(Qt.AlignmentFlag.AlignVCenter);return place(item,x,y,w,h)
def box(x,y,w,h,color='black',width='0.35'):
    item=QgsLayoutItemShape(layout);item.setShapeType(QgsLayoutItemShape.Rectangle)
    item.setSymbol(QgsFillSymbol.createSimple({'color':'255,255,255,0','outline_color':color,'outline_width':width}));return place(item,x,y,w,h)
mp=QgsLayoutItemMap(layout);place(mp,10,10,283,276);mp.setCrs(QgsCoordinateReferenceSystem('EPSG:32749'));mp.setLayers([area,ref]);mp.setKeepLayerSet(True);mp.zoomToExtent(ref.extent());mp.setFrameEnabled(True)
grid=mp.grid();grid.setEnabled(True);grid.setCrs(QgsCoordinateReferenceSystem('EPSG:32749'));grid.setIntervalX(500);grid.setIntervalY(500)
grid.setStyle(QgsLayoutItemMapGrid.FrameAnnotationsOnly);grid.setFrameStyle(QgsLayoutItemMapGrid.ExteriorTicks);grid.setFrameWidth(2)
grid.setAnnotationEnabled(True);grid.setAnnotationPrecision(0);grid.setAnnotationFont(QFont('Arial',9,QFont.Weight.Bold));grid.setAnnotationFontColor(QColor('#247daf'))
for side in [QgsLayoutItemMapGrid.Left,QgsLayoutItemMapGrid.Right]:grid.setAnnotationDirection(QgsLayoutItemMapGrid.VerticalDescending,side)
box(304,7,109,282);box(304,7,109,28);box(304,35,109,28)
label('PETA\nLOKASI PENELITIAN',305,8,107,25,23,True,center=True)
label('Kecamatan\nLakarsantri - Karang Pilang - Driyorejo\nSurabaya dan Gresik, Jawa Timur',305,37,107,24,11,True,'#0783ef',True)
north=QgsLayoutItemPicture(layout);place(north,326,71,22,28);north.setPicturePath('C:/OSGeo4W/apps/qgis/svg/arrows/NorthArrow_04.svg')
scale=QgsLayoutItemScaleBar(layout);scale.setStyle('Single Box');scale.setLinkedMap(mp);scale.applyDefaultSize();scale.setUnits(Qgis.DistanceUnit.Meters);scale.setUnitsPerSegment(100);scale.setNumberOfSegments(2);scale.setNumberOfSegmentsLeft(0);scale.setUnitLabel('m');scale.setHeight(2);place(scale,355,79,44,10)
label('Legenda',310,105,90,9,18,True)
box(311,120,10,6,'#e61419','0.9');label('Area Akuisisi',324,118,83,10,12)
box(311,131,10,6);label('Batas Kecamatan*',324,129,83,10,12)
label('Sistem koordinat\nWGS 84 / UTM zona 49S\nEPSG:32749',310,155,96,20,10)
label('*Batas dan label kecamatan mengikuti\ngambar acuan; belum berupa layer vektor.\nCitra acuan direferensikan dari grid UTM.\nBukan raster elevasi untuk perhitungan TC.',310,180,97,27,8)
inset=QgsLayoutItemPicture(layout);place(inset,305,224,107,63);inset.setPicturePath(os.path.join(out,'Inset_acuan.png'))
label('Sumber: Lokasi.png (citra/batas/inset)\ndan Area Akuisisi.gpkg (polygon).',310,212,96,10,8)
p.layoutManager().addLayout(layout)
p.setTitle('Lokasi Penelitian dan Persiapan Terrain Correction')
p.setFileName(os.path.join(out,'Lokasi_Penelitian_TC.qgz'));print('SAVED',p.write())
ex=QgsLayoutExporter(layout);settings=QgsLayoutExporter.ImageExportSettings();settings.dpi=180
print('PNG',ex.exportToImage(os.path.join(out,'Peta_Lokasi_Penelitian.png'),settings))
iface.mapCanvas().setExtent(ref.extent());iface.mapCanvas().refresh()
print('LAYOUT',layout.name())

