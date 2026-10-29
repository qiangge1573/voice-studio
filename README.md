# Voice Studio · 声音克隆工作台

> 录制一段声音样本 → 生成专属克隆音色 → 用它朗读文本、给视频配音、批量合成。三端一栈：**微信小程序** + **网页版** + **FastAPI 后端**。

参考开源项目 [debpalash/VoiceStudio](https://github.com/debpalash/VoiceStudio) 的核心思路，落地为可直接使用的全栈工程：

- **微信小程序端** `miniprogram/`：原生小程序，录音采样 → 音色库 → 文本合成 → 视频配音 → 批量合成 → 历史回放；
- **网页版** `web/`：单页原生 HTML/JS，浏览器直开，功能与小程序对齐；
- **后端** `server/`：Python FastAPI + SQLite + 自签 JWT + 线程池异步任务，引擎可插拔；
- **云 TTS（默认）**：火山引擎（豆包语音）**few-shot 声音复刻**，参考音频 + 文本一次请求完成合成，无需训练流程；未配置密钥时自动回退 Mock 引擎，demo 无密钥也能跑通全流程。

> ⚠️ 合规提示：本功能仅用于克隆**本人或已获授权**的声音。界面内置授权确认，云合成默认开启 AIGC 水印（AI 生成内容标识），前端结果均标注「AI 合成内容」。禁止未经授权克隆、冒充他人声音或用于欺诈等违法用途。

## 功能一览

| 模块 | 说明 |
| --- | --- |
| 录音采样 | 小程序 RecorderManager / 网页 MediaRecorder 录制 5–20s 样本（网页端自动转 16kHz 单声道 WAV），试听后可重录 |
| 音色库 | 上传样本创建音色、试听、删除、「去合成」直达 |
| 文本合成 | 选择音色 + 输入文本 → 异步任务 → 轮询 → 播放（标注 AI 合成内容） |
| 视频配音 | 上传视频 + 配音台本（`[mm:ss]` 时间锚点 / 顺序接续可混用）→ 逐段云合成 → ffmpeg 按时间轴混音（叠加或替换原声）→ 输出 mp4 |
| 批量合成 | 多行文本一次提交（≤100 行），逐条合成、逐个试听 |
| 合成历史 | 回放、下载、删除历史记录 |
| 登录鉴权 | 微信 jscode2session → 自签 JWT；开发模式（dev_login）免微信联调 |

## 网页截图

| 首页 | 克隆音色 |
| --- | --- |
| ![首页](screenshots/home.png) | ![克隆音色](screenshots/record.png) |

> 截图于本地打开、mock 引擎（未配置 `VOLC_API_KEY`，合成输出为演示音）的运行状态；配置真实后端与 `VOLC_API_KEY` 后引擎状态与合成效果随之生效。

## 架构

完整架构图见 [`docs/architecture.html`](docs/architecture.html)（浏览器打开）。

```
前端（小程序 miniprogram/ ｜ 网页版 web/）
├─ 录音采样          RecorderManager（小程序）/ MediaRecorder→WAV16k（网页）
├─ 音色库 / 合成 / 配音 / 批量 / 历史
└─ 请求层            HTTPS · Bearer JWT · 音频/视频 URL 兼容 ?token=
        │
FastAPI 后端 server/
├─ /api/auth/login    微信 code2session → JWT（dev 模式免登录）
├─ /api/voices        上传样本 / 列表 / 试听 / 删除（consent 授权校验）
├─ /api/tts           合成提交 → 异步任务 → 轮询 → 音频
├─ /api/dubbing       视频配音：上传视频+台本 → 逐段合成 → ffmpeg 混音 → mp4
├─ /api/batch         批量合成：多行文本 → 逐条合成 → 逐条音频
├─ /api/history       历史列表 / 删除
├─ SQLite             users / voices / tts_tasks / dubbing_tasks / batch_tasks
└─ engines/           cloud(火山云TTS,默认) ｜ mock(占位音频联调) ｜ xtts ｜ cosyvoice
```

## 目录结构

```
voice-studio/
├─ README.md
├─ docs/architecture.html      # 架构可视化（浏览器打开）
├─ screenshots/                # 网页版截图
├─ miniprogram/                # 微信小程序前端（微信开发者工具导入此目录）
│  ├─ app.js / app.json / app.wxss / project.config.json / sitemap.json
│  ├─ utils/        api.js（请求/上传/登录/authUrl）· config.js（后端地址/登录模式）
│  ├─ components/   voice-card（音色卡片）
│  └─ pages/        index · record · voices · synthesize · history · dubbing · batch
├─ web/                        # 网页版（单页原生 HTML/JS，浏览器直开）
│  ├─ index.html / styles.css / app.js
└─ server/                     # Python FastAPI 后端
   ├─ main.py  requirements.txt  .env.example  scripts/download_models.py
   ├─ app/          config · database · auth · deps · audio_utils · video_utils · task_manager
   ├─ app/engines/  base · cloud · mock · xtts · cosyvoice
   └─ app/routers/  auth · voices · tts · dubbing · batch · history
```

## 快速开始

### 1. 启动后端

```bash
cd server
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # 按需配置 VOLC_API_KEY / JWT_SECRET 等

# 默认云引擎；未配 VOLC_API_KEY 时自动回退 mock 引擎（输出占位音频）
python main.py
# → http://0.0.0.0:8000  /api/health 返回 {"status":"ok","engine":"cloud|mock","dev_mode":true}
```

### 2. 打开网页版

浏览器直接打开 `web/index.html`（或已发布链接）。默认连接 `http://127.0.0.1:8000`；部署公网后点页面右上角齿轮修改后端地址（自动记忆）。

### 3. 运行微信小程序

用微信开发者工具导入 `miniprogram/` 目录；`utils/config.js` 中 `BASE_URL` 指向后端地址（小程序需配置 request/uploadFile 合法域名，本地调试可勾选「不校验合法域名」）。

## 云 TTS 配置（火山引擎 · 豆包语音）

| 项 | 值 |
| --- | --- |
| 合成接口 | `POST https://openspeech.bytedance.com/api/v3/tts/create`（音频生成 HTTP，few-shot 即时复刻） |
| 鉴权 | 请求头 `X-Api-Key`（+ `X-Api-Request-Id`，uuid） |
| 请求体 | `{"model":"seed-audio-1.0","text_prompt":"文本","audio_data":"参考音频base64","audio_config":{"format":"mp3","sample_rate":24000},"watermark":{"aigc_watermark":true}}` |
| 限制 | 参考音频 ≤30s / ≤10MB；文本 ≤2048 字符；输出 ≤120s |
| 环境变量 | `VOLC_API_KEY`（必填才启用云引擎） |
| 文档 | [音频生成 HTTP](https://www.volcengine.com/docs/6561/2550782?lang=zh) · [音色训练 HTTP](https://www.volcengine.com/docs/6561/2534906?lang=zh) |

> 选择 few-shot「音频生成」而非训练式「音色训练」的原因：前者无需 speaker_id 与训练流程，参考音频 + 文本一次请求完成，与「样本即音色」的架构完全吻合。

### 引擎切换

| 引擎 | 配置 | 说明 |
| --- | --- | --- |
| `cloud`（默认） | `ENGINE=cloud` + `VOLC_API_KEY` | 火山云 few-shot 复刻；无密钥自动回退 mock |
| `mock` | `ENGINE=mock` | 占位正弦波音频，全流程联调用 |
| `xtts` / `cosyvoice` | `ENGINE=xtts|cosyvoice` + `COSYVOICE_MODEL_DIR` 等 | 自托管开源模型，需 GPU，见 `scripts/download_models.py` |

## API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | `{"code":"dev"}`（dev 模式）或微信 code → `{token, user}` |
| POST | `/api/voices` | multipart `file` + `name`/`lang`/`consent=1` 创建音色 |
| GET | `/api/voices` · `/api/voices/{id}/sample` · DELETE `/api/voices/{id}` | 列表 / 试听 / 删除 |
| POST | `/api/tts/synthesize` | `{voice_id, text(≤1000字), language}` → `{task_id}` |
| GET | `/api/tts/tasks/{id}` · `/api/tts/tasks/{id}/audio` | 轮询状态 / 下载音频 |
| POST | `/api/dubbing` | multipart `file`(≤100MB) + `voice_id/script/mode(overlay|replace)` |
| GET | `/api/dubbing/tasks` · `/api/dubbing/tasks/{id}` · `.../video` | 任务列表 / 状态 / 下载成片 |
| POST | `/api/batch` | `{voice_id, lines(≤100行), language}` → 任务轮询含 `items[]` |
| GET/DELETE | `/api/history` · `/api/history/{task_id}` | 历史列表 / 删除 |

鉴权：除 `login` 外均需 `Authorization: Bearer <token>`；**音频/视频下载接口兼容 `?token=` 查询参数**（便于小程序与网页 `<audio>/<video>` 直接播放）。

## 配置项（`server/.env`）

```env
ENGINE=cloud                    # cloud | mock | xtts | cosyvoice
VOLC_API_KEY=                   # 火山引擎密钥（cloud 必需）
WECHAT_APP_ID=                  # 微信小程序（留空则 dev 模式）
WECHAT_APP_SECRET=
JWT_SECRET=change-me            # 生产环境请更换
HOST=0.0.0.0
PORT=8000
DEVICE=cpu                      # cuda | cpu
COSYVOICE_MODEL_DIR=
DATA_DIR=./data                 # 样本 / 合成音频 / 视频 / SQLite
```

## 合规与安全（深度合成）

- 录音页强制**声音授权确认**（前端勾选 + 后端 `consent=1` 双重校验）；
- 云合成默认开启 `aigc_watermark`（合成音频结尾节奏标识），前端结果标注「AI 合成内容」；
- 面向小程序/App 上架时，请按所在平台要求完成深度合成服务提供者备案与功能标识；
- 生产部署务必更换 `JWT_SECRET`、为 `VOLC_API_KEY` 配置密钥托管、后端仅暴露 HTTPS。

## License

[MIT](LICENSE)
