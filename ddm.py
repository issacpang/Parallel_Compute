import numpy as np
from multiprocessing import Process, Queue

# -----------------------------------------------------------------------------
#  Domain  – master process: spawns workers, assembles Schur system, shuts down
# -----------------------------------------------------------------------------
import pickle
import numpy as np
from multiprocessing import Process, Queue

class Domain:
    def __init__(self, partitions):
        """
        partitions: list of PartitionBuilder instances
        """
        self.partitions        = partitions
        self.workers           = []        # list of Process
        self.to_subdomain      = []        # list of Queue (to worker)
        self.from_subdomain    = []        # list of Queue (from worker)
        self.interface_guess   = {}        # {(node, dof): value}
        self.interface_order   = []        # [(node, dof), …] in global order

        # Spawn one Subdomain worker per partition
        for part in partitions:
            to_q   = Queue()
            from_q = Queue()
            # Use the unbound staticmethod so Python won't inject `self`
            p = Process(
                target=Domain._subdomain_worker,
                args=(pickle.dumps(part), to_q, from_q)
            )
            p.start()

            self.workers.append(p)
            self.to_subdomain.append(to_q)
            self.from_subdomain.append(from_q)

    # ------------------------------------------------------------------
    # BLOCK-JACOBI STEP
    # ------------------------------------------------------------------
    def step(self):
        """
        Perform one block-Jacobi solve:
        • Send current interface_guess to each Subdomain
        • Collect each subdomain’s interface reactions
        Returns a list of each subdomain’s reaction dict.
        """
        interface_data = {
            "dirichlet": self.interface_guess.copy(),
            "neumann":   {}
        }

        # 1) Broadcast “solve” to every worker
        for q in self.to_subdomain:
            q.put({"cmd": "solve", "data": interface_data})

        # 2) Collect and return
        return [q.get() for q in self.from_subdomain]

    # ------------------------------------------------------------------
    # SCHUR-COMPLEMENT UPDATE
    # ------------------------------------------------------------------
    def schur_update(self):
        """
        • First perform a local solve on each subdomain (to assemble K & R),
          then ask each one for its (S_i, g_i), assemble & solve the interface.
        """

        # 1) Now request each Subdomain’s local Schur data
        for q in self.to_subdomain:
            q.put({"cmd": "schur"})

        # 2) Collect and sum all S_i, g_i
        S_total = None
        g_total = None
        for q in self.from_subdomain:
            S_i, g_i = q.get()
            if S_total is None:
                S_total = S_i.copy()
                g_total = g_i.copy()
            else:
                S_total += S_i
                g_total += g_i

        # 3) Solve the dense interface system
        u_gamma = np.linalg.solve(S_total, g_total)

        # 4) Map back into {(node, dof): value}
        self.interface_guess = self.unpack_interface_vector(u_gamma)
        return u_gamma

    def unpack_interface_vector(self, flat_u):
        """
        flat_u: 1D array of length = len(self.interface_order)
        returns dict {(node,dof): value}
        """
        return {
            self.interface_order[i]: float(flat_u[i])
            for i in range(len(flat_u))
        }

    # ------------------------------------------------------------------
    # CLEAN SHUTDOWN
    # ------------------------------------------------------------------
    def shutdown(self):
        """
        Tell every Subdomain worker to terminate, then join().
        """
        for q in self.to_subdomain:
            q.put("TERMINATE")
        for p in self.workers:
            p.join()

    # ------------------------------------------------------------------
    # WORKER FUNCTION
    # ------------------------------------------------------------------
    @staticmethod
    def _subdomain_worker(serialized_partition, to_q, from_q):
        """
        Worker loop, runs in each child process.
        Listens for commands either as plain strings ("schur", "exit")
        or as dicts with a 'cmd' key.
        """
        import pickle
        from ddm import Subdomain
        from partitions import LeftQuadPartition, RightQuadPartition

        # Reconstruct the PartitionBuilder
        try:
            partition = pickle.loads(serialized_partition)
            print(f"Worker: Successfully deserialized partition of type {type(partition).__name__}")
        except Exception as e:
            print(f"Worker: Failed to deserialize partition: {e}")
            raise

        # Verify partition has expected attributes
        if not hasattr(partition, 'node_tags') or not hasattr(partition, 'fixed_nodes'):
            raise AttributeError(f"Deserialized partition lacks required attributes: {dir(partition)}")

        # Build the local FEM model in this process
        sd = Subdomain(partition)
        print(f"Worker: Subdomain created with partition {type(partition).__name__}")

        while True:
            msg = to_q.get()
            # Normalize message to a simple command string
            cmd = msg['cmd'] if isinstance(msg, dict) and 'cmd' in msg else msg

            if cmd == "schur":
                # Call the existing method to get (S_i, g_i)
                S_i, g_i = sd.get_schur_data()
                from_q.put((S_i, g_i))

            elif cmd in ("exit", "TERMINATE"):
                break

            else:
                raise RuntimeError(f"Unknown message to subdomain worker: {msg}")

class Subdomain:
    def __init__(self, partition):
        """
        Build a local OpenSeesPy model for one partition and set up
        the analysis pipeline.  ‘partition’ is a PartitionBuilder that
        knows how to add nodes/elements and provide interior/interface DOFs.
        """
        # Import OpenSeesPy commands (kept local to avoid polluting globals)
        from openseespy.opensees import (
            model,
            system,
            numberer,
            constraints,
            integrator,
            algorithm,
            analysis,
        )

        # Store partition
        self.partition = partition
        if not hasattr(self.partition, 'node_tags'):
            raise AttributeError(f"Partition object lacks node_tags: {type(self.partition).__name__}")

        # 1) Start a fresh 2-D, 2-DOF-per-node OpenSees model
        model("BasicBuilder", "-ndm", 2, "-ndf", 2)

        # 2) Let the partition builder populate nodes/elements/materials/etc.
        partition.populate(self)

        # 3) Analysis pipeline — use **FullGeneral** so printA/printB can dump K & R
        system("FullGeneral")
        numberer("Plain")
        constraints("Plain")
        integrator("LoadControl", 1.0)
        algorithm("Linear")
        analysis("Static")

        # 4) Keep track of interior vs. interface DOF indices
        dofs = partition.get_dof_partition()
        self.interior_dofs  = dofs["interior"]     # list[int]
        self.interface_dofs = dofs["interface"]    # list[int]

    # ---------------------------------------------------------------------
    # PUBLIC HELPERS
    # ---------------------------------------------------------------------

    def apply_interface_conditions(self, interface_data):
        """
        interface_data = {
            "dirichlet": {(node, dof): value, …},
            "neumann":   {(node, dof): value, …}
        }
        Imposes SP (Dirichlet) and nodal load (Neumann) conditions
        on the *interface* nodes of this sub-domain.
        """
        from openseespy.opensees import sp, load
        for (node, dof), val in interface_data.get("dirichlet", {}).items():
            sp(node, dof, val)               # single-point constraint

        for (node, dof), val in interface_data.get("neumann", {}).items():
            load(node, dof, val)             # nodal load in global axes

    # ---------------------------------------------------------------------
    # SCHUR-COMPLEMENT CONTRIBUTION
    # ---------------------------------------------------------------------

    def get_schur_data(self):
        from openseespy.opensees import analyze, printA, systemSize
        import numpy as np
        print("Assembling tangent")
        rc = analyze(1)
        if rc != 0:
            raise RuntimeError(f"OpenSees assemble failed (rc={rc})")
        print("Assembly complete, fetching K")
        N = systemSize()
        K = np.array(printA("-ret"), dtype=float).reshape((N, N))
        print(f"System size: {N}, K shape: {K.shape}")

        # Construct R_global from partition's nodal loads
        R_global = np.zeros(N, dtype=float)
        # Use same free node order as get_dof_partition
        free_node_list = [n for n in self.partition.node_tags if n not in self.partition.fixed_nodes]
        free_nodes = {n: i * 2 for i, n in enumerate(free_node_list)}
        # print(f"Free nodes mapping: {free_nodes}")
        nodal_loads = self.partition.get_nodal_loads()
        for node, (Fx, Fy) in nodal_loads.items():
            if node in free_nodes:
                dof_base = free_nodes[node]
                R_global[dof_base] = Fx      # u_x direction (DOF 1)
                R_global[dof_base + 1] = Fy  # u_y direction (DOF 2)
                print(f"Assigning load for node {node}: Fx={Fx} at DOF {dof_base}, Fy={Fy} at DOF {dof_base + 1}")
        print("   R_global =", R_global)

        # Partition into interior (I) and interface (G)
        I, G = self.interior_dofs, self.interface_dofs
        K_II = K[np.ix_(I, I)]
        K_IG = K[np.ix_(I, G)]
        K_GI = K[np.ix_(G, I)]
        K_GG = K[np.ix_(G, G)]
        R_I = R_global[I]
        R_G = R_global[G]

        print("   R_I =", R_I)
        print("   R_G =", R_G)

        KII_inv_KIG = np.linalg.solve(K_II, K_IG)
        KII_inv_RI = np.linalg.solve(K_II, R_I)
        S_local = K_GG - K_GI @ KII_inv_KIG
        g_local = R_G - K_GI @ KII_inv_RI

        return S_local, g_local

    # ---------------------------------------------------------------------
    # INTERNAL UTILS
    # ---------------------------------------------------------------------

    def _active_dof_dirs(self, node):
        """
        For a plain 2-D quadrilateral mesh each node has
        two translational DOFs: [1 = u_x, 2 = u_y].
        """
        return [1, 2]