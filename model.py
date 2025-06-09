from openseespy.opensees import *

# Define the 2D model with 2 DOFs per node
model("BasicBuilder", "-ndm", 2, "-ndf", 2)

# Define all nodes with coordinates (unit square, 2x2 grid)
node(1, 0.0, 0.0)  # Bottom-left
node(2, 0.5, 0.0)  # Bottom-middle
node(3, 1.0, 0.0)  # Bottom-right
node(4, 0.0, 0.5)  # Middle-left
node(5, 0.5, 0.5)  # Center
node(6, 1.0, 0.5)  # Middle-right
node(7, 0.0, 1.0)  # Top-left
node(8, 0.5, 1.0)  # Top-middle
node(9, 1.0, 1.0)  # Top-right

# Define material (Elastic Isotropic)
nDMaterial("ElasticIsotropic", 1, 2.0e11, 0.30)

# Define quadrilateral elements (thickness = 1.0, PlaneStress)
element("quad", 1, 1, 2, 5, 4, 1.0, "PlaneStress", 1)  # Left-bottom
element("quad", 2, 2, 3, 6, 5, 1.0, "PlaneStress", 1)  # Right-bottom
element("quad", 3, 4, 5, 8, 7, 1.0, "PlaneStress", 1)  # Left-top
element("quad", 4, 5, 6, 9, 8, 1.0, "PlaneStress", 1)  # Right-top

# Apply boundary conditions (fix nodes 1 and 3)
fix(1, 1, 1)  # Node 1 fixed in x and y
fix(3, 1, 1)  # Node 3 fixed in x and y

# Define load (downward at node 5)
timeSeries("Constant", 1)
pattern("Plain", 1, 1)
load(4, 0.0, -2.0e3)  # Fy = -1000 N

# Set up analysis
system("FullGeneral")
numberer("RCM")
constraints("Plain")
integrator("LoadControl", 1.0)
algorithm("Linear")
analysis("Static")

# Run the analysis
analyze(1)

# Extract displacements at interface nodes (2, 5, 8)
displacements = {
    (2, 1): nodeDisp(2, 1),  # Node 2, DOF 1 (ux)
    (2, 2): nodeDisp(2, 2),  # Node 2, DOF 2 (uy)
    (5, 1): nodeDisp(5, 1),  # Node 5, DOF 1 (ux)
    (5, 2): nodeDisp(5, 2),  # Node 5, DOF 2 (uy)
    (8, 1): nodeDisp(8, 1),  # Node 8, DOF 1 (ux)
    (8, 2): nodeDisp(8, 2),  # Node 8, DOF 2 (uy)
}

# Print the results
print("Displacements at interface nodes (node, dof): value")
for (node, dof), disp in displacements.items():
    print(f"Node {node}, DOF {dof}: {disp:.12e}")