// จัดกลุ่มประวัติแชตตามวันที่คุยล่าสุด (เวลาท้องถิ่นของเครื่อง) แบบแอปแชตทั่วไป
const DAY = 86400000;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

export const GROUPS = [
  ['today', 'วันนี้', 'Today'],
  ['yesterday', 'เมื่อวาน', 'Yesterday'],
  ['week', '7 วันที่ผ่านมา', 'Previous 7 days'],
  ['older', 'ก่อนหน้านั้น', 'Older'],
];

export function groupChats(items, now = new Date()) {
  const today = startOfDay(now);
  const buckets = { today: [], yesterday: [], week: [], older: [] };
  for (const c of items ?? []) {
    const t = Date.parse(c.updated_at ?? c.created_at ?? '');
    const key = !Number.isFinite(t) ? 'older'
      : t >= today ? 'today'
        : t >= today - DAY ? 'yesterday'
          : t >= today - 7 * DAY ? 'week' : 'older';
    buckets[key].push(c);
  }
  return GROUPS.map(([key, th, en]) => ({ key, th, en, items: buckets[key] })).filter((g) => g.items.length);
}
