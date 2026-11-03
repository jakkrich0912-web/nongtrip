// ตัววาด WebGL ของมาสคอต: วาดภาพหนึ่งภาพ (หรือเฟดสองภาพไม่เกิน 70 มิลลิวินาที) บนแผ่นตาข่ายจาก mascotSheet.js
// มีภาพเดียวอยู่บนจอเสมอ ไม่ซ้อนชิ้นส่วน/ไม่วางแพตช์ทับหน้า สลับสีหน้าคือสลับทั้งภาพ
import { OVER } from './mascotSheet.js';

const VS = `attribute vec2 a, d; attribute float s; varying vec2 vUv; varying float vS;
uniform vec2 lean; uniform float overS;
void main(){ vUv = a; vS = s; vec2 p = a + d + lean; gl_Position = vec4(vec2(p.x-.5, .5-p.y)*2./overS, 0., 1.); }`;
const FS = `precision highp float; varying vec2 vUv; varying float vS;
uniform sampler2D faceA, faceB; uniform float fade;
void main(){
  if(vUv.x<0.||vUv.y<0.||vUv.x>1.||vUv.y>1.){ gl_FragColor = vec4(0.); return; }
  vec4 c = mix(texture2D(faceA,vUv), texture2D(faceB,vUv), fade);
  if(c.a<.004){ gl_FragColor = vec4(0.); return; }
  gl_FragColor = vec4(c.rgb*vS, c.a);
}`;

let supported;
// ทดสอบครั้งเดียวต่อหน้าว่าเบราว์เซอร์สร้างบริบท WebGL ได้ไหม (ไม่ได้ก็ใช้ภาพนิ่งเดิมทั้งหมด)
export function webglSupported() {
  if (supported !== undefined) return supported;
  try {
    const probe = document.createElement('canvas');
    supported = Boolean(probe.getContext('webgl'));
  } catch { supported = false; }
  return supported;
}

export function createRenderer(canvas, sheet) {
  const gl = canvas.getContext('webgl', { alpha: true, premultipliedAlpha: true, antialias: true });
  if (!gl) return null;
  const shader = (type, src) => {
    const o = gl.createShader(type); gl.shaderSource(o, src); gl.compileShader(o);
    if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o));
    return o;
  };
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, VS));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, FS));
  gl.linkProgram(program);
  gl.useProgram(program);
  const loc = { lean: gl.getUniformLocation(program, 'lean'), fade: gl.getUniformLocation(program, 'fade') };
  gl.uniform1f(gl.getUniformLocation(program, 'overS'), OVER);
  gl.uniform1i(gl.getUniformLocation(program, 'faceA'), 0);
  gl.uniform1i(gl.getUniformLocation(program, 'faceB'), 1);

  gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ARRAY_BUFFER, sheet.rest, gl.STATIC_DRAW);
  const aa = gl.getAttribLocation(program, 'a');
  gl.enableVertexAttribArray(aa); gl.vertexAttribPointer(aa, 2, gl.FLOAT, false, 0, 0);
  const dynBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, dynBuf);
  gl.bufferData(gl.ARRAY_BUFFER, sheet.dyn, gl.DYNAMIC_DRAW);
  const ad = gl.getAttribLocation(program, 'd');
  const as = gl.getAttribLocation(program, 's');
  gl.enableVertexAttribArray(ad); gl.vertexAttribPointer(ad, 2, gl.FLOAT, false, 12, 0);
  gl.enableVertexAttribArray(as); gl.vertexAttribPointer(as, 1, gl.FLOAT, false, 12, 8);
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, gl.createBuffer());
  gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, sheet.index, gl.STATIC_DRAW);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA); gl.clearColor(0, 0, 0, 0);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);

  const textures = {};
  return {
    gl,
    has: (name) => Boolean(textures[name]),
    upload(name, img) {
      const t = gl.createTexture();
      gl.activeTexture(gl.TEXTURE5);
      gl.bindTexture(gl.TEXTURE_2D, t);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      textures[name] = t;
    },
    resize(cssW, cssH) {
      const r = Math.min(window.devicePixelRatio || 1, 2);
      const w = Math.max(1, Math.round(cssW * r)); const h = Math.max(1, Math.round(cssH * r));
      if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; }
      gl.viewport(0, 0, canvas.width, canvas.height);
    },
    draw(faceA, faceB, fade, leanX, leanY) {
      const a = textures[faceA] ?? textures.base; const b = textures[faceB] ?? textures.base;
      if (!a || !b) return false;
      gl.bindBuffer(gl.ARRAY_BUFFER, dynBuf);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, sheet.dyn);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, a);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, b);
      gl.uniform1f(loc.fade, Math.max(0, Math.min(1, fade)));
      gl.uniform2f(loc.lean, leanX, leanY);
      gl.drawElements(gl.TRIANGLES, sheet.index.length, gl.UNSIGNED_SHORT, 0);
      return true;
    },
    dispose() {
      for (const t of Object.values(textures)) gl.deleteTexture(t);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    },
  };
}
