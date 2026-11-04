import { createContext, useContext } from 'react';
import { useChatSession } from './useChatSession.js';

// แชตของหน้า /chat อยู่ระดับแอป (ไม่ผูกกับหน้า): กดไปหน้าอื่น เช่น การ์ดสถานที่ในคำตอบ แล้วกลับมา บทสนทนายังอยู่
// คำตอบที่กำลังสตรีมก็ตอบต่อจนจบแม้ออกจากหน้าไปแล้ว และเก็บใน sessionStorage ของแท็บ รีเฟรชแล้วยังอยู่
const ChatPageContext = createContext(null);

export function ChatPageProvider({ children }) {
  const session = useChatSession({ persistKey: 'nongtrip-chat-page' });
  return <ChatPageContext.Provider value={session}>{children}</ChatPageContext.Provider>;
}

export const useChatPage = () => useContext(ChatPageContext);
