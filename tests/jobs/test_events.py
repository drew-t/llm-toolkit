import json

from llm_toolkit.jobs.events import JobEvent


def test_log_event_to_json():
    e = JobEvent.log("hello world")
    assert e.type == "log"
    assert e.to_json() == json.dumps({"type": "log", "line": "hello world"})


def test_status_event_to_json():
    e = JobEvent.status("running")
    assert e.to_json() == json.dumps({"type": "status", "status": "running"})


def test_finished_event_to_json():
    e = JobEvent.finished("success", exit_code=0, results_imported=12)
    payload = json.loads(e.to_json())
    assert payload == {
        "type": "finished",
        "status": "success",
        "exit_code": 0,
        "results_imported": 12,
    }


def test_result_event_to_json():
    e = JobEvent.result(
        result_id=42,
        benchmark="throughput_benchy",
        model="qwen3:8b",
        metrics={"tg_throughput": 73.4},
    )
    payload = json.loads(e.to_json())
    assert payload["type"] == "result"
    assert payload["result_id"] == 42
    assert payload["metrics"]["tg_throughput"] == 73.4
