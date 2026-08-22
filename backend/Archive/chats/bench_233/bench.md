# bench
Agent: coder
Project: coder_glm51_bench
Created: 2026-08-13 05:59:07.898933

---

**User** (2026-08-13 05:59:07.925440):
代码审查任务（只读，不修改）：审查以下代码，按 P0-P3 分级指出问题并给出修复建议：
```python
def process(data):
    q = "SELECT * FROM users WHERE id = " + data
    import os
    for f in os.listdir(data):
        pass
    return eval(q)
```

**Assistant** (2026-08-13 05:59:57.272101):
代码已在消息中直接提供，无需读取文件。以下是审查结果：

---

## 代码审查报告

```python
def process(data):
    q = "SELECT * FROM users WHERE id = " + data
    import os
    for f in os.listdir(data):
        pass
    return eval(q)
```

### 问题清单

| # | 位置 | 问题描述 | 严重程度 | 修复建议 |
|---|------|---------|---------|---------|
| 1 | `q = "SELECT * FROM users WHERE id = " + data` | **SQL 注入**：直接拼接用户输入构造 SQL，攻击者可注入任意 SQL（如 `1; DROP TABLE users`） | **P0** | 使用参数化查询：`cursor.execute("SELECT * FROM users WHERE id = %s", (data,))` |
| 2 | `return eval(q)` | **任意代码执行**：`eval()` 对字符串求值等同于执行任意 Python 代码，且此处入参是拼接了用户输入的 SQL 字符串，攻击者可构造 `__import__('os').system('rm -rf /')` 等恶意代码 | **P0** | 永远不要对不可信输入使用 `eval()`。如需执行 SQL，应通过数据库驱动（如 `psycopg2`/`sqlite3`）的参数化接口；如需动态求值，用 `ast.literal_eval()` 替代 |
| 3 | `os.listdir(data)` | **路径穿越**：`data` 未做任何校验，攻击者可传入 `../../etc` 等路径遍历敏感目录 | **P1** | 校验并规范化路径：`base = Path("/safe/dir").resolve(); target = (base / data).resolve(); assert target.is_relative_to(base)` |
| 4 | `import os`（函数体内导入） | **风格问题**：在函数体内 `import`，每次调用都执行 import 语句，且违反 PEP 8 将导入置于模块顶部的约定 | **P3** | 将 `import os` 移至文件顶部 |
| 5 | 函数签名 `def process(data)` | **类型缺失**：参数和返回值无类型注解，可读性差 | **P3** | 添加类型注解：`def process(data: str) -> Any` |
| 6 | 整体函数设计 | **职责混乱**：一个函数同时做 SQL 拼接、文件系统遍历、动态代码执行，严重违反单一职责原则 | **P2** | 拆分为独立函数：`query_user(user_id)` / `list_directory(path)` |

### 修复后参考代码

```python
import os
from pathlib import Path

ALLOWED_DIR = Path("/safe/dir").resolve()

def query_user(user_id: str) -> dict | None:
    """通过参数化查询获取用户信息"""
    # cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    ...  # 使用数据库驱动的参数化查询

def list_safe_directory(relative_path: str) -> list[str]:
    """在允许目录内安全列出文件"""
    target = (ALLOWED_DIR / relative_path).resolve()
    if not target.is_relative_to(ALLOWED

