"""Web 服务测试：Flask test client + mock IC 客户端（含定时抢座调度）。"""

import time

import pytest

from uibe_booker import webapp


class MockClient:
    """可编程的假 IC 客户端。"""

    def __init__(self):
        self.token = None
        self.seats_result = [{"id": 42, "name": "A-01", "status": "空闲"}]
        self.fail_reserve = False

    def login(self):
        self.token = "tok"
        return self.token

    def buildings(self):
        return [{"id": "B1", "name": "主馆"}]

    def spaces(self, building_id):
        return [{"id": "S1", "name": "三层阅览区"}]

    def seats(self, space_id, day):
        return self.seats_result

    def reserve(self, seat_id, day, start, end):
        if self.fail_reserve:
            raise Exception("该座位已被预约")
        return {"reservation_id": 77}

    def cancel(self, rid):
        return {"cancelled": rid}

    def my_reservations(self):
        return [{"id": 77, "seat": "A-01", "day": "2026-09-15"}]


@pytest.fixture
def web(monkeypatch):
    client = MockClient()
    monkeypatch.setattr(webapp, "get_client", lambda: client)
    webapp._state["jobs"] = {}
    webapp._state["client"] = client
    app = webapp.app
    app.config["TESTING"] = True
    return app.test_client(), client


def test_index_served(web):
    tc, _ = web
    r = tc.get("/")
    assert r.status_code == 200
    assert "贸大预约助手".encode() in r.data


def test_areas_endpoint(web):
    tc, _ = web
    r = tc.get("/api/areas")
    assert r.json == {"ok": True, "data": [{"id": "B1", "name": "主馆"}]}


def test_seats_endpoint(web):
    tc, client = web
    r = tc.get("/api/seats?space_id=S1&day=2026-09-15")
    assert r.json["ok"] is True
    assert r.json["data"][0]["id"] == 42


def test_reserve_and_error_path(web):
    tc, client = web
    r = tc.post("/api/reserve", json={"seat_id": 42, "day": "2026-09-15",
                                      "start": "08:00", "end": "10:00"})
    assert r.json["ok"] is True
    client.fail_reserve = True
    r = tc.post("/api/reserve", json={"seat_id": 42, "day": "2026-09-15",
                                      "start": "08:00", "end": "10:00"})
    assert r.status_code == 502
    assert "已被预约" in r.json["error"]


def test_job_lifecycle_and_firing(web):
    tc, client = web
    # 触发时间设为过去 → 调度器立即触发
    trigger = "2020-01-01 00:00:00"
    r = tc.post("/api/jobs", json={
        "seat_id": 42, "day": "2026-09-15", "start": "08:00",
        "end": "10:00", "trigger_at": trigger})
    assert r.json["ok"] is True
    job_id = r.json["job_id"]

    deadline = time.time() + 5
    while time.time() < deadline:
        jobs = tc.get("/api/jobs").json["jobs"]
        mine = [j for j in jobs if j["id"] == job_id][0]
        if mine["status"] in ("预约成功", "失败（硬性错误）",
                              "失败（超时未成功）", "已手动停止"):
            break
        time.sleep(0.1)
    assert mine["status"] == "预约成功"


def test_job_missing_field_rejected(web):
    tc, _ = web
    r = tc.post("/api/jobs", json={"seat_id": 1})
    assert r.status_code == 400


def test_job_delete(web):
    tc, _ = web
    r = tc.post("/api/jobs", json={
        "seat_id": 1, "day": "2026-09-20", "start": "08:00", "end": "10:00",
        "trigger_at": "2030-01-01 00:00:00"})
    job_id = r.json["job_id"]
    assert tc.delete(f"/api/jobs/{job_id}").json["ok"] is True
    assert tc.delete("/api/jobs/NOPE").status_code == 404


def test_cors_headers(web):
    tc, _ = web
    r = tc.get("/api/areas")
    assert "Access-Control-Allow-Origin" in r.headers
