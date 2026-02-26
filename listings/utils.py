import math
from typing import Dict, Tuple, List

Coordinates = Tuple[float, float]


def haversine(coord1: Coordinates, coord2: Coordinates) -> float:
    """Return distance in kilometers between two lat/lon points."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    # convert degrees to radians
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def dijkstra(start: Coordinates, points: Dict[int, Coordinates]) -> Dict[int, float]:
    """Compute shortest straight-line distances from start to each point using Dijkstra.
    This is effectively identical to computing haversine for each node, but we
    implement the algorithm to satisfy the requirement and to allow future
    edge-based graphs.

    Args:
        start: lat/lon of source
        points: mapping from node id to lat/lon coordinate
    Returns:
        mapping node id -> distance (km)
    """
    # for the simple complete graph we can directly compute
    distances: Dict[int, float] = {nid: float('inf') for nid in points}
    visited: Dict[int, bool] = {nid: False for nid in points}

    # initial distances from start to each node
    for nid, coord in points.items():
        distances[nid] = haversine(start, coord)

    # since graph is complete and edge weights symmetric, no need to iterate
    # more than once; but we'll simulate the selection process for Dijkstra
    # to demonstrate the algorithm.
    for _ in points:
        # pick unvisited node with smallest distance
        current = min((nid for nid in points if not visited[nid]), key=lambda x: distances[x], default=None)
        if current is None:
            break
        visited[current] = True
        # relax edges
        for nid, coord in points.items():
            if visited[nid]:
                continue
            new_dist = distances[current] + haversine(points[current], coord)
            if new_dist < distances[nid]:
                distances[nid] = new_dist
    return distances


def nearest_properties(start: Coordinates, prop_coords: Dict[int, Coordinates], k: int = 10) -> List[int]:
    """Return list of property ids sorted by distance from start."""
    dists = dijkstra(start, prop_coords)
    sorted_ids = sorted(dists, key=lambda pid: dists[pid])
    return sorted_ids[:k]
