import openseespy.opensees as ops
from partitions import GlobalQuadMesh, LeftQuadPartition, RightQuadPartition

if __name__ == "__main__":
    # Mesh and parameters
    nx, ny = 6, 2
    mesh = GlobalQuadMesh(nx, ny)
    fixed_left = [1]
    fixed_right = [6]
    nodal_loads = {18: (0.0, -1000.0)}  # same as parallel

    # Build full model
    ops.wipe()
    ops.model('basic', '-ndm', 2, '-ndf', 2)
    for tag, (x, y) in mesh.node_coords.items():
        ops.node(tag, x, y)
    ops.nDMaterial('ElasticIsotropic', 1, 2.0e11, 0.3)
    for eTag, conn in mesh.elements:
        ops.element('quad', eTag, *conn, 1.0, 'PlaneStress', 1)

    # Apply BCs
    for n in fixed_left + fixed_right:
        ops.fix(n, 1, 1)

    # External loads
    ops.timeSeries('Constant', 1)
    ops.pattern('Plain', 1, 1)
    for n, (fx, fy) in nodal_loads.items():
        ops.load(n, fx, fy)

    # Solver settings (matches DDM subdomains)
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Transformation')
    ops.test('NormDispIncr', 1e-8, 6)
    ops.algorithm('Linear')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')

    # Perform static analysis
    if ops.analyze(1) != 0:
        raise RuntimeError('Analysis failed')

    # Print interface displacements (for reference)
    print('\n Serial interface nodes (i=3)')
    for j in range(ny+1):
        node = 1 + j*(nx+1) + 3  # node at i=3
        ux = ops.nodeDisp(node, 1)
        uy = ops.nodeDisp(node, 2)
        print(f"Node {node:2d}: ux={ux:.6e}, uy={uy:.6e}")

    # Print Node 16 (non‐overlap) for verification
    node16 = 13
    ux16 = ops.nodeDisp(node16, 1)
    uy16 = ops.nodeDisp(node16, 2)
    print(f"\nSerial Node {node16}: ux={ux16:.6e}, uy={uy16:.6e}\n")
