/**
 * PhysicsBody — 抽象物理体接口
 * 后续实现 PhysicalBody 的类必须暴露这些属性/方法
 */
export class PhysicsBody {
  constructor(x = 0, y = 0) {
    this.position = { x, y };
    this.velocity = { x: 0, y: 0 };
    this.acceleration = { x: 0, y: 0 };
    this.mass = 1;
  }

  /** 每物理步进更新一次，子类可覆写 */
  update(dt) {
    this.velocity.x += this.acceleration.x * dt;
    this.velocity.y += this.acceleration.y * dt;
    this.position.x += this.velocity.x * dt;
    this.position.y += this.velocity.y * dt;
  }

  /** 施加瞬时力 */
  applyForce(fx, fy) {
    this.acceleration.x += fx / this.mass;
    this.acceleration.y += fy / this.mass;
  }
}

/**
 * PhysicsWorld — 物理世界接口
 * 初期空壳实现，仅做匀速运动 + 基础阻尼
 */
export class BasicPhysics {
  constructor(options = {}) {
    this.bodies = [];
    this.damping = options.damping ?? 0.98;
    this.gravity = options.gravity ?? 0;
  }

  addBody(body) {
    this.bodies.push(body);
  }

  removeBody(body) {
    const idx = this.bodies.indexOf(body);
    if (idx !== -1) this.bodies.splice(idx, 1);
  }

  step(dt) {
    for (const body of this.bodies) {
      body.acceleration.x = 0;
      body.acceleration.y = this.gravity;
      body.update(dt);
      body.velocity.x *= this.damping;
      body.velocity.y *= this.damping;
    }
  }

  clear() {
    this.bodies.length = 0;
  }
}
