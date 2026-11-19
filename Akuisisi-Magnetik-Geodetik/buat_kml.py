"""Tugas Geodetik 4: KML titik GNSS dari 'Data Koordinat Geodetik.xlsx' untuk Google Earth."""
import sys
import openpyxl
from xml.sax.saxutils import escape

SRC, OUT = sys.argv[1], sys.argv[2]
ws = openpyxl.load_workbook(SRC).active
pts = []
for r in range(5, ws.max_row + 1):
    if not isinstance(ws.cell(r, 1).value, int):
        break
    pts.append([ws.cell(r, c).value for c in range(2, 11)])

marks = []
for name, lon, lat, e, n, h, N, H, acc in pts:
    desc = (f"<table border='1' cellpadding='3'>"
            f"<tr><td>Longitude</td><td>{lon:.9f}°</td></tr><tr><td>Latitude</td><td>{lat:.9f}°</td></tr>"
            f"<tr><td>UTM X (49S)</td><td>{e:.3f} m</td></tr><tr><td>UTM Y (49S)</td><td>{n:.3f} m</td></tr>"
            f"<tr><td>Ellipsoid Height h</td><td>{h:.4f} m</td></tr><tr><td>Geoid Undulation N</td><td>{N:.3f} m</td></tr>"
            f"<tr><td>Orthometric Height H</td><td>{H:.3f} m</td></tr></table>")
    marks.append(f"""    <Placemark>
      <name>{escape(str(name))}</name>
      <styleUrl>#titik</styleUrl>
      <description><![CDATA[{desc}]]></description>
      <Point><altitudeMode>clampToGround</altitudeMode><coordinates>{lon:.9f},{lat:.9f},0</coordinates></Point>
    </Placemark>""")
lon0 = sum(p[1] for p in pts) / len(pts); lat0 = sum(p[2] for p in pts) / len(pts)
kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Titik GNSS Geodetik - 18 Okt 2026</name>
    <description>Titik pengukuran GNSS ComNav T300 (WGS84), post-processing NRTK BIG, geoid INAGEOID2020 v2.</description>
    <LookAt><longitude>{lon0:.6f}</longitude><latitude>{lat0:.6f}</latitude><altitude>0</altitude>
      <heading>0</heading><tilt>0</tilt><range>450</range><altitudeMode>relativeToGround</altitudeMode></LookAt>
    <Style id="titik">
      <IconStyle><color>ff00ffff</color><scale>1.2</scale>
        <Icon><href>http://maps.google.com/mapfiles/kml/paddle/ylw-circle.png</href></Icon></IconStyle>
      <LabelStyle><color>ff00ffff</color><scale>1.3</scale></LabelStyle>
    </Style>
{chr(10).join(marks)}
  </Document>
</kml>
"""
open(OUT, "w", encoding="utf-8").write(kml)
print("saved", OUT, [p[0] for p in pts])
