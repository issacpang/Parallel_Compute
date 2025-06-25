from ddm import Domain
from partitions import GlobalQuadMesh, LeftQuadPartition, RightQuadPartition

# 1) Build one global mesh: 6×2 quads (so each half is 3×2)
global_mesh = GlobalQuadMesh(nx=6, ny=3)

# 2) Create left/right partitions sharing the global numbering
#    - left fixed at node 1; load at node 11 (global tag for (0.5,0.5))
#    - right fixed at node 7 (global tag for (1.0,0.0)); no loads
left  = LeftQuadPartition(global_mesh, fixed_nodes=[1],  nodal_loads={11: (0.0, -2.0e3)})
right = RightQuadPartition(global_mesh, fixed_nodes=[7], nodal_loads={})

# 3) Instantiate the DDM master with both subdomains
domain = Domain([left, right])

# 4) Auto-detect the shared interface nodes at x = 0.5
interface_nodes = global_mesh.get_interface_nodes(x_val=0.5)
print("Interface node IDs:", interface_nodes)

# 5) Build the global interface DOF ordering (ux=1, uy=2)
domain.interface_order = [(n, d) for n in interface_nodes for d in (1, 2)]
# Initialize the interface guess to zero
domain.interface_guess = {key: 0.0 for key in domain.interface_order}

# 6) Solve the Schur complement system
print("\nCalling schur_update …")
u_gamma = domain.schur_update()
print(" → interface solution computed.\n")

# 7) (Optional) Print only the left-side interface DOFs
print("Left-side interface DOF results:")
print(" Node | DOF |    Value    ")
print("------+-----+-------------")
for n in interface_nodes:
    if n in left.node_tags:
        for d in (1, 2):
            v = domain.interface_guess[(n, d)]
            print(f"  {n:2d}  |  {d}  | {v: .3e}")

# 8) Clean up worker processes
domain.shutdown()
print("\nDone.")
