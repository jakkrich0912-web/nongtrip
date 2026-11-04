import head from '../assets/mascot/head.webp';

// หน้าน้องแมวสำหรับโลโก้และรูปโปรไฟล์ หมวกโผล่พ้นกรอบเล็กน้อยให้ดูมีมิติ
export default function MascotHead({ size = 46, className = '' }) {
  return (
    <span className={`mascot-head ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <span className="mascot-head-face"><img src={head} alt="" draggable="false" /></span>
    </span>
  );
}
