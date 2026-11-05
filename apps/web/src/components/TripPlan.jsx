// ทริปจากสถานที่โปรด (หน้าทริปของฉัน): เรียงจากที่พัก ปุ่มไปจุดถัดไป ติ๊กจุดที่ไปแล้ว กลุ่มที่ไปวันเดียวได้ และถามเรื่องทริป
import { useEffect, useMemo, useState } from 'react';
import { askTrip } from '../lib/api.js';
import { placeName } from '../lib/data.js';
import { mapsDirUrl } from '../lib/geo.js';
import { useLanguage } from '../lib/language.jsx';
import { groupNearby, loadDone, nextStop, orderStops, saveDone } from '../lib/trip.js';
import FavButton from './FavButton.jsx';

const ASK_EXAMPLES = [
  ['ทริปนี้ขาดคาเฟ่ไหม', 'Does my trip have cafés?'],
  ['จุดไหนอยู่ใกล้กันบ้าง', 'Which places are close together?'],
  ['ไปที่ไหนก่อนดี', 'Which order should I go?'],
];

export default function TripPlan({ userId, favs, searches }) {
  const { t, lang } = useLanguage();
  const [stayId, setStayId] = useState(() => searches[0]?.id ?? null);
  useEffect(() => { if (stayId != null && !searches.some((s) => s.id === stayId)) setStayId(searches[0]?.id ?? null); }, [searches, stayId]);
  const stay = searches.find((s) => s.id === stayId) ?? null;
  const stops = useMemo(() => orderStops(favs, stay), [favs, stay]);
  const groups = useMemo(() => groupNearby(stops), [stops]);
  const [done, setDone] = useState(() => loadDone(userId));
  const toggle = (id) => setDone((d) => {
    const n = new Set(d);
    if (n.has(id)) n.delete(id); else n.add(id);
    saveDone(userId, n);
    return n;
  });
  const reset = () => { const n = new Set(); saveDone(userId, n); setDone(n); };
  const next = nextStop(stops, done);

  if (!stops.length) return null;
  return (
    <section className="mt-card trip-plan">
      <header>
        <h2>{t('ทริปจากสถานที่โปรด', 'Trip from your favourites')}<small>{stops.length}</small></h2>
        {done.size > 0 && <button type="button" className="linkbtn" onClick={reset}>{t('เริ่มใหม่', 'Start over')}</button>}
      </header>
      {searches.length > 0 ? (
        <label className="trip-stay">
          {t('เริ่มจากที่พัก', 'Start from')}
          <select value={stayId ?? ''} onChange={(e) => setStayId(Number(e.target.value))}>
            {searches.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
      ) : <p className="note">{t('ยังไม่มีที่พักที่ค้นไว้ จึงเรียงตามลำดับที่บันทึก ค้นที่พักในหน้าค้นหาเพื่อเรียงจากที่พัก', 'No saved stay yet, so stops follow the order you saved them. Search for your stay to order them from it.')}</p>}

      {next ? (
        <a className="btn small trip-next" href={next.directions_url ?? mapsDirUrl(next)} target="_blank" rel="noreferrer">
          {t('ไปจุดถัดไป', 'Go to next stop')}: {placeName(next, lang)}
        </a>
      ) : <p className="trip-finished" role="status">{t('ไปครบทุกจุดแล้ว', 'You have visited every stop.')}</p>}

      <ol className="trip-stops">
        {stops.map((p) => (
          <li key={p.id} className={done.has(p.id) ? 'is-done' : ''}>
            <label>
              <input type="checkbox" checked={done.has(p.id)} onChange={() => toggle(p.id)} aria-label={t(`ไป ${placeName(p, lang)} แล้ว`, `Visited ${placeName(p, lang)}`)} />
              <span>{placeName(p, lang)}</span>
            </label>
            {p.distance_km != null && <small>{p.distance_km} {t('กม. (เส้นตรง)', 'km (straight-line)')}</small>}
          </li>
        ))}
      </ol>
      <p className="attr">{t('ปุ่มไปจุดถัดไปเปิด Google Maps นำทางจากตำแหน่งปัจจุบันของคุณ จุดที่ติ๊กเก็บไว้ในเครื่องนี้เท่านั้น', 'Go to next stop opens Google Maps from where you are. Ticks are kept on this device only.')}</p>

      {groups.length > 0 && (
        <>
          <h3 className="trip-h3">{t('ไปวันเดียวกันได้ (ห่างกันไม่เกิน 2 กม. เส้นตรง)', 'Fits in one day (within 2 km straight-line)')}</h3>
          <ul className="trip-groups">
            {groups.map((g) => (
              <li key={g.items.map((p) => p.id).join('|')}>
                <strong>{t(`แถว${placeName(g.anchor, lang)}`, `Around ${placeName(g.anchor, lang)}`)}</strong>
                <small>{g.items.length} {t('แห่ง', 'places')} · {t(`ไกลสุด ${g.span_km} กม.`, `up to ${g.span_km} km apart`)}</small>
                <span>{g.items.map((p) => placeName(p, lang)).join(', ')}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <TripAsk stayId={stay?.id ?? null} />
    </section>
  );
}

function TripAsk({ stayId }) {
  const { t, lang } = useLanguage();
  const [q, setQ] = useState('');
  const [state, setState] = useState({ status: 'idle' });
  const ask = async (question) => {
    const text = question.trim();
    if (!text) return;
    setQ(text);
    setState({ status: 'loading' });
    try {
      const d = await askTrip({ question: text, stay_id: stayId, lang });
      setState({ status: 'ok', data: d });
    } catch (e) {
      setState({ status: 'error', message: e.message });
    }
  };
  return (
    <div className="trip-ask">
      <h3 className="trip-h3">{t('ถามน้องทริปเรื่องทริปนี้', 'Ask NongTrip about this trip')}</h3>
      <div className="trip-ask-chips">
        {ASK_EXAMPLES.map(([th, en]) => <button key={th} type="button" className="chip" onClick={() => ask(t(th, en))}>{t(th, en)}</button>)}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input value={q} maxLength={300} onChange={(e) => setQ(e.target.value)} placeholder={t('เช่น ทริปนี้มีจุดชมวิวไหม', 'e.g. Does my trip have a viewpoint?')} aria-label={t('คำถามเรื่องทริป', 'Question about the trip')} />
        <button className="btn small" disabled={state.status === 'loading' || !q.trim()}>{t('ถาม', 'Ask')}</button>
      </form>
      {state.status === 'loading' && <p className="note" role="status">{t('กำลังดูทริป', 'Checking your trip…')}</p>}
      {state.status === 'error' && <p className="auth-error" role="alert">{state.message}</p>}
      {state.status === 'ok' && (
        <div className="trip-answer" role="status">
          {state.data.answer.split('\n').map((line, i) => <p key={i}>{line}</p>)}
          {state.data.places?.items?.length > 0 && (
            <ul className="mt-list">
              {state.data.places.items.map((p) => (
                <li key={p.id}>
                  <div className="mt-main"><strong>{placeName(p, lang)}</strong><small>{p.distance_km} {t('กม. (เส้นตรง)', 'km (straight-line)')}</small></div>
                  <FavButton place={p} />
                </li>
              ))}
            </ul>
          )}
          {state.data.places?.attribution && <p className="attr">{state.data.places.attribution}</p>}
          <p className="attr">{t('ตอบจากสถานที่โปรดและที่พักที่บันทึกไว้เท่านั้น', 'Answered only from your saved favourites and stays.')}</p>
        </div>
      )}
    </div>
  );
}
