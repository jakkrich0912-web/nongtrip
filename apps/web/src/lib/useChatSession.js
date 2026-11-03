// สถานะแชตที่ใช้ร่วมกันระหว่างหน้า /chat และหน้าต่างแชตของน้องทริปที่เดินอยู่ทุกหน้า
// ย้ายมาจาก pages/Chat.jsx: ส่งข้อความ รับสตรีม หยุดรอ เลือกที่พัก และตอบปุ่มเลือกตำแหน่งเมื่อน้องทริปถามกลับ (done.ask)
import { useEffect, useRef, useState } from 'react';
import { sendChat } from './chat.js';
import { useLanguage } from './language.jsx';
import { useAuth } from './auth.jsx';

// ต้องล้างแชตไหม: เคยมีผู้ใช้ที่ล็อกอินอยู่ แล้วเปลี่ยนเป็นคนอื่นหรือออกจากระบบ
export const userChanged = (prev, next) => prev != null && prev !== next;

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
  // ผู้ใช้เปลี่ยน (ล็อกเอาต์ หรือล็อกอินเป็นคนอื่น): ล้างบทสนทนา จุดค้น และจังหวัดล่าสุด
  // คนถัดไปที่ใช้เครื่องเดียวกันจะไม่เห็นแชตของคนก่อน ส่วนการล็อกอินจากสถานะไม่ล็อกอินยังคุยต่อได้ (คนเดิม)
  const prevUser = useRef(user?.id ?? null);
  useEffect(() => {
    const next = user?.id ?? null;
    const prev = prevUser.current;
    prevUser.current = next;
    chatId.current = null;
    if (!userChanged(prev, next)) return;
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    setMessages([]);
    setText('');
    setContext(null);
    lastProvince.current = null;
  }, [user?.id]);

  // ctxOverride: ใช้จุดค้นนี้กับข้อความนี้ทันที (เช่น เพิ่งได้ตำแหน่งปัจจุบัน) โดยไม่ต้องรอ state รอบถัดไป
  const send = async (value, displayText = value, ctxOverride) => {
    const message = value.trim();
    const where = ctxOverride === undefined ? context : ctxOverride;
    if (!message || message.length > 500 || controller.current) return;
    const id = ++serial.current;
    const aborter = new AbortController();
    controller.current = aborter;
    activeId.current = id;
    setBusy(true);
    setText('');
    setMessages((items) => [...items, { id: `user-${id}`, role: 'user', text: displayText.trim() }, { id, role: 'bot', text: '', sources: [], status: 'searching', question: message }]);
    const update = (patch) => setMessages((items) => items.map((item) => item.id === id ? (typeof patch === 'function' ? patch(item) : { ...item, ...patch }) : item));
    try {
      await sendChat({ message, context: where && { lat: where.lat, lon: where.lon }, chat_id: user ? chatId.current : null, last_province: lastProvince.current, lang }, (event, data) => {
        if (aborter.signal.aborted) return;
        if (event === 'token' && typeof data.text === 'string') update((item) => ({ ...item, text: item.text + data.text, status: 'answering' }));
        if (event === 'places') update({ places: data });
        if (event === 'lodgings') update({ lodgings: data });
        if (event === 'sources') update({ sources: Array.isArray(data.items) ? data.items : [] });
        if (event === 'done') {
          if (user && data.chat_id) chatId.current = data.chat_id;
          if (typeof data.province === 'string') lastProvince.current = data.province;
          update({ status: 'done', mode: data.mode, ask: typeof data.ask === 'string' ? data.ask : null });
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
  // ตอบปุ่มที่ขึ้นตอนน้องทริปถามว่าให้ค้นแถวไหน: ถามคำถามเดิมซ้ำพร้อมจังหวัดที่เลือก
  const askInProvince = (question, province, provinceEn) => send(lang === 'en' ? `${question} in ${provinceEn}` : `${question} ใน${province}`);
  // ใช้ตำแหน่งปัจจุบันของเครื่อง (เบราว์เซอร์ถามสิทธิ์เอง) แล้วถามคำถามเดิมซ้ำรอบจุดนั้น
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState('');
  const askHere = (question, label) => {
    setLocateError('');
    if (typeof navigator === 'undefined' || !navigator.geolocation) { setLocateError('unsupported'); return; }
    setLocating(true);
    navigator.geolocation.getCurrentPosition((pos) => {
      setLocating(false);
      const here = { lat: pos.coords.latitude, lon: pos.coords.longitude, name: label };
      setContext(here);
      send(question, question, here);
    }, () => { setLocating(false); setLocateError('denied'); }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  };
  return { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input, lastProvince, askInProvince, askHere, locating, locateError };
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

// จังหวัดที่เสนอเป็นปุ่มเมื่อยังไม่รู้ว่าให้ค้นแถวไหน
export const QUICK_PROVINCES = [
  ['เชียงใหม่', 'Chiang Mai'], ['กรุงเทพมหานคร', 'Bangkok'], ['ภูเก็ต', 'Phuket'], ['ชลบุรี', 'Chon Buri'],
];
