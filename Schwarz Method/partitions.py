from collections import OrderedDict
from itertools import groupby

class GlobalQuadMesh:
    """
    Build a single quadrilateral mesh on [0,1]x[0,1], subdivided into nx x ny elements.
    """
    def __init__(self, nx, ny):
        self.nx, self.ny = nx, ny
        self.node_coords = OrderedDict()   # tag -> (x, y)
        self.elements    = []              # list of (eTag, [n1,n2,n3,n4])
        self._build_mesh()

    def _build_mesh(self):
        dx = 1.0 / self.nx
        dy = 1.0 / self.ny
        # create nodes
        tag = 1
        for j in range(self.ny + 1):
            y = j * dy
            for i in range(self.nx + 1):
                x = i * dx
                self.node_coords[tag] = (x, y)
                tag += 1
        # create elements
        eTag = 1
        def n(i, j): return 1 + j * (self.nx + 1) + i
        for j in range(self.ny):
            for i in range(self.nx):
                self.elements.append((eTag, [n(i,j), n(i+1,j), n(i+1,j+1), n(i,j+1)]))
                eTag += 1

    def get_overlap_nodes(self):
        """
        Return dict with overlap node lists:
         - overlap_nodes: all nodes in overlap band
         - left_send, right_send: Dirichlet exchange sets
         - central_nodes: interior overlap nodes for convergence check
        """
        dx = 1.0 / self.nx
        tol = dx * 0.01
        low = 0.5 - dx - tol
        high = 0.5 + dx + tol
        # all overlap nodes
        overlap = [tag for tag,(x,_) in self.node_coords.items() if low < x < high]
        # group by y to pick left/right/central
        overlap.sort(key=lambda t: (self.node_coords[t][1], self.node_coords[t][0]))
        grouped = {y:list(g) for y,g in groupby(overlap, key=lambda t: self.node_coords[t][1])}
        left_send = []
        right_send = []
        central = []
        for y in sorted(grouped):
            row = grouped[y]
            m = len(row)//2
            left_send.extend(row[m:])
            right_send.extend(row[:m])
            central.extend(row[m:m+1])
        return {
            'overlap_nodes': overlap,
            'left_send': left_send,
            'right_send': right_send,
            'central_nodes': central
        }

class LeftQuadPartition:
    """
    Partition of the global mesh for x <= 0.5, extended to include overlap.
    """
    def __init__(self, mesh: GlobalQuadMesh, fixed_nodes=None, nodal_loads=None):
        dx = 1.0/mesh.nx
        tol = dx * 0.01
        # include one element beyond 0.5 for overlap
        self.node_tags = [tag for tag,(x,_) in mesh.node_coords.items() if x <= 0.5 + dx + tol]
        self.node_coords = {t:mesh.node_coords[t] for t in self.node_tags}
        # elements wholly inside this partition
        self.elements = [(e,ns) for e,ns in mesh.elements if all(n in self.node_tags for n in ns)]
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads = nodal_loads or {}
        # overlap information
        ov = mesh.get_overlap_nodes()
        # Swap send and recv for intended exchange
        self.send_overlap = ov['right_send']  # now sends nodes [3,10,17]
        self.recv_overlap = ov['left_send']   # now receives nodes [4,5,11,12,18,19]
        self.central_overlap = ov['central_nodes']

    def populate(self, model):
        for t, (x, y) in self.node_coords.items():
            model.node(t, x, y)
        model.nDMaterial('ElasticIsotropic', 1, 2e11, 0.3)
        for e, ns in self.elements:
            model.element('quad', e, *ns, 1.0, 'PlaneStress', 1)
            # Optional: Assign lumped mass
            mass_per_node = 1.0 / 4.0  # Adjust as needed
            for n in ns:
                model.mass(n, mass_per_node, mass_per_node)
        for n in self.fixed_nodes:
            model.fix(n, 1, 1)
        if self.nodal_loads:
            model.timeSeries('Constant', 1)
            model.pattern('Plain', 1, 1)
            for n, (fx, fy) in self.nodal_loads.items():
                model.load(n, fx, fy)

    def get_dof_partition(self):
        free = [n for n in self.node_tags if n not in self.fixed_nodes]
        ntod = {n:i*2 for i,n in enumerate(free)}
        iface = self.send_overlap + self.recv_overlap
        interior = [n for n in free if n not in iface]
        return {
            'interior':[ntod[n]+d for n in interior for d in (0,1)],
            'interface':[ntod[n]+d for n in iface for d in (0,1)]
        }

    def get_overlap_nodes(self):
        """
        Return (send, recv, central) node lists for Schwarz exchange.
        """
        return (self.send_overlap, self.recv_overlap, self.central_overlap)

class RightQuadPartition:
    """
    Partition of the global mesh for x >= 0.5, extended to include overlap.
    """
    def __init__(self, mesh: GlobalQuadMesh, fixed_nodes=None, nodal_loads=None):
        dx = 1.0/mesh.nx
        tol = dx * 0.01
        self.node_tags = [tag for tag,(x,_) in mesh.node_coords.items() if x >= 0.5 - dx - tol]
        self.node_coords = {t:mesh.node_coords[t] for t in self.node_tags}
        self.elements = [(e,ns) for e,ns in mesh.elements if all(n in self.node_tags for n in ns)]
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads = nodal_loads or {}
        ov = mesh.get_overlap_nodes()
        # Swap send and recv for intended exchange
        self.send_overlap = ov['left_send']   # now sends nodes [4,5,11,12,18,19]
        self.recv_overlap = ov['right_send']  # now receives nodes [3,10,17]
        self.central_overlap = ov['central_nodes']

    def populate(self, model):
        for t, (x, y) in self.node_coords.items():
            model.node(t, x, y)
        model.nDMaterial('ElasticIsotropic', 1, 2e11, 0.3)
        for e, ns in self.elements:
            model.element('quad', e, *ns, 1.0, 'PlaneStress', 1)
            # Optional: Assign lumped mass
            mass_per_node = 1.0 / 4.0
            for n in ns:
                model.mass(n, mass_per_node, mass_per_node)
        for n in self.fixed_nodes:
            model.fix(n, 1, 1)
        if self.nodal_loads:
            model.timeSeries('Constant', 1)
            model.pattern('Plain', 1, 1)
            for n, (fx, fy) in self.nodal_loads.items():
                model.load(n, fx, fy)

    def get_dof_partition(self):
        free = [n for n in self.node_tags if n not in self.fixed_nodes]
        ntod = {n:i*2 for i,n in enumerate(free)}
        iface = self.send_overlap + self.recv_overlap
        interior = [n for n in free if n not in iface]
        return {
            'interior':[ntod[n]+d for n in interior for d in (0,1)],
            'interface':[ntod[n]+d for n in iface for d in (0,1)]
        }

    def get_overlap_nodes(self):
        """
        Return (send, recv, central) node lists for Schwarz exchange.
        """
        return (self.send_overlap, self.recv_overlap, self.central_overlap)
