import { useState } from 'react';
import Mascot from '../components/Mascot.jsx';
import MascotHead from '../components/MascotHead.jsx';

const SUGGEST = ['คาเฟ่ใกล้ที่พักมีที่ไหนบ้าง', 'วัดสวยๆ ใน 10 กม.', 'ที่เที่ยวสำหรับถ่ายรูป'];

// หน้าแชต: รอ endpoint แชตจาก services/api (สตรีมผลทีละขั้น)
export default function Chat() {
  const [msgs, setMsgs] = useState([{ role: 'bot', text: 'สวัสดีค่ะ บอกชื่อที่พักหรือถามเรื่องที่เที่ยวรอบๆ ได้เลย' }]);
  const [text, setText] = useState('');
  const send = (t) => {
    if (!t.trim()) return;
    setMsgs((m) => [...m, { role: 'user', text: t }, { role: 'bot', text: 'ผู้ช่วยยังไม่เชื่อมกับระบบค้น ระหว่างนี้ใช้หน้าค้นหาได้ก่อนค่ะ' }]);
    setText('');
  };
  return (
    <section className="chat">
      <div className="chat-head">
        <Mascot size={72} mood="happy" />
        <div>
          <h2>ถามน้องทริป</h2>
          <p className="note">ผู้ช่วยค้นจากข้อมูลจริงชุดเดียวกับหน้าค้นหา ไม่เดาข้อมูล</p>
        </div>
      </div>
      <div className="msgs" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            {m.role === 'bot' && <MascotHead size={38} className="avatar" />}
            <div className={`msg ${m.role}`}>{m.text}</div>
          </div>
        ))}
      </div>
      <div className="suggest">
        {SUGGEST.map((s) => <button key={s} className="chip" onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="พิมพ์คำถาม" aria-label="ข้อความ" />
        <button className="btn">ส่ง</button>
      </form>
    </section>
  );
}
