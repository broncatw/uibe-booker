"""Web 服务：预约 UI + REST API + 定时抢座调度。

启动：python -m uibe_booker.webapp [--port 8643]
页面：http://127.0.0.1:8643/
"""

from __future__ import annotations

import threading
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

from uibe_booker.client import ICSeatClient, ICError
from uibe_booker.config import DEFAULT_CONFIG_FILE, BookConfig

app = Flask(__name__, static_folder="static", static_url_path="/static")

_state = {
    "client": None,          # ICSeatClient
    "config_file": DEFAULT_CONFIG_FILE,
    "jobs": {},              # job_id -> dict（含 stop 事件）
    "lock": threading.Lock(),
}


# ------------------------------------------------------------------ #
# 客户端与配置
# ------------------------------------------------------------------ #
def reload_client() -> None:
    """按当前配置文件重建客户端（登录态重置）。"""
    with _state["lock"]:
        cfg = BookConfig.load(config_file=_state["config_file"])
        _state["client"] = ICSeatClient(cfg)


def get_client() -> ICSeatClient:
    with _state["lock"]:
        if _state["client"] is None:
            reload_client()
        return _state["client"]


def error(message: str, code: int = 400):
    resp = jsonify({"ok": False, "error": message})
    resp.status_code = code
    return resp


@app.after_request
def add_cors(resp):
    """允许博客页面（任意来源）跨域调用本地助手。"""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resp


# ------------------------------------------------------------------ #
# REST API
# ------------------------------------------------------------------ #
@app.route("/", methods=["GET"])
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/config")
def api_set_config():
    """运行中修改配置（学号/密码/字段名等），立即重建客户端。"""
    body = request.json or {}
    allowed = ("username", "password", "base_url", "auth_header",
               "login_field", "timeout")
    lines = []
    current = {}
    path = _state["config_file"]
    try:
        import tomllib
        with open(path, "rb") as f:
            current = tomllib.load(f)
    except FileNotFoundError:
        pass
    for key in allowed:
        if key in body:
            current[key] = body[key]
    current.setdefault("username", "")
    current.setdefault("password", "")
    with open(path, "w", encoding="utf-8") as f:
        for key, value in current.items():
            f.write(f'{key} = {value!r}\n'.replace("'", '"')
                    if not isinstance(value, (int, float)) else
                    f"{key} = {value}\n")
    with _state["lock"]:
        _state["client"] = None
    return jsonify({"ok": True, "saved": list(body.keys())})


@app.post("/api/login")
def api_login():
    try:
        token = get_client().login()
        return jsonify({"ok": True, "token_prefix": token[:8]})
    except ICError as exc:
        return error(str(exc), 502)
    except Exception as exc:                 # noqa: BLE001 — 网络/配置错误统一出口
        return error(f"连接失败: {exc}", 502)


@app.get("/api/areas")
def api_areas():
    try:
        return jsonify({"ok": True, "data": get_client().buildings()})
    except (ICError, Exception) as exc:      # noqa: BLE001
        return error(str(exc), 502)


@app.get("/api/spaces/<building_id>")
def api_spaces(building_id):
    try:
        return jsonify({"ok": True, "data": get_client().spaces(building_id)})
    except Exception as exc:                 # noqa: BLE001
        return error(str(exc), 502)


@app.get("/api/seats")
def api_seats():
    space_id = request.args.get("space_id", "")
    day = request.args.get("day", "")
    try:
        return jsonify({"ok": True,
                        "data": get_client().seats(space_id, day)})
    except Exception as exc:                 # noqa: BLE001
        return error(str(exc), 502)


@app.post("/api/reserve")
def api_reserve():
    body = request.json or {}
    try:
        data = get_client().reserve(body.get("seat_id"), body.get("day"),
                                    body.get("start"), body.get("end"))
        return jsonify({"ok": True, "data": data})
    except Exception as exc:                 # noqa: BLE001
        return error(str(exc), 502)


@app.get("/api/mine")
def api_mine():
    try:
        return jsonify({"ok": True, "data": get_client().my_reservations()})
    except Exception as exc:                 # noqa: BLE001
        return error(str(exc), 502)


@app.post("/api/cancel")
def api_cancel():
    body = request.json or {}
    try:
        return jsonify({"ok": True,
                        "data": get_client().cancel(body.get("id"))})
    except Exception as exc:                 # noqa: BLE001
        return error(str(exc), 502)


# ------------------------------------------------------------------ #
# 定时抢座调度
# ------------------------------------------------------------------ #
_scheduler_started = False


def _fire_job(job_id: str) -> None:
    """到达触发时间后：确保登录 → 连续尝试预约，直到成功/超时/手动停止。"""
    job = _state["jobs"].get(job_id)
    if not job:
        return
    job["status"] = "运行中"
    deadline = time.time() + job.get("max_wait", 90)
    attempt = 0
    while time.time() < deadline:
        if job.get("stop"):
            job["status"] = "已手动停止"
            return
        attempt += 1
        try:
            client = get_client()
            if not client.token:
                client.login()
            client.reserve(job["seat_id"], job["day"],
                           job["start"], job["end"])
            job["status"] = "预约成功"
            job["attempts"] = attempt
            return
        except ICError as exc:
            job["last_error"] = str(exc)
            job["attempts"] = attempt
            # 已被占/参数错等硬失败：立即停止，避免无意义重试
            if any(k in str(exc) for k in ("已被预约", "不存在", "不能为空", "冲突")):
                job["status"] = "失败（硬性错误）"
                return
        except Exception as exc:             # noqa: BLE001 — 网络抖动重试
            job["last_error"] = f"网络异常: {exc}"
            job["attempts"] = attempt
        time.sleep(job.get("retry_interval", 0.3))
    job["status"] = "失败（超时未成功）"


def _scheduler_loop() -> None:
    """每 0.2 秒扫描任务，到点的任务标记后起独立抢座线程。"""
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _state["lock"]:
            jobs = list(_state["jobs"].items())
        for job_id, job in jobs:
            if (job["status"] == "等待触发"
                    and job["trigger_at"] <= now):
                # 先标记再启动，避免抢座线程的最终状态被本行覆盖
                job["status"] = "已触发"
                threading.Thread(target=_fire_job, args=(job_id,),
                                 daemon=True).start()
        time.sleep(0.2)


def start_scheduler() -> None:
    global _scheduler_started
    if not _scheduler_started:
        threading.Thread(target=_scheduler_loop, daemon=True).start()
        _scheduler_started = True


@app.get("/api/jobs")
def api_jobs():
    return jsonify({"ok": True,
                    "jobs": [{**{k: v for k, v in j.items() if k != "stop"},
                              "id": jid} for jid, j in _state["jobs"].items()]})


@app.post("/api/jobs")
def api_create_job():
    """创建定时抢座任务。

    body: {seat_id, day, start, end, trigger_at: "YYYY-MM-DD HH:MM:SS",
           max_wait(秒, 可选), retry_interval(秒, 可选)}
    """
    body = request.json or {}
    for key in ("seat_id", "day", "start", "end", "trigger_at"):
        if not body.get(key):
            return error(f"缺少字段: {key}")
    try:
        datetime.strptime(body["trigger_at"], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return error("trigger_at 格式应为 YYYY-MM-DD HH:MM:SS")

    job_id = uuid.uuid4().hex[:8]
    _state["jobs"][job_id] = {
        "seat_id": body["seat_id"], "day": body["day"],
        "start": body["start"], "end": body["end"],
        "trigger_at": body["trigger_at"],
        "max_wait": float(body.get("max_wait", 90)),
        "retry_interval": float(body.get("retry_interval", 0.3)),
        "status": "等待触发", "stop": False, "attempts": 0,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    start_scheduler()
    return jsonify({"ok": True, "job_id": job_id})


@app.delete("/api/jobs/<job_id>")
def api_delete_job(job_id):
    job = _state["jobs"].get(job_id)
    if not job:
        return error("任务不存在", 404)
    job["stop"] = True
    _state["jobs"].pop(job_id, None)
    return jsonify({"ok": True})


@app.delete("/api/jobs")
def api_clear_finished():
    for jid in [j for j, v in _state["jobs"].items()
                if v["status"] in ("预约成功", "失败（硬性错误）",
                                   "失败（超时未成功）", "已手动停止")]:
        _state["jobs"].pop(jid, None)
    return jsonify({"ok": True})


def main(port: int = 8643) -> None:
    start_scheduler()
    print(f"预约助手 Web UI: http://127.0.0.1:{port}/")
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8643)
    args = parser.parse_args()
    main(args.port)
