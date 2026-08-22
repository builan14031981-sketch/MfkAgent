from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="Todo API")

# 内存存储
todos: dict[int, dict] = {}
next_id: int = 1


class TodoCreate(BaseModel):
    text: str


class TodoResponse(BaseModel):
    id: int
    text: str


@app.get("/")
def root():
    """根路由：说明各接口用法"""
    return {
        "message": "Todo API",
        "endpoints": {
            "GET /health": "健康检查",
            "GET /todos": "获取所有待办事项",
            "POST /todos": "新增待办事项 (body: {'text': 'xxx'})",
            "DELETE /todos/{id}": "删除指定 ID 的待办事项"
        }
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.get("/todos")
def get_todos():
    """获取所有待办事项"""
    return list(todos.values())


@app.post("/todos", response_model=TodoResponse)
def create_todo(todo: TodoCreate):
    """新增待办事项"""
    global next_id
    new_todo = {"id": next_id, "text": todo.text}
    todos[next_id] = new_todo
    next_id += 1
    return new_todo


@app.delete("/todos/{todo_id}")
def delete_todo(todo_id: int):
    """删除指定待办事项"""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    del todos[todo_id]
    return {"message": f"Todo {todo_id} deleted"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
