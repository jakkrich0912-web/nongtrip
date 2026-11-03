import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import Icon from '../components/landing/Icon.jsx';
import { provincesList, systemHealth } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';
import { REPO_URL } from './Privacy.jsx';
import './info.css';

// รวมตัวเลขจาก GET /api/provinces: จังหวัดทั้งหมด จังหวัดที่มีสถานที่ที่ตรวจแล้ว
export function coverageOf(data) {
  const all = (data?.regions ?? []).flatMap((r) => r.provinces ?? []);
  return { provinces: all.length, withVerified: all.filter((p) => p.verified_count > 0).length };
}

// หน้าเกี่ยวกับเรา: น้องทริปคืออะไร หลักการ ข้อมูลมาจากไหนพร้อมสัญญาอนุญาต ตัวเลขจริงตอนนี้ และทีม
export default function About() {
  const { t } = useLanguage();
  const [stats, setStats] = useState({ verified: null, provinces: null, withVerified: null });
  useEffect(() => {
    let live = true;
    systemHealth().then((d) => live && setStats((s) => ({ ...s, verified: d?.verified_places ?? null }))).catch(() => {});
    provincesList().then((d) => live && setStats((s) => ({ ...s, ...coverageOf(d) }))).catch(() => {});
    return () => { live = false; };
  }, []);
  const num = (n) => (n == null ? '–' : n.toLocaleString());

  const sources = [
    ['OpenStreetMap', t('ที่พัก ที่เที่ยว และคาเฟ่ทั่วประเทศ (ชื่อ ประเภท พิกัด) ผ่าน Nominatim และ Overpass บางจังหวัดดึงเก็บไว้ล่วงหน้า และภาพแผนที่', 'Stays, attractions and cafés nationwide (name, type, coordinates) via Nominatim and Overpass, a pre-fetched copy for some provinces, and the map images'), 'ODbL · © OpenStreetMap contributors', 'https://www.openstreetmap.org/copyright'],
    ['Wikipedia', t('ชื่อและพิกัดของสถานที่ที่ตรวจที่มาแล้ว และข้อความจากบทความที่แชตใช้เรียบเรียงคำตอบ (มีที่มาใต้คำตอบทุกครั้ง)', 'Names and coordinates of verified places, and the article passages chat uses to write answers (always cited under the answer)'), 'CC BY-SA 4.0', 'https://creativecommons.org/licenses/by-sa/4.0/'],
    ['Google Maps', t('เฉพาะปุ่มนำทางและลิงก์ดูรีวิว เปิดเมื่อคุณกด เราไม่ดึงข้อมูลจาก Google มาแสดง', 'Only the directions button and the review link, opened when you tap them. We show no Google data.'), t('ลิงก์ออกเท่านั้น', 'Outbound links only'), null],
    [t('โมเดลภาษา', 'Language model'), t('เรียบเรียงคำตอบในแชตจากข้อความที่ระบบค้นได้ ทุกคำตอบผ่านด่านตรวจ ไม่ผ่านจะตอบด้วยกฎแทน', 'Writes chat answers from retrieved passages. Every answer is checked; failures fall back to rule-based replies.'), t('ไม่ใช่แหล่งข้อมูล', 'Not a data source'), null],
  ];

  return (
    <div className="nti-page nt-container">
      <nav className="nti-crumbs" aria-label={t('ตำแหน่งหน้า', 'Breadcrumb')}>
        <Link to="/">{t('หน้าแรก', 'Home')}</Link><span aria-hidden="true">›</span><span>{t('เกี่ยวกับเรา', 'About')}</span>
      </nav>
      <header className="nti-hero">
        <div>
          <span className="nt-eyebrow"><span />{t('เกี่ยวกับน้องทริป', 'ABOUT NONGTRIP')}</span>
          <h1>{t('เพื่อนเที่ยวที่บอกที่มาเสมอ', 'A travel buddy that shows its sources')}</h1>
          <p>{t(
            'น้องทริปช่วยหาที่เที่ยวและคาเฟ่รอบที่พักทั้ง 77 จังหวัด พิมพ์ชื่อที่พัก ปักหมุด หรือถามในแชต แล้วดูว่ามีอะไรใกล้ ๆ เรียงจากใกล้ไปไกล ทุกข้อมูลบอกที่มา และข้อมูลที่ไม่รู้ เราไม่เดา',
            'NongTrip helps you find attractions and cafés around your stay in all 77 provinces. Type your stay, drop a pin or ask in chat, then see what is nearby, nearest first. Every fact shows its source, and we never guess what we do not know.',
          )}</p>
        </div>
        <Mascot size={150} mood="front" interactive={false} />
      </header>

      <section className="nti-section">
        <h2>{t('หลักการของเรา', 'Our principles')}</h2>
        <ul className="nti-cards">
          <li><span><Icon name="shield" size={20} /></span><strong>{t('ไม่เดา', 'No guessing')}</strong><p>{t('ค่าที่ไม่รู้เก็บเป็นค่าว่างและไม่แสดง ไม่เติมคำเดาให้ดูครบ', 'Unknown values stay empty and hidden. We never fill gaps with guesses.')}</p></li>
          <li><span><Icon name="link" size={20} /></span><strong>{t('บอกที่มาทุกชิ้น', 'Every fact has a source')}</strong><p>{t('ป้ายบอกว่าสถานที่ตรวจแล้วหรือมาจาก OpenStreetMap พร้อมสัญญาอนุญาต', 'Labels show whether a place is verified or from OpenStreetMap, with its licence.')}</p></li>
          <li><span><Icon name="compass" size={20} /></span><strong>{t('ระยะเป็นเส้นตรง', 'Straight-line distance')}</strong><p>{t('บอกชัดทุกที่ว่าไม่ใช่ระยะขับรถ ถ้าจะไปจริงกดนำทางด้วย Google Maps', 'Always labelled as not driving distance. Tap directions to plan the real route.')}</p></li>
          <li><span><Icon name="check" size={20} /></span><strong>{t('ไม่มีราคา รีวิว หรือการจอง', 'No prices, reviews or bookings')}</strong><p>{t('เราไม่มีแหล่งยืนยันข้อมูลพวกนี้ จึงไม่แสดง และไม่จองหรือชำระเงินแทนคุณ', 'We cannot verify them, so we do not show them, and we never book or pay for you.')}</p></li>
        </ul>
      </section>

      <section className="nti-section">
        <h2>{t('ข้อมูลตอนนี้', 'Coverage right now')}</h2>
        <div className="nti-stats" aria-live="polite">
          <div><b>{num(stats.provinces || 77)}</b><small>{t('จังหวัดที่ค้นรอบที่พักได้ ผ่าน OpenStreetMap', 'provinces you can search around a stay, via OpenStreetMap')}</small></div>
          <div><b>{num(stats.verified)}</b><small>{t('สถานที่ในชุดข้อมูลที่ทีมคัดเองพร้อมที่มา', 'places in the team’s own sourced dataset')}</small></div>
          <div><b>{num(stats.withVerified)}</b><small>{t('จังหวัดที่มีสถานที่จากชุดข้อมูลของทีมอย่างน้อย 1 แห่ง', 'provinces with at least one place from that dataset')}</small></div>
        </div>
        <p>{t('ตัวเลขนี้ดึงจากระบบตอนเปิดหน้า ', 'These numbers come live from the system. ')}<Link to="/provinces">{t('ดูรายจังหวัด →', 'See each province →')}</Link></p>
      </section>

      <section className="nti-section">
        <h2>{t('ข้อมูลมาจากไหน', 'Where the data comes from')}</h2>
        <div className="nti-table-wrap">
          <table className="nti-table">
            <thead><tr><th>{t('แหล่ง', 'Source')}</th><th>{t('ใช้ทำอะไร', 'Used for')}</th><th>{t('สัญญาอนุญาต', 'Licence')}</th></tr></thead>
            <tbody>
              {sources.map(([name, use, licence, href]) => (
                <tr key={name}><td>{name}</td><td>{use}</td><td>{href ? <a href={href} target="_blank" rel="noreferrer">{licence}</a> : licence}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>{t('เราตรวจสถานที่อย่างไร', 'How we verify places')}</h3>
        <p>{t(
          'สถานที่ในชุดข้อมูลของทีมส่วนใหญ่ เราจับคู่กับบทความ Wikipedia แล้วเทียบพิกัดกับขอบเขตของจังหวัด รายการที่พิกัดไม่เข้าพวกถูกตัดออก ข้อมูลอย่างเวลาเปิดปิดหรือค่าเข้าที่ไม่มีแหล่งยืนยันจะไม่แสดง ข้อมูลจาก OpenStreetMap มีแค่ชื่อ ประเภท และพิกัด คุณภาพต่างกันไปตามพื้นที่ เพราะเป็นข้อมูลที่อาสาสมัครช่วยกันเขียน',
          'Most places in the team’s dataset were matched to a Wikipedia article and their coordinates checked against the province. Mismatches were removed. Facts without a confirming source, such as opening hours or fees, are not shown. OpenStreetMap data has only name, type and coordinates, and its quality varies by area because volunteers write it.',
        )}</p>
      </section>

      <section className="nti-section">
        <h2>{t('ผู้จัดทำ', 'The team')}</h2>
        <ul className="nti-team">
          <li><strong>Jakkrich</strong><small>@jakkrich0912-web</small><p>{t('ระบบค้นหา API ตัวตรวจผลค้น แชตบอท และหน้าค้นหา', 'Search engine, API, result validator, chatbot and the search page')}</p></li>
          <li><strong>Jirapa Gongmool</strong><small>@jirapa-gm</small><p>{t('หน้าแรก หน้าเข้าสู่ระบบและทริปของฉัน ข้อมูลที่ตรวจแล้ว ชุดทดสอบ และสไลด์', 'Home page, sign-in and My trips, verified data, test set and slides')}</p></li>
        </ul>
        <p>{t(
          'โครงงานวิชา Advanced Topics in Computer Software มหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี ซอร์สโค้ดทั้งหมดอยู่บน ',
          'A project for Advanced Topics in Computer Software, Rajamangala University of Technology Thanyaburi. All source code is on ',
        )}<a href={REPO_URL} target="_blank" rel="noreferrer">GitHub</a></p>
        <p><Link to="/privacy">{t('อ่านว่าเราเก็บข้อมูลอะไรบ้าง →', 'Read what data we keep →')}</Link></p>
      </section>
    </div>
  );
}
