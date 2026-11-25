
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
        if not shared or not any(normal@(eye-origin)>=-1e-8 for normal,origin in shared):
            hidden.add(frozenset((a,b)))
    return hidden


def check_projection(vertices, edges, projection, to_display):
    """Check the printed 2-D projection in display units, including unequal axes."""
    from mpl_toolkits.mplot3d import proj3d

    names = list(vertices)
    points = np.asarray([vertices[name] for name in names], dtype=float)
    x, y, _ = proj3d.proj_transform(*points.T, projection)
    projected = dict(zip(names, to_display.transform(np.column_stack((x,y))), strict=True))
    for a,b in edges:
        start = projected[a]
        vector = projected[b]-start
        length = np.linalg.norm(vector)
        if length < 2:
            raise ValueError(f"棱 {a}{b} 在投影中重合，请调整 view_angles")
        original_start = np.asarray(vertices[a], dtype=float)
        original_vector = np.asarray(vertices[b], dtype=float)-original_start
        for name, point in projected.items():
            if name in (a,b):
                continue
            # A marked point actually on a 3-D edge is an intended incidence.
            delta = np.asarray(vertices[name], dtype=float)-original_start
            fraction = delta@original_vector/(original_vector@original_vector)
            if 0 <= fraction <= 1 and np.linalg.norm(delta-fraction*original_vector) < 1e-8:
                continue
            position = np.clip((point-start)@vector/length**2,0,1)
            if np.linalg.norm(point-start-position*vector) < max(2,length*.05):
                raise ValueError(f"顶点 {name} 与非相连棱 {a}{b} 投影过近，请调整 view_angles")
