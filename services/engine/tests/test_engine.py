import math

from app.engine import _polyline_length_m, search


ORIGIN = (45.815, 15.982)  # Zagreb


def test_search_returns_top_5():
    results = search(ORIGIN[0], ORIGIN[1], "run", 5.0)
    assert len(results) == 5
    # Ranked by confidence, descending.
    confs = [r.confidence for r in results]
    assert confs == sorted(confs, reverse=True)


def test_results_are_within_distance_tolerance():
    target_km = 8.0
    tol = 0.15
    results = search(ORIGIN[0], ORIGIN[1], "walk", target_km, tolerance=tol)
    for r in results:
        # Effective distance jitter is bounded by the tolerance band.
        assert (target_km * (1 - tol) * 1000) <= r.distance_m <= (target_km * (1 + tol) * 1000)


def test_loops_close_back_to_origin():
    results = search(ORIGIN[0], ORIGIN[1], "run", 5.0)
    for r in results:
        first, last = r.polyline[0], r.polyline[-1]
        # First and last point should coincide (closed loop).
        assert math.isclose(first[0], last[0], abs_tol=1e-6)
        assert math.isclose(first[1], last[1], abs_tol=1e-6)


def test_polyline_length_matches_reported_distance():
    results = search(ORIGIN[0], ORIGIN[1], "run", 6.0)
    for r in results:
        assert math.isclose(_polyline_length_m(r.polyline), r.distance_m, rel_tol=1e-6)


def test_search_is_deterministic():
    a = search(ORIGIN[0], ORIGIN[1], "run", 5.0)
    b = search(ORIGIN[0], ORIGIN[1], "run", 5.0)
    assert [r.route_id for r in a] == [r.route_id for r in b]
    assert [r.confidence for r in a] == [r.confidence for r in b]


def test_run_is_faster_than_walk():
    run = search(ORIGIN[0], ORIGIN[1], "run", 5.0)
    walk = search(ORIGIN[0], ORIGIN[1], "walk", 5.0)
    run_by_id = {r.route_id: r for r in run}
    for w in walk:
        if w.route_id in run_by_id:
            assert run_by_id[w.route_id].est_time_s < w.est_time_s
