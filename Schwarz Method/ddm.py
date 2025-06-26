import pickle
from multiprocessing import Process, Queue
import openseespy.opensees as ops
from partitions import LeftQuadPartition, RightQuadPartition

class Domain:
    def __init__(self, partitions, dt=0.01, tol=1e-6, max_iter=100):
        self.partitions = partitions
        self.dt = dt
        self.tol = tol
        self.max_iter = max_iter

        # Initialize interface data to zero on recv_overlap
        self.interface_data = [{} for _ in partitions]
        for i, part in enumerate(partitions):
            for node in part.get_overlap_nodes()[1]:  # recv_overlap
                for dof in (0, 1):
                    self.interface_data[i][(node, dof)] = 0.0

        # Central nodes for convergence test
        self.central_nodes = set(partitions[0].get_overlap_nodes()[2])

        # Spawn subdomain workers
        self.to_sub = []
        self.from_sub = []
        self.workers = []
        for part in partitions:
            to_q = Queue()
            from_q = Queue()
            p = Process(target=Domain._worker, args=(pickle.dumps(part), to_q, from_q))
            p.start()
            self.to_sub.append(to_q)
            self.from_sub.append(from_q)
            self.workers.append(p)

    def step(self, time, load_factor=1.0):
        reactions = None
        for itr in range(self.max_iter):
            # Send current interface_data
            for i, q in enumerate(self.to_sub):
                q.put({
                    'cmd': 'solve',
                    'data': self.interface_data[i],
                    'time': time,
                    'load_factor': load_factor
                })
            # Collect subdomain results
            reactions = [q.get() for q in self.from_sub]

            # Update interface_data by preserving and updating only send_overlap DOFs
            for i, part in enumerate(self.partitions):
                send_nodes = part.get_overlap_nodes()[0]
                other = 1 - i
                self.interface_data[other].update({
                    (n, dof): reactions[i]['displacements'][(n, dof)]
                    for n in send_nodes for dof in (0, 1)
                })

            # Check convergence on central nodes
            max_diff = 0.0
            for node in self.central_nodes:
                for dof in (0, 1):
                    vals = [r['displacements'].get((node, dof), 0.0) for r in reactions]
                    diff = max(vals) - min(vals)
                    max_diff = max(max_diff, diff)

            # Require at least two sweeps before accepting convergence
            if itr >= 1 and max_diff < self.tol:
                return True, reactions

        return False, reactions

    def shutdown(self):
        # Terminate workers
        for q in self.to_sub:
            q.put('TERMINATE')
        for p in self.workers:
            p.join()

    @staticmethod
    def _worker(serialized_part, to_q, from_q):
        partition = pickle.loads(serialized_part)
        sd = Subdomain(partition)
        while True:
            msg = to_q.get()
            if isinstance(msg, dict) and msg.get('cmd') == 'solve':
                res = sd.solve(msg['data'], msg['time'], msg['load_factor'])
                from_q.put(res)
            elif msg == 'TERMINATE':
                break

class Subdomain:
    def __init__(self, partition):
        self.partition = partition

    def solve(self, interface_data, time, load_factor):
        # Recreate OpenSees model from scratch
        ops.wipe()
        ops.model('basic', '-ndm', 2, '-ndf', 2)
        self.partition.populate(ops)
        ops.constraints('Transformation')
        ops.numberer('RCM')
        ops.system('BandGeneral')
        ops.test('NormDispIncr', 1.0e-8, 6)
        ops.algorithm('Linear')
        ops.integrator('LoadControl', 1.0)
        ops.analysis('Static')

        # Apply interface prescribed displacements
        ops.timeSeries('Constant', 2)
        ops.pattern('Plain', 2, 2)
        for (node, dof), val in interface_data.items():
            if node in self.partition.recv_overlap:
                ops.sp(node, dof+1, val)

        # Apply external loads (defined in partition.populate)
        ops.analyze(1)

        # Extract ALL free-node displacements
        displacements = {}
        free_nodes = [n for n in self.partition.node_tags if n not in self.partition.fixed_nodes]
        for node in free_nodes:
            displacements[(node, 0)] = ops.nodeDisp(node, 1)
            displacements[(node, 1)] = ops.nodeDisp(node, 2)

        return {'displacements': displacements}
