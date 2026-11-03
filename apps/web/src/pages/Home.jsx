import { Link } from 'react-router-dom';
import { useLanguage } from '../lib/language.jsx';
import Mascot from '../components/Mascot.jsx';
import Icon from '../components/landing/Icon.jsx';
import ExploreDemo from '../components/landing/ExploreDemo.jsx';

function Hero() {
  const { t } = useLanguage();
  return <section className="nt-hero nt-container">
    <div className="nt-hero-copy">
      <span className="nt-eyebrow"><span />{t('เพื่อนตัวเล็ก สำหรับทริปของคุณ', 'A LITTLE FRIEND FOR YOUR NEXT ADVENTURE')}</span>
      <h1>{t('จองที่พักแล้ว', 'Stay booked.')}<br /><span className="nt-highlight">{t('ไปไหนต่อดี?', 'What’s nearby?')}</span></h1>
      <p>{t('ให้น้องทริปพาไปรู้จักที่เที่ยวและคาเฟ่รอบที่พัก', 'Meet the places and cafés around your stay.')}<br className="nt-desktop-break" />{t('ดูบนแผนที่ เลือกที่ถูกใจ แล้วออกไปเที่ยวกัน', 'Find your favorites on the map. Then go explore.')}</p>
      <div className="nt-hero-actions"><Link className="nt-button nt-button-amber" to="/search">{t('ค้นหารอบที่พัก', 'Explore around my stay')}<Icon /></Link><a className="nt-text-link" href="#try-it">{t('ลองเล่นตัวอย่าง', 'Try the demo')}<span>↘</span></a></div>
      <div className="nt-hero-note"><Icon name="check" size={16} />{t('เริ่มค้นหาได้เลย โดยไม่ต้องสมัครสมาชิก', 'Start exploring without an account')}</div>
    </div>
    <div className="nt-hero-art" aria-label={t('น้องทริป แมวส้มนักสำรวจ', 'NongTrip, your orange explorer cat')}>
      <div className="nt-orbit nt-orbit-outer" /><div className="nt-orbit nt-orbit-middle" /><div className="nt-orbit nt-orbit-inner" />
      <span className="nt-art-spark nt-spark-one">✦</span><span className="nt-art-spark nt-spark-two">✧</span>
      <span className="nt-orbit-pin nt-pin-one"><Icon name="pin" size={24} /></span><span className="nt-orbit-pin nt-pin-two"><Icon name="cafe" size={25} /></span>
      <span className="nt-speech">{t('แถวนี้มีอะไรน่าเที่ยวบ้างนะ?', 'Let’s see what’s around!')}</span>
      <Mascot size={298} mood="front" className="nt-hero-mascot" />
      <div className="nt-mascot-name"><span>สวัสดี! Hello!</span><strong>{t('เราชื่อน้องทริป', 'I’m NongTrip')}</strong><Icon name="compass" size={26} /></div>
      <span className="nt-art-caption">A LITTLE CURIOUS. ALWAYS READY.</span>
    </div>
  </section>;
}
function HowItWorks() {
  const { t } = useLanguage();
  const steps = [
    ['pin', t('เริ่มจากที่พักของคุณ', 'Start with your stay'), t('ค้นชื่อที่พัก หรือปักหมุดบนแผนที่ เลือกตำแหน่งที่ใช่ด้วยตัวเอง', 'Search for your stay or drop a pin, then choose the right location.')],
    ['compass', t('มองหาที่ที่อยากไป', 'Find your next little adventure'), t('ดูที่เที่ยวและคาเฟ่ในรัศมีที่เลือก เรียงจากใกล้ไปไกล หรือถามน้องทริป', 'Browse attractions and cafés from nearest to farthest, or ask NongTrip.')],
    ['arrow', t('พร้อมแล้ว ก็ออกไปกัน', 'And you’re ready to explore'), t('เปิดแหล่งข้อมูลเพื่อรู้จักสถานที่ แล้วใช้ Google Maps นำทางต่อได้เลย', 'Check the source to learn more, then open directions in Google Maps.')],
  ];
  return <section className="nt-how nt-container" id="how-it-works"><div className="nt-section-heading"><span className="nt-eyebrow">A SMALL START. A LOVELY TRIP.</span><h2>{t('ทริปดี ๆ เริ่มจากใกล้ตัว', 'Good trips begin nearby.')}</h2><p>{t('จากหมุดที่พัก สู่วันพักผ่อนที่เป็นคุณ', 'From your stay to a day that feels like you.')}</p></div><ol className="nt-steps">{steps.map(([icon, title, body], i) => <li key={icon}><div className="nt-step-top"><span className="nt-step-icon"><Icon name={icon} size={27} /></span><span>0{i + 1}</span></div><h3>{title}</h3><p>{body}</p></li>)}</ol></section>;
}
function TrustSection() {
  const { t } = useLanguage();
  return <section className="nt-trust"><div className="nt-container nt-trust-inner"><div><span className="nt-eyebrow">EXPLORE WITH A LITTLE MORE CONFIDENCE</span><h2>{t('เพื่อนเที่ยวที่บอก', 'A travel buddy')}<br />{t('ที่มาที่ไปเสมอ', 'with sources to share.')}</h2><p>{t('ให้คุณตัดสินใจจากข้อมูลที่ตรวจสอบต่อได้', 'Make your own choices with information you can check.')}</p></div><div className="nt-trust-list">{[
    ['shield', t('ตรวจชื่อและพิกัดแล้ว', 'Names and coordinates checked'), t('ตัวอย่างนี้ใช้สถานที่ที่ผ่านการตรวจสอบจากชุดข้อมูลของโครงการ', 'This demo uses verified places from the project’s dataset.')],
    ['link', t('มีที่มาให้เปิดอ่าน', 'Sources you can open'), t('เปิดดูแหล่งอ้างอิงของแต่ละสถานที่ และสัญญาอนุญาตเมื่อมีข้อมูล', 'Open place references and their licenses when provided.')],
    ['compass', t('ระยะทางบอกตรง ๆ', 'Clear about distance'), t('ทุกระยะเป็นเส้นตรงจากที่พัก ไม่ใช่ระยะขับรถ', 'Every distance is straight-line from your stay, not driving distance.')],
  ].map(([icon,title,body]) => <article key={icon}><span><Icon name={icon} size={24}/></span><div><h3>{title}</h3><p>{body}</p></div></article>)}</div></div></section>;
}
function StartBanner() {
  const { t } = useLanguage();
  return <section className="nt-start nt-container"><div className="nt-start-inner"><Mascot mood="wave" size={174} interactive={false} /><div><span className="nt-eyebrow">YOUR NEXT ADVENTURE IS JUST AROUND THE CORNER</span><h2>{t('ทริปหน้า ให้น้องทริปไปด้วยนะ', 'Take NongTrip on your next trip.')}</h2><p>{t('เริ่มจากที่พัก แล้วไปเจอที่ใหม่ ๆ ด้วยกัน', 'Start with your stay. Discover something new together.')}</p></div><Link to="/search" className="nt-button nt-button-amber">{t('เริ่มสำรวจเลย', 'Let’s explore')}<Icon /></Link></div></section>;
}
export default function Home() {
  return <div className="nt-landing"><Hero /><ExploreDemo /><HowItWorks /><TrustSection /><StartBanner /></div>;
}
