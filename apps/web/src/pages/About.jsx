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

// หน้าเกี่ยวกับเรา แบบหน้าเว็บทั่วไป: เรื่องที่มา ภารกิจ สิ่งที่ยึดถือ สิ่งที่ไม่ทำ ทีม เครดิตข้อมูล และปุ่มชวนเริ่มใช้
// ตัวเลขทุกตัวดึงจากระบบจริงตอนเปิดหน้า ยังโหลดไม่เสร็จแสดงขีด ไม่ใส่ตัวเลขเดา
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

  const values = [
    ['shield', t('ไม่เดา', 'No guessing'), t('ข้อมูลที่ไม่รู้ เราปล่อยว่าง ดีกว่าเติมคำเดาให้ดูครบ', 'If we don’t know it, we leave it blank rather than fill the gap with a guess.')],
    ['link', t('บอกที่มาทุกชิ้น', 'Every fact has a source'), t('ทุกสถานที่มีป้ายบอกว่ามาจากไหน กดไปดูต้นทางได้เสมอ', 'Every place says where it came from, and you can always open the original.')],
    ['compass', t('พูดตรงเรื่องระยะ', 'Honest about distance'), t('ระยะที่เห็นเป็นเส้นตรงจากที่พัก เราบอกชัด ไม่ให้เข้าใจผิดว่าเป็นระยะขับรถ', 'Distances are straight-line from your stay, and we say so plainly.')],
    ['check', t('คุณเป็นคนเลือก', 'You decide'), t('น้องทริปช่วยหา ไม่ตัดสินใจแทน ไม่ดันร้านไหนขึ้นมาก่อนเพราะผลประโยชน์', 'NongTrip helps you look. It never decides for you or pushes a place for profit.')],
  ];
  const nots = [
    [t('ไม่แต่งข้อมูล', 'No made-up facts'), t('เวลาเปิดปิดหรือค่าเข้าที่ไม่มีแหล่งยืนยัน จะไม่โผล่บนหน้าจอ', 'Opening hours or fees without a confirming source never appear.')],
    [t('ไม่มีราคาและรีวิวที่ยืนยันไม่ได้', 'No unverifiable prices or reviews'), t('อยากอ่านรีวิว เราส่งต่อให้ไปดูที่ Google Maps', 'Want reviews? We link you to Google Maps.')],
    [t('ไม่จองหรือรับเงินแทนคุณ', 'No bookings or payments'), t('เราไม่ใช่เอเจนซี่ ไม่มีค่าคอมมิชชัน', 'We are not an agency and earn no commission.')],
    [t('ไม่มีโฆษณาหรือตัวติดตาม', 'No ads or trackers'), t('ไม่เก็บสถิติผู้เข้าชม และไม่ขายข้อมูลของใคร', 'No visitor analytics, and nobody’s data is sold.')],
  ];

  return (
    <div className="nta">
      <section className="nta-hero nt-container">
        <div>
          <span className="nt-eyebrow"><span />{t('เรื่องของเรา', 'OUR STORY')}</span>
          <h1>{t('ทุกทริปดี ๆ', 'Every good trip')}<br /><span className="nt-highlight">{t('เริ่มจากที่พัก', 'starts at your stay')}</span></h1>
          <p>{t(
            'น้องทริปคือเพื่อนเที่ยวตัวเล็กที่ช่วยตอบคำถามแรกของทุกทริป: รอบที่พักมีอะไรน่าไปบ้าง ทั้ง 77 จังหวัด และบอกที่มาของทุกอย่างที่แนะนำ',
            'NongTrip is a little travel buddy that answers the first question of every trip: what’s worth visiting around your stay? In all 77 provinces, with a source for everything it suggests.',
          )}</p>
          <div className="nta-hero-actions">
            <Link className="nt-button nt-button-amber" to="/search">{t('ลองค้นรอบที่พัก', 'Explore around a stay')}<Icon /></Link>
            <a className="nt-text-link" href="#story">{t('อ่านเรื่องของเรา', 'Read our story')}<span>↓</span></a>
          </div>
        </div>
        <div className="nta-hero-art" aria-hidden="true">
          <div className="nta-ring nta-ring-1" /><div className="nta-ring nta-ring-2" />
          <Mascot size={250} mood="wave" interactive={false} />
          <span className="nta-chip nta-chip-1"><Icon name="pin" size={18} />{t('77 จังหวัด', '77 provinces')}</span>
          <span className="nta-chip nta-chip-2"><Icon name="link" size={18} />{t('บอกที่มาทุกชิ้น', 'Sourced')}</span>
          <span className="nta-chip nta-chip-3"><Icon name="cafe" size={18} />{t('ที่เที่ยว และคาเฟ่', 'Sights & cafés')}</span>
        </div>
      </section>

      <section id="story" className="nta-story nt-container">
        <div>
          <span className="nt-eyebrow"><span />{t('จุดเริ่มต้น', 'HOW IT STARTED')}</span>
          <h2>{t('จองที่พักเสร็จแล้ว', 'The stay is booked.')}<br />{t('...แล้วไปไหนต่อดี?', '…now what?')}</h2>
        </div>
        <div className="nta-story-body">
          <p>{t(
            'หลังกดจองที่พัก คำถามที่ตามมามักเหมือนกันทุกครั้ง แถวนี้มีอะไรเที่ยว คาเฟ่ไหนเดินไปได้ แล้วที่ไหนไกลเกินไปสำหรับวันเดียว',
            'Right after booking a stay, the same questions always follow. What is there to see nearby? Which café is walkable? What is too far for one day?',
          )}</p>
          <p>{t(
            'คำตอบกระจายอยู่หลายที่ ต้องเปิดแผนที่ ค้นทีละหมวด แล้วนั่งเทียบระยะเอง ข้อมูลที่เจอก็ไม่ค่อยบอกว่ามาจากไหน เชื่อได้แค่ไหน',
            'The answers are scattered. You open a map, search one category at a time and compare distances yourself, and most of what you find never says where it came from.',
          )}</p>
          <p>{t(
            'เราจึงทำน้องทริปขึ้นมา ให้ที่พักเป็นจุดเริ่มต้น แล้วพาไปดูว่ารอบตัวมีอะไร เรียงจากใกล้ไปไกล บนแผนที่เดียว พร้อมบอกที่มาของทุกข้อมูล',
            'So we built NongTrip. Your stay is the starting point, and everything around it is laid out nearest first on one map, each with its source.',
          )}</p>
          <p className="nta-sign">{t('— ทีมน้องทริป', '— The NongTrip team')}</p>
        </div>
      </section>

      <section className="nt-container">
        <div className="nta-mission">
          <div>
            <span className="nt-eyebrow"><span />{t('ภารกิจของเรา', 'OUR MISSION')}</span>
            <h2>{t('ให้ทุกทริปเริ่มต้นอย่างมั่นใจ ด้วยข้อมูลที่ตรวจสอบได้', 'Help every trip start with confidence, using information you can check.')}</h2>
          </div>
          <dl className="nta-stats" aria-live="polite">
            <div><dt>{t('จังหวัดที่ค้นรอบที่พักได้', 'provinces you can explore')}</dt><dd>{num(stats.provinces || 77)}</dd></div>
            <div><dt>{t('สถานที่ที่ทีมคัดเองพร้อมที่มา', 'places in our sourced dataset')}</dt><dd>{num(stats.verified)}</dd></div>
            <div><dt>{t('จังหวัดที่มีสถานที่จากชุดข้อมูลนี้', 'provinces covered by that dataset')}</dt><dd>{num(stats.withVerified)}</dd></div>
          </dl>
        </div>
      </section>

      <section className="nta-values nt-container">
        <div className="nt-section-heading">
          <span className="nt-eyebrow">{t('สิ่งที่เรายึดถือ', 'WHAT WE STAND FOR')}</span>
          <h2>{t('สัญญาสี่ข้อ ในทุกหน้าที่คุณเห็น', 'Four promises on every page')}</h2>
        </div>
        <ol>
          {values.map(([icon, title, body], i) => (
            <li key={icon}>
              <div className="nta-value-top"><span className="nta-value-icon"><Icon name={icon} size={26} /></span><span>0{i + 1}</span></div>
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="nta-nots">
        <div className="nt-container nta-nots-inner">
          <div>
            <span className="nt-eyebrow"><span />{t('สิ่งที่เราเลือกไม่ทำ', 'WHAT WE CHOOSE NOT TO DO')}</span>
            <h2>{t('บางอย่างไม่ทำ', 'Some things we')}<br />{t('เพราะอยากให้คุณเชื่อใจได้', 'leave out on purpose')}</h2>
            <p>{t('เว็บท่องเที่ยวส่วนใหญ่อยากให้คุณจองหรือซื้อ น้องทริปแค่อยากให้คุณรู้ว่ารอบตัวมีอะไร', 'Most travel sites want you to book or buy. NongTrip just wants you to know what’s around you.')}</p>
          </div>
          <ul>
            {nots.map(([title, body]) => (
              <li key={title}><span aria-hidden="true">✕</span><div><h3>{title}</h3><p>{body}</p></div></li>
            ))}
          </ul>
        </div>
      </section>

      <section className="nta-team nt-container">
        <div className="nt-section-heading">
          <span className="nt-eyebrow">{t('คนเบื้องหลัง', 'THE PEOPLE BEHIND IT')}</span>
          <h2>{t('ทีมเล็ก ๆ กับแมวส้มอีกหนึ่งตัว', 'A small team and one orange cat')}</h2>
          <p>{t('โครงงานวิชา Advanced Topics in Computer Software มหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี', 'A project for Advanced Topics in Computer Software, Rajamangala University of Technology Thanyaburi')}</p>
        </div>
        <ul>
          <li>
            <span className="nta-avatar" aria-hidden="true">J</span>
            <h3>Jakkrich</h3>
            <small>{t('ระบบค้นหาและแชตบอท', 'Search and chatbot')}</small>
            <p>{t('ดูแลเครื่องมือค้น API ตัวตรวจผลค้น แชตบอท และหน้าค้นหา', 'Builds the search engine, API, result checker, chatbot and search page.')}</p>
          </li>
          <li>
            <span className="nta-avatar nta-avatar-2" aria-hidden="true">J</span>
            <h3>Jirapa Gongmool</h3>
            <small>{t('ประสบการณ์ผู้ใช้และข้อมูล', 'Experience and data')}</small>
            <p>{t('ดูแลหน้าแรก หน้าเข้าสู่ระบบและทริปของฉัน ข้อมูลที่ตรวจแล้ว และชุดทดสอบ', 'Builds the home, sign-in and My trips pages, the verified data and the test set.')}</p>
          </li>
          <li className="nta-team-cat">
            <Mascot size={86} mood="happy" interactive={false} />
            <h3>{t('น้องทริป', 'NongTrip')}</h3>
            <small>{t('เพื่อนร่วมทริป', 'Travel buddy')}</small>
            <p>{t('แมวส้มนักสำรวจ เดินตามคุณทุกหน้า กดแล้วคุยด้วยได้เลย', 'An orange explorer cat who follows you on every page. Tap to chat.')}</p>
          </li>
        </ul>
      </section>

      <section className="nta-credits nt-container" aria-labelledby="nta-credits-title">
        <h2 id="nta-credits-title">{t('ขอบคุณข้อมูลจากชุมชน', 'Built on community data')}</h2>
        <p>{t('น้องทริปเป็นไปได้เพราะข้อมูลที่อาสาสมัครทั่วโลกช่วยกันสร้างและเปิดให้ทุกคนใช้', 'NongTrip exists thanks to data that volunteers around the world create and share openly.')}</p>
        <div className="nta-credit-list">
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
            <strong>OpenStreetMap</strong>
            <span>{t('ที่พัก ที่เที่ยว คาเฟ่ และแผนที่', 'Stays, sights, cafés and maps')}</span>
            <small>ODbL · © OpenStreetMap contributors</small>
          </a>
          <a href="https://creativecommons.org/licenses/by-sa/4.0/" target="_blank" rel="noreferrer">
            <strong>Wikipedia</strong>
            <span>{t('ชื่อ พิกัด และข้อความที่แชตใช้ตอบ', 'Names, coordinates and chat passages')}</span>
            <small>CC BY-SA 4.0</small>
          </a>
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            <strong>{t('ซอร์สโค้ดเปิด', 'Open source')}</strong>
            <span>{t('ตรวจได้ทุกบรรทัดบน GitHub', 'Every line is on GitHub')}</span>
            <small>github.com/jakkrich0912-web/nongtrip</small>
          </a>
        </div>
        <p className="nta-credit-note">{t('Google Maps ใช้แค่ลิงก์นำทางและดูรีวิว ', 'Google Maps is used only for directions and review links. ')}<Link to="/privacy">{t('อ่านว่าเราเก็บข้อมูลอะไรบ้าง', 'See what data we keep')}</Link></p>
      </section>

      <section className="nt-start nt-container">
        <div className="nt-start-inner">
          <Mascot mood="front" size={150} interactive={false} />
          <div>
            <span className="nt-eyebrow">{t('พร้อมออกเดินทางหรือยัง', 'READY WHEN YOU ARE')}</span>
            <h2>{t('บอกชื่อที่พักมา เดี๋ยวน้องทริปพาไปดูรอบ ๆ', 'Tell us your stay, and we’ll show you around')}</h2>
            <p>{t('ไม่ต้องสมัคร เริ่มได้เลย', 'No account needed')}</p>
          </div>
          <Link to="/search" className="nt-button nt-button-amber">{t('เริ่มสำรวจเลย', 'Let’s explore')}<Icon /></Link>
        </div>
      </section>
    </div>
  );
}
