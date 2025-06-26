import numpy as np
from ddm import Domain
from partitions import GlobalQuadMesh, LeftQuadPartition, RightQuadPartition

def main():
    # Simulation parameters
    dt = 0.01
    total_time = 1.0
    tol = 1e-6
    max_iter = 100
    load_factor = 1.0

    # Build mesh and partitions
    mesh = GlobalQuadMesh(6, 2)
    fixed_left = [1]
    fixed_right = [6]
    nodal_loads = {18: (0.0, -1000.0)}
    left_part = LeftQuadPartition(mesh, fixed_nodes=fixed_left)
    right_part = RightQuadPartition(mesh, fixed_nodes=fixed_right, nodal_loads=nodal_loads)

    # Initialize domain decomposition
    domain = Domain([left_part, right_part], dt, tol, max_iter)
    print(f"Global central nodes: {domain.central_nodes}\n")

    time = 0.0
    while time <= total_time + 1e-8:
        print(f"Time step: {time:.2f}s")
        # Perform Schwarz iterations
        converged, reactions = domain.step(time, load_factor)
        if not converged:
            print("Warning: Did not converge within max iterations!")

        # Print displacement for Node 16 (non-overlap)
        node = 13
        # Determine owning subdomain
        if node in left_part.node_tags and node not in right_part.node_tags:
            owner = 0
        elif node in right_part.node_tags and node not in left_part.node_tags:
            owner = 1
        else:
            owner = 0  # overlap: pick left
        ux = reactions[owner]['displacements'][(node, 0)]
        uy = reactions[owner]['displacements'][(node, 1)]
        print(f"Node {node} (owner {owner}): x = {ux:.6e}, y = {uy:.6e}\n")

        time += dt

    domain.shutdown()
    print("\n Simulation completed.")

if __name__ == '__main__':
    main()
