import { PhysicsBody } from './physics.js';

/** 单个粒子：挂载一个文字字符 + 物理属性 + 视觉属性 */
export class Particle extends PhysicsBody {
  constructor(char, x, y, options = {}) {
    super(x, y);
    /** 显示的文字字符 */
    this.glyph = char;
    /** 备用图片（未来扩展） */
    this.image = options.image || null;
    /** 备用几何图形类型（未来扩展） */
    this.shape = options.shape || null;

    // 视觉属性
    this.fontSize = options.fontSize || 24;
    this.fontFamily = options.fontFamily || 'sans-serif';
    this.fontWeight = options.fontWeight || 'normal';
    this.color = options.color || '#ffffff';
    this.opacity = options.opacity ?? 1;
    this.scale = options.scale ?? 1;
    this.rotation = options.rotation ?? 0;

    // 生命周期
    this.alive = true;
    this.age = 0;
    this.maxAge = options.maxAge ?? Infinity;

    // 用户自定义数据挂载点
    this.userData = {};
  }

  update(dt) {
    super.update(dt);
    this.age += dt;
    if (this.age >= this.maxAge) {
      this.alive = false;
    }
  }
}
