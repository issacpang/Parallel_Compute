import openseespy.opensees as ops

# ------------------------------------------------------------------
class LeftQuadPartition:
    """
    Left half – local nodes = [1,2,4,5,7,8]
    Interface nodes = {2,5,8}; Interior nodes = {1,4,7}
    """

    def __init__(self):
        self.node_tags = [1, 2, 4, 5, 7, 8]
        self.tag2local = {tag: i for i, tag in enumerate(self.node_tags)}
        self.fixed_nodes = [1]
        self.nodal_loads = {4: [0.0, -2.0e3]}

    def populate(self, subdomain):
        # 1) Nodes
        ops.node(1, 0.0, 0.0)
        ops.node(2, 0.5, 0.0)
        ops.node(4, 0.0, 0.5)
        ops.node(5, 0.5, 0.5)
        ops.node(7, 0.0, 1.0)
        ops.node(8, 0.5, 1.0)

        # 2) Material
        ops.nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)

        # 3) Elements
        ops.element("quad", 1, 1, 2, 5, 4, 1.0, "PlaneStress", 1)
        ops.element("quad", 3, 4, 5, 8, 7, 1.0, "PlaneStress", 1)

        # 4) Supports
        ops.fix(1, 1, 1)

        # 5) Loads
        ops.timeSeries("Constant", 1)
        ops.pattern("Plain", 1, 1)
        ops.load(4, 0.0, -2.0e3)

    def get_nodal_loads(self):
        return self.nodal_loads

    def get_dof_partition(self):
        free_nodes = [n for n in self.node_tags if n not in self.fixed_nodes]
        node_to_dof = {n: i * 2 for i, n in enumerate(free_nodes)}
        interior_tags = [t for t in [1, 4, 7] if t not in self.fixed_nodes]
        interface_tags = [t for t in [2, 5, 8] if t not in self.fixed_nodes]
        interior_dofs = [node_to_dof[t] + d for t in interior_tags for d in (0,1)]
        interface_dofs = [node_to_dof[t] + d for t in interface_tags for d in (0,1)]
        return {"interior": interior_dofs, "interface": interface_dofs}

# ------------------------------------------------------------------
class RightQuadPartition:
    """
    Right half – local nodes = [2,3,5,6,8,9]
    Interface nodes = {2,5,8}; Interior nodes = {3,6,9}
    """

    def __init__(self):
        self.node_tags = [2, 3, 5, 6, 8, 9]
        self.tag2local = {tag: i for i, tag in enumerate(self.node_tags)}
        self.fixed_nodes = [3]
        self.nodal_loads = {}

    def populate(self, subdomain):
        ops.node(2, 0.5, 0.0)
        ops.node(3, 1.0, 0.0)
        ops.node(5, 0.5, 0.5)
        ops.node(6, 1.0, 0.5)
        ops.node(8, 0.5, 1.0)
        ops.node(9, 1.0, 1.0)

        ops.nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)

        ops.element("quad", 2, 2, 3, 6, 5, 1.0, "PlaneStress", 1)
        ops.element("quad", 4, 5, 6, 9, 8, 1.0, "PlaneStress", 1)

        ops.fix(3, 1, 1)

    def get_nodal_loads(self):
        return self.nodal_loads

    def get_dof_partition(self):
        free_nodes = [n for n in self.node_tags if n not in self.fixed_nodes]
        node_to_dof = {n: i * 2 for i, n in enumerate(free_nodes)}
        interior_tags = [t for t in [3, 6, 9] if t not in self.fixed_nodes]
        interface_tags = [t for t in [2, 5, 8] if t not in self.fixed_nodes]
        interior_dofs = [node_to_dof[t] + d for t in interior_tags for d in (0,1)]
        interface_dofs = [node_to_dof[t] + d for t in interface_tags for d in (0,1)]
        return {"interior": interior_dofs, "interface": interface_dofs}
