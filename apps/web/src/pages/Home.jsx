import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { PROVINCES } from '../lib/provinces.js';
import { PLACES, subtypeLabel, iconGroup } from '../lib/data.js';
import { placesAround } from '../lib/geo.js';
import CatIcon from '../components/CatIcon.jsx';
import Mascot from '../components/Mascot.jsx';

// จุดตัวอย่าง: ย่านนิมมานฯ เชียงใหม่ ผลที่แสดงคำนวณจากข้อมูลจริงในระบบ
const DEMO = { lat: 18.7965, lon: 98.9677, name: 'ย่านนิมมานเหมินท์ เชียงใหม่' };

export default function Home() {
  const [prov, setProv] = useState('');
  const nav = useNavigate();
  const go = (e) => { e.preventDefault(); if (prov) nav(`/search?province=${encodeURIComponent(prov)}`); };

  const demo = useMemo(() => placesAround(DEMO, PLACES).slice(0, 4), []);
  const topProv = useMemo(() => {
    const c = {};
    PLACES.forEach((p) => { c[p.province] = (c[p.province] ?? 0) + 1; });
    return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, []);
  const byCat = useMemo(() => {
    const m = {};
    PLACES.forEach((p) => { (m[p.subtype] ??= []).push(p); });
    return Object.entries(m).sort((a, b) => b[1].length - a[1].length);
  }, []);

  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <h1>จองที่พักแล้ว<br />ไปไหนต่อดี</h1>
          <p>ปักหมุดที่พักของคุณ แล้วดูที่เที่ยวในรัศมี 30 กม. เรียงจากใกล้ไปไกล พร้อมปุ่มนำทางไปทีละที่</p>
          <form className="picker" onSubmit={go}>
            <select value={prov} onChange={(e) => setProv(e.target.value)} aria-label="จังหวัดที่จะไป">
              <option value="">จะไปจังหวัดไหน</option>
              {PROVINCES.map((p) => <option key={p}>{p}</option>)}
            </select>
            <button className="btn" disabled={!prov}>ดูรอบที่พัก</button>
          </form>
          <div className="facts">
            <div><strong>77</strong>จังหวัด</div>
            <div><strong>{PLACES.length}</strong>สถานที่ที่ตรวจที่มาแล้ว</div>
            <div><strong>30 กม.</strong>รัศมีรอบที่พัก</div>
          </div>
        </div>

        <div className="demo-wrap">
        <div className="buddy">
          <Mascot size={96} />
          <span className="bubble">ลองปักหมุดที่พักดูนะ!</span>
        </div>
        <div className="demo" aria-label="ตัวอย่างผลค้น">
          <div className="demo-map" aria-hidden="true">
            <span className="r r3" /><span className="r r2" /><span className="r r1" />
            <i className="home" />
            {demo.map((p, k) => {
              const dx = (p.lon - DEMO.lon) * 900, dy = (DEMO.lat - p.lat) * 900;
              return <em key={p.id} className="dpin" style={{ left: `calc(50% + ${Math.max(-46, Math.min(46, dx))}%)`, top: `calc(50% + ${Math.max(-40, Math.min(40, dy))}%)`, animationDelay: `${0.9 + k * 0.12}s` }} />;
            })}
          </div>
          <div className="demo-list">
            <p className="demo-from">ที่พักตัวอย่าง: {DEMO.name}</p>
            {demo.map((p) => (
              <div key={p.id} className="demo-row">
                <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={18} /></span>
                <span className="demo-name">{p.name_th}<small>{subtypeLabel(p.subtype, p.kind)}</small></span>
                <span className="demo-km">{p.distance_km} กม.<small>เส้นตรง</small></span>
              </div>
            ))}
          </div>
        </div>
        </div>
      </section>

      <section className="band how">
        <h2>สามขั้นจากที่พักถึงที่เที่ยว</h2>
        <ol className="steps">
          <li><b>1</b><h3>ปักหมุดที่พัก</h3><p>เลือกจังหวัด แล้วแตะบนแผนที่ตรงที่พักของคุณ</p></li>
          <li><b>2</b><h3>ดูรอบตัว 30 กม.</h3><p>สถานที่เรียงจากใกล้ไปไกล กรองตามประเภทได้</p></li>
          <li><b>3</b><h3>กดนำทาง</h3><p>เปิด Google Maps นำทาง หรือไปอ่านรีวิวจริงก่อนไป</p></li>
        </ol>
      </section>

      <section className="band">
        <div className="band-head">
          <h2>เที่ยวแบบไหนดี</h2>
          <p>ทุกแห่งตรวจที่มาของพิกัดแล้ว</p>
        </div>
        <div className="cats">
          {byCat.map(([c, list]) => (
            <article key={c} className={`cat c-${c}`}>
              <div className="cat-top">
                <span className="ico big"><CatIcon cat={c} size={26} /></span>
                <span className="cat-n">{list.length} แห่ง</span>
              </div>
              <h3>{subtypeLabel(c)}</h3>
              <ul>{list.slice(0, 3).map((p) => <li key={p.id}>{p.name_th}<small>{p.province}</small></li>)}</ul>
            </article>
          ))}
        </div>
      </section>

      <section className="band provs">
        <div className="band-head">
          <h2>จังหวัดที่มีข้อมูลมากที่สุด</h2>
          <p>ข้อมูลจังหวัดอื่นกำลังทยอยเพิ่ม</p>
        </div>
        <div className="prov-grid">
          {topProv.map(([p, n]) => (
            <Link key={p} to={`/search?province=${encodeURIComponent(p)}`} className="prov">
              <span>{p}</span><small>{n} แห่ง</small>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
