---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: fa3797463809205706cb55406b27ff93_8954ad8f961311f1b50c525400826444
    ReservedCode1: 5sH+AuA774SG3up6jXUV/rNj6BBFX3xPN4LbN8OzHJ3uHA+gkR5f19sWkWS1gII3ZzLh5LL6DMr1BLP+M/YiNPD3OA6QU1+Leo/vvgjyi3WeZMdf3vcQPhIe81lRnU0lJ401c1lyRsRCI0TvbR4ISiqagvk1nXTyzop/UjTbv/ZRHZThgBRGL6MR8TE=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: fa3797463809205706cb55406b27ff93_8954ad8f961311f1b50c525400826444
    ReservedCode2: 5sH+AuA774SG3up6jXUV/rNj6BBFX3xPN4LbN8OzHJ3uHA+gkR5f19sWkWS1gII3ZzLh5LL6DMr1BLP+M/YiNPD3OA6QU1+Leo/vvgjyi3WeZMdf3vcQPhIe81lRnU0lJ401c1lyRsRCI0TvbR4ISiqagvk1nXTyzop/UjTbv/ZRHZThgBRGL6MR8TE=
---

# 物理动画效果调研报告

> 调研范围：GitHub 上优秀的文字粒子动画项目，聚焦物理效果编码（非完整物理引擎）。

---

## 一、十大核心物理效果模式

### 1. 弹簧力 / 弹性系统（Spring-Damper）

**原理**：胡克定律 F = -k × (x - target)，每帧施加阻尼 friction。

```js
// 核心公式（来源：ParticleText 项目）
velocity.x += (targetX - position.x) * springConstant;
velocity.y += (targetY - position.y) * springConstant;
velocity.x *= friction;  // 典型值 0.82
velocity.y *= friction;
position.x += velocity.x;
position.y += velocity.y;
```

| 参数 | 典型值 | 效果 |
|------|--------|------|
| springConstant | 0.02~0.05 | 越大越"硬"，越小越"飘" |
| friction | 0.80~0.95 | 越接近 1 越有弹性，越小越快静止 |
| 模式切换 | 不同场景用不同系数 | 球体模式 0.02 / 文字模式 0.022 |

**来源**：[kshiteej-dev/ParticleText](https://github.com/kshiteej-dev/ParticleText) — 10000 粒子，3D 球体与文字间弹簧过渡

---

### 2. 刚体重力模拟（Rigid Body）

**原理**：使用 Box2D 物理（碰撞检测、动量、角动量、摩擦、弹性）。

```js
// forge2d（Box2D 的 Dart 移植）参数
gravity: 30.0,       // m/s²
density: 1.0,        // 密度
friction: 0.4,       // 摩擦系数
restitution: 0.1,    // 弹性（低值使堆叠稳定）
pixelsPerMeter: 50.0 // 世界坐标缩放
```

每个文字片段成为独立刚体，掉落、碰撞、堆积。支持点击踢飞、拖拽投掷。

**来源**：[YeLwinOo-Steve/pretty_animated_text](https://github.com/YeLwinOo-Steve/pretty_animated_text) — GravityText 效果

---

### 3. 排斥力 / 吸引力（Repulsion / Attraction）

**原理**：径向力，强度随距离衰减。

```js
// 排斥（来源：ParticleText）
const dx = particle.x - mouse.x;
const dy = particle.y - mouse.y;
const dist = Math.sqrt(dx * dx + dy * dy);
if (dist < REPEL_RADIUS) {  // 典型值 100px
  const force = REPEL_FORCE * (1 - dist / REPEL_RADIUS) * 5;  // 典型值 8
  velocity.x += (dx / dist) * force;
  velocity.y += (dy / dist) * force;
}
```

```js
// 吸引（来源：CodePen VerletPhysics2D）
physics.addBehavior(new AttractionBehavior(attractor, radius, strength));
// strength > 0 = 吸引, strength < 0 = 排斥
```

**变体**：鼠标经过文字时粒子散开，移开后弹簧拉回，形成"推散—回弹"循环。

---

### 4. Verlet 积分（Verlet Integration）

**原理**：比 Euler 更稳定的数值积分，能量守恒性好。

```js
// 来源：TyDomben/flow-field-particles
velocity += acceleration;
velocity.limit(maxSpeed);   // 速度上限防爆
position += velocity;
acceleration *= 0;          // 每帧清零
```

**优势**：对粒子系统极其稳定，不会因步长波动而发散。

**来源**：[TyDomben/flow-field-particles](https://github.com/TyDomben/flow-field-particles) + CodePen 上的 toxiclibs VerletPhysics2D 示例

---

### 5. 流场 / Curl Noise（流体运动）

**原理**：用 Perlin/Simplex 噪声生成速度场，粒子跟随场向量运动，产生有机的涡流感。

```js
// Curl Noise 核心（伪代码）
// 对 2D/3D 噪声场取旋度（curl），得到无散速度场
curl = (∂noise/∂y, -∂noise/∂x)  // 2D 情况
velocity = curl * strength;
```

**特征**：
- 完全非压缩性（无散度），粒子不会聚集也不会散开
- 比完整流体模拟轻量几个数量级
- 视觉效果：像风、烟雾、有机涡流

**来源**：[Sammii-HK/creative-coding](https://github.com/Sammii-HK/creative-coding) experiment-10 + [WebGPU Curl Noise](https://techblog.kayac.com/webgpu-particle-compute-shader-curl-noise)

---

### 6. Boids / 群集行为（Flocking）

**原理**：三条简单规则产生涌现行为。

```
分离（Separation）：避开邻近同伴
对齐（Alignment）：朝邻近同伴的平均方向
凝聚（Cohesion）：朝邻近同伴的平均位置
```

每条规则产生一个转向向量，加权叠加后驱动粒子运动。

**来源**：[Valentin-Lemaire/boids](https://github.com/Valentin-Lemaire/boids)

---

### 7. 3D 透视投影（Perspective Projection）

**原理**：模拟相机，产生深度感。

```js
// 来源：ParticleText
screenX = (worldX * FOV) / (worldZ + CAMERA_Z) + centerX;
screenY = (worldY * FOV) / (worldZ + CAMERA_Z) + centerY;
// FOV: 550, CAMERA_Z: 600
```

粒子在球面分布（斐波那契球），整体绕 Y 轴旋转，配合透视产生立体旋转效果。

---

### 8. 位图采样（Off-screen Canvas → 粒子坐标）

**原理**：文字渲染到隐藏 Canvas → 逐像素采样 → 以 alpha 通道为阈值提取坐标 → 分配给粒子作为目标位置。

```js
// 来源：ParticleText
const offCtx = offCanvas.getContext('2d');
offCtx.font = '900 ${fontSize}px Arial Black';
offCtx.fillText(text, 0, 0);

const imageData = offCtx.getImageData(0, 0, w, h);
for (let y = 0; y < h; y++) {
  for (let x = 0; x < w; x++) {
    if (imageData.data[(y * w + x) * 4 + 3] > 120) {  // alpha 阈值
      targets.push({ x, y });  // 收集文字像素坐标
    }
  }
}
// Fisher-Yates 随机打乱 → 粒子随机分配到文字像素
```

**关键技巧**：
- 加 ±0.4px 抖动避免网格感
- 自适应字号（根据文字长度和视口）
- 多行自动换行

---

### 9. 波形振荡 / 行波（Wave / Traveling Wave）

**原理**：正弦位移 + 时间偏移，形成波浪传播。

```js
// 基础正弦波
offset = sin(index * frequency * 60 + time * speed) * amplitude;
y = baseY + offset;

// 弹性行波（来源：pretty_animated_text SquashBounceText）
// 每个字依次下落 → 压扁 → 弹性回弹
// 各字的起止时间紧密排列，形成连续行波
dropFraction: 0.5,    // 下落幅度（相对字高）
squashScaleY: 0.3,    // 压扁时的 Y 缩放
rotateDegrees: 17,    // 峰值旋转角度
waveSpread: 0.6,      // 波紧凑度
```

**来源**：[YeLwinOo-Steve/pretty_animated_text](https://github.com/YeLwinOo-Steve/pretty_animated_text) SquashBounceText

---

### 10. 湍流 / 噪声扰动（Turbulence / Jitter）

**原理**：对粒子位置/颜色叠加多层噪声，产生有机的不规则感。

```js
// 轨道抖动
angle += random(-jitter, jitter);
radius += random(-jitter, jitter);

// 颜色漂移
hue = baseHue + noise(x, y) * hueRange;
```

**应用场景**：让球体粒子有"呼吸感"，防止机械感。

---

## 二、标杆项目速览

| 项目 | Stars | 核心技术 | 文件数 |
|------|-------|----------|--------|
| [kshiteej-dev/ParticleText](https://github.com/kshiteej-dev/ParticleText) | — | 弹簧力 + 3D 透视 + 排斥 + 位图采样 + Float32Array 高性能 | 单文件 |
| [YeLwinOo-Steve/pretty_animated_text](https://github.com/YeLwinOo-Steve/pretty_animated_text) | — | 弹簧/重力(B2D)/squash bounce/glitch RGB撕裂/scramble 乱码/reveal 扫光 | Flutter |
| [Sammii-HK/creative-coding](https://github.com/Sammii-HK/creative-coding) | — | 流场/粒子场/晶体生长/pixel sort/glitch/Lissajous万花筒/气泡玻璃 | 15+ 单文件实验 |
| [TyDomben/flow-field-particles](https://github.com/TyDomben/flow-field-particles) | — | Verlet积分 + 流场 + HSB渐变 + 触摸吸引子 | p5.js |
| [rajanarahul93/Particle-Text-Animation](https://github.com/rajanarahul93/Particle-Text-Animation) | — | 重力 + 鼠标排斥 + 粒子连线 + 拖尾 + 颜色循环 | 3 文件 |
| [Ashborn-047/kinetic-typography](https://github.com/Ashborn-047/kinetic-typography) | — | 弹性物理/色散层/3D日蚀阴影/glitch撕裂/vapor拖尾/pixel scramble/霓虹光晕/WebGL顶点/流体湍流 | GSAP+Three.js |

---

## 三、对 MARVIS Animation Lab 的建议架构

### 推荐物理效果模块设计

```
physics/
├── spring.js          # 弹簧力（最核心，80% 效果基于此）
├── repulsion.js       # 排斥/吸引力场
├── flowfield.js       # Perlin 噪声流场
├── verlet.js          # Verlet 积分器
├── gravity.js         # 简化重力（非 B2D，仅 Y 轴加速度 + 地面碰撞）
└── wave.js            # 波形传播工具函数
```

### 优先级排序（按画面冲击力 / 实现复杂度）

| 优先级 | 效果 | 视觉冲击力 | 实现难度 | 建议 |
|--------|------|-----------|---------|------|
| P0 | 弹簧力到目标位置 | ★★★★★ | ★★ | 粒子文字的核心引擎，必须先做 |
| P0 | 位图采样生成粒子 | ★★★★★ | ★★ | 文字→粒子坐标的唯一路径 |
| P1 | 排斥力（鼠标交互） | ★★★★ | ★ | 三行代码，交互感质变 |
| P1 | 波形振荡 | ★★★★ | ★ | 已有雏形，需加强行波 |
| P1 | Verlet 积分 | ★★★ | ★★ | 替代简单 Euler，稳定十倍 |
| P2 | 流场/Curl Noise | ★★★★★ | ★★★★ | 需要实现 2D/3D Simplex 噪声 |
| P2 | 简化重力+碰撞 | ★★★★ | ★★★ | 不做 B2D，只做 Y 轴 + 地面 |
| P3 | Boids 群集 | ★★★ | ★★★ | 适合粒子数量>500 的群体动画 |
| P3 | 3D 透视 | ★★★★ | ★★★ | 需调整现有渲染器架构 |

---

## 四、ParticleText 完整源码核心摘录

已抓取到完整源码（199 行 JS，10000 粒子），核心公式如下：

```js
// 1. 粒子数据结构（Float32Array × 13）
const N = 10000;
const px = new Float32Array(N);  // position x
const py = new Float32Array(N);
const pz = new Float32Array(N);
const vx = new Float32Array(N);  // velocity
const vy = new Float32Array(N);
const vz = new Float32Array(N);
const tx = new Float32Array(N);  // target
const ty = new Float32Array(N);
const tz = new Float32Array(N);
const ox = new Float32Array(N);  // original sphere home
const oy = new Float32Array(N);
const oz = new Float32Array(N);
const hue = new Float32Array(N);  // per-particle hue
const phase = new Float32Array(N); // wobble phase

// 2. 斐波那契球面分布（默认空闲态）
const phi = Math.acos(1 - 2 * (i + 0.5) / N);
const theta = Math.PI * (1 + Math.sqrt(5)) * i;
ox[i] = R * Math.sin(phi) * Math.cos(theta);
oy[i] = R * Math.sin(phi) * Math.sin(theta);
oz[i] = R * Math.cos(phi);

// 3. 位图采样 → 目标位置
// 渲染文字到 offCanvas → getImageData → 遍历 alpha>120 的像素
// 如果采样点数 > N，随机取子集
// 如果采样点数 < N，部分粒子维持球面位置

// 4. 每帧物理更新
const sp = appState === 0 ? 0.02 : 0.022;  // 弹簧系数
for (let i = 0; i < N; i++) {
  vx[i] += (tx[i] - px[i]) * sp;
  vy[i] += (ty[i] - py[i]) * sp;
  vz[i] += (tz[i] - pz[i]) * sp;
  vx[i] *= 0.82;  // 摩擦
  vy[i] *= 0.82;
  vz[i] *= 0.82;
  px[i] += vx[i];
  py[i] += vy[i];
  pz[i] += vz[i];
}

// 5. 光标排斥（仅文字模式）
if (appState === 1 && mouseActive) {
  const sx = (px[i] * FOV) / (pz[i] + CAM_Z) + cx;  // 先投影到屏幕
  const sy = (py[i] * FOV) / (pz[i] + CAM_Z) + cy;
  const dx = sx - mouseX;
  const dy = sy - mouseY;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist < REPEL_RADIUS) {
    const force = REPEL_FORCE * (1 - dist / REPEL_RADIUS);
    // 把屏幕空间的力逆投影回 3D 世界施加到速度上
  }
}

// 6. 3D 投影
const sx = (px[i] * FOV) / (pz[i] + CAM_Z) + cx;
const sy = (py[i] * FOV) / (pz[i] + CAM_Z) + cy;
// 粒子大小随 z 深度缩放
const scale = FOV / (pz[i] + CAM_Z);
const radius = 1.8 * scale;
```

---

## 五、其他值得关注的项目

| 项目/资源 | 亮点 |
|-----------|------|
| [anvaka/fieldplay](https://github.com/anvaka/fieldplay) | 交互式向量场可视化，直接在浏览器里画流线 |
| [codrops/ParticleEffectsButtons](https://github.com/codrops/ParticleEffectsButtons) | 按钮点击爆炸粒子效果 |
| [catdad/canvas-confetti](https://github.com/catdad/canvas-confetti) | 高性能五彩纸屑（庆典撒花效果） |
| [crashmax-dev/fireworks-js](https://github.com/crashmax-dev/fireworks-js) | 烟花粒子系统 |
| [barrior/jparticles](https://github.com/barrior/jparticles) | 轻量 Canvas 粒子库（雪/波浪/液态填充/加载动画） |
*（内容由AI生成，仅供参考）*
