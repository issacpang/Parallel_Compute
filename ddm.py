import numpy as np
import pickle
from multiprocessing import Process, Queue


class Domain:
    def __init__(self, partitions):
        """
        master process: spawns workers, assembles Schur system, shuts down

        partitions: list of PartitionBuilder instances
        """
        self.partitions        = partitions
        self.workers           = []        # list of Process
        self._send      = []        # list of Queue (to worker)
        self._recv    = []        # list of Queue (from worker)
        self.interface_guess   = {}        # {(node, dof): value}
        self.interface_order   = []        # [(node, dof), ...] in global order

        # Spawn one Subdomain worker per partition
        for part in partitions:
            q_send = Queue()
            q_recv = Queue()
            p = Process(
                target=Domain._subdomain_worker,
                args=(pickle.dumps(part), q_send, q_recv)
            )
            p.start()

            self.workers.append(p)
            self._send.append(q_send)
            self._recv.append(q_recv)

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
        for q in self._send:
            q.put({"cmd": "solve", "data": interface_data})

        return [q.get() for q in self._recv]


    def schur_update(self):
        """
        Assemble and solve the global Schur system.
        """
        for q in self._send:
            q.put({"cmd": "schur"})


        S_total = None
        g_total = None
        for q in self._recv:
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
        for q in self._send:
            q.put("TERMINATE")
        for p in self.workers:
            p.join()


    @staticmethod
    def _subdomain_worker(serialized_partition, q_send, q_recv):

        partition = pickle.loads(serialized_partition)
        sd = Subdomain(partition)

        while True:
            msg = q_send.get()
            cmd = msg['cmd'] if isinstance(msg, dict) and 'cmd' in msg else msg

            if cmd == "schur":
                S_i, g_i = sd.get_schur_data()
                q_recv.put((S_i, g_i))

            elif cmd in ("exit", "TERMINATE"):
                break

            else:
                raise RuntimeError(f"Unknown message to subdomain worker: {msg}")


class Subdomain:
    def __init__(self, partition):
        self.partition = partition

        if not hasattr(self.partition, 'node_tags'):
            raise AttributeError("Partition object lacks node_tags")

        import opensees.openseespy as _ops
        model = _ops.Model("BasicBuilder", "-ndm", 2, "-ndf", 2)
        self.model = model

        partition.populate(model)

        model.system("FullGeneral")
        model.numberer("Plain")
        model.constraints("Plain")
        model.integrator("LoadControl", 1.0)
        model.algorithm("Linear")
        model.analysis("Static")

        dofs = partition.get_dof_partition()
        self.interior_dofs  = dofs["interior"]
        self.interface_dofs = dofs["interface"]



    def apply_interface_conditions(self, interface_data):
        for (node, dof), val in interface_data.get("dirichlet", {}).items():
            self.model.sp(node, dof, val)

        for (node, dof), val in interface_data.get("neumann", {}).items():
            self.model.load(node, dof, val)


    def get_schur_data(self):
        print("Assembling tangent")
        self.model.system("FullGeneral")
        self.model.numberer("Plain")
        self.model.constraints("Plain")
        self.model.test("FixedNumIter", 1)
        self.model.integrator("LoadControl", 1.0)
        self.model.algorithm("Linear")
        self.model.analysis("Static")

        rc = self.model.analyze(1, operation="increment")
        if rc != 0:
            raise RuntimeError(f"OpenSees assemble failed (rc={rc})")

#       N = self.model.systemSize()
        K = self.model.getTangent()

        # Build global residual
        R_global = self.model.getResidual()

#       free_node_list = [
#               n for n in self.partition.node_tags
#                         if n not in self.partition.fixed_nodes
#       ]
#       free_nodes = {n: i*2 for i, n in enumerate(free_node_list)}

#       for node, (Fx, Fy) in self.partition.get_nodal_loads().items():
#           if node in free_nodes:
#               base = free_nodes[node]
#               R_global[base]   = Fx
#               R_global[base+1] = Fy


#       print(R_global)
#       print(f"getResid = {self.model.getResidual()}")

        I, G = self.interior_dofs, self.interface_dofs

        K_II = K[np.ix_(I, I)]
        K_IG = K[np.ix_(I, G)]
        K_GI = K[np.ix_(G, I)]
        K_GG = K[np.ix_(G, G)]
        R_I = R_global[I]
        R_G = R_global[G]

        KII_inv_KIG = np.linalg.solve(K_II, K_IG)
        KII_inv_RI  = np.linalg.solve(K_II, R_I)
        S_local = K_GG - K_GI @ KII_inv_KIG
        g_local = R_G  - K_GI @ KII_inv_RI
        return S_local, g_local


if __name__ == "__main__":
    from partitions import LeftQuadPartition, RightQuadPartition
    left  = LeftQuadPartition()
    right = RightQuadPartition()

    print("Starting domain setup")
    domain = Domain([left, right])
    domain.interface_order = [(2,1), (2,2), (5,1), (5,2), (8,1), (8,2)]
    domain.interface_guess = {key: 0.0 for key in domain.interface_order}

    print("Calling schur_update")
    u_gamma = domain.schur_update()

    print("schur_update completed, interface_guess:", domain.interface_guess)
    domain.shutdown()
    print("Domain shut down")

