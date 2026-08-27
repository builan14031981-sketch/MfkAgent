---
name: comfyui
description: 当用户要在本地用 ComfyUI 生成或修改图片时使用——文生图、二次高清放大、参考图生图（IPAdapter）、参考图+高清。通过调用本机 ComfyUI 的 REST API（comfy_call.py）完成，无需安装任何额外服务/MCP Server。
---

# ComfyUI 本地生图调用

让 Agent 直接调用本机 ComfyUI（127.0.0.1:8188）出图。ComfyUI 那头无需任何改动，Agent 这头只需要一个零依赖的 Python 调用器 comfy_call.py。

## 前置条件（务必先确认）

1. ComfyUI 正在运行且监听 http://127.0.0.1:8188。
   启动命令（不要用带 --use-sage-attention 的方式，否则 IPAdapter 会出全黑图）：
   "E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\python\python.exe" "E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\ComfyUI\main.py" --auto-launch --preview-method auto --disable-cuda-malloc
2. 调用器与 4 套工作流在：E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\ComfyUI\workflows_opencode\
   - comfy_call.py（通用调用器，仅用标准库，无需 pip 安装）
   - 01_快捷出图_T2I.json / 02_二次渲染高清_T2I_HiRes.json
   - 03_加参考图一次出图_IPAdapter.json / 04_加参考图二次高清_IPAdapter_HiRes.json

## 动态发现工作流（重要）

- 当用户问"有哪些工作流 / 列出工作流"，或你对具体文件名不确定时，**先运行** `python comfy_call.py --list` 获取当前真实清单（含中文别名、用途、是否需 --ref），再决定用哪个。
- 下方「工作流选择指南」是常见意图的快速映射，但 `--list` 才是权威来源。以后若增删工作流，以 `--list` 输出为准，无需改本文档。

## 工作流选择指南（按用户意图选）

| 用户想要 | 工作流 | 是否需要参考图 |
| --- | --- | --- |
| 直接凭文字出一张图 | 01_快捷出图_T2I.json | 否 |
| 出图后再放大/变清晰（高清修复） | 02_二次渲染高清_T2I_HiRes.json | 否 |
| 照着某张参考图出同风格/同构图的图 | 03_加参考图一次出图_IPAdapter.json | 是（--ref） |
| 参考图 + 再高清放大 | 04_加参考图二次高清_IPAdapter_HiRes.json | 是（--ref） |

## 中文别名（口语调用）

除了文件名，`--workflow` 也接受中文别名；你也可直接用自然语言描述意图，由 Agent 映射到对应工作流：

- 快捷出图 / 文生图 → 01_快捷出图_T2I.json
- 高清修复 / 二次高清 → 02_二次渲染高清_T2I_HiRes.json
- 参考图生图 → 03_加参考图一次出图_IPAdapter.json（需 --ref）
- 参考图高清 → 04_加参考图二次高清_IPAdapter_HiRes.json（需 --ref）

口语示例：
- "用参考图生图工作流，参考图是 C:\a.jpg，画同角色新姿势"
- 或命令：`python comfy_call.py --workflow 参考图生图 --ref C:\a.jpg --prompt "same character"`

## 调用方式

用 Bash 运行（路径按上面填）：

python "E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\ComfyUI\workflows_opencode\comfy_call.py" --workflow 01_快捷出图_T2I.json --prompt "masterpiece, best quality, 1girl, silver hair, cherry blossoms" --neg "lowres, bad anatomy, worst quality, blurry" --seed 1 --steps 20 --cfg 7

参考图生图（IPAdapter）：

python "E:\BaiduNetdiskDownload\ComfyUI-aki-v3.2\ComfyUI\workflows_opencode\comfy_call.py" --workflow 03_加参考图一次出图_IPAdapter.json --prompt "same character, new pose" --ref "C:\path\to\ref.jpg" --seed 5

## 参数说明

- --workflow 必填，工作流文件名、完整路径，或中文别名（如 快捷出图 / 二次高清 / 参考图生图）。
- --prompt 正面提示词（英文效果更好，模型是 SD1.5）。
- --neg 负面提示词，默认已有一套通用负面词，可覆盖。
- --ref 参考图路径，仅 IPAdapter 工作流用；脚本会自动上传并接到 LoadImage。
- --model 模型名称或别名（写实/摄影: `realistic`, 精细插画/概念: `counterfeit` / `artistic`, 二次元/动漫: `anime`）。
- --seed 种子，不填则随机。
- --steps / --cfg 采样步数 / 引导系数，应用到所有 KSampler。
- --width / --height 覆盖出图尺寸（仅作用于 EmptyLatentImage，高清工作流会自动放大 2x）。
- --host ComfyUI 地址，默认 http://127.0.0.1:8188（换机器/端口时改这里）。
- --out 结果保存目录，默认 comfy_call.py 同目录下的 results\。
- --list 列出当前可用工作流及用法后退出（含中文别名；其他平台接入时可用它做自检）。

脚本会：提交 /prompt -> 轮询 /history 直到完成 -> 通过 /view 下载图片到 --out -> 打印每张图的最终本地路径。把返回的图片路径直接给用户即可。

## 故障排查

- 出图全黑：几乎都是因为 ComfyUI 启动时带了 --use-sage-attention。用上面的无 sage 命令重启 ComfyUI 即可。
- 找不到工作流 / 连不上 8188：确认 ComfyUI 已启动、端口对；可用 --list 核对当前工作流名。
- IPAdapter 报错 "model not present"：不要用 IPAdapterModelLoader，工作流里用的是 IPAdapterUnifiedLoader（已内置正确接法）。

## 给其他 Agent 平台（通用性）

本 skill 刻意做成平台无关：任何支持"运行 shell 命令 + 读 SKILL.md"的 Agent（Claude Code、Cursor、自研 Agent 等）只要把 comfyui-skill/ 这个文件夹整体放进自己的 skills 目录就能用。核心逻辑都在 comfy_call.py 这一份零依赖脚本里，平台只负责在合适时机调用它。