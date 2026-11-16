"""Feed watch: identical lift content is detected across observations, a change is not hidden."""
from unlock.network import feedwatch as F


def _doc(at, text="Panne ascenseur Quai 1"):
    o = [{"id": "RATP:1", "text": text, "first_reported": "2026-09-01T08:00:00", "last_update": "2026-10-09T09:00:00", "messages": 2}]
    return {"observed_at": at, "counts": {"lifts": 1, "messages": 2}, "outages": o,
            "feed_last_lift_update": "2026-10-09T09:00:00", "feed_non_lift_last_update": at[:19]}


def test_identical_then_changed(tmp_path):
    p = tmp_path / "h.json"
    F.append(_doc("2026-11-16T19:00:00+00:00"), p)
    h = F.append(_doc("2026-11-17T08:00:00+00:00"), p)
    s = F.summary(h)
    assert s["observations"] == 2 and s["all_identical"] and s["identical_since"].startswith("2026-11-16")
    h = F.append(_doc("2026-11-18T08:00:00+00:00", text="Panne réparée"), p)
    s = F.summary(h)
    assert not s["all_identical"] and s["identical_lift_content"] == 1
    h = F.append(_doc("2026-11-18T08:00:00+00:00", text="Panne réparée"), p)   # same observation twice is not double-counted
    assert F.summary(h)["observations"] == 3
