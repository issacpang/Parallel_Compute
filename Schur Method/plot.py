import matplotlib.pyplot as plt
import numpy as np
from collections import OrderedDict

# Inline mesh and partitions definitions
class GlobalQuadMesh:
    def __init__(self, nx, ny):
        self.nx, self.ny = nx, ny
        self.node_coords = OrderedDict()
        self.elements = []
        self._build_mesh()

    def _build_mesh(self):
        dx = 1.0 / self.nx
        dy = 1.0 / self.ny
        tag = 1
        for j in range(self.ny + 1):
            y = j * dy
            for i in range(self.nx + 1):
                x = i * dx
                self.node_coords[tag] = (x, y)
                tag += 1
        eTag = 1
        def n(i, j): return 1 + j * (self.nx + 1) + i
        for j in range(self.ny):
            for i in range(self.nx):
                self.elements.append((eTag, [n(i,j), n(i+1,j), n(i+1,j+1), n(i,j+1)]))
                eTag += 1

    def get_interface_nodes(self, x_val=0.5, tol=1e-8):
        return [tag for tag, (x, _) in self.node_coords.items() if abs(x - x_val) < tol]

class LeftQuadPartition:
    def __init__(self, mesh, fixed_nodes=None, nodal_loads=None):
        self.node_tags = [tag for tag, (x, _) in mesh.node_coords.items() if x <= 0.5]
        self.node_coords = {tag: mesh.node_coords[tag] for tag in self.node_tags}
        self.elements = [(eTag, nodes) for eTag, nodes in mesh.elements if all(n in self.node_tags for n in nodes)]
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads = nodal_loads or {}

class RightQuadPartition:
    def __init__(self, mesh, fixed_nodes=None, nodal_loads=None):
        self.node_tags = [tag for tag, (x, _) in mesh.node_coords.items() if x >= 0.5]
        self.node_coords = {tag: mesh.node_coords[tag] for tag in self.node_tags}
        self.elements = [(eTag, nodes) for eTag, nodes in mesh.elements if all(n in self.node_tags for n in nodes)]
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads = nodal_loads or {}

# 1) Build global mesh and partitions
global_mesh = GlobalQuadMesh(nx=6, ny=3)
left  = LeftQuadPartition(global_mesh, fixed_nodes=[1], nodal_loads={11:(0.0,-2e3)})
right = RightQuadPartition(global_mesh, fixed_nodes=[7], nodal_loads={})

# 2) Plot setup
fig, ax = plt.subplots()
ax.set_aspect('equal', 'box')
ax.set_title('Global Partitioned Mesh\nElement and Node Labels')

# 3) Plot left elements in blue, labeled L1…L6
for idx, (_, nodes) in enumerate(left.elements, start=1):
    pts = np.array([global_mesh.node_coords[n] for n in nodes] + [global_mesh.node_coords[nodes[0]]])
    ax.plot(pts[:,0], pts[:,1], color='blue')
    centroid = pts[:-1].mean(axis=0)
    ax.text(centroid[0], centroid[1], f'L{idx}', color='blue', ha='center', va='center')

# 4) Plot right elements in red, labeled R1…R6
for idx, (_, nodes) in enumerate(right.elements, start=1):
    pts = np.array([global_mesh.node_coords[n] for n in nodes] + [global_mesh.node_coords[nodes[0]]])
    ax.plot(pts[:,0], pts[:,1], color='red')
    centroid = pts[:-1].mean(axis=0)
    ax.text(centroid[0], centroid[1], f'R{idx}', color='red', ha='center', va='center')

# 5) Plot all nodes with labels offset left/down for both
for tag, (x, y) in global_mesh.node_coords.items():
    # Color by side membership
    color = 'blue' if tag in left.node_tags else 'red'
    ax.scatter(x, y, color=color, s=20)
    ax.text(x - 0.02, y - 0.02, str(tag), color=color, ha='right', va='top')

# 6) Finish
ax.set_xlim(-0.1, 1.1)
ax.set_ylim(-0.1, 1.1)
ax.set_xticks([]); ax.set_yticks([])
plt.show()
