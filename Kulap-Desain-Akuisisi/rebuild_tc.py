import os,json,math,csv
import numpy as np
from osgeo import gdal
from qgis.core import *
from qgis.PyQt.QtGui import QColor
gdal.UseExceptions()
p=QgsProject.instance();work=os.path.dirname(p.fileName());base=os.path.dirname(work)
out=os.path.join(work,'TC_Processing');os.makedirs(out,exist_ok=True)
area=p.mapLayersByName('Area Akuisisi')[0];stations=p.mapLayersByName('Titik Gravity')[0]
old_local=p.mapLayersByName('Lokal DEMNAS 10 m - CAKUPAN BELUM LENGKAP')[0]
old_single=p.mapLayersByName('DEMNAS 1608-41 | Elevasi UTM 49S (10 m)')[0]
names=['1508-62','1508-64','1608-41','1608-42','1608-43','1608-44']
inputs=[]
for name in names:
 src=os.path.join(base,'DEMNAS_'+name+'_v1.0.tif');ds=gdal.Open(src);gt=ds.GetGeoTransform();assert 110<gt[0]<115 and -10<gt[3]<-5
 v=os.path.join(out,'source_'+name+'.vrt');ds=gdal.Translate(v,src,format='VRT',outputSRS='EPSG:4326');ds=None;inputs.append(v)
vrt=os.path.join(out,'DEMNAS_Merge.vrt');ds=gdal.BuildVRT(vrt,inputs,srcNodata='nan',VRTNodata='nan');ds=None
mosaic=os.path.join(out,'DEMNAS_Merge_WGS84.tif');ds=gdal.Translate(mosaic,vrt,creationOptions=['COMPRESS=LZW','TILED=YES']);ds=None
# Recreate both metric buffers from the original survey polygon.
geom=QgsGeometry.unaryUnion([f.geometry() for f in area.getFeatures()]);geom.transform(QgsCoordinateTransform(area.crs(),QgsCoordinateReferenceSystem('EPSG:32749'),p))
gpkg=os.path.join(out,'Area_dan_Buffer.gpkg');buffers={}
for key,distance in [('Area_Akuisisi',0),('Buffer_Lokal_10km',10000),('Buffer_Regional_167km',167000)]:
 layer=QgsVectorLayer('MultiPolygon?crs=EPSG:32749',key,'memory');g=QgsGeometry(geom) if distance==0 else geom.buffer(distance,120);g.convertToMultiType();f=QgsFeature();f.setGeometry(g);layer.dataProvider().addFeatures([f]);layer.updateExtents()
 opt=QgsVectorFileWriter.SaveVectorOptions();opt.driverName='GPKG';opt.layerName=key
 if os.path.exists(gpkg):opt.actionOnExistingFile=QgsVectorFileWriter.CreateOrOverwriteLayer
 result=QgsVectorFileWriter.writeAsVectorFormatV3(layer,gpkg,p.transformContext(),opt);assert result[0]==QgsVectorFileWriter.NoError
 if distance:buffers[distance]=layer.extent()
def bounds(e,res):return [math.floor(e.xMinimum()/res)*res,math.floor(e.yMinimum()/res)*res,math.ceil(e.xMaximum()/res)*res,math.ceil(e.yMaximum()/res)*res]
bat=os.path.join(base,'BATNAS_110E-115E_10S-05S_MSL_v1.6.tif');report={'tiles':names,'crs':'EPSG:32749','method':'Merge DEMNAS; clip by buffer extent and reproject, bilinear','nodata':-9999,'outputs':{}}
paths={}
for key,source,radius,res in [('DEM_Lokal_10m',mosaic,10000,10),('DEM_Regional_200m',bat,167000,200)]:
 path=os.path.join(out,key+'.tif');paths[key]=path
 ds=gdal.Warp(path,source,srcSRS='EPSG:4326',dstSRS='EPSG:32749',outputBounds=bounds(buffers[radius],res),xRes=res,yRes=res,resampleAlg='bilinear',outputType=gdal.GDT_Float32,srcNodata=float('nan'),dstNodata=-9999,creationOptions=['COMPRESS=LZW','TILED=YES'])
 a=ds.ReadAsArray();valid=np.isfinite(a)&(a!=-9999);report['outputs'][key]={'source':'DEMNAS merge' if radius==10000 else 'BATNAS','radius_m':radius,'resolution_m':res,'shape':[ds.RasterYSize,ds.RasterXSize],'valid_pct':float(valid.mean()*100),'nodata_pixels':int((~valid).sum()),'min':float(a[valid].min()),'max':float(a[valid].max())};ds=None
 assert valid.all(),key+' contains NoData'
 ers=path.replace('.tif','.ers');ds=gdal.Translate(ers,path,format='ERS',outputType=gdal.GDT_Float32,noData=-9999);ds=None
 assert np.array_equal(gdal.Open(ers).ReadAsArray(),a)
 print(key,report['outputs'][key])
ds=gdal.Open(paths['DEM_Lokal_10m']);gt=ds.GetGeoTransform();a=ds.ReadAsArray()
with open(os.path.join(out,'Titik_Gravity_Z_DEM.csv'),'w',newline='',encoding='utf-8') as f:
 w=csv.writer(f);w.writerow(['Station','UTM_X','UTM_Y','Z_DEM_EGM2008_m','Sumber_Z'])
 for feat in stations.getFeatures():
  g=QgsGeometry(feat.geometry());g.transform(QgsCoordinateTransform(stations.crs(),QgsCoordinateReferenceSystem('EPSG:32749'),p));pt=g.asPoint();z=float(a[int((pt.y()-gt[3])/gt[5]),int((pt.x()-gt[0])/gt[1])]);assert z!=-9999 and np.isfinite(z)
  w.writerow([feat['Station'],round(pt.x(),3),round(pt.y(),3),round(z,3),'Estimasi DEM; bukan pengukuran lapangan'])
report['stations']=stations.featureCount();report['TC_computed']=False;report['vertical_datums']={'DEMNAS':'EGM2008','BATNAS':'MSL'}
with open(os.path.join(out,'QC.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
with open(os.path.join(out,'PETUNJUK.txt'),'w',encoding='utf-8') as f:f.write('INPUT OASIS MONTAJ - PERSIAPAN TC\nLokal: DEM_Lokal_10m.ers, dari merge 6 DEMNAS; extent buffer area 10 km; resolusi 10 m.\nRegional: DEM_Regional_200m.ers, dari BATNAS; extent buffer area 167 km; resolusi 200 m.\nCRS: WGS84 UTM49S. NoData -9999, bukan 0. Kedua grid telah diverifikasi penuh tanpa NoData.\nSimpan file .ers bersama file data bernama sama tanpa ekstensi.\nParameter PPT: densitas awal 2.67 g/cc, inner 10000 m, outer 167000 m.\nGrid regional masih elevasi, bukan hasil Create Regional Correction Grid. TC gravitasi belum dihitung.\nCSV Z merupakan estimasi DEM EGM2008, bukan elevasi pengukuran. BATNAS memakai MSL; kesesuaian datum vertikal harus dinilai sebelum TC final.\n')
# Build tidy project layers, update layouts before removing superseded layers.
newlocal=QgsRasterLayer(paths['DEM_Lokal_10m'],'DEM Lokal | DEMNAS | 10 m');newlocal.setRenderer(old_single.renderer().clone());p.addMapLayer(newlocal)
newreg=QgsRasterLayer(paths['DEM_Regional_200m'],'DEM Regional | BATNAS | 200 m');p.addMapLayer(newreg)
merge=QgsRasterLayer(mosaic,'DEMNAS | Gabungan 6 tile');p.addMapLayer(merge)
for layer in [newreg,merge]:
 stat=layer.dataProvider().bandStatistics(1,QgsRasterBandStats.All);sh=QgsColorRampShader();sh.setColorRampType(QgsColorRampShader.Interpolated);colors=['#244a85','#62b6c9','#d6e6b5','#b98a55','#f1f0eb'];lo=stat.minimumValue;hi=stat.maximumValue
 sh.setColorRampItemList([QgsColorRampShader.ColorRampItem(lo+(hi-lo)*i/4,QColor(c),str(round(lo+(hi-lo)*i/4))) for i,c in enumerate(colors)]);rs=QgsRasterShader();rs.setRasterShaderFunction(sh);rr=QgsSingleBandPseudoColorRenderer(layer.dataProvider(),1,rs);rr.setClassificationMin(lo);rr.setClassificationMax(hi);layer.setRenderer(rr)
newbuffers=[]
for key,title,color in [('Buffer_Lokal_10km','Buffer Lokal | 10 km','#222222'),('Buffer_Regional_167km','Buffer Regional | 167 km','#6f39a6')]:
 layer=QgsVectorLayer(gpkg+'|layername='+key,title,'ogr');layer.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':color,'outline_width':'0.4','outline_style':'dash'}));p.addMapLayer(layer);newbuffers.append(layer)
oldids={old_local.id(),old_single.id()}
for layout in p.layoutManager().layouts():
 for item in layout.items():
  if isinstance(item,QgsLayoutItemMap):item.setLayers([newlocal if x.id() in oldids else x for x in item.layers()])
  if isinstance(item,QgsLayoutItemLegend):
   for node in list(item.model().rootGroup().findLayers()):
    if node.layerId() in oldids:
     item.model().rootGroup().removeChildNode(node);node=item.model().rootGroup().addLayer(newlocal);node.setUseLayerName(False);node.setName('Elevasi (m)');QgsMapLayerLegendUtils.setLegendNodeOrder(node,[1]);item.model().refreshLayerLegend(node)
  if isinstance(item,QgsLayoutItemLabel) and 'Sumber: DEMNAS BIG 1608-41' in item.text():item.setText(item.text().replace('DEMNAS BIG 1608-41','DEMNAS BIG (merge 6 tile)'))
remove=[]
for layer in p.mapLayers().values():
 src=layer.source().replace('\\','/')
 if layer.id() in oldids or '/Processing_TC_4tile/' in src or 'Persiapan_TC.gpkg' in src:remove.append(layer.id())
p.removeMapLayers(remove)
sources=[]
for name in names:
 path=os.path.join(base,'DEMNAS_'+name+'_v1.0.tif');match=[x for x in p.mapLayers().values() if os.path.normcase(os.path.normpath(x.source()))==os.path.normcase(os.path.normpath(path))]
 layer=match[0] if match else QgsRasterLayer(path,'DEMNAS '+name)
 if not match:p.addMapLayer(layer)
 layer.setName('DEMNAS | '+name);layer.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'));sources.append(layer)
batlayer=next(x for x in p.mapLayers().values() if os.path.normcase(os.path.normpath(x.source()))==os.path.normcase(os.path.normpath(bat)));batlayer.setName('BATNAS | Sumber MSL');sources.append(batlayer)
root=p.layerTreeRoot();groups=[root.addGroup(n) for n in ['01 | Area dan Titik','02 | Buffer','03 | Grid untuk TC','04 | Data Sumber','05 | Referensi Peta']]
area.setName('Area Akuisisi');stations.setName('Titik Gravity | 90 titik')
assigned=[area,stations]+newbuffers+[newlocal,newreg,merge]+sources
other=[x for x in p.mapLayers().values() if x not in assigned]
for group,layers in zip(groups,[[area,stations],newbuffers,[newlocal,newreg,merge],sources,other]):
 for layer in layers:
  node=root.findLayer(layer.id());copy=node.clone();group.addChildNode(copy);node.parent().removeChildNode(node);copy.setItemVisibilityChecked(layer in [area,stations,newbuffers[0],newlocal])
for group in list(root.findGroups()):
 if group not in groups and not group.children():group.parent().removeChildNode(group)
for group in groups[3:]:group.setExpanded(False)
root.setHasCustomLayerOrder(False)
for layer in [newlocal,newreg,merge]:layer.saveNamedStyle(os.path.join(out,layer.name().split('|')[0].strip().replace(' ','_')+'.qml'))
e=QgsRectangle(newbuffers[0].extent());e.scale(1.08);iface.mapCanvas().setExtent(e);iface.mapCanvas().refresh();p.write()
layout=p.layoutManager().layoutByName('DEMNAS - A4 Landscape')
if layout:
 ex=QgsLayoutExporter(layout);s=QgsLayoutExporter.ImageExportSettings();s.dpi=300;assert ex.exportToImage(os.path.join(work,'Peta_DEMNAS_A4_Landscape.png'),s)==0
 layout.saveAsTemplate(os.path.join(work,'Layout_DEMNAS_A4.qpt'),QgsReadWriteContext())
print('COMPLETE',out)
