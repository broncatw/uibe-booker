# uibe-booker · 贸大预约助手

对外经济贸易大学图书馆 **IC 信息共享空间预约系统**（seat.uibe.edu.cn）的命令行助手：**图书馆座位预约、研讨间（小组讨论室）预约、我的预约管理**，一条命令完成。

> ⚠️ 使用说明：本工具是个人便捷预约客户端，请遵守图书馆预约规定（按时签到、不恶意占座、不高频请求）。接口路径如遇学校升级调整，按下方"接口抓包校准"自行更新配置即可。

## 系统背景（2026-09 调研）

- 图书馆预约系统入口：http://seat.uibe.edu.cn/（"Information Commons" 系统，Vue SPA + `/ic-web` JSON API）
- 预约渠道：微信公众号 / 网页 / 一层大厅触摸屏
- 模块：座位（8）、研讨间（1）、考研座位（32）
- 座位按时段管理（如 15:30–18:30 可预约当日 18:30–22:00 时段）
- 空教室（教学楼）查询/借用走教务综合管理系统 zhjw.uibe.edu.cn（需校园网/VPN + 教务账号），与本工具相互独立

## 安装与配置

```bash
pip install requests          # 唯一运行依赖
cp config.example.toml config.local.toml
# 编辑 config.local.toml，填入学号与密码（该文件已被 .gitignore 排除）
```

或使用环境变量 `UIBE_USERNAME` / `UIBE_PASSWORD`。

## 使用

```bash
python -m uibe_booker login-test                     # 测试账号密码是否可用
python -m uibe_booker areas                          # 楼栋/区域列表
python -m uibe_booker spaces <building_id>           # 阅览区/研讨间列表
python -m uibe_booker seats <space_id> 2026-09-15    # 某区某日座位
python -m uibe_booker book <seat_id> 2026-09-15 18:30 22:00
python -m uibe_booker mine                           # 我的当前预约
python -m uibe_booker cancel <reservation_id>
```

也可 `pip install -e .` 后直接用 `uibe` 命令。

## 接口抓包校准

系统接口若调整，用浏览器开发者工具（F12 → 网络）抓一次真实操作：

1. 登录：看 `/ic-web/login` 的请求体格式（JSON 还是表单）与响应里 token 字段名；
2. 预约：看 `/ic-web/reserve` 的请求体字段；
3. 把差异填进 `config.local.toml` 的 `[endpoints]` 覆盖表或 `auth_header`。

测试全部基于 mock，不依赖真实账号。

## 免责声明

仅供个人学习自动化使用，请遵守学校与图书馆的相关规定；因使用本工具造成的任何后果由使用者自行承担。
