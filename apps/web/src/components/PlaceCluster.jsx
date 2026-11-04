// หมุดสถานที่บนแผนที่หน้าค้นหา รวมหมุดที่ซ้อนกันเป็นวงตัวเลขเมื่อซูมออก กดวงแล้วซูมเข้า
// ใช้ leaflet.markercluster (MIT) หมุดที่พักและหมุดที่ผู้ใช้ปักไม่อยู่ในกลุ่มนี้ จึงไม่ถูกรวม
import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.markercluster';
import 'leaflet.markercluster/dist/MarkerCluster.css';

const clusterIcon = (cluster) => L.divIcon({
  className: 'nt-cluster',
  html: `<span>${cluster.getChildCount()}</span>`,
  iconSize: [36, 36],
});

// ชื่อสถานที่มาจาก OSM ใส่เป็นข้อความเท่านั้น ไม่ใส่เป็น HTML
const popupNode = (text) => {
  const el = document.createElement('span');
  el.textContent = text;
  return el;
};

export default function PlaceCluster({ places, activeId, icon, activeIcon, label, onPick }) {
  const map = useMap();
  const group = useRef(null);
  const markers = useRef(new Map());
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    const g = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 48, spiderfyOnMaxZoom: true, iconCreateFunction: clusterIcon });
    map.addLayer(g);
    group.current = g;
    return () => { map.removeLayer(g); group.current = null; };
  }, [map]);

  useEffect(() => {
    const g = group.current;
    if (!g) return;
    g.clearLayers();
    markers.current = new Map();
    const list = places.map((p) => {
      const m = L.marker([p.lat, p.lon], { icon, title: label(p).title });
      m.bindPopup(popupNode(label(p).popup));
      m.on('click', () => pick.current(p));
      markers.current.set(p.id, m);
      return m;
    });
    g.addLayers(list);
  }, [places, icon, label]);

  // เปลี่ยนเฉพาะไอคอนของหมุดที่เลือก ไม่สร้างหมุดใหม่ทั้งชุด (ป๊อปอัปที่เปิดอยู่จะได้ไม่ปิดเอง)
  useEffect(() => {
    const m = activeId != null ? markers.current.get(activeId) : null;
    if (!m) return undefined;
    m.setIcon(activeIcon);
    return () => m.setIcon(icon);
  }, [activeId, places, icon, activeIcon]);

  return null;
}
