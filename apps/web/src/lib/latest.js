// ใช้ผลของคำขอล่าสุดเท่านั้น: เริ่มคำขอใหม่ได้ token ผลที่กลับมาด้วย token เก่าให้ทิ้ง
// ใช้กันผลค้นครั้งก่อนที่มาช้ามาทับผลครั้งหลัง (รีวิว PR #15)
export function latestOnly() {
  let current = 0;
  return {
    next: () => ++current,
    isCurrent: (token) => token === current,
    cancel: () => { current += 1; },
  };
}
