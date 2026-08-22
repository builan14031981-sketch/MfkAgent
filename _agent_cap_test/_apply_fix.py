import urllib.request, json

BASE = 'http://127.0.0.1:8001/api'

def call(method, path, payload=None):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {'HTTP_ERROR': e.code, 'body': e.read().decode('utf-8', 'ignore')}

# 1. 把 chat 303 / 304 的模型切成 qwen-plus（修复空参数根因）
for cid in (303, 304):
    res = call('PATCH', f'/chat/{cid}', {'model': 'qwen-plus'})
    print(f'PATCH chat {cid} ->', {k: res.get(k) for k in ('id', 'model', 'agent_id', 'project_id')})

# 2. 新建干净会话（熔断计数器全新），frontend_ui + qwen-plus + 项目1
new = call('POST', '/chat', {
    'agent_id': 'frontend_ui',
    'project_id': 1,
    'model': 'qwen-plus',
    'mode': 'build',
    'title': 'UI 修复验证（新会话）',
})
print('NEW chat ->', {k: new.get(k) for k in ('id', 'model', 'agent_id', 'project_id', 'project_path', 'mode')})
