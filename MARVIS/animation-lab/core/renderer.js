/**
 * CanvasRenderer — 渲染器
 * 管理 Canvas、渲染循环、效果叠加
 */
export class CanvasRenderer {
  constructor(canvas, options = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.bgColor = options.bgColor || '#0a0a0f';

    /** 注册的效果列表，按顺序叠加渲染 */
    this.effects = [];

    this._running = false;
    this._lastTime = 0;
    this._rafId = null;
  }

  /** 注册一个效果（需实现 update(dt) 和 getParticles()） */
  addEffect(effect) {
    this.effects.push(effect);
  }

  /** 移除效果 */
  removeEffect(effect) {
    const idx = this.effects.indexOf(effect);
    if (idx !== -1) this.effects.splice(idx, 1);
  }

  start() {
    if (this._running) return;
    this._running = true;
    this._lastTime = performance.now();
    this._loop(this._lastTime);
  }

  stop() {
    this._running = false;
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
  }

  _loop(now) {
    if (!this._running) return;
    const dt = Math.min((now - this._lastTime) / 1000, 0.1); // 上限 100ms，防跳帧
    this._lastTime = now;

    this._update(dt);
    this._draw();

    this._rafId = requestAnimationFrame((t) => this._loop(t));
  }

  _update(dt) {
    for (const effect of this.effects) {
      if (effect.update) effect.update(dt);
    }
  }

  _draw() {
    const { ctx, canvas } = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 背景
    ctx.fillStyle = this.bgColor;
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // 逐效果逐粒子绘制
    for (const effect of this.effects) {
      const particles = effect.getParticles ? effect.getParticles() : [];
      for (const p of particles) {
        if (!p.alive) continue;

        ctx.save();
        ctx.globalAlpha = p.opacity;
        ctx.translate(p.position.x, p.position.y);
        ctx.rotate(p.rotation);
        ctx.scale(p.scale, p.scale);

        // 文字粒子
        if (p.glyph) {
          ctx.font = `${p.fontWeight} ${p.fontSize}px ${p.fontFamily}`;
          ctx.fillStyle = p.color;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(p.glyph, 0, 0);
        }
        // 图片粒子（预留）
        else if (p.image) {
          const w = p.fontSize * p.scale;
          const h = w * (p.image.height / p.image.width);
          ctx.drawImage(p.image, -w / 2, -h / 2, w, h);
        }

        ctx.restore();
      }
    }
  }

  /** 自适应窗口大小 */
  resizeToWindow() {
    this.canvas.width = window.innerWidth;
    this.canvas.height = window.innerHeight;
  }
}
