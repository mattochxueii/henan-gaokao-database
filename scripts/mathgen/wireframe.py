
"""Physical visibility of edges in a projected convex polyhedron."""
from itertools import combinations

import numpy as np


def convex_faces(points, tol=1e-8):
    faces={}
    for i,j,k in combinations(range(len(points)),3):
        normal=np.cross(points[j]-points[i],points[k]-points[i])
        length=np.linalg.norm(normal)
        if length<tol:
            continue
        normal=normal/length
        distances=(points-points[i])@normal
        if distances.min()<-tol and distances.max()>tol:
            continue
        if distances.max()>tol:
            normal=-normal
        if np.max(np.abs(distances))<tol:
            continue
        coplanar=frozenset(np.flatnonzero(np.abs(distances)<tol))
        faces[coplanar]=(normal,points[i])
    return faces


def hidden_edges(vertices, edges, camera):
    names=list(vertices)
    points=np.asarray([vertices[name] for name in names],dtype=float)
    faces=convex_faces(points)
    eye=np.asarray(camera)
    hidden=set()
    for a,b in edges:
        i,j=names.index(a),names.index(b)
        shared=[(normal,origin) for ids,(normal,origin) in faces.items() if i in ids and j in ids]
        if len(shared)<2 or not any(normal@(eye-origin)>=-1e-8 for normal,origin in shared):
            hidden.add(frozenset((a,b)))
    return hidden
