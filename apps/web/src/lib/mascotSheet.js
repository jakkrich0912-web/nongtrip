// แผ่นผิวยืดได้ของมาสคอต: ภาพหนึ่งภาพวางบนแผ่นตาข่ายที่นิ่มเหมือนแป้ง ดึงแล้วยืด ปล่อยแล้วสั่นกลับ
// ไฟล์นี้เป็นฟิสิกส์ล้วน ไม่แตะ DOM/WebGL จึงเทสต์ได้ ดู components/MascotSheet.jsx สำหรับตัววาด
//
// กติกาที่ห้ามแตก (แต่ละข้อเคยเป็นบั๊กจริงในงานต้นแบบ):
//  - แผ่นห้ามพับทับตัวเอง สามเหลี่ยมที่ซ้อนกันจะวาดเป็นรอยหวี ทุกเฟรมจึงบังคับแต่ละแถวและแต่ละคอลัมน์ให้เรียงลำดับ
//    เหลือช่องห่างขั้นต่ำเสมอ (untangle) แผ่นบีบได้แต่ข้ามกันไม่ได้
//  - ฟิสิกส์เดินด้วยก้าวคงที่ 1/240 วินาทีไม่ว่าเฟรมเรตเท่าไร ไม่งั้นจอใหญ่จะฉีกเป็นหนาม
//  - ระยะดึงสูงสุดถูกจำกัด (นุ่มลงเมื่อไกล) ความชันจึงไม่พับ

export const OVER = 1.7; // แผ่นกว้างเป็น 1.7 เท่าของภาพ เผื่อที่ให้ยืดออกนอกกรอบ
export const STEP = 1 / 240;
const MAX_STEPS = 9;

const WOBBLE = 2.3 * 2 * Math.PI;
const REACH_UV = 0.085; // ความเร็วคลื่นในหน่วย uv ต่อวินาที = REACH_UV * WOBBLE ไม่ขึ้นกับความละเอียดตาข่าย
const GAMMA = 2 * 0.14 * WOBBLE;

export function createSheet({ n = 64 } = {}) {
  const N = n;
  const M = N + 1;
  const count = M * M;
  const SPAN = OVER / N;
  const ORIGIN = 0.5 - OVER / 2;
  const REACH = REACH_UV / SPAN;
  const C = REACH * WOBBLE;
  const NU = 0.2 * C;
  const GAP = SPAN * 0.34;

  const ux = new Float32Array(count);
  const uy = new Float32Array(count);
  const vx = new Float32Array(count);
  const vy = new Float32Array(count);
  const rest = new Float32Array(count * 2);
  const restX = new Float32Array(count);
  const restY = new Float32Array(count);
  for (let j = 0, k = 0, p = 0; j < M; j++) {
    for (let i = 0; i < M; i++, k++) {
      rest[p++] = restX[k] = ORIGIN + i * SPAN;
      rest[p++] = restY[k] = ORIGIN + j * SPAN;
    }
  }
  const index = new Uint16Array(N * N * 6);
  for (let j = 0, k = 0; j < N; j++) {
    for (let i = 0; i < N; i++) {
      const a = j * M + i; const b = a + 1; const c = a + M; const d = c + 1;
      index[k++] = a; index[k++] = c; index[k++] = b; index[k++] = b; index[k++] = c; index[k++] = d;
    }
  }

  const sx = new Float32Array(count);
  const sy = new Float32Array(count);
  const dyn = new Float32Array(count * 3); // dx, dy, ความสว่างตามความยืด
  const lineA = new Float32Array(M);
  const lineB = new Float32Array(M);
  const lineP = new Float32Array(M);

  let brush = null;
  let left = 0;

  function order(start, stride, field, base) {
    for (let i = 0; i < M; i++) { const k = start + i * stride; lineP[i] = base[k] + field[k]; }
    lineA[0] = lineP[0];
    for (let i = 1; i < M; i++) lineA[i] = Math.max(lineP[i], lineA[i - 1] + GAP);
    lineB[N] = lineP[N];
    for (let i = N - 1; i >= 0; i--) lineB[i] = Math.min(lineP[i], lineB[i + 1] - GAP);
    for (let i = 0; i < M; i++) { const k = start + i * stride; field[k] = (lineA[i] + lineB[i]) / 2 - base[k]; }
  }
  function untangle() {
    for (let pass = 0; pass < 2; pass++) {
      for (let j = 0; j < M; j++) order(j * M, 1, sx, restX);
      for (let i = 0; i < M; i++) order(i, M, sy, restY);
    }
  }

  // คลื่นหน่วงบนการกระจัดของแต่ละปม ปมริมขอบถูกตรึงไว้ที่ศูนย์
  function step(dt) {
    const c2 = C * C;
    const wo2 = WOBBLE * WOBBLE;
    for (let j = 1; j < N; j++) {
      for (let i = 1; i < N; i++) {
        const k = j * M + i; const l = k - 1; const r = k + 1; const t = k - M; const b = k + M;
        const lx = ux[l] + ux[r] + ux[t] + ux[b] - 4 * ux[k];
        const ly = uy[l] + uy[r] + uy[t] + uy[b] - 4 * uy[k];
        const lvx = vx[l] + vx[r] + vx[t] + vx[b] - 4 * vx[k];
        const lvy = vy[l] + vy[r] + vy[t] + vy[b] - 4 * vy[k];
        vx[k] += (c2 * lx - wo2 * ux[k] - GAMMA * vx[k] + NU * lvx) * dt;
        vy[k] += (c2 * ly - wo2 * uy[k] - GAMMA * vy[k] + NU * lvy) * dt;
      }
    }
    if (brush) {
      for (const [k, w, u0, v0] of brush.list) {
        const K = 3000 * w; const D = 90 * w;
        vx[k] += ((u0 + brush.px * w - ux[k]) * K - vx[k] * D) * dt;
        vy[k] += ((v0 + brush.py * w - uy[k]) * K - vy[k] * D) * dt;
      }
    }
    for (let k = 0; k < count; k++) { ux[k] += vx[k] * dt; uy[k] += vy[k] * dt; }
  }

  return {
    n: N, m: M, count, gap: GAP, index, rest, dyn, ux, uy, vx, vy,
    get holding() { return brush !== null; },
    get hold() { return brush; },

    // จับผิวบริเวณจุด (u,v): ปมใกล้จุดตามมือ ตรงกลางตามเต็มที่
    takeHold(u, v, radius = 0.22) {
      const list = [];
      for (let k = 0; k < count; k++) {
        const dx = restX[k] + ux[k] - u; const dy = restY[k] + uy[k] - v;
        const w = Math.exp(-(dx * dx + dy * dy) / (radius * radius));
        if (w > 0.02) list.push([k, w, ux[k], uy[k]]);
      }
      brush = { u, v, list, px: 0, py: 0 };
      return brush;
    },
    // ย้ายมือ: ระยะดึงถูกจำกัด ยิ่งไกลยิ่งนุ่ม (ไม่ให้ความชันพับ)
    dragTo(u, v, limit = 0.24) {
      if (!brush) return 0;
      let px = u - brush.u; let py = v - brush.v;
      const len = Math.hypot(px, py);
      if (len > 0) { const k = limit * (1 - Math.exp(-len / limit)) / len; px *= k; py *= k; }
      brush.px = px; brush.py = py;
      return Math.hypot(px, py);
    },
    // ตั้งตำแหน่งมือตรง ๆ (มือผีดึงแก้ม) ไม่ผ่านการจำกัดระยะ แต่ยังถูก untangle กันพับ
    setHand(px, py) { if (brush) { brush.px = px; brush.py = py; } },
    releaseHold() { brush = null; },
    pull() { return brush ? Math.hypot(brush.px, brush.py) : 0; },

    // ผลักจากความว่าง: จาม สะดุ้ง แมลงบินมาเกาะ
    poke(u, v, dx, dy, radius = 0.09) {
      for (let k = 0; k < count; k++) {
        const ax = restX[k] - u; const ay = restY[k] - v;
        const w = Math.exp(-(ax * ax + ay * ay) / (radius * radius));
        vx[k] += dx * w; vy[k] += dy * w;
      }
    },

    // เดินฟิสิกส์ตามเวลาจริง (วินาที) แล้วสร้างบัฟเฟอร์ dyn สำหรับวาด คืนจำนวนก้าวที่เดิน
    advance(dt) {
      left += Math.min(dt, 0.1);
      let steps = 0;
      while (left >= STEP && steps < MAX_STEPS) { step(STEP); left -= STEP; steps++; }
      if (steps === MAX_STEPS) left = 0;
      for (let j = 0; j < M; j++) {
        for (let i = 0; i < M; i++) {
          const k = j * M + i;
          const edge = i === 0 || j === 0 || i === N || j === N;
          sx[k] = edge ? ux[k] : (ux[k] * 4 + ux[k - 1] + ux[k + 1] + ux[k - M] + ux[k + M]) / 8;
          sy[k] = edge ? uy[k] : (uy[k] * 4 + uy[k - 1] + uy[k + 1] + uy[k - M] + uy[k + M]) / 8;
        }
      }
      untangle();
      for (let k = 0, o = 0; k < count; k++) {
        dyn[o++] = sx[k]; dyn[o++] = sy[k];
        const col = k % M; const row = (k / M) | 0;
        let shade = 1;
        if (col > 0 && col < N && row > 0 && row < N) {
          shade = Math.max(0.86, Math.min(1.16, 1 - ((sx[k + 1] - sx[k - 1]) + (sy[k + M] - sy[k - M])) * 1.8));
        }
        dyn[o++] = shade;
      }
      return steps;
    },

    // พลังงานที่เหลือ (ผลรวมการกระจัด + ความเร็ว) ใช้ตัดสินว่านิ่งพอจะหยุดวาดได้หรือยัง
    energy() {
      let e = 0;
      for (let k = 0; k < count; k++) e += Math.abs(ux[k]) + Math.abs(uy[k]) + Math.abs(vx[k]) * 0.02 + Math.abs(vy[k]) * 0.02;
      return e;
    },
    settle() { ux.fill(0); uy.fill(0); vx.fill(0); vy.fill(0); sx.fill(0); sy.fill(0); left = 0; },

    // ตัวชี้วัดการพับ: ช่องห่างน้อยสุดระหว่างปมข้างเคียงตามแถว (x) และตามคอลัมน์ (y) หลัง untangle
    minGaps() {
      let gx = Infinity; let gy = Infinity;
      for (let j = 0; j < M; j++) {
        for (let i = 0; i < N; i++) {
          const a = j * M + i;
          gx = Math.min(gx, (restX[a + 1] + sx[a + 1]) - (restX[a] + sx[a]));
        }
      }
      for (let j = 0; j < N; j++) {
        for (let i = 0; i < M; i++) {
          const a = j * M + i;
          gy = Math.min(gy, (restY[a + M] + sy[a + M]) - (restY[a] + sy[a]));
        }
      }
      return { x: gx, y: gy };
    },
  };
}
