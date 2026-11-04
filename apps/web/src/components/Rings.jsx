// วงรัศมี 10/20/30 กม. รอบที่พัก: ภาพจำหลักของน้องทริป
export default function Rings({ pins = true }) {
  return (
    <div className="rings" aria-hidden="true">
      <span /><span /><span /><i />
      <b>30 กม.</b><b>20 กม.</b><b>10 กม.</b>
      {pins && [[22, 30], [70, 24], [58, 64], [36, 72], [44, 42]].map(([x, y], k) => (
        <em key={k} className="pin" style={{ left: `${x}%`, top: `${y}%` }} />
      ))}
    </div>
  );
}
