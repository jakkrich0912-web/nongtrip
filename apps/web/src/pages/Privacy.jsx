import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import Icon from '../components/landing/Icon.jsx';
import { systemHealth } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';
import './info.css';

export const PRIVACY_UPDATED = '2026-11-04';
export const REPO_URL = 'https://github.com/jakkrich0912-web/nongtrip';

// หน้าความเป็นส่วนตัว: บอกตรง ๆ ว่าเก็บอะไร ส่งอะไรออกไปนอกระบบ และลบอย่างไร
// ทุกข้อความต้องตรงกับโค้ดจริง (services/api/store.py, accounts.py, chat.py) แก้โค้ดแล้วต้องแก้หน้านี้ด้วย
export default function Privacy() {
  const { t } = useLanguage();
  const [llm, setLlm] = useState(null); // null = ยังไม่รู้, true/false = แชตใช้โมเดลภาษาอยู่หรือไม่
  useEffect(() => {
    let live = true;
    systemHealth().then((d) => live && setLlm(Boolean(d?.rag?.llm))).catch(() => {});
    return () => { live = false; };
  }, []);

  const toc = [
    ['summary', t('สรุปสั้น ๆ', 'In short')],
    ['stored', t('ข้อมูลที่เก็บ', 'What we store')],
    ['outside', t('ข้อมูลที่ส่งออกไปนอกระบบ', 'What leaves our system')],
    ['device', t('คุกกี้และข้อมูลในเครื่อง', 'Cookies and local storage')],
    ['logs', t('บันทึกของเซิร์ฟเวอร์', 'Server logs')],
    ['control', t('ดูและลบข้อมูลของคุณ', 'Your controls')],
    ['security', t('เราดูแลข้อมูลอย่างไร', 'How we protect it')],
    ['contact', t('เกี่ยวกับหน้านี้', 'About this page')],
  ];

  return (
    <div className="nti-page nt-container">
      <nav className="nti-crumbs" aria-label={t('ตำแหน่งหน้า', 'Breadcrumb')}>
        <Link to="/">{t('หน้าแรก', 'Home')}</Link><span aria-hidden="true">›</span><span>{t('ความเป็นส่วนตัว', 'Privacy')}</span>
      </nav>
      <header className="nti-hero">
        <div>
          <span className="nt-eyebrow"><span />{t('ความเป็นส่วนตัว', 'PRIVACY')}</span>
          <h1>{t('ข้อมูลของคุณ คุณเป็นคนกำหนด', 'Your data, your call')}</h1>
          <p>{t(
            'น้องทริปใช้ได้โดยไม่ต้องสมัคร ถ้าสมัคร เราเก็บเฉพาะสิ่งที่หน้า "ทริปของฉัน" ต้องใช้ และคุณลบได้เองทุกเมื่อ หน้านี้บอกทุกอย่างที่ระบบเก็บ และทุกอย่างที่ส่งออกไปนอกระบบ',
            'You can use NongTrip without an account. If you sign up, we keep only what “My trips” needs, and you can delete it yourself at any time. This page lists everything we store and everything that leaves our system.',
          )}</p>
          <p className="nti-updated">{t('ปรับปรุงล่าสุด', 'Last updated')} {PRIVACY_UPDATED}</p>
        </div>
        <Mascot size={150} mood="happy" interactive={false} />
      </header>

      <div className="nti-layout">
        <nav className="nti-toc" aria-label={t('หัวข้อในหน้านี้', 'On this page')}>
          <strong>{t('ในหน้านี้', 'ON THIS PAGE')}</strong>
          {toc.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>

        <article className="nti-article">
          <section id="summary" className="nti-section">
            <h2>{t('สรุปสั้น ๆ', 'In short')}</h2>
            <ul className="nti-cards">
              <li><span><Icon name="search" size={20} /></span><strong>{t('ไม่สมัครก็ใช้ได้', 'No account needed')}</strong><p>{t('ค้นหาและแชตได้ครบ โดยระบบไม่บันทึกประวัติไว้ให้ใคร', 'Search and chat fully. Nothing is saved to any account.')}</p></li>
              <li><span><Icon name="shield" size={20} /></span><strong>{t('เก็บเท่าที่จำเป็น', 'Only what is needed')}</strong><p>{t('ไม่มีโฆษณา ไม่มีตัวติดตามรายคน และไม่ขายหรือแบ่งปันข้อมูล', 'No ads, no per-person tracking. We never sell or share your data.')}</p></li>
              <li><span><Icon name="check" size={20} /></span><strong>{t('ลบได้เองทั้งหมด', 'Delete it all yourself')}</strong><p>{t('ลบทีละรายการ ลบทั้งหมด หรือลบบัญชีทิ้งได้จากหน้าทริปของฉัน', 'Delete single items, everything, or the whole account from My trips.')}</p></li>
            </ul>
          </section>

          <section id="stored" className="nti-section">
            <h2>{t('ข้อมูลที่เก็บ (เฉพาะผู้ที่มีบัญชี)', 'What we store (account holders only)')}</h2>
            <p>{t('ข้อมูลทั้งหมดอยู่ในฐานข้อมูล SQLite บนเซิร์ฟเวอร์ของโครงงาน ไม่มีฟิลด์ราคา คะแนน หรือรีวิวในตารางใดเลย', 'Everything lives in the project’s own SQLite database. No table has fields for prices, ratings or reviews.')}</p>
            <div className="nti-table-wrap">
              <table className="nti-table">
                <thead><tr><th>{t('ข้อมูล', 'Data')}</th><th>{t('เก็บอะไร', 'What exactly')}</th><th>{t('ใช้ทำอะไร', 'Why')}</th></tr></thead>
                <tbody>
                  <tr><td>{t('อีเมล', 'Email')}</td><td>{t('อีเมลที่ใช้สมัคร และวันที่สมัคร', 'The address you signed up with, and the sign-up date')}</td><td>{t('ใช้เข้าสู่ระบบ ระบบไม่ส่งอีเมลหาคุณ', 'Signing in. We never send you email.')}</td></tr>
                  <tr><td>{t('รหัสผ่าน', 'Password')}</td><td>{t('เฉพาะค่าแฮช scrypt ที่มี salt ของแต่ละคน ไม่มีรหัสผ่านจริงในฐานข้อมูล', 'Only a salted scrypt hash. Your real password is never stored.')}</td><td>{t('ตรวจรหัสผ่านตอนเข้าสู่ระบบ', 'Checking your password at sign-in')}</td></tr>
                  <tr><td>{t('บัญชี Google', 'Google account')}</td><td>{t('ถ้าเข้าด้วย Google: อีเมล และรหัสบัญชี Google (sub) ไม่มีรหัสผ่าน Google', 'If you use Google: your email and Google account ID (sub). Never your Google password.')}</td><td>{t('จำว่าเป็นคนเดิมทุกครั้งที่เข้า', 'Recognising you each time')}</td></tr>
                  <tr><td>{t('เซสชัน', 'Sessions')}</td><td>{t('แฮชของรหัสเซสชัน วันที่เข้าสู่ระบบ และวันหมดอายุ (7 วัน) แยกตามอุปกรณ์', 'A hash of each session ID, when it started and when it expires (7 days), per device')}</td><td>{t('ให้คุณออกจากระบบได้จริง และสั่งออกจากระบบอุปกรณ์อื่นได้', 'So signing out really ends the session, and you can sign out other devices')}</td></tr>
                  <tr><td>{t('ที่พักที่เคยค้น', 'Stays you searched')}</td><td>{t('ชื่อที่พัก พิกัด และเวลา เก็บล่าสุด 100 รายการ', 'Stay name, coordinates and time; the latest 100')}</td><td>{t('กลับไปดูรอบที่พักเดิมได้ในคลิกเดียว', 'Reopen an area in one click')}</td></tr>
                  <tr><td>{t('สถานที่โปรด', 'Favourites')}</td><td>{t('ชื่อ ประเภท พิกัด จังหวัด และที่มาของสถานที่ สูงสุด 500 แห่ง', 'Name, type, coordinates, province and source; up to 500')}</td><td>{t('เก็บที่อยากไปไว้ดูทีหลัง', 'Keeping places for later')}</td></tr>
                  <tr><td>{t('ประวัติแชต', 'Chat history')}</td><td>{t('คำถามที่คุณพิมพ์ และคำตอบของน้องทริป', 'The questions you typed and NongTrip’s answers')}</td><td>{t('เปิดแชตเก่าแล้วคุยต่อได้', 'Reopening and continuing a chat')}</td></tr>
                </tbody>
              </table>
            </div>
            <p>{t('ถ้าไม่ได้เข้าสู่ระบบ ระบบไม่บันทึกที่พักที่ค้น สถานที่โปรด หรือแชตไว้ที่ใดเลย ปิดหน้าเว็บแล้วหายไป', 'If you are not signed in, no searches, favourites or chats are saved anywhere. Close the page and they are gone.')}</p>
          </section>

          <section id="outside" className="nti-section">
            <h2>{t('ข้อมูลที่ส่งออกไปนอกระบบ', 'What leaves our system')}</h2>
            <p>{t('น้องทริปไม่ได้ทำทุกอย่างเอง บางงานต้องใช้บริการภายนอก ข้างล่างคือทุกกรณี', 'Some jobs need outside services. These are all of them.')}</p>
            <h3>{t('ผู้ให้บริการโมเดลภาษา (เมื่อแชตใช้โมเดลภาษา)', 'Language-model provider (when chat uses one)')}</h3>
            <p>{t(
              'เมื่อคุณถามในแชต ระบบส่งข้อความที่คุณพิมพ์ พร้อมข้อความจากบทความ Wikipedia ที่ค้นได้ ไปให้ผู้ให้บริการโมเดลภาษาที่ผู้ดูแลระบบตั้งไว้ (เช่น Anthropic) เรียบเรียงคำตอบ ระบบไม่ส่งอีเมลหรือข้อมูลบัญชีของคุณไปด้วย',
              'When you ask in chat, the text you typed and passages from matching Wikipedia articles are sent to the language-model provider the operator configured (for example Anthropic) to write the answer. Your email and account details are not sent.',
            )}</p>
            {llm === true && <div className="nti-callout"><span>!</span><p>{t('ตอนนี้แชตใช้โมเดลภาษาอยู่ ข้อความที่คุณพิมพ์ในแชตจึงถูกส่งออกไปภายนอก อย่าพิมพ์ข้อมูลส่วนตัว เช่น เบอร์โทร เลขบัตร หรือรหัสผ่าน', 'Chat is using a language model right now, so what you type in chat is sent outside. Please don’t type personal details such as phone numbers, ID numbers or passwords.')}</p></div>}
            {llm === false && <div className="nti-callout is-ok"><span>✓</span><p>{t('ตอนนี้แชตตอบด้วยกฎของระบบเอง ข้อความที่คุณพิมพ์ในแชตไม่ถูกส่งออกไปนอกระบบ', 'Chat is answering with built-in rules right now, so what you type in chat does not leave our system.')}</p></div>}
            <h3>OpenStreetMap</h3>
            <p>{t(
              'เวลาค้นที่พักหรือสถานที่รอบจุด เซิร์ฟเวอร์ของเราเป็นผู้ส่งคำค้นและพิกัดไปที่ Nominatim และ Overpass ของ OpenStreetMap บริการเหล่านั้นเห็นคำค้น แต่ไม่เห็นที่อยู่ IP ของคุณ ส่วนภาพแผนที่ เบราว์เซอร์ของคุณโหลดจาก tile.openstreetmap.org โดยตรง OpenStreetMap จึงเห็นที่อยู่ IP ของคุณ เหมือนการเปิดเว็บทั่วไป',
              'When you search for a stay or nearby places, our server sends the query and coordinates to OpenStreetMap’s Nominatim and Overpass. They see the query but not your IP address. Map images are loaded by your browser directly from tile.openstreetmap.org, so OpenStreetMap sees your IP address, as with any website.',
            )}</p>
            <h3>Google</h3>
            <p>{t(
              'หน้าเข้าสู่ระบบโหลดสคริปต์ของ Google เพื่อแสดงปุ่ม "ลงชื่อเข้าใช้ด้วย Google" (เมื่อเปิดใช้) ปุ่มนำทางและลิงก์ดูรีวิวเปิดเว็บ Google Maps เฉพาะเมื่อคุณกดเท่านั้น เราไม่ดึงข้อมูลใดจาก Google มาแสดง',
              'The sign-in page loads Google’s script to show the “Sign in with Google” button (when enabled). Directions and review links open Google Maps only when you tap them. We do not pull any data from Google.',
            )}</p>
            <h3>{t('ลิงก์ที่มาของข้อมูล', 'Source links')}</h3>
            <p>{t('ลิงก์ไปบทความ Wikipedia หรือหน้า OpenStreetMap เปิดเว็บเหล่านั้นเมื่อคุณกดเท่านั้น', 'Links to Wikipedia articles or OpenStreetMap pages open those sites only when you tap them.')}</p>
          </section>

          <section id="device" className="nti-section">
            <h2>{t('คุกกี้และข้อมูลในเครื่อง', 'Cookies and local storage')}</h2>
            <ul>
              <li>{t('คุกกี้ ', 'One cookie, ')}<code>nt_session</code>{t(' ใบเดียว ตั้งเมื่อคุณเข้าสู่ระบบ ใช้จำว่าเข้าสู่ระบบอยู่ อายุ 7 วัน สคริปต์ในหน้าเว็บอ่านไม่ได้ (HttpOnly)', ', set when you sign in to remember the session. It lasts 7 days and page scripts cannot read it (HttpOnly).')}</li>
              <li>{t('การตั้งค่าหน้าจอ เช่น ภาษาที่เลือก เก็บใน localStorage ของเบราว์เซอร์คุณเอง ไม่ส่งมาที่เซิร์ฟเวอร์', 'Display settings such as language are kept in your browser’s localStorage and never sent to the server.')}</li>
              <li>{t('ไม่มีคุกกี้โฆษณา คุกกี้ติดตาม หรือเครื่องมือวัดสถิติผู้เข้าชม', 'No advertising cookies, tracking cookies or visitor analytics.')}</li>
            </ul>
          </section>

          <section id="logs" className="nti-section">
            <h2>{t('บันทึกของเซิร์ฟเวอร์', 'Server logs')}</h2>
            <p>{t(
              'เพื่อกันคนส่งคำขอรัว ๆ ระบบจำที่อยู่ IP ไว้ในหน่วยความจำชั่วคราว (เช่น แชตไม่เกิน 20 ครั้งต่อนาที) ไม่เขียนลงฐานข้อมูล และหายเมื่อระบบรีสตาร์ท เว็บเซิร์ฟเวอร์ยังบันทึก log การเข้าถึงตามค่าเริ่มต้น คือ ที่อยู่ IP เวลา และที่อยู่หน้าที่ขอ ซึ่งอาจมีพิกัดที่ค้นอยู่ในนั้น log นี้ใช้ดูแลระบบเท่านั้น',
              'To stop request floods, IP addresses are kept briefly in memory (for example, at most 20 chat messages a minute). They are not written to the database and vanish on restart. The web server also keeps standard access logs (IP address, time and requested address, which can include searched coordinates). These logs are used only to run the system.',
            )}</p>
            <p>{t(
              'เพื่อดูแลคุณภาพระบบ เรานับยอดรวมรายวัน เช่น จำนวนการค้น จังหวัดที่ถูกค้น จำนวนแชตแยกตามวิธีตอบ และเหตุที่ด่านตรวจตีตกคำตอบ แต่ละแถวมีแค่ วัน ชนิด ค่า และจำนวน ไม่มีข้อความ ที่อยู่ IP หรือรหัสผู้ใช้ จึงย้อนกลับไปหาว่าใครทำอะไรไม่ได้ ผู้ดูแลระบบดูได้เฉพาะยอดรวมเหล่านี้',
              'To keep the system healthy we count daily totals, such as searches, searched provinces, chats by answer type and why the checker rejected answers. Each row holds only a day, a type, a value and a count, with no text, IP address or user ID, so nothing can be traced back to a person. Administrators see only these totals.',
            )}</p>
          </section>

          <section id="control" className="nti-section">
            <h2>{t('ดูและลบข้อมูลของคุณ', 'Your controls')}</h2>
            <ul>
              <li>{t('ดูทุกอย่างที่เก็บไว้ได้ที่ ', 'See everything we keep on ')}<Link to="/me">{t('ทริปของฉัน', 'My trips')}</Link></li>
              <li>{t('ลบที่พักที่ค้น สถานที่โปรด หรือแชต ทีละรายการหรือทั้งหมดได้ทันที', 'Delete searches, favourites or chats one by one or all at once')}</li>
              <li>{t('ลบบัญชีแล้ว ข้อมูลทั้งหมดของบัญชีถูกลบถาวรทันที รวมถึงทุกเซสชัน กู้คืนไม่ได้', 'Deleting your account permanently removes all of its data at once, including every session. It cannot be undone.')}</li>
              <li>{t('เปลี่ยนรหัสผ่าน หรือสั่งออกจากระบบอุปกรณ์อื่นได้ที่ ', 'Change your password or sign out other devices in ')}<Link to="/settings">{t('ตั้งค่าบัญชี', 'Account settings')}</Link></li>
              <li>{t('ข้อมูลอยู่จนกว่าคุณจะลบ ยกเว้นที่พักที่ค้นซึ่งเก็บแค่ 100 รายการล่าสุด และเซสชันที่หมดอายุซึ่งถูกล้างอัตโนมัติ', 'Data stays until you delete it, except searches (only the latest 100 are kept) and expired sessions, which are cleared automatically.')}</li>
            </ul>
          </section>

          <section id="security" className="nti-section">
            <h2>{t('เราดูแลข้อมูลอย่างไร', 'How we protect it')}</h2>
            <ul>
              <li>{t('รหัสผ่านแฮชด้วย scrypt ทุกบัญชีมี salt ของตัวเอง', 'Passwords are hashed with scrypt, each with its own salt.')}</li>
              <li>{t('คุกกี้เซสชันเซ็นด้วย HMAC และต้องตรงกับเซสชันในฐานข้อมูล ออกจากระบบหรือเปลี่ยนรหัสผ่านแล้ว คุกกี้เดิมใช้ไม่ได้ทันที', 'Session cookies are HMAC-signed and must match a session in the database. Signing out or changing your password ends the old cookie immediately.')}</li>
              <li>{t('จำกัดการเดารหัสผ่าน การสมัครบัญชี และการส่งแชต ต่อ IP หรือต่ออีเมล', 'Password guesses, sign-ups and chat messages are rate-limited per IP or per email.')}</li>
              <li>{t('ทุกคำขอข้อมูลส่วนตัวตรวจว่าเป็นของบัญชีที่เข้าสู่ระบบอยู่ ดูหรือลบข้อมูลของคนอื่นไม่ได้', 'Every personal-data request is checked against the signed-in account. Nobody can read or delete someone else’s data.')}</li>
            </ul>
          </section>

          <section id="contact" className="nti-section">
            <h2>{t('เกี่ยวกับหน้านี้', 'About this page')}</h2>
            <p>{t(
              'น้องทริปเป็นโครงงานของนักศึกษามหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี ไม่ใช่บริการเชิงพาณิชย์ ถ้าระบบเปลี่ยนวิธีเก็บข้อมูล เราจะแก้หน้านี้และวันที่ปรับปรุงด้านบน มีคำถามหรือพบปัญหา แจ้งทีมได้ที่ ',
              'NongTrip is a student project at Rajamangala University of Technology Thanyaburi, not a commercial service. If the way we handle data changes, we update this page and the date above. Questions or problems? Tell the team on ',
            )}<a href={`${REPO_URL}/issues`} target="_blank" rel="noreferrer">GitHub</a>{t(' (ซอร์สโค้ดทั้งหมดเปิดให้ตรวจได้)', ' (all source code is open for review).')}</p>
            <p><Link to="/about">{t('อ่านเพิ่มว่าข้อมูลสถานที่มาจากไหน →', 'Read where our place data comes from →')}</Link></p>
          </section>
        </article>
      </div>
    </div>
  );
}
