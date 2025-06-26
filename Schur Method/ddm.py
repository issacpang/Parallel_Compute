import numpy as np
import pickle
from multiprocessing import Process, Queue
import openseespy.opensees as ops

class Domain:
    def __init__(self, partitions):
        """
        partitions: list of PartitionBuilder instances
        """
        self.partitions        = partitions
        self.workers           = []       
        self.to_subdomain      = []        
        self.from_subdomain    = []       
        self.interface_guess   = {}       
        self.interface_order   = []        

        # Spawn one Subdomain worker per partition
        for part in partitions:
            to_q   = Queue()
            from_q = Queue()
            p = Process(
                target=Domain._subdomain_worker,
                args=(pickle.dumps(part), to_q, from_q)
            )
            p.start()

            self.workers.append(p)
            self.to_subdomain.append(to_q)
            self.from_subdomain.append(from_q)

    def step(self):
        """
        Perform one block-Jacobi solve:
        • Send current interface_guess to each Subdomain
        • Collect each subdomain’s interface reactions
        Returns a list of each subdomain’s reaction dict.
        """
        interface_data = {
            "dirichlet": self.interface_guess.copy(),
            "neumann": {}
        }
        for q in self.to_subdomain:
            q.put({"cmd": "solve", "data": interface_data})
        return [q.get() for q in self.from_subdomain]

    def schur_update(self):
        """
        Assemble and solve the global Schur system.
        """
        for q in self.to_subdomain:
            q.put({"cmd": "schur"})

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

        u_gamma = np.linalg.solve(S_total, g_total)
        self.interface_guess = self.unpack_interface_vector(u_gamma)
        return u_gamma

    def unpack_interface_vector(self, flat_u):
        return {
            self.interface_order[i]: float(flat_u[i])
            for i in range(len(flat_u))
        }

    def shutdown(self):
        for q in self.to_subdomain:
            q.put("TERMINATE")
        for p in self.workers:
            p.join()

    @staticmethod
    def _subdomain_worker(serialized_partition, to_q, from_q):
        import pickle
        from ddm import Subdomain
        from partitions import LeftQuadPartition, RightQuadPartition

        partition = pickle.loads(serialized_partition)
        sd = Subdomain(partition)

        while True:
            msg = to_q.get()
            cmd = msg['cmd'] if isinstance(msg, dict) and 'cmd' in msg else msg

            if cmd == "schur":
                S_i, g_i = sd.get_schur_data()
                from_q.put((S_i, g_i))
            elif cmd in ("exit", "TERMINATE"):
                break
            else:
                raise RuntimeError(f"Unknown message to subdomain worker: {msg}")

class Subdomain:
    def __init__(self, partition):
        self.partition = partition
        if not hasattr(self.partition, 'node_tags'):
            raise AttributeError("Partition object lacks node_tags")

        ops.model("BasicBuilder", "-ndm", 2, "-ndf", 2)
        partition.populate(ops)
        ops.system("FullGeneral")
        ops.numberer("Plain")
        ops.constraints("Plain")
        ops.integrator("LoadControl", 1.0)
        ops.algorithm("Linear")
        ops.analysis("Static")

        dofs = partition.get_dof_partition()
        self.interior_dofs = dofs["interior"]
        self.interface_dofs = dofs["interface"]

    def apply_interface_conditions(self, interface_data):
        for (node, dof), val in interface_data.get("dirichlet", {}).items():
            ops.sp(node, dof, val)
        for (node, dof), val in interface_data.get("neumann", {}).items():
            ops.load(node, dof, val)

    def get_schur_data(self):
        print("Assembling tangent")
        rc = ops.analyze(1)
        if rc != 0:
            raise RuntimeError(f"OpenSees assemble failed (rc={rc})")
        print("Assembly complete, fetching K")
        N = ops.systemSize()
        K = np.array(ops.printA("-ret"), dtype=float).reshape((N, N))

        # Build global residual
        R_global = np.zeros(N)
        free_node_list = [n for n in self.partition.node_tags if n not in self.partition.fixed_nodes]
        free_nodes = {n: i*2 for i, n in enumerate(free_node_list)}
        for node, (Fx, Fy) in self.partition.get_nodal_loads().items():
            if node in free_nodes:
                base = free_nodes[node]
                R_global[base] = Fx
                R_global[base+1] = Fy

        I, G = self.interior_dofs, self.interface_dofs
        K_II = K[np.ix_(I, I)]
        K_IG = K[np.ix_(I, G)]
        K_GI = K[np.ix_(G, I)]
        K_GG = K[np.ix_(G, G)]
        R_I = R_global[I]
        R_G = R_global[G]

        KII_inv_KIG = np.linalg.solve(K_II, K_IG)
        KII_inv_RI = np.linalg.solve(K_II, R_I)
        S_local = K_GG - K_GI @ KII_inv_KIG
        g_local = R_G - K_GI @ KII_inv_RI
        return S_local, g_local
