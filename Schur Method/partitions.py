from collections import OrderedDict

class GlobalQuadMesh:
    """
    Build a single quadrilateral mesh on [0,1]×[0,1], subdivided into nx×ny elements.
    Nodes are numbered 1…(nx+1)*(ny+1); elements 1…nx*ny.
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

    def get_interface_nodes(self, x_val=0.5, tol=1e-8):
        """Return list of node tags whose x-coordinate == x_val within tol."""
        return [tag for tag,(x,_) in self.node_coords.items() if abs(x - x_val) < tol]


class LeftQuadPartition:
    """
    Partition of the global mesh for x <= 0.5.
    """
    def __init__(self, mesh: GlobalQuadMesh, fixed_nodes=None, nodal_loads=None):
        # filter nodes on left side
        self.node_tags = [tag for tag,(x,_) in mesh.node_coords.items() if x <= 0.5]
        self.node_coords = {tag: mesh.node_coords[tag] for tag in self.node_tags}
        # filter elements whose all nodes are in left side
        self.elements = [(eTag, nodes) for eTag,nodes in mesh.elements
                         if all(n in self.node_tags for n in nodes)]
        # boundary conditions and loads
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads  = nodal_loads or {}

    def populate(self, model):
        # 1) Nodes
        for tag,(x,y) in self.node_coords.items():
            model.node(tag, x, y)
        # 2) Material
        model.nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)
        # 3) Elements
        for eTag, nodes in self.elements:
            model.element("quad", eTag, *nodes, 1.0, "PlaneStress", 1)
        # 4) Fixities
        for n in self.fixed_nodes:
            model.fix(n, 1, 1)
        # 5) Loads
        if self.nodal_loads:
            model.timeSeries("Constant", 1)
            model.pattern("Plain", 1, 1)
            for n,(Fx,Fy) in self.nodal_loads.items():
                model.load(n, Fx, Fy)

    def get_nodal_loads(self):
        return self.nodal_loads

    def get_dof_partition(self):
        # map free nodes to DOF base index
        free = [n for n in self.node_tags if n not in self.fixed_nodes]
        node_to_dof = {n: i*2 for i,n in enumerate(free)}
        # determine interface tags (x==0.5)
        interface_tags = [n for n in free if abs(self.node_coords[n][0] - 0.5) < 1e-8]
        interior_tags  = [n for n in free if n not in interface_tags]
        # build DOF lists
        interior = [node_to_dof[n] + d for n in interior_tags for d in (0,1)]
        interface = [node_to_dof[n] + d for n in interface_tags for d in (0,1)]
        return {"interior": interior, "interface": interface}


class RightQuadPartition:
    """
    Partition of the global mesh for x >= 0.5.
    """
    def __init__(self, mesh: GlobalQuadMesh, fixed_nodes=None, nodal_loads=None):
        # filter nodes on right side
        self.node_tags = [tag for tag,(x,_) in mesh.node_coords.items() if x >= 0.5]
        self.node_coords = {tag: mesh.node_coords[tag] for tag in self.node_tags}
        # filter elements whose all nodes are in right side
        self.elements = [(eTag, nodes) for eTag,nodes in mesh.elements
                         if all(n in self.node_tags for n in nodes)]
        # boundary conditions and loads
        self.fixed_nodes = fixed_nodes or []
        self.nodal_loads  = nodal_loads or {}

    def populate(self, model):
        for tag,(x,y) in self.node_coords.items():
            model.node(tag, x, y)
        model.nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)
        for eTag, nodes in self.elements:
            model.element("quad", eTag, *nodes, 1.0, "PlaneStress", 1)
        for n in self.fixed_nodes:
            model.fix(n, 1, 1)
        if self.nodal_loads:
            model.timeSeries("Constant", 1)
            model.pattern("Plain", 1, 1)
            for n,(Fx,Fy) in self.nodal_loads.items():
                model.load(n, Fx, Fy)

    def get_nodal_loads(self):
        return self.nodal_loads

    def get_dof_partition(self):
        free = [n for n in self.node_tags if n not in self.fixed_nodes]
        node_to_dof = {n: i*2 for i,n in enumerate(free)}
        interface_tags = [n for n in free if abs(self.node_coords[n][0] - 0.5) < 1e-8]
        interior_tags  = [n for n in free if n not in interface_tags]
        interior = [node_to_dof[n] + d for n in interior_tags for d in (0,1)]
        interface = [node_to_dof[n] + d for n in interface_tags for d in (0,1)]
        return {"interior": interior, "interface": interface}
