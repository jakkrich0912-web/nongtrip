import { useEffect, useRef, useState } from 'react';
import { PROVINCES } from '../lib/provinces.js';
import { subtypeLabel } from '../lib/data.js';
import { lodgingsSearch } from '../lib/api.js';
import { latestOnly } from '../lib/latest.js';

// ประเภทที่พักที่ API รับ (CONTRACT v0.11)
const LODGING_SUBTYPES = ['hotel', 'guest_house', 'hostel', 'motel', 'resort', 'apartment', 'chalet'];

// ค้นที่พักจากชื่อ GET /api/lodgings/search พร้อมตัวกรองจังหวัด ย่าน ประเภท
// ผู้ใช้ต้องกดเลือกที่พักเองเสมอ แม้เจอแห่งเดียว (ชื่อกำกวมไม่เดา)
export default function LodgingSearch({ province: initialProvince = '', onChoose, onResults }) {
  const [q, setQ] = useState('');
  const [province, setProvince] = useState(initialProvince);
  const [area, setArea] = useState('');
  const [subtype, setSubtype] = useState('');
  const [state, setState] = useState({ status: 'idle' });
  // ค้นซ้ำเร็วๆ หรือเลือกที่พักไปแล้ว ผลของคำขอเก่าที่มาช้าจะถูกทิ้ง ไม่ทับรายการและหมุดบนแผนที่
  const seq = useRef(latestOnly()).current;
  // ช่องค้นถูกปิด (สลับโหมด เลือกจังหวัดใหม่ หรือแตะแผนที่เลือกเอง) ระหว่างรอผล: ทิ้งผลที่ค้างอยู่
  useEffect(() => () => seq.cancel(), []); // eslint-disable-line react-hooks/exhaustive-deps
  const choose = (l) => { seq.cancel(); onChoose(l); };

  const search = (e) => {
    e.preventDefault();
    if (!q.trim()) return;
    const token = seq.next();
    setState({ status: 'loading' });
    onResults?.([]);
    lodgingsSearch({ q: q.trim(), province, area: area.trim(), subtype })
      .then((d) => {
        if (!seq.isCurrent(token)) return;
        setState({ status: 'ok', data: d });
        onResults?.(d.items ?? []);
      })
      .catch((err) => { if (seq.isCurrent(token)) setState({ status: 'error', message: err.message }); });
  };

  const items = state.data?.items ?? [];
  const filtersOn = [area, subtype].filter(Boolean).length + (province && province !== initialProvince ? 1 : 0);

  return (
    <div className="lsearch">
      <form className="lsearch-form" onSubmit={search} role="search">
        <div className="lsearch-row">
          <input
            className="field" value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="ชื่อที่พักที่จองไว้" aria-label="ชื่อที่พัก" autoComplete="off"
          />
          <button className="btn small" disabled={!q.trim() || state.status === 'loading'}>ค้นหา</button>
        </div>
        <details className="lsearch-more">
          <summary>ตัวกรองแยกชื่อซ้ำ{filtersOn ? ` (${filtersOn})` : ''}</summary>
          <label>จังหวัด
            <select value={province} onChange={(e) => setProvince(e.target.value)}>
              <option value="">ทุกจังหวัด</option>
              {PROVINCES.map((p) => <option key={p}>{p}</option>)}
            </select>
          </label>
          <label>ย่าน อำเภอ หรือถนน
            <input className="field" value={area} maxLength={100} onChange={(e) => setArea(e.target.value)} placeholder="เช่น นิมมานเหมินท์" />
          </label>
          <label>ประเภทที่พัก
            <select value={subtype} onChange={(e) => setSubtype(e.target.value)}>
              <option value="">ทุกประเภท</option>
              {LODGING_SUBTYPES.map((s) => <option key={s} value={s}>{subtypeLabel(s)}</option>)}
            </select>
          </label>
        </details>
      </form>

      {state.status === 'loading' && <p className="count" role="status">กำลังค้นที่พัก</p>}
      {state.status === 'error' && <p className="notice" role="alert">{state.message}</p>}
      {state.status === 'ok' && (
        <div className="lsearch-results" aria-live="polite">
          {(state.data.notices ?? []).map((n) => <p key={n} className="notice">{n}</p>)}
          {items.length > 0 && (
            <>
              <p className="count">
                {items.length > 1 ? <>พบ <b>{items.length}</b> แห่ง</> : 'ตรวจว่าใช่ที่พักที่จองไว้ แล้วกดเลือก'}
              </p>
              <ul className="cands">
                {items.map((l) => (
                  <li key={l.id}>
                    <div>
                      <strong>{l.name}</strong>
                      <small>
                        {[l.subtype && subtypeLabel(l.subtype), l.province ?? 'ไม่ทราบจังหวัด', l.address].filter(Boolean).join(' · ')}
                      </small>
                    </div>
                    <button className="btn small" onClick={() => choose(l)}>เลือก</button>
                  </li>
                ))}
              </ul>
              <p className="attr">ไม่เจอที่พักของคุณ ลองใช้ตัวกรอง หรือแตะบนแผนที่ตรงที่พักแทน</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
