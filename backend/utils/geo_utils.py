# backend/utils/geo_utils.py — Geospatial helper functions
"""Geospatial utilities for coordinate validation and distance calculation."""

import math
from typing import Tuple, Optional


def haversine_distance(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: First point (decimal degrees)
        lat2, lon2: Second point (decimal degrees)

    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km

    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def point_in_polygon_check(
    lat: float,
    lon: float,
    polygon_coords: list,
    buffer_km: float = 0.5,
) -> bool:
    """
    Simple ray-casting check if a point is inside a polygon.
    Falls back to this when Shapely is not available.

    Args:
        lat, lon: Point to check
        polygon_coords: List of [lon, lat] pairs forming polygon
        buffer_km: Tolerance buffer in kilometers

    Returns:
        True if point is inside polygon (± buffer)
    """
    if not polygon_coords:
        return False

    # Convert buffer to approximate degrees
    buffer_deg = buffer_km / 111.0  # ~111km per degree

    n = len(polygon_coords)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon_coords[i][0], polygon_coords[i][1]
        xj, yj = polygon_coords[j][0], polygon_coords[j][1]

        if ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i

    # If not inside, check if within buffer distance of polygon boundary
    if not inside:
        for coord in polygon_coords:
            dist = haversine_distance(lat, lon, coord[1], coord[0])
            if dist <= buffer_km:
                return True

    return inside


def bbox_from_center(
    lat: float,
    lon: float,
    radius_km: float = 5.0,
) -> Tuple[float, float, float, float]:
    """
    Create a bounding box around a center point.

    Returns:
        (min_lat, min_lon, max_lat, max_lon)
    """
    delta_lat = radius_km / 111.0
    delta_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    return (
        lat - delta_lat,
        lon - delta_lon,
        lat + delta_lat,
        lon + delta_lon,
    )
