"""Unit tests for graph edge filtering and pleasantness (T0.1)."""

from __future__ import annotations

import networkx as nx

from mappet_spike.graph import (
    GraphPreferences,
    edge_pleasantness,
    filter_graph_edges,
    is_excluded_highway,
    search_radius_m,
)


def test_excluded_highways():
    assert is_excluded_highway("motorway")
    assert is_excluded_highway("trunk")
    assert is_excluded_highway("motorway_link")
    assert is_excluded_highway("trunk_link")
    assert not is_excluded_highway("residential")
    assert not is_excluded_highway("footway")
    assert not is_excluded_highway(None)


def test_filter_removes_motorways_and_attaches_pleasantness():
    g = nx.MultiDiGraph()
    g.add_node(1, x=15.98, y=45.81)
    g.add_node(2, x=15.981, y=45.811)
    g.add_node(3, x=15.982, y=45.812)

    g.add_edge(1, 2, 0, highway="residential", length=100.0)
    g.add_edge(2, 3, 0, highway="motorway", length=200.0)
    g.add_edge(1, 3, 0, highway="footway", length=150.0)

    prefs = GraphPreferences(avoid_busy_roads=True, prefer_quiet=True)
    filtered = filter_graph_edges(g, prefs)

    highways = [
        d.get("highway") for _, _, _, d in filtered.edges(keys=True, data=True)
    ]
    assert "motorway" not in highways
    assert "residential" in highways
    assert "footway" in highways
    assert filtered.number_of_edges() == 2

    for _, _, _, data in filtered.edges(keys=True, data=True):
        assert "pleasantness" in data
        assert 0.05 <= data["pleasantness"] <= 1.0
        assert "weight" in data
        assert data["weight"] > 0


def test_pleasantness_prefers_quiet_over_busy():
    prefs = GraphPreferences(avoid_busy_roads=True, prefer_quiet=True)
    quiet = edge_pleasantness({"highway": "footway"}, prefs)
    busy = edge_pleasantness({"highway": "primary"}, prefs)
    assert quiet > busy


def test_search_radius_scales_with_distance():
    assert search_radius_m(0.1) >= 1000.0
    assert search_radius_m(200.0) <= 25_000.0
    r5 = search_radius_m(5.0)
    r10 = search_radius_m(10.0)
    assert r10 > r5
    assert abs(r5 - 5000.0 / 2.5) < 1e-6
