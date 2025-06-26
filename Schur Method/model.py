import openseespy.opensees as ops

ops.wipe()
ops.model("BasicBuilder", "-ndm", 2, "-ndf", 2)

nx, ny = 6, 2
dx, dy = 1.0/nx, 1.0/ny

# helper to compute node tag from grid indices
def n(i, j):
    # i = 0..nx, j = 0..ny
    return 1 + j*(nx+1) + i


for j in range(ny+1):
    for i in range(nx+1):
        ops.node(n(i,j), i*dx, j*dy)

ops.nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)

eTag = 1
for j in range(ny):
    for i in range(nx):
        ops.element("quad", eTag,
                    n(i,j),   n(i+1,j),
                    n(i+1,j+1), n(i,j+1),
                    1.0, "PlaneStress", 1)
        eTag += 1

ops.fix(n(0,0), 1, 1)
ops.fix(n(nx,0), 1, 1)

ops.timeSeries("Constant", 1)
ops.pattern("Plain", 1, 1)
ops.load(n(3,1), 0.0, -2.0e3)

ops.system("FullGeneral")
ops.numberer("Plain")
ops.constraints("Plain")
ops.integrator("LoadControl", 1.0)
ops.algorithm("Linear")
ops.analysis("Static")

ret = ops.analyze(1)
if ret != 0:
    raise RuntimeError(f"OpenSees analyze failed (rc={ret})")

interface = [n(3, j) for j in range(ny+1)]
print("\nSingle‐proc interface DOFs:")
print(" Node |  ux (DOF 1)   |  uy (DOF 2)")
print("------+---------------+---------------")
for nd in interface:
    ux = ops.nodeDisp(nd, 1)
    uy = ops.nodeDisp(nd, 2)
    print(f"  {nd:2d}  | {ux: .6e} | {uy: .6e}")
