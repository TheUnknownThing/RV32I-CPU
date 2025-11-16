from assassyn.frontend import *
from ..common import MemWidth

class MemoryAccess(Module):
    """Handles load/store operations and forwards results to writeback."""

    def __init__(self):
        super().__init__(
            ports={
                "rd": Port(Bits(5)),
                "exec_value": Port(Bits(32)),
                "write_enable": Port(Bits(1)),
                "is_load": Port(Bits(1)),
                "is_store": Port(Bits(1)),
                "mem_width": Port(Bits(2)),
                "mem_unsigned": Port(Bits(1)),
                "store_data": Port(Bits(32)),
                "pc_value": Port(Bits(32)),
                "is_ebreak": Port(Bits(1)),
                "byte_offset": Port(Bits(2)),
            }
        )
        self.name = "Memory"

    @module.combinational
    def build(self, dout: RegArray, wb: Module):
        (
            rd,
            exec_value,
            write_enable,
            is_load,
            is_store,
            mem_width,
            mem_unsigned,
            store_data,
            pc_value,
            is_ebreak,
            byte_offset,
        ) = self.pop_all_ports(False)

        width_half = mem_width == Bits(2)(MemWidth.HALF)
        width_byte = mem_width == Bits(2)(MemWidth.BYTE)

        word_value = dout[0].bitcast(Bits(32))
        shift_amount = (byte_offset.bitcast(UInt(2)) * UInt(5)(8)).bitcast(Bits(5))
        shifted = word_value >> shift_amount
        byte_value = shifted[0:7]
        half_value = shifted[0:15]

        extended_byte = _extend_to_32(byte_value, 8, mem_unsigned)
        extended_half = _extend_to_32(half_value, 16, mem_unsigned)
        load_value = word_value
        load_value = width_byte.select(extended_byte, load_value)
        load_value = width_half.select(extended_half, load_value)

        with Condition(is_load):
            log("toy-memacc | load  pc=0x{:08x} addr=0x{:08x} value=0x{:08x}", pc_value, exec_value, load_value)

        with Condition(is_store):
            log(
                "toy-memacc | store pc=0x{:08x} addr=0x{:08x} value=0x{:08x}",
                pc_value,
                exec_value,
                store_data,
            )

        result_value = is_load.select(load_value, exec_value)
        final_write = write_enable & ~is_store

        wb.async_called(rd=rd, value=result_value, enable=final_write, is_ebreak=is_ebreak)


def _extend_to_32(value: Value, width: int, is_unsigned: Value) -> Value:
    if width == 32:
        return value
    pad_width = 32 - width
    zero_pad = Bits(pad_width)(0)
    sign_pad = Bits(pad_width)((1 << pad_width) - 1)
    msb = value[width - 1 : width - 1]
    sign_extended = msb.select(sign_pad, zero_pad)
    pad = is_unsigned.select(zero_pad, sign_extended)
    return concat(pad, value)
