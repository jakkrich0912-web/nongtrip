// ไอคอนประจำประเภทสถานที่ (วาดเอง ไม่ใช้รูปจากภายนอก)
const PATHS = {
  temple: <path d="M12 2l2 4h-4l2-4zm-5 6h10l-1 3H8L7 8zm-2 5h14v2H5v-2zm1 4h12v5h-3v-3h-6v3H6v-5z" />,
  museum: <path d="M12 2l10 5v2H2V7l10-5zM4 11h3v7H4v-7zm6.5 0h3v7h-3v-7zM17 11h3v7h-3v-7zM2 20h20v2H2v-2z" />,
  nature: <path d="M12 2c4 4 6 7.5 6 10.5A6 6 0 0113 18.4V22h-2v-3.6A6 6 0 016 12.5C6 9.5 8 6 12 2z" />,
  activity: <path d="M12 3a2 2 0 110 4 2 2 0 010-4zM9 8h6l2 6h-2.3l-.7 8h-4l-.7-8H7l2-6z" />,
  cafe: <path d="M4 8h13v5a5 5 0 01-5 5H9a5 5 0 01-5-5V8zm13 1h1.5a2.5 2.5 0 010 5H17v-2h1.5a.5.5 0 000-1H17V9zM7 3c1 1 1 2 0 3M10.5 3c1 1 1 2 0 3M14 3c1 1 1 2 0 3M3 20h15v2H3z" />,
  market: <path d="M3 4h18l-1.5 6a3 3 0 01-5.5 1 3 3 0 01-4 0 3 3 0 01-5.5-1L3 4zm2 9.5V21h14v-7.5a5 5 0 01-2 .5v5H7v-5a5 5 0 01-2-.5z" />,
};
export default function CatIcon({ cat, size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      {PATHS[cat] ?? <circle cx="12" cy="12" r="6" />}
    </svg>
  );
}
