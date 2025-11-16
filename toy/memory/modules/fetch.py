from assassyn.frontend import *
from assassyn.backend import *

class Fetcher(Module):
    """Maintains the program counter."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Fetcher"

    @module.combinational
    def build(self, depth_log: int, decoder: Module, pc_offset: int):
        pc_reg = RegArray(Bits(32), 1, initializer=[pc_offset & 0xFFFFFFFF])
        pc_value = pc_reg[0]

        rel_pc = (pc_value.bitcast(Int(32)) - Int(32)(pc_offset & 0xFFFFFFFF)).bitcast(Bits(32))
        addr_bits = rel_pc[2 : 2 + depth_log]
        pc_addr = addr_bits.bitcast(Int(depth_log))

        log("toy-fetch  | pc=0x{:08x}", pc_value)

        decoder.async_called(pc_value=pc_value)

        next_pc = (pc_value.bitcast(Int(32)) + Int(32)(4)).bitcast(Bits(32))
        pc_reg[0] = next_pc

        return pc_reg, pc_addr
