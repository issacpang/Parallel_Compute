from ddm import Domain
from partitions import LeftQuadPartition, RightQuadPartition

left  = LeftQuadPartition()
right = RightQuadPartition()
print("Starting domain setup")
domain = Domain([left, right])
print("Domain initialized")
domain.interface_order = [(2,1), (2,2), (5,1), (5,2), (8,1), (8,2)]
domain.interface_guess = {key: 0.0 for key in domain.interface_order}
print("Calling schur_update")
u_gamma = domain.schur_update()
print("schur_update completed, interface_guess:", domain.interface_guess)
domain.shutdown()
print("Domain shut down")
