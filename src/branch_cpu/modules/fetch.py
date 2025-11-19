from assassyn.frontend import *
from assassyn.backend import *

from ..common import (
    BTB_COUNTER_BITS,
    BTB_ENTRY_BITS,
    BTB_INDEX_BITS,
    btb_index_bits,
    btb_tag_bits,
    fetch_prediction,
    unpack_btb_entry,
)


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
        on_hazard: Array,
        program_words: int,
        branch_mispredict: Array,
        correct_pc: Array,
        btb: Array,
        btb_write_enable: Array,
        btb_write_index: Array,
        btb_write_data: Array,
    ):
        wait_until(~on_hazard[0])

        pc_reg = RegArray(Bits(32), 1, initializer=[pc_offset & 0xFFFFFFFF])
        pc_value = pc_reg[0]
        pc_int = pc_value.bitcast(Int(32))
        rel_pc_int = pc_int - Int(32)(pc_offset & 0xFFFFFFFF)
        rel_pc = rel_pc_int.bitcast(Bits(32))

        addr_bits = rel_pc[2 : 2 + depth_log]
        pc_addr = addr_bits.bitcast(Int(depth_log))

        fetch_index_bits = btb_index_bits(pc_value)
        fetch_index = fetch_index_bits.bitcast(Int(BTB_INDEX_BITS))
        
        btb_we = btb_write_enable[0]
        entry_bits = btb[fetch_index].bitcast(Bits(BTB_ENTRY_BITS))
        valid, tag, target_pc, counter = unpack_btb_entry(entry_bits)
        pc_tag = btb_tag_bits(pc_value)
        btb_hit = valid & (tag == pc_tag)
        
        counter_msb = counter[BTB_COUNTER_BITS - 1 : BTB_COUNTER_BITS - 1]
        predict_taken = btb_hit & counter_msb

        sequential_pc = (pc_int + Int(32)(4)).bitcast(Bits(32))
        predicted_pc = predict_taken.select(target_pc, sequential_pc)

        program_bytes = Int(32)(program_words * 4)
        has_remaining = rel_pc_int < program_bytes

        mispredict_active = branch_mispredict[0]
        hold_or_pred = btb_we.select(pc_value, predicted_pc)
        bounded_pc = has_remaining.select(hold_or_pred, pc_value)
        next_pc = mispredict_active.select(correct_pc[0], bounded_pc)
        pc_reg[0] = next_pc

        fetch_meta = fetch_prediction.bundle(
            btb_hit=btb_hit,
            counter=counter,
            predict_taken=predict_taken,
            target_pc=target_pc,
        )

        do_fetch = has_remaining & ~btb_we & ~mispredict_active

        with Condition(do_fetch):
            log(
                "branch-fetch | fetch | pc=0x{:08x} hit={} predict_taken={} target=0x{:08x}",
                pc_value,
                btb_hit,
                predict_taken,
                target_pc,
            )
            decoder.async_called(pc_value=pc_value, fetch_meta=fetch_meta)

        with Condition(~do_fetch):
            log(
                "branch-fetch | stall | pc=0x{:08x} mispredict={} btb_we={} has_remaining={}",
                pc_value,
                mispredict_active,
                btb_we,
                has_remaining,
            )

        with Condition(mispredict_active):
            branch_mispredict[0] = Bits(1)(0)
        with Condition(btb_we):
            write_index_bits = btb_write_index[0]
            write_index = write_index_bits.bitcast(Int(BTB_INDEX_BITS))
            btb[write_index] = btb_write_data[0]
            btb_write_enable[0] = Bits(1)(0)

        return pc_reg, pc_addr
