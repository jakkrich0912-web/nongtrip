// เทียบที่พัก 2 แห่ง (หน้าทริปของฉัน): นับที่เที่ยว คาเฟ่ และสถานที่ที่ตรวจที่มาแล้ว ในรัศมี 5 กม. (เส้นตรง)
// นับอย่างเดียว ไม่จัดอันดับ ไม่บอกว่าที่ไหนดีกว่า
import { useEffect, useRef, useState } from 'react';
import { placesNearby } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';
import { COMPARE_RADIUS_KM, compareCounts } from '../lib/trip.js';

export default function CompareStays({ searches }) {
  const { t } = useLanguage();
  const [picked, setPicked] = useState([]);
  const [rows, setRows] = useState({});
  // คำขอที่ส่งไปแล้วต้องได้ผลแม้เลือกแห่งที่สองระหว่างรอ ทิ้งผลเฉพาะเมื่อออกจากหน้านี้
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { setPicked((p) => p.filter((id) => searches.some((s) => s.id === id))); }, [searches]);
  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p.slice(-1), id]));

  useEffect(() => {
    picked.forEach((id) => {
      if (rows[id]) return;
      const s = searches.find((x) => x.id === id);
      if (!s) return;
      setRows((r) => ({ ...r, [id]: { status: 'loading' } }));
      placesNearby({ lat: s.lat, lon: s.lon, radius_km: COMPARE_RADIUS_KM, limit: 1 })
        .then((d) => mounted.current && setRows((r) => ({ ...r, [id]: { status: 'ok', ...compareCounts(d), attribution: d.attribution } })))
        .catch((e) => mounted.current && setRows((r) => ({ ...r, [id]: { status: 'error', message: e.message } })));
    });
  }, [picked]); // eslint-disable-line react-hooks/exhaustive-deps

  if (searches.length < 2) return null;
  const chosen = picked.map((id) => searches.find((s) => s.id === id)).filter(Boolean);
  return (
    <div className="compare">
      <h3 className="trip-h3">{t('เทียบที่พัก 2 แห่ง', 'Compare two stays')}</h3>
      <div className="compare-pick" role="group" aria-label={t('เลือกที่พักที่จะเทียบ', 'Pick stays to compare')}>
        {searches.slice(0, 10).map((s) => (
          <button key={s.id} type="button" className="chip" aria-pressed={picked.includes(s.id)} onClick={() => toggle(s.id)}>{s.name}</button>
        ))}
      </div>
      {chosen.length === 2 && (
        <>
          <table className="compare-table">
            <caption>{t(`นับสถานที่ในรัศมี ${COMPARE_RADIUS_KM} กม. (เส้นตรง) รอบที่พัก`, `Places within ${COMPARE_RADIUS_KM} km (straight-line) of each stay`)}</caption>
            <thead><tr><th />{chosen.map((s) => <th key={s.id} scope="col">{s.name}</th>)}</tr></thead>
            <tbody>
              {[['attraction', t('ที่เที่ยว', 'Attractions')], ['cafe', t('คาเฟ่', 'Cafés')], ['verified', t('ตรวจที่มาแล้ว', 'Source verified')]].map(([k, label]) => (
                <tr key={k}>
                  <th scope="row">{label}</th>
                  {chosen.map((s) => {
                    const r = rows[s.id];
                    return <td key={s.id}>{!r || r.status === 'loading' ? '…' : r.status === 'error' ? t('ค้นไม่ได้', 'Unavailable') : r[k]}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="attr">{t('เป็นจำนวนนับเท่านั้น ไม่ได้บอกว่าที่ไหนดีกว่า', 'Counts only. This does not say which stay is better.')} {chosen.some((s) => rows[s.id]?.attribution) && rows[chosen[0].id]?.attribution}</p>
        </>
      )}
      {chosen.length < 2 && <p className="note">{t('เลือก 2 แห่งเพื่อเทียบ', 'Pick two to compare.')}</p>}
    </div>
  );
}
