import os,json,csv,math
import numpy as np
from osgeo import gdal
from qgis.core import *
gdal.UseExceptions()
p=QgsProject.instance();base=os.path.dirname(os.path.dirname(p.fileName()))
out=os.path.join(os.path.dirname(p.fileName()),'Processing_TC_4tile');os.makedirs(out,exist_ok=True)
names=['1508-62','1508-64','1608-41','1608-43'];inputs=[]
for name in names:
 src=os.path.join(base,'DEMNAS_'+name+'_v1.0.tif')
 vrt=os.path.join(out,'source_'+name+'.vrt')
 ds=gdal.Translate(vrt,src,format='VRT',outputSRS='EPSG:4326');ds=None;inputs.append(vrt)
 for layer in p.mapLayersByName('DEMNAS_'+name+'_v1.0'):layer.setCrs(QgsCoordinateReferenceSystem('EPSG:4326'))
vrt=os.path.join(out,'DEMNAS_4tile_mosaic.vrt');ds=gdal.BuildVRT(vrt,inputs,srcNodata='nan',VRTNodata='nan');ds=None
mosaic=os.path.join(out,'DEMNAS_4tile_WGS84.tif');ds=gdal.Translate(mosaic,vrt,creationOptions=['COMPRESS=LZW','TILED=YES']);ds=None
print('Mosaic complete')
def bounds(layer,res):
 e=layer.extent();return [math.floor(e.xMinimum()/res)*res,math.floor(e.yMinimum()/res)*res,math.ceil(e.xMaximum()/res)*res,math.ceil(e.yMaximum()/res)*res]
local=p.mapLayersByName('Buffer lokal 10 km')[0];regional=p.mapLayersByName('Buffer regional 167 km')[0]
bat=r'D:\1. LAKSA\1. ITS BOYYY\3. Semester 3\7. Prak. EGBM\W10\Data Gravity\DEMNAS & BATNAS\BATNAS_110E-115E_10S-05S_MSL_v1.6.tif'
report={'source_tiles':names,'horizontal_crs':'EPSG:32749','nodata':-9999,'density_for_later_TC_g_cm3':2.67,'local_radius_m':10000,'regional_radius_m':167000,'outputs':{}}
results=[]
for title,source,buffer,res in [('Local_10m_INCOMPLETE',mosaic,local,10),('Regional_200m',bat,regional,200)]:
 dest=os.path.join(out,title+'.tif')
 ds=gdal.Warp(dest,source,srcSRS='EPSG:4326',dstSRS='EPSG:32749',outputBounds=bounds(buffer,res),xRes=res,yRes=res,resampleAlg='bilinear',outputType=gdal.GDT_Float32,srcNodata=float('nan'),dstNodata=-9999,creationOptions=['COMPRESS=LZW','TILED=YES'])
 ar=ds.GetRasterBand(1).ReadAsArray();valid=np.isfinite(ar)&(ar!=-9999)
 report['outputs'][title]={'resolution_m':res,'width':ds.RasterXSize,'height':ds.RasterYSize,'valid_pct':100*float(valid.mean()),'nodata_count':int((~valid).sum()),'valid_min':float(ar[valid].min()),'valid_max':float(ar[valid].max())};ds=None
 ers=os.path.join(out,title+'.ers');e=gdal.Translate(ers,dest,format='ERS',outputType=gdal.GDT_Float32,noData=-9999);e=None
 check=gdal.Open(ers);assert check is not None;assert check.RasterXSize==ar.shape[1];check=None
 results.append(dest)
 print(title,json.dumps(report['outputs'][title]))
# Sample elevations only as DEM-derived estimates; do not overwrite measured station heights.
dem=gdal.Open(results[0]);gt=dem.GetGeoTransform();arr=dem.GetRasterBand(1).ReadAsArray()
stations=p.mapLayersByName('Titik Gravity')[0]
csvpath=os.path.join(out,'Stations_Z_DEM_ESTIMATED.csv')
with open(csvpath,'w',newline='',encoding='utf-8') as f:
 writer=csv.writer(f);writer.writerow(['Station','UTM_X','UTM_Y','Z_DEM_EGM2008_m','Elevation_source'])
 for feat in stations.getFeatures():
  geom=QgsGeometry(feat.geometry());geom.transform(QgsCoordinateTransform(stations.crs(),QgsCoordinateReferenceSystem('EPSG:32749'),p));pt=geom.asPoint();col=int((pt.x()-gt[0])/gt[1]);row=int((pt.y()-gt[3])/gt[5]);z=float(arr[row,col]);assert np.isfinite(z) and z!=-9999
  writer.writerow([feat['Station'],round(pt.x(),3),round(pt.y(),3),round(z,3),'DEM estimate; not surveyed elevation'])
report['station_count']=stations.featureCount();report['station_elevation_status']='DEM estimates only, not surveyed heights'
report['vertical_datums']={'local':'EGM2008','regional':'MSL (source BATNAS); compatibility must be assessed before final TC'}
report['status']='LOCAL COVERAGE INCOMPLETE; no final terrain correction computed'
with open(os.path.join(out,'QC_processing.json'),'w',encoding='utf-8') as f:json.dump(report,f,indent=2)
with open(os.path.join(out,'README.txt'),'w',encoding='utf-8') as f:
 f.write('Merge 4 tile DEMNAS dan persiapan grid sesuai PPT slide 36-43.\nLocal: extent buffer 10 km, UTM49S, 10 m, bilinear. Regional: extent buffer 167 km, UTM49S, 200 m, bilinear.\nDEMNAS asli tidak diubah. NoData -9999 dipertahankan; tidak diisi 0.\nLocal_10m_INCOMPLETE.ers BELUM siap untuk TC final: sisi timur perlu tile 1608-42 dan 1608-44.\nFile .ers adalah header: simpan bersama file data dengan nama sama tanpa ekstensi.\nZ stasiun dalam CSV adalah estimasi DEM EGM2008, bukan elevasi hasil pengukuran.\nDatum vertikal BATNAS MSL dan DEMNAS EGM2008 perlu diperiksa sebelum TC final.\nParameter Oasis sesuai PPT: density awal 2.67 g/cc, inner 10000 m, outer 167000 m.\nBelum menjalankan Create Regional Correction Grid atau Terrain Corrections di Oasis; raster regional ini adalah elevasi, bukan grid koreksi gravitasi.\n')
group=p.layerTreeRoot().addGroup('Processing TC - 4 tile (lokal belum lengkap)')
new=[]
old=p.mapLayersByName('DEMNAS 1608-41 | Elevasi UTM 49S (10 m)')[0]
for path,name in [(mosaic,'DEMNAS gabungan 4 tile - WGS84'),(results[1],'Regional BATNAS 200 m - elevasi'),(results[0],'Lokal DEMNAS 10 m - CAKUPAN BELUM LENGKAP')]:
 layer=QgsRasterLayer(path,name);assert layer.isValid();layer.setRenderer(old.renderer().clone());p.addMapLayer(layer,False);node=group.addLayer(layer);node.setItemVisibilityChecked(path==results[0]);new.append(layer)
root=p.layerTreeRoot()
for layer in p.mapLayers().values():
 if layer.id() not in [new[-1].id()] and (layer.name().startswith('DEMNAS') or layer.name().startswith('Google')):root.findLayer(layer.id()).setItemVisibilityChecked(False)
area=p.mapLayersByName('Area Akuisisi')[0]
local.renderer().setSymbol(QgsFillSymbol.createSimple({'color':'0,0,0,0','outline_color':'20,20,20,255','outline_width':'0.4','outline_style':'dash'}));root.findLayer(local.id()).setItemVisibilityChecked(True)
order=[area,stations,local,new[-1]];root.setHasCustomLayerOrder(True);root.setCustomLayerOrder(order+[x for x in p.mapLayers().values() if x not in order])
view=QgsRectangle(local.extent());view.scale(1.08);iface.mapCanvas().setExtent(view);iface.mapCanvas().refresh();p.write()
print('DONE',out)
