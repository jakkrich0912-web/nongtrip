// สถานะแชตที่ใช้ร่วมกันระหว่างหน้า /chat และหน้าต่างแชตของน้องทริปที่เดินอยู่ทุกหน้า
// ย้ายมาจาก pages/Chat.jsx ไม่เปลี่ยนพฤติกรรม: ส่งข้อความ รับสตรีม หยุดรอ เลือกที่พัก
import { useEffect, useRef, useState } from 'react';
import { sendChat } from './chat.js';
import { useLanguage } from './language.jsx';
import { useAuth } from './auth.jsx';

export function useChatSession({ initialContext = null } = {}) {
  const { lang } = useLanguage();
  const { user } = useAuth();
  const [context, setContext] = useState(initialContext);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef(null);
  const chatId = useRef(null);
  const lastProvince = useRef(null); // จังหวัดที่ถามไว้ล่าสุด (จาก event done)
  const serial = useRef(0);
  const activeId = useRef(null);
  const input = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { chatId.current = null; }, [user?.id]);

  const send = async (value, displayText = value) => {
    const message = value.trim();
    if (!message || message.length > 500 || controller.current) return;
    const id = ++serial.current;
    const aborter = new AbortController();
    controller.current = aborter;
    activeId.current = id;
    setBusy(true);
    setText('');
    setMessages((items) => [...items, { id: `user-${id}`, role: 'user', text: displayText.trim() }, { id, role: 'bot', text: '', sources: [], status: 'searching' }]);
    const update = (patch) => setMessages((items) => items.map((item) => item.id === id ? (typeof patch === 'function' ? patch(item) : { ...item, ...patch }) : item));
    try {
      await sendChat({ message, context: context && { lat: context.lat, lon: context.lon }, chat_id: user ? chatId.current : null, last_province: lastProvince.current, lang }, (event, data) => {
        if (aborter.signal.aborted) return;
        if (event === 'token' && typeof data.text === 'string') update((item) => ({ ...item, text: item.text + data.text, status: 'answering' }));
        if (event === 'places') update({ places: data });
        if (event === 'lodgings') update({ lodgings: data });
        if (event === 'sources') update({ sources: Array.isArray(data.items) ? data.items : [] });
        if (event === 'done') {
          if (user && data.chat_id) chatId.current = data.chat_id;
          if (typeof data.province === 'string') lastProvince.current = data.province;
          update({ status: 'done', mode: data.mode });
        }
      }, aborter.signal);
    } catch (error) {
      if (error?.status === 404) chatId.current = null; // แชตเดิมถูกลบไปแล้ว รอบหน้าเริ่มแชตใหม่
      if (!aborter.signal.aborted) update({ status: 'error', error: error.message });
    } finally {
      if (controller.current === aborter) {
        controller.current = null;
        setBusy(false);
      }
    }
  };
  // หยุดรอคำตอบ: ยกเลิกคำขอที่ค้างอยู่ ข้อความที่ได้มาแล้วยังคงอยู่ และให้ถามใหม่ได้ทันที
  const stop = () => {
    const aborter = controller.current;
    if (!aborter) return;
    aborter.abort();
    controller.current = null;
    setBusy(false);
    setMessages((items) => items.map((item) => item.id === activeId.current ? { ...item, status: 'stopped' } : item));
    input.current?.focus();
  };
  const chooseLodging = (lodging) => {
    setContext({ lat: lodging.lat, lon: lodging.lon, name: lodging.name });
    input.current?.focus();
  };
  return { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input, lastProvince };
}

// คำถามแนะนำ ส่งตามภาษาที่เลือก (ตัวแยกคำถามเข้าใจทั้งไทยและอังกฤษ)
export function chatSuggestions(hasContext) {
  return hasContext ? [
    ['คาเฟ่ใกล้ที่พักมีที่ไหนบ้าง', 'Which cafés are near my accommodation?'],
    ['ที่เที่ยวในระยะเส้นตรง 10 กม.', 'Attractions within 10 km straight-line distance'],
    ['ที่เที่ยวรอบที่พัก', 'Attractions near my accommodation'],
  ] : [
    ['คาเฟ่ในเชียงใหม่', 'Cafés in Chiang Mai'],
    ['ที่เที่ยวในเชียงราย ในระยะเส้นตรง 10 กม.', 'Attractions in Chiang Rai within 10 km straight-line distance'],
    ['ที่เที่ยวในกรุงเทพมหานคร', 'Attractions in Bangkok'],
  ];
}
