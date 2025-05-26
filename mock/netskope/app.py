from __future__ import annotations

import random
from typing import List, TypedDict

from flask import Flask, jsonify, request

app = Flask(__name__)

EVENT_TYPES = {
    "application": ["allow", "block"],
    "network": ["allow", "block"],
    "page": ["view", "click"],
    "alert": ["notify", "quarantine"],
    "audit": ["create", "update", "delete"],
}


class Event(TypedDict):
    id: str
    actions: str


def _generate_events(ev_type: str, since_ts: int) -> List[Event]:
    actions = EVENT_TYPES[ev_type]
    return [
        {
            "id": f"{ev_type}-{random.randint(1000, 9999)}",
            "actions": random.choice(actions),
        }
        for _ in range(5)
    ]


@app.route("/api/v2/events/dataexport/events/<ev_type>")
def data_export(ev_type: str):
    if ev_type not in EVENT_TYPES:
        return jsonify({"error": "unsupported event type"}), 404

    op = request.args.get("operation", "0")

    if op != "next":
        try:
            since_ts = int(op)
        except ValueError:
            return jsonify({"error": "operation must be epoch seconds or 'next'"}), 400

        events = _generate_events(ev_type, since_ts)
        return jsonify({"ok": 1, "result": events, "wait_time": 0})

    return jsonify({"ok": 1, "result": [], "wait_time": 0})


@app.route("/events")
def legacy_events():
    return data_export("application")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
