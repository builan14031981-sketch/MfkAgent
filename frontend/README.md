# MfkAgent

智能 Agent 工作平台。

## 启动

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8001

# 前端
cd frontend
npm install
npm run dev
```

## 技术栈

- Frontend: Next.js + Electron
- Backend: FastAPI + SQLAlchemy
- Database: SQLite
