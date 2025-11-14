from assassyn.frontend import *

decoded_instr = Record(
    rs1=Bits(5),
    rs2=Bits(5),
    rd=Bits(5),
    alu_select=Bits(2), # 01: add, 10: addi, but we do not use this
    is_addi=Bits(1) # we use is_addi for simplicity
)