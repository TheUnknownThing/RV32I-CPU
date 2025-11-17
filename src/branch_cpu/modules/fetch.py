from assassyn.frontend import *
from assassyn.backend import *


class Fetcher(Module):
    """Maintains the program counter and handles control-flow redirects."""

    def __init__(self):
        super().__init__(ports={})
        self.name = "Fetcher"

    @module.combinational
    def build(
        self,
        depth_log: int,
        decoder: Module,
        pc_offset: int,
        on_branch: Array,
        on_hazard: Array,
        program_words: int,
        btb_addr_reg: Array,
        bcache: Module,
    ):
        wait_until(~on_hazard[0])

        pc_reg = RegArray(Bits(32), 1, initializer=[pc_offset & 0xFFFFFFFF])
        pc_value = pc_reg[0]
        pc_int = pc_value.bitcast(Int(32))
        rel_pc_int = pc_int - Int(32)(pc_offset & 0xFFFFFFFF)
        rel_pc = rel_pc_int.bitcast(Bits(32))

        addr_bits = rel_pc[2 : 2 + depth_log]
        pc_addr = addr_bits.bitcast(Int(depth_log))


        program_bytes = Int(32)(program_words * 4)
        has_remaining = rel_pc_int < program_bytes

        do_fetch = has_remaining

        with Condition(do_fetch):
            log("naive-fetch | fetch | pc=0x{:08x} busy={} ", pc_value)

            btb_out = bcache.dout[0].bitcast(Bits(57))
            btb_valid = btb_out[0]
            btb_tag = btb_out[1:23]
            btb_target = btb_out[23:55]
            btb_counter = btb_out[55:57]

            with Condition(btb_valid & (btb_tag == pc_int[10:32])):
                log("naive-fetch | branch btb hit pc=0x{:08x} target=0x{:08x}", pc_value, btb_target)
                pass # TODO: implement branch prediction target

            with Condition(~(btb_valid & (btb_tag == pc_int[10:32]))):
                next_pc = (pc_int + Int(32)(4)).bitcast(Bits(32))
                pc_reg[0] = next_pc
                btb_addr_reg[0] = next_pc[2:10]
            
            decoder.async_called(pc_value=pc_value, pred_pc=btb_target, pred_counter=btb_counter)

        with Condition(~do_fetch):
            log("naive-fetch | stalled | pc=0x{:08x} busy={}", pc_value)

        return pc_reg, pc_addr
