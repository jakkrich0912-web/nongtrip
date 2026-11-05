// แจ้งข้อมูลผิดจากหน้ารายละเอียดสถานที่ ส่งให้ผู้ดูแลตรวจ ไม่ต้องล็อกอิน ไม่บันทึกว่าใครแจ้ง
import { useState } from 'react';
import { reportPlace } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';

export const REPORT_REASONS = [
  ['closed', 'ปิดกิจการแล้ว', 'Permanently closed'],
  ['wrong_location', 'ตำแหน่งบนแผนที่ผิด', 'Wrong location on the map'],
  ['wrong_name', 'ชื่อผิด', 'Wrong name'],
  ['wrong_type', 'ประเภทผิด', 'Wrong type'],
  ['other', 'อื่น ๆ', 'Something else'],
];

export default function ReportPlace({ place, name }) {
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [state, setState] = useState({ status: 'idle' });

  if (state.status === 'sent') return <p className="report-done" role="status">{t('ส่งให้ผู้ดูแลตรวจแล้ว ขอบคุณที่ช่วยแจ้ง', 'Sent to our team. Thanks for letting us know.')}</p>;
  if (!open) return <button type="button" className="linkbtn report-open" onClick={() => setOpen(true)}>{t('แจ้งข้อมูลผิด', 'Report a problem')}</button>;

  const submit = async (e) => {
    e.preventDefault();
    if (!reason) return;
    setState({ status: 'sending' });
    try {
      await reportPlace({ place_id: place.id, place_name: name, reason, note: note.trim() });
      setState({ status: 'sent' });
    } catch (err) {
      setState({ status: 'error', message: err.message });
    }
  };

  return (
    <form className="report-form" onSubmit={submit}>
      <fieldset>
        <legend>{t('ข้อมูลไหนผิด', 'What is wrong?')}</legend>
        {REPORT_REASONS.map(([id, th, en]) => (
          <label key={id}><input type="radio" name="report-reason" value={id} checked={reason === id} onChange={() => setReason(id)} /> {t(th, en)}</label>
        ))}
      </fieldset>
      <label className="report-note">
        {t('รายละเอียดเพิ่มเติม (ไม่บังคับ ไม่ต้องใส่ข้อมูลส่วนตัว)', 'Details (optional, no personal information)')}
        <textarea maxLength={300} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      {state.status === 'error' && <p className="auth-error" role="alert">{state.message}</p>}
      <div className="report-actions">
        <button className="btn small" disabled={!reason || state.status === 'sending'}>{state.status === 'sending' ? t('กำลังส่ง', 'Sending…') : t('ส่งให้ผู้ดูแล', 'Send')}</button>
        <button type="button" className="linkbtn" onClick={() => { setOpen(false); setState({ status: 'idle' }); }}>{t('ยกเลิก', 'Cancel')}</button>
      </div>
    </form>
  );
}
