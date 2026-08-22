import { Particle } from '../core/particle.js';
import { BasicPhysics } from '../core/physics.js';

/**
 * TextWave — 文字波浪效果
 * 将一段文字拆成粒子，按正弦波浮动，颜色渐变
 */
export class TextWave {
  constructor(canvas, text, options = {}) {
    this.canvas = canvas;
    this.physics = new BasicPhysics({ damping: 0.98, gravity: 0 });

    /** 显示的完整文字 */
    this.text = text;
    /** 粒子数组 */
    this.particles = [];

    // 可配置参数
    this.fontSize = options.fontSize || 48;
    this.fontFamily = options.fontFamily || '"Microsoft YaHei", "PingFang SC", sans-serif';
    this.fontWeight = options.fontWeight || 'bold';
    this.amplitude = options.amplitude || 40;       // 波浪振幅
    this.frequency = options.frequency || 0.004;    // 波浪频率
    this.speed = options.speed || 2;                 // 波浪速度
    this.spacing = options.spacing || 0.85;          // 字间距系数（相对 fontSize）
    this.colorStart = options.colorStart || [100, 200, 255]; // 左侧颜色 RGB
    this.colorEnd = options.colorEnd || [255, 100, 200];     // 右侧颜色 RGB

    this._time = 0;
    this._init();
  }

  _init() {
    const chars = [...this.text]; // 正确处理中文多字节字符
    const totalWidth = chars.length * this.fontSize * this.spacing;
    const startX = (this.canvas.width - totalWidth) / 2 + this.fontSize / 2;
    const baseY = this.canvas.height / 2;

    for (let i = 0; i < chars.length; i++) {
      const x = startX + i * this.fontSize * this.spacing;
      const t = chars.length > 1 ? i / (chars.length - 1) : 0.5;

      const r = Math.floor(this.colorStart[0] + (this.colorEnd[0] - this.colorStart[0]) * t);
      const g = Math.floor(this.colorStart[1] + (this.colorEnd[1] - this.colorStart[1]) * t);
      const b = Math.floor(this.colorStart[2] + (this.colorEnd[2] - this.colorStart[2]) * t);

      const p = new Particle(chars[i], x, baseY, {
        fontSize: this.fontSize,
        fontFamily: this.fontFamily,
        fontWeight: this.fontWeight,
        color: `rgb(${r},${g},${b})`,
        opacity: 0.9
      });
      p.userData.baseY = baseY;
      p.userData.index = i;
      this.particles.push(p);
      this.physics.addBody(p);
    }
  }

  update(dt) {
    this._time += dt * this.speed;
    for (const p of this.particles) {
      const offset = Math.sin(p.userData.index * this.frequency * 60 + this._time * 3) * this.amplitude;
      p.position.y = p.userData.baseY + offset;
      // 根据偏移量微调透明度，增加层次感
      p.opacity = 0.7 + (offset / this.amplitude + 1) * 0.15;
    }
    this.physics.step(dt);
  }

  getParticles() {
    return this.particles;
  }

  /** 窗口大小变化时重新布局 */
  resize(canvas) {
    this.canvas = canvas;
    this.physics.clear();
    this.particles = [];
    this._init();
  }
}
