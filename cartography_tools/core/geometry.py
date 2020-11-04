# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math
from typing import List, Tuple, Optional

from qgis.core import (QgsLineString,
                       QgsVertexId,
                       QgsPoint,
                       QgsPointXY,
                       QgsGeometry)

from cartography_tools.core.utils import Utils


class GeometryUtils:
    """
    Utilities for geometry handling and manipulation
    """

    @staticmethod
    def generate_rotated_points_along_path(points: List[QgsPointXY],
                                           point_count: Optional[int] = None,
                                           point_distance: Optional[float] = None,
                                           orientation: float = 0, include_endpoints: bool = True) -> List[
        Tuple[QgsPointXY, float]]:
        """
        Generates a list of rotated points along a path defined by a list of QgsPointXY objects
        """

        # trim duplicate points
        points = Utils.unique_ordered_list(points)

        if len(points) < 2:
            return []

        if point_distance is not None and not point_distance:
            return []

        # calculate total length
        total_length = 0
        prev_point = None
        for p in points:
            if prev_point is not None:
                total_length += prev_point.distance(p)
            prev_point = p

        if total_length == 0:
            return []

        distance = 0

        if point_distance is not None:
            point_count = math.ceil((total_length / point_distance) + 1)

        if point_count == 1:
            marker_spacing = total_length
            distance = total_length / 2
        else:
            if include_endpoints:
                marker_spacing = total_length / (point_count - 1)
            else:
                marker_spacing = total_length / point_count
                distance = marker_spacing / 2

        line_geom = QgsGeometry.fromPolylineXY(points)

        return_points = []
        for i in range(point_count):
            if point_count > 1 and i == point_count - 1 and include_endpoints:
                distance = total_length

            point = line_geom.interpolate(distance).asPoint()
            angle = line_geom.interpolateAngle(distance) * 180 / math.pi - orientation

            return_points.append((point, angle))

            distance += marker_spacing

        return return_points

    @staticmethod
    def average_linestrings(line1: QgsLineString, line2: QgsLineString, weight: float = 1) -> QgsLineString:
        """
        Averages two linestring geometries
        """
        g1 = line1.clone()

        # project points from g2 onto g1
        for n in range(line2.numPoints()):
            vertex = line2.pointN(n)
            _, pt, after, _ = g1.closestSegment(vertex)
            g1.insertVertex(QgsVertexId(0, 0, after.vertex), pt)

        # iterate through vertices in g1
        out = []
        for n in range(g1.numPoints()):
            vertex = g1.pointN(n)
            _, pt, after, _ = line2.closestSegment(vertex)

            # average pts
            x = (vertex.x() * weight + pt.x()) / (weight + 1)
            y = (vertex.y() * weight + pt.y()) / (weight + 1)
            out.append(QgsPoint(x, y))

        return QgsLineString(out)
