from openseespy.opensees import (
    node, nDMaterial, element, fix, load,
    timeSeries, pattern
)

# ------------------------------------------------------------------
class LeftQuadPartition:
    """
    Left half – local nodes = [1,2,4,5,7,8]
    Interface nodes = {2,5,8}; Interior nodes = {1,4,7}
    """

    def __init__(self):
        self.node_tags = [1, 2, 4, 5, 7, 8]
        self.tag2local = {tag: i for i, tag in enumerate(self.node_tags)}
        self.fixed_nodes = [1]  # Define fixed nodes
        self.nodal_loads = {4: [0.0, -2.0e3]}  # node 4: [Fx, Fy]

    # --------------------------------------------------------------
    def populate(self, subdomain):
        # 1) Nodes (must follow self.node_tags order)
        node(1, 0.0, 0.0)
        node(2, 0.5, 0.0)
        node(4, 0.0, 0.5)
        node(5, 0.5, 0.5)
        node(7, 0.0, 1.0)
        node(8, 0.5, 1.0)

        # 2) 2-D elastic material (PlaneStress)
        nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)  # tag=1

        # 3) Elements (thk=1.0, "PlaneStress", matTag=1)
        element("quad", 1, 1, 2, 5, 4, 1.0, "PlaneStress", 1)  # E1
        element("quad", 3, 4, 5, 8, 7, 1.0, "PlaneStress", 1)  # E3

        # 4) Physical supports (bottom edge)
        fix(1, 1, 1)    # node-1 ux,uy fixed

        # 5) External nodal load (downward at node-4)
        timeSeries("Constant", 1)
        pattern("Plain", 1, 1)
        load(4, 0.0, -2.0e3)      # Fy = −2000 N

    # --------------------------------------------------------------
    def get_nodal_loads(self):
        """
        Returns a dictionary of nodal loads {node: [Fx, Fy]}
        """
        return self.nodal_loads

    # --------------------------------------------------------------
    def get_dof_partition(self):
        # Identify free nodes
        free_nodes = [n for n in self.node_tags if n not in self.fixed_nodes]  # [2, 4, 5, 7, 8]
        # Map free nodes to starting DOF indices (0-based for K)
        node_to_dof = {n: i * 2 for i, n in enumerate(free_nodes)}
        # Filter tags to include only free nodes
        interior_tags = [t for t in [1, 4, 7] if t not in self.fixed_nodes]  # [4, 7]
        interface_tags = [t for t in [2, 5, 8] if t not in self.fixed_nodes]  # [2, 5, 8]
        # Compute DOF indices
        interior_dofs = [node_to_dof[t] + d for t in interior_tags for d in (0, 1)]  # [2, 3, 6, 7]
        interface_dofs = [node_to_dof[t] + d for t in interface_tags for d in (0, 1)]  # [0, 1, 4, 5, 8, 9]
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
        self.fixed_nodes = [3]  # Define fixed nodes
        self.nodal_loads = {}  # No loads defined

    # --------------------------------------------------------------
    def populate(self, subdomain):
        node(2, 0.5, 0.0)
        node(3, 1.0, 0.0)
        node(5, 0.5, 0.5)
        node(6, 1.0, 0.5)
        node(8, 0.5, 1.0)
        node(9, 1.0, 1.0)

        nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)

        element("quad", 2, 2, 3, 6, 5, 1.0, "PlaneStress", 1)  # E2
        element("quad", 4, 5, 6, 9, 8, 1.0, "PlaneStress", 1)  # E4

        # Fix bottom-right corner node-3
        fix(3, 1, 1)

    # --------------------------------------------------------------
    def get_nodal_loads(self):
        """
        Returns a dictionary of nodal loads {node: [Fx, Fy]}
        """
        return self.nodal_loads

    # --------------------------------------------------------------
    def get_dof_partition(self):
        # Identify free nodes
        free_nodes = [n for n in self.node_tags if n not in self.fixed_nodes]  # [2, 5, 6, 8, 9]
        # Map free nodes to starting DOF indices
        node_to_dof = {n: i * 2 for i, n in enumerate(free_nodes)}
        # Filter tags to include only free nodes
        interior_tags = [t for t in [3, 6, 9] if t not in self.fixed_nodes]  # [6, 9]
        interface_tags = [t for t in [2, 5, 8] if t not in self.fixed_nodes]  # [2, 5, 8]
        # Compute DOF indices
        interior_dofs = [node_to_dof[t] + d for t in interior_tags for d in (0, 1)]  # [4, 5, 8, 9]
        interface_dofs = [node_to_dof[t] + d for t in interface_tags for d in (0, 1)]  # [0, 1, 2, 3, 6, 7]
        return {"interior": interior_dofs, "interface": interface_dofs}