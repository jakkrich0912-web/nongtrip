import { safeUrl as safeSourceUrl } from '../../lib/chat.js';

export default function SourceCards({ sources = [], t = (thai) => thai }) {
  if (!sources.length) return null;
  return (
    <section className="nt-chat-sources" aria-label={t('แหล่งที่มา', 'Sources')}>
      <h3>{t('แหล่งที่มาของคำตอบ', 'Answer sources')}</h3>
      <ul>
        {sources.map((source, index) => {
          const url = safeSourceUrl(source.url);
          return (
            <li key={`${source.id ?? 'source'}-${index}`}>
              {url ? <a href={url} target="_blank" rel="noreferrer">[{index + 1}] {source.title || t('เปิดแหล่งที่มา', 'Open source')} <span aria-hidden="true">↗</span></a>
                : <strong>[{index + 1}] {source.title || t('แหล่งที่มา', 'Source')}</strong>}
              {source.id && <small>{source.id}</small>}
              <small>{t('สัญญาอนุญาต: ', 'License: ')}{source.license || t('ไม่ระบุ', 'Not specified')}</small>
              {source.checked_on && <small>{t('ตรวจสอบเมื่อ ', 'Checked on ')}{source.checked_on}</small>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
