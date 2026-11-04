// หน้าต่าง ๆ บอกน้องทริปว่าตอนนี้ผู้ใช้กำลังดูอะไรอยู่ (จุดบนแผนที่ สถานที่ หรือจังหวัด)
// หน้าต่างแชตของมาสคอตจะค้นรอบจุดนั้นหรือถามต่อในจังหวัดนั้นให้เลย ไม่ต้องบอกซ้ำ
import { createContext, useContext, useEffect, useMemo, useState } from 'react';

const Ctx = createContext({ hint: null, setHint: () => {} });

export function CompanionHintProvider({ children }) {
  const [hint, setHint] = useState(null);
  const value = useMemo(() => ({ hint, setHint }), [hint]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useCompanionHint = () => useContext(Ctx).hint;

// เรียกจากหน้าที่มีบริบท: hint = { lat, lon, name } หรือ { province } หรือ null
export function useShareCompanionHint(hint) {
  const { setHint } = useContext(Ctx);
  const lat = hint?.lat;
  const lon = hint?.lon;
  const name = hint?.name;
  const province = hint?.province;
  useEffect(() => {
    if (Number.isFinite(lat) && Number.isFinite(lon)) setHint({ lat, lon, name: name || '' });
    else if (province) setHint({ province });
    else setHint(null);
    return () => setHint(null);
  }, [lat, lon, name, province, setHint]);
}
