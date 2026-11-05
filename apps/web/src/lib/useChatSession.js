// สถานะแชตที่ใช้ร่วมกันระหว่างหน้า /chat และหน้าต่างแชตของน้องทริปที่เดินอยู่ทุกหน้า
// ย้ายมาจาก pages/Chat.jsx: ส่งข้อความ รับสตรีม หยุดรอ เลือกที่พัก และตอบปุ่มเลือกตำแหน่งเมื่อน้องทริปถามกลับ (done.ask)
import { useEffect, useRef, useState } from 'react';
import { sendChat } from './chat.js';
import { getChat, rateMessage } from './api.js';
import { useLanguage } from './language.jsx';
import { useAuth } from './auth.jsx';

// ต้องล้างแชตไหม: เคยมีผู้ใช้ที่ล็อกอินอยู่ แล้วเปลี่ยนเป็นคนอื่นหรือออกจากระบบ
export const userChanged = (prev, next) => prev != null && prev !== next;

// แปลงแชตที่บันทึกไว้ (GET /api/me/chats/{id}) เป็นรายการข้อความของหน้าจอ เก็บไว้แค่ข้อความ (การ์ดสถานที่ไม่ได้บันทึก)
export function historyToMessages(chat) {
  return (chat?.messages ?? [])
    .filter((m) => typeof m?.content === 'string' && m.content.trim())
    .map((m, i) => {
      if (m.role === 'user') return { id: `h-user-${i}`, serverId: m.id ?? null, role: 'user', text: m.content };
      const extra = m.extra && typeof m.extra === 'object' ? m.extra : {};
      return {
        id: `h-bot-${i}`, serverId: m.id ?? null, role: 'bot', text: m.content, status: 'done', restored: true,
        rating: m.rating === 1 || m.rating === -1 ? m.rating : 0,
        mode: typeof extra.mode === 'string' ? extra.mode : undefined,
        places: extra.places ?? undefined, lodgings: extra.lodgings ?? undefined,
        sources: Array.isArray(extra.sources?.items) ? extra.sources.items : [],
      };
    });
}

// ---------- จำบทสนทนา ----------
// บทสนทนาก่อนหน้าที่ส่งให้บอท (CONTRACT v0.24): คำถามของผู้ใช้กับคำตอบที่เสร็จแล้ว ไม่เกิน 6 ข้อความท้าย ตัดแต่ละข้อความไว้ 400 ตัวอักษร
export const HISTORY_TURNS = 6;
export function historyFor(messages) {
  return (messages ?? [])
    .filter((m) => typeof m?.text === 'string' && m.text.trim() && (m.role === 'user' || (m.role === 'bot' && m.status === 'done')))
    .slice(-HISTORY_TURNS)
    .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text.trim().slice(0, 400) }));
}

// เก็บแชตที่คุยอยู่ไว้ใน sessionStorage ของแท็บนี้: ไปหน้าอื่นหรือรีเฟรชแล้วกลับมายังอยู่ ปิดแท็บแล้วหายไป
// ผูกกับผู้ใช้ (uid) คนอื่นที่ล็อกอินในแท็บเดียวกันจะไม่เห็น ข้อความที่ค้างตอบอยู่ตอนออกจากหน้า ถือว่าหยุดแล้ว
export const KEEP_MESSAGES = 40;
const FINAL = new Set(['done', 'error', 'stopped']);
export function packChat({ uid, messages, context, chatId, lastProvince }) {
  return { v: 1, uid: uid ?? null, messages: (messages ?? []).slice(-KEEP_MESSAGES), context: context ?? null, chatId: chatId ?? null, lastProvince: lastProvince ?? null };
}
export function unpackChat(raw, uid) {
  let data = raw;
  if (typeof raw === 'string') { try { data = JSON.parse(raw); } catch { return null; } }
  if (!data || data.v !== 1 || (data.uid ?? null) !== (uid ?? null) || !Array.isArray(data.messages)) return null;
  const messages = data.messages
    .filter((m) => m && typeof m === 'object' && (m.role === 'user' || m.role === 'bot') && m.id != null)
    .map((m) => (m.role === 'bot' && !FINAL.has(m.status) ? { ...m, status: 'stopped' } : m))
    .filter((m) => m.role === 'user' || (typeof m.text === 'string' && m.text.trim()) || m.status === 'error');
  const ctx = data.context;
  const context = ctx && Number.isFinite(ctx.lat) && Number.isFinite(ctx.lon) ? { lat: ctx.lat, lon: ctx.lon, name: typeof ctx.name === 'string' ? ctx.name : '' } : null;
  return { messages, context, chatId: Number.isInteger(data.chatId) ? data.chatId : null, lastProvince: typeof data.lastProvince === 'string' ? data.lastProvince : null };
}
function readKept(key) {
  try { return globalThis.sessionStorage?.getItem(key) ?? null; } catch { return null; }
}
function writeKept(key, value) {
  try {
    if (value) globalThis.sessionStorage?.setItem(key, JSON.stringify(value));
    else globalThis.sessionStorage?.removeItem(key);
  } catch { /* เก็บไม่ได้ (โหมดส่วนตัว พื้นที่เต็ม) ก็แค่จำไม่ได้หลังรีเฟรช */ }
}

// persistKey: ชื่อที่ใช้เก็บใน sessionStorage (ไม่ใส่ = ไม่เก็บ)
export function useChatSession({ initialContext = null, persistKey = null } = {}) {
  const { lang } = useLanguage();
  const auth = useAuth();
  const user = auth?.user ?? null;
  const ready = auth?.ready ?? true;
  const [context, setContext] = useState(initialContext);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [currentChat, setCurrentChat] = useState(null); // รหัสแชตที่บันทึกอยู่ (ล็อกอินแล้วเท่านั้น) ไว้ไฮไลต์ในแถบประวัติ
  const controller = useRef(null);
  const chatId = useRef(null);
  const lastProvince = useRef(null); // จังหวัดที่ถามไว้ล่าสุด (จาก event done)
  const serial = useRef(0);
  const activeId = useRef(null);
  const input = useRef(null);
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const contextRef = useRef(context);
  contextRef.current = context;
  useEffect(() => () => controller.current?.abort(), []);
  // ผู้ใช้เปลี่ยน (ล็อกเอาต์ หรือล็อกอินเป็นคนอื่น): ล้างบทสนทนา จุดค้น และจังหวัดล่าสุด
  // คนถัดไปที่ใช้เครื่องเดียวกันจะไม่เห็นแชตของคนก่อน ส่วนการล็อกอินจากสถานะไม่ล็อกอินยังคุยต่อได้ (คนเดิม)
  const prevUser = useRef(user?.id ?? null);
  useEffect(() => {
    const next = user?.id ?? null;
    const prev = prevUser.current;
    prevUser.current = next;
    chatId.current = null;
    setCurrentChat(null);
    if (!userChanged(prev, next)) return;
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    setMessages([]);
    setText('');
    setContext(null);
    lastProvince.current = null;
  }, [user?.id]);

  // กู้แชตที่คุยค้างไว้ในแท็บนี้ (รอรู้ก่อนว่าใครล็อกอินอยู่ จึงกู้ได้ถูกคน) ถ้าเริ่มคุยไปแล้วก่อนกู้ทัน ใช้ของใหม่
  const hydrated = useRef(!persistKey);
  useEffect(() => {
    if (hydrated.current || !ready) return;
    hydrated.current = true;
    if (messagesRef.current.length) return;
    const kept = unpackChat(readKept(persistKey), user?.id ?? null);
    if (!kept || !kept.messages.length) return;
    setMessages(kept.messages);
    if (kept.context && !contextRef.current) setContext(kept.context);
    chatId.current = kept.chatId;
    setCurrentChat(kept.chatId);
    lastProvince.current = kept.lastProvince;
    serial.current = Math.max(serial.current, ...kept.messages.map((m) => (typeof m.id === 'number' ? m.id : 0)));
  }, [ready, user?.id, persistKey]);
  // บันทึกเมื่อแต่ละคำตอบจบ (ระหว่างสตรีมไม่เขียนทุกตัวอักษร)
  useEffect(() => {
    if (!persistKey || !hydrated.current || busy) return;
    const keep = messages.length ? packChat({ uid: user?.id, messages, context, chatId: chatId.current, lastProvince: lastProvince.current }) : null;
    writeKept(persistKey, keep);
  }, [persistKey, messages, context, currentChat, busy, user?.id]);

  // ctxOverride: ใช้จุดค้นนี้กับข้อความนี้ทันที (เช่น เพิ่งได้ตำแหน่งปัจจุบัน) โดยไม่ต้องรอ state รอบถัดไป
  // opts.from = ข้อความผู้ใช้ที่จะแทน (แก้คำถาม/ถามใหม่): ตัดบทสนทนาตั้งแต่ข้อความนั้นลงไป และให้หลังบ้านลบตาม (edit_from)
  const send = async (value, displayText = value, ctxOverride, opts = {}) => {
    const message = value.trim();
    const where = ctxOverride === undefined ? context : ctxOverride;
    if (!message || message.length > 500 || controller.current) return;
    const id = ++serial.current;
    const aborter = new AbortController();
    controller.current = aborter;
    activeId.current = id;
    setBusy(true);
    setText('');
    const from = opts.from ?? null;
    const editFrom = from && user && chatId.current ? from.serverId ?? null : null;
    const cutAt = from ? messagesRef.current.findIndex((m) => m.id === from.id) : -1;
    const history = historyFor(cutAt >= 0 ? messagesRef.current.slice(0, cutAt) : messagesRef.current);
    setMessages((items) => {
      const cut = from ? items.findIndex((m) => m.id === from.id) : -1;
      const kept = cut >= 0 ? items.slice(0, cut) : items;
      return [...kept, { id: `user-${id}`, role: 'user', text: displayText.trim() }, { id, role: 'bot', text: '', sources: [], status: 'searching', question: message }];
    });
    const update = (patch) => setMessages((items) => items.map((item) => item.id === id ? (typeof patch === 'function' ? patch(item) : { ...item, ...patch }) : item));
    try {
      await sendChat({ message, context: where && { lat: where.lat, lon: where.lon }, chat_id: user ? chatId.current : null, last_province: lastProvince.current, lang, edit_from: editFrom, history }, (event, data) => {
        if (aborter.signal.aborted) return;
        if (event === 'token' && typeof data.text === 'string') update((item) => ({ ...item, text: item.text + data.text, status: 'answering' }));
        if (event === 'places') update({ places: data });
        if (event === 'lodgings') update({ lodgings: data });
        if (event === 'sources') update({ sources: Array.isArray(data.items) ? data.items : [] });
        if (event === 'done') {
          if (user && data.chat_id) { chatId.current = data.chat_id; setCurrentChat(data.chat_id); }
          if (typeof data.province === 'string') lastProvince.current = data.province;
          update({ status: 'done', mode: data.mode, ask: typeof data.ask === 'string' ? data.ask : null, serverId: data.message_id ?? null, rating: 0 });
          if (data.user_message_id) setMessages((items) => items.map((item) => item.id === `user-${id}` ? { ...item, serverId: data.user_message_id } : item));
        }
      }, aborter.signal);
    } catch (error) {
      if (error?.status === 404) { chatId.current = null; setCurrentChat(null); } // แชตเดิมถูกลบไปแล้ว รอบหน้าเริ่มแชตใหม่
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
  // ถามใหม่: ส่งคำถามของคำตอบล่าสุดซ้ำ แทนคำถาม/คำตอบเดิม
  const regenerate = () => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUser) send(lastUser.text, lastUser.text, undefined, { from: lastUser });
  };
  // แก้คำถามที่ส่งไปแล้ว: ตัดตั้งแต่คำถามนั้นลงไป แล้วถามด้วยข้อความใหม่
  const editAndResend = (userMessage, newText) => send(newText, newText, undefined, { from: userMessage });
  // ให้คะแนนคำตอบ (ล็อกอินแล้วและคำตอบถูกบันทึก) กดซ้ำค่าเดิม = ยกเลิก
  const rate = async (message, value) => {
    if (!user || !chatId.current || !message.serverId) return;
    const next = message.rating === value ? 0 : value;
    setMessages((items) => items.map((m) => m.id === message.id ? { ...m, rating: next } : m));
    try {
      await rateMessage(chatId.current, message.serverId, next);
    } catch {
      setMessages((items) => items.map((m) => m.id === message.id ? { ...m, rating: message.rating ?? 0 } : m));
    }
  };
  // เริ่มแชตใหม่: หยุดคำตอบที่ค้าง ล้างบทสนทนา จุดค้น และจังหวัดล่าสุด
  const newChat = () => {
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    setMessages([]);
    setText('');
    setContext(null);
    chatId.current = null;
    setCurrentChat(null);
    lastProvince.current = null;
    input.current?.focus();
  };
  // เปิดแชตเก่าที่บันทึกไว้ แล้วคุยต่อในแชตเดิม (ข้อความใหม่บันทึกต่อท้ายแชตนั้น)
  const openChat = async (id) => {
    if (!user) return false;
    controller.current?.abort();
    controller.current = null;
    setBusy(false);
    const chat = await getChat(id);
    setMessages(historyToMessages(chat));
    setText('');
    setContext(null);
    chatId.current = chat.id;
    setCurrentChat(chat.id);
    lastProvince.current = null;
    return true;
  };
  return { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input, lastProvince, askInProvince, askHere, locating, locateError, newChat, openChat, currentChat, regenerate, editAndResend, rate, canRate: Boolean(user) };
}

// คำถามแนะนำ ส่งตามภาษาที่เลือก (ตัวแยกคำถามเข้าใจทั้งไทยและอังกฤษ)
// interest = กลุ่มความสนใจจากหน้าค้นหา ใส่เป็นคำถามแรก (แชตกรองตามประเภทให้)
export function chatSuggestions(hasContext, interest = null) {
  if (hasContext && interest?.ask) return [interest.ask, ...chatSuggestions(true).slice(0, 2)];
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
