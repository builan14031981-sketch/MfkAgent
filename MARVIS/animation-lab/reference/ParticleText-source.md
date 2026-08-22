---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: fa3797463809205706cb55406b27ff93_8a894aea961311f195a2525400e6dd8f
    ReservedCode1: 846Hgg1y4J6SSWmXhx79AmCLKgtoiUtzktVxxX5QgDKwTyP6sqR32d5zBXQ/1hNzTLnCyH0dcyTNQk6Vw50kgD7WZ0XtH7bYnGmUgqFHxf48BV+ekm2dqFZ3GRy7rZWigkDbWzVdW11uc7g+M9zb3Pd2kC0DWFYypB3ioLzShbcvukMTl50rSzl0zpQ=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: fa3797463809205706cb55406b27ff93_8a894aea961311f195a2525400e6dd8f
    ReservedCode2: 846Hgg1y4J6SSWmXhx79AmCLKgtoiUtzktVxxX5QgDKwTyP6sqR32d5zBXQ/1hNzTLnCyH0dcyTNQk6Vw50kgD7WZ0XtH7bYnGmUgqFHxf48BV+ekm2dqFZ3GRy7rZWigkDbWzVdW11uc7g+M9zb3Pd2kC0DWFYypB3ioLzShbcvukMTl50rSzl0zpQ=
---

# ParticleText 完整源码（学习参考）

来源: https://github.com/kshiteej-dev/ParticleText (MIT License)
抓取日期: 2026-08-12

核心要点:
- 10000 粒子, Float32Array 零 GC
- 斐波那契球面分布 + 弹簧力 + 摩擦阻尼 + 光标排斥 + 3D 透视投影
- 位图采样: offscreen canvas 渲染文字 → getImageData → alpha>120 收集坐标
- Fisher-Yates 打乱, 目标分配避免聚集
- 弹簧系数: sphere 0.02 / text 0.022, 摩擦 0.82

--- 以下是核心 JS 片段摘录 ---

// 1. 粒子数据 (Float32Array)
const N = 10000;
const px = new Float32Array(N), py = new Float32Array(N), pz = new Float32Array(N);
const vx = new Float32Array(N), vy = new Float32Array(N), vz = new Float32Array(N);
const tx = new Float32Array(N), ty = new Float32Array(N), tz = new Float32Array(N);
const ox = new Float32Array(N), oy = new Float32Array(N), oz = new Float32Array(N);
const hue = new Float32Array(N), phase = new Float32Array(N);

// 2. 斐波那契球面分布
const PHI = Math.PI * (1 + Math.sqrt(5));
for (let i = 0; i < N; i++) {
    const polar = Math.acos(1 - 2 * (i + 0.5) / N);
    const azim = PHI * i;
    ox[i] = Math.sin(polar) * Math.cos(azim) * R;
    oy[i] = Math.sin(polar) * Math.sin(azim) * R;
    oz[i] = Math.cos(polar) * R;
    tx[i] = ox[i]; ty[i] = oy[i]; tz[i] = oz[i];
}

// 3. 位图采样 → 粒子目标
function sampleTextPositions(phrase) {
    const off = document.createElement('canvas');
    off.width = cW; off.height = cH;
    const c2 = off.getContext('2d');
    // 多行换行 + 自适应字号
    // 渲染: c2.font = `900 ${fs}px Arial Black`; c2.fillText(line, cW/2, y);
    const data = c2.getImageData(0, 0, cW, cH).data;
    const pts = [];
    for (let y = 0; y < cH; y += step) {
        for (let x = 0; x < cW; x += step) {
            if (data[(y * cW + x) * 4 + 3] > 120) {
                pts.push(x - cW/2 + (Math.random()-0.5)*0.8, y - cH/2 + (Math.random()-0.5)*0.8);
            }
        }
    }
    // Fisher-Yates shuffle
    return pts;
}

// 4. 每帧物理更新 (核心!)
const sp = appState === 0 ? 0.02 : 0.022;
for (let i = 0; i < N; i++) {
    // Y 轴旋转目标
    const cosY = Math.cos(rotY), sinY = Math.sin(rotY);
    let targetX = tx[i] * cosY - tz[i] * sinY;
    let targetY = ty[i];
    let targetZ = tx[i] * sinY + tz[i] * cosY;

    // 弹簧力
    vx[i] += (targetX - px[i]) * sp;
    vy[i] += (targetY - py[i]) * sp;
    vz[i] += (targetZ - pz[i]) * sp;

    // 光标排斥 (先投影到屏幕空间)
    const scale = FOV / (FOV + pz[i] + CAMERA_Z);
    const sx = px[i] * scale + CX;
    const sy = py[i] * scale + CY;
    const rdx = sx - mouseX, rdy = sy - mouseY;
    const d2 = rdx*rdx + rdy*rdy;
    if (d2 < REPEL_RADIUS*REPEL_RADIUS && d2 > 1) {
        const d = Math.sqrt(d2);
        const mag = REPEL_FORCE * (1 - d/REPEL_RADIUS) * 5;
        vx[i] += (rdx/d) * mag;
        vy[i] += (rdy/d) * mag;
    }

    // 摩擦阻尼
    vx[i] *= 0.82; vy[i] *= 0.82; vz[i] *= 0.82;
    px[i] += vx[i]; py[i] += vy[i]; pz[i] += vz[i];
}

// 5. 3D 透视投影渲染
const zPos = pz[i] + CAMERA_Z;
const scale = FOV / zPos;
const sx = px[i] * scale + CX;
const sy = py[i] * scale + CY;
// 速度越大越亮越大: a = min(1, (0.18 + spd*0.1) * (scale*0.65));
// 拖尾: ctx.fillStyle = 'rgba(5,5,15,0.22)' 半透明背景覆盖

// 参数速查
// REPEL_RADIUS = 100, REPEL_FORCE = 8, FOV = 550, CAMERA_Z = 600
// rotY += 0.006 (球体旋转), jitter = 1.8 (球体浮动)
*（内容由AI生成，仅供参考）*
