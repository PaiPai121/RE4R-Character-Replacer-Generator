"""Limit local skin-weight jumps introduced by joint landmark retargeting."""
import numpy as np
from mathutils.kdtree import KDTree


def regularize(objects, armature):
    names = list(armature.data.bones.keys())
    columns = {name:i for i,name in enumerate(names)}
    points, rows, members, clusters, edges = [], [], [], {}, set()
    for obj in objects:
        lookup = {}
        for vertex in obj.data.vertices:
            point = obj.matrix_world @ vertex.co
            key = tuple(round(c,6) for c in point)
            if key not in clusters:
                clusters[key] = len(points)
                points.append(tuple(point));rows.append(np.zeros(len(names)));members.append([])
            index = clusters[key];lookup[vertex.index] = index
            members[index].append((obj,vertex.index))
            for item in vertex.groups:
                column = columns.get(obj.vertex_groups[item.group].name)
                if column is not None:rows[index][column] += item.weight
        edges.update(tuple(sorted((lookup[e.vertices[0]],lookup[e.vertices[1]]))) for e in obj.data.edges)
    points = np.asarray(points)
    height = max(float(np.ptp(points[:,2])),.001)
    tree = KDTree(len(points))
    for i,point in enumerate(points):tree.insert(point,i)
    tree.balance()
    parent = list(range(len(points)))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]];i=parent[i]
        return i
    for i,point in enumerate(points):
        for _,j,_ in tree.find_range(point,height*2e-5):
            a,b=root(i),root(j)
            if a!=b:parent[max(a,b)]=min(a,b)
    merged = {}
    for i in range(len(points)):merged.setdefault(root(i),[]).append(i)
    remap = {old:new for new,group in enumerate(merged.values()) for old in group}
    points = np.asarray([points[group].mean(axis=0) for group in merged.values()])
    rows = [sum((rows[i] for i in group),np.zeros(len(names))) for group in merged.values()]
    members = [[item for i in group for item in members[i]] for group in merged.values()]
    edges = {tuple(sorted((remap[a],remap[b]))) for a,b in edges}
    weights = np.asarray(rows)
    weights /= weights.sum(axis=1,keepdims=True)
    original = weights.copy()
    height = max(float(np.ptp(points[:,2])),.001)
    constraints = [(a,b,max(.016,float(np.linalg.norm(points[a]-points[b]))/(height*.04)))
                   for a,b in sorted(edges) if a!=b]
    # Project only violating adjacent pairs, preserving rigid regions and seam equality.
    for _ in range(24):
        changed = False
        for a,b,limit in constraints:
            difference = weights[a]-weights[b]
            distance = float(np.abs(difference).sum())
            if distance > limit+1e-6:
                correction = difference*((distance-limit)/(2*distance))
                weights[a] -= correction;weights[b] += correction;changed=True
        if not changed:break
    count = 0
    for i,group in enumerate(members):
        if len(group)==1 and np.max(np.abs(original[i]-weights[i]))<1e-7:continue
        top = np.argsort(weights[i])[-8:]
        total = weights[i,top].sum()
        for obj,index in group:
            for vertex_group in obj.vertex_groups:vertex_group.remove([index])
            for column in top:
                if weights[i,column]>1e-8:
                    obj.vertex_groups[names[column]].add([index],float(weights[i,column]/total),'REPLACE')
            count += 1
    return {'adjusted_vertices':count,'gradient_length_fraction':.04,'iterations_limit':24}
