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

from qgis.core import (QgsLineString,
                       QgsVertexId,
                       QgsPoint)

class GeometryUtils:

    @staticmethod
    def average_linestrings(line1, line2, weight=1):
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
            x = (vertex.x() * weight + pt.x()) / (weight+1)
            y = (vertex.y() * weight + pt.y()) / (weight+1)
            out.append(QgsPoint(x, y))

        return QgsLineString(out)
