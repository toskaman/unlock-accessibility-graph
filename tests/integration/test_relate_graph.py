"""Integration tests against the real Relate engine (file-backed store)."""
import pytest
import relate

from conftest import HALL, Q1, Q2, Q3, build_fixture_doc, pair_id
from unlock.db import GraphStore, backup
from unlock.engine import graph as G
from unlock.engine import impact as I
from unlock.engine.model import EquipmentStatus as E, PairClass as C
from unlock.engine.service import InvalidScenario, UnlockService
from unlock.ingest.load import import_document


def test_store_persists_across_reopen(tmp_path, fixture_doc):
    path = tmp_path / "p.rl"
    with GraphStore(path) as db:
        import_document(db, fixture_doc)
        n1 = db.counts()
    with GraphStore(path) as db:
        assert db.counts() == n1
    assert n1["nodes"]["Lift"] == 7


def test_import_is_idempotent(store, fixture_doc):
    before = store.counts()
    import_document(store, fixture_doc)
    assert store.counts() == before


def test_uniqueness_constraint_enforced(store):
    with pytest.raises(relate.IntegrityError):
        store.query("CREATE (:Lift {id: 'L1'})")


def test_parameterised_queries_are_not_injectable(store):
    rows = store.query("MATCH (l:Lift {id: $id}) RETURN l.id AS id", {"id": "L1' OR 1=1 //"})
    assert rows == []


def test_transaction_rolls_back_on_error(store):
    before = store.counts()
    with pytest.raises(relate.Error):
        store.transaction([("CREATE (:Probe {id: 'x'})", {}), ("THIS IS NOT CYPHER", {})])
    assert store.counts() == before


def test_traversal_finds_alternative_routes(store):
    pairs = {p.id: p for p in G.load_pairs(store)}
    v12 = pairs[pair_id(Q1, Q2)]
    assert sorted(r.lifts for r in v12.routes) == [("L1", "L2"), ("L4", "L5")]
    # route through hall exists for Voie 1 via L1+L3
    assert ("L1", "L3") in [r.lifts for r in pairs[pair_id(Q1, HALL)].routes]


def test_unspecified_end_never_creates_a_route(store):
    pairs = G.load_pairs(store)
    assert not any("L7" in r.lifts for p in pairs for r in p.routes)


def test_baseline_classification(store):
    svc = UnlockService(store)
    res = svc.baseline.results
    assert res[pair_id(Q1, Q2)].cls == C.CONFIRMED_ACCESSIBLE
    assert res[pair_id(Q1, HALL)].cls == C.CONFIRMED_ACCESSIBLE
    assert res[pair_id(Q1, Q3)].cls == C.UNVERIFIED


def test_outage_with_alternative_vs_without(store):
    svc = UnlockService(store)
    sc = svc.create_scenario("t", {"L1": "UNAVAILABLE"})
    a = svc.analyze(sc["id"])
    # Both pairs survive: V1-V2 via the passerelle, V1-hall via passerelle -> Voie 2 -> souterrain
    assert pair_id(Q1, Q2) not in a["lost_confirmed"]
    assert pair_id(Q1, HALL) not in a["lost_confirmed"]
    # L3 is the only lift reaching the hall: losing it cuts every platform->hall pair
    sc2 = svc.create_scenario("t2", {"L3": "UNAVAILABLE"})
    lost = svc.analyze(sc2["id"])["lost_confirmed"]
    assert sorted(lost) == sorted([pair_id(Q1, HALL), pair_id(Q2, HALL)])


def test_scenario_is_non_destructive_and_reversible(store):
    svc = UnlockService(store)
    snap_before = store.query("MATCH (o:StatusSnapshot) RETURN o.id AS id, o.state AS s ORDER BY id")
    base = dict(svc.baseline.counts)
    sc = svc.create_scenario("t", {"L1": "UNAVAILABLE", "L4": "UNAVAILABLE"})
    assert svc.analyze(sc["id"])["scenario_counts"] != base
    assert store.query("MATCH (o:StatusSnapshot) RETURN o.id AS id, o.state AS s ORDER BY id") == snap_before
    svc.update_overrides(sc["id"], {"L1": "AVAILABLE"})       # restore
    assert svc.analyze(sc["id"])["scenario_counts"] == base
    svc.delete_scenario(sc["id"])
    assert store.query("MATCH (s:Scenario) RETURN count(s) AS n")[0]["n"] == 0


def test_analysis_is_deterministic_and_persisted(store):
    svc = UnlockService(store)
    s1 = svc.create_scenario("a", {"L3": "UNAVAILABLE"})
    s2 = svc.create_scenario("b", {"L3": "UNAVAILABLE"})
    a1, a2 = svc.analyze(s1["id"]), svc.analyze(s2["id"])
    assert a1["analysis_id"] == a2["analysis_id"] and a1["scenario_counts"] == a2["scenario_counts"]
    assert store.query("MATCH (:Scenario {id: $id})-[:PRODUCES]->(a:AnalysisResult) RETURN a.id AS id",
                       {"id": s1["id"]})[0]["id"] == a1["analysis_id"]


def test_ranking_restores_simulated_outage(store):
    svc = UnlockService(store)
    sc = svc.create_scenario("t", {"L3": "UNAVAILABLE"})
    r = svc.rank(sc["id"])
    top = r["candidates"][0]
    assert top["lift_id"] == "L3" and top["gain"] == 2 and top["simulated"]


def test_invalid_scenarios_rejected(store):
    svc = UnlockService(store)
    with pytest.raises(InvalidScenario):
        svc.create_scenario("t", {"NOPE": "UNAVAILABLE"})
    with pytest.raises(InvalidScenario):
        svc.create_scenario("t", {"L1": "BROKEN"})
    with pytest.raises(InvalidScenario):
        svc.create_scenario("t", {})


def test_snapshot_consistency_uses_one_snapshot(tmp_path):
    path = tmp_path / "s.rl"
    with GraphStore(path) as db:
        import_document(db, build_fixture_doc(snapshot="fixture@1"))
        later = build_fixture_doc({"L1": "KO", "L2": "OK", "L3": "OK", "L4": "OK", "L5": "OK", "L6": "OK", "L7": "OK"},
                                  snapshot="fixture@2")
        for s in later["status_snapshots"]:
            s["observed_at"] = "2026-11-16T11:00:00+00:00"
        import_document(db, later)
        assert db.query("MATCH (o:StatusSnapshot) RETURN count(o) AS n")[0]["n"] == 14   # history kept
        svc = UnlockService(db)
        assert svc.snapshot["id"] == "fixture@2"
        assert svc.lifts["L1"].baseline == E.UNAVAILABLE and svc.lifts["L6"].baseline == E.AVAILABLE


def test_explanation_path_comes_from_graph(store):
    svc = UnlockService(store)
    sc = svc.create_scenario("t", {"L3": "UNAVAILABLE"})
    d = svc.explain_pair(pair_id(Q1, HALL), sc["id"], candidate_lift="L3")
    path = d["routes"][0]["path"]
    assert [n["id"] for n in path["nodes"]] == list(svc.pairs_by_id[pair_id(Q1, HALL)].routes[0].nodes)
    assert {r["type"] for r in path["relationships"]} == {"SERVES"}
    assert d["classification"]["scenario"] == "CONFIRMED_BLOCKED"
    assert d["classification"]["with_candidate"] == "CONFIRMED_ACCESSIBLE"
    assert d["routes"][0]["lifts"][0]["evidence"]["status"]["snapshot_id"] == "fixture@1"


def test_backup_and_restore(tmp_path, fixture_doc):
    path = tmp_path / "b.rl"
    with GraphStore(path) as db:
        import_document(db, fixture_doc)
        n = db.counts()
    bk = backup(path, tmp_path / "bk")
    with GraphStore(path) as db:
        db.query("MATCH (l:Lift {id: 'L7'}) DETACH DELETE l")
    bk.replace(path)
    with GraphStore(path) as db:
        assert db.counts() == n


def test_second_writer_is_refused(tmp_path, fixture_doc):
    path = tmp_path / "w.rl"
    with GraphStore(path) as db:
        import_document(db, fixture_doc)
        with pytest.raises(Exception):
            GraphStore(path).close()


def test_connection_is_thread_affine_but_store_serialises(store):
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda _: store.query("MATCH (l:Lift) RETURN count(l) AS n")[0]["n"], range(40)))
    assert set(res) == {7}
