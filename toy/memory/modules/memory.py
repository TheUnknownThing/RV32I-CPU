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
            }
        )
        self.name = "Memory"

    @module.combinational
    def build(self, dcache: Module, wb: Module, data_offset: int, data_bytes: int, word_addr_width: int):
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
        ) = self.pop_all_ports(False)

        addr_uint = exec_value.bitcast(UInt(32))
        base_uint = UInt(32)(data_offset & 0xFFFFFFFF)
        rel_uint = addr_uint - base_uint
        rel_bits = rel_uint.bitcast(Bits(32))

        total_bytes = UInt(32)(data_bytes)
        width_half = mem_width == Bits(2)(MemWidth.HALF)
        width_word = mem_width == Bits(2)(MemWidth.WORD)
        width_byte = mem_width == Bits(2)(MemWidth.BYTE)

        bytes_needed = UInt(32)(1)
        bytes_needed = width_half.select(UInt(32)(2), bytes_needed)
        bytes_needed = width_word.select(UInt(32)(4), bytes_needed)
        end_addr = rel_uint + bytes_needed

        addr_underflow = addr_uint < base_uint
        addr_overflow = end_addr > total_bytes
        is_mem = is_load | is_store

        with Condition(is_mem & (addr_underflow | addr_overflow)):
            upper = data_offset + data_bytes
            log(
                "toy-memacc | addr 0x{:08x} outside data memory [0x{:08x}, 0x{:08x})",
                exec_value,
                Bits(32)(data_offset & 0xFFFFFFFF),
                Bits(32)(upper & 0xFFFFFFFF),
            )
            assume(Bits(1)(0))

        byte_offset = rel_bits[0:1]
        half_unaligned = width_half & byte_offset[0:0]
        word_unaligned = width_word & (byte_offset != Bits(2)(0))
        with Condition(is_mem & (half_unaligned | word_unaligned)):
            log("toy-memacc | misaligned addr=0x{:08x} width={}", exec_value, mem_width)
            assume(Bits(1)(0))

        upper_bit = 2 + max(word_addr_width - 1, 0)
        word_index = is_mem.select(rel_bits[2 : upper_bit], Bits(word_addr_width)(0))

        # # SRAM exposes its register-buffered dout port, but the first access may read the
        # # reset value before the read enable gets a chance to push the actual payload into
        # # that buffer.  Grab the word straight from the payload array so the very first
        # # load/store in a workload observes the initialized memory contents.
        word_value = dcache._payload[word_index].bitcast(Bits(32))
        # word_value = dcache.dout[0].bitcast(Bits(32)) # this would yield wrong result
        shift_amount = _byte_shift(byte_offset)
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

        store_mask = Bits(32)(0xFFFFFFFF)
        store_mask = width_half.select(Bits(32)(0x0000FFFF), store_mask)
        store_mask = width_byte.select(Bits(32)(0x000000FF), store_mask)
        mask_shifted = store_mask << shift_amount
        store_payload = (store_data & store_mask) << shift_amount
        new_word = (word_value & ~mask_shifted) | store_payload

        dcache.build(we=is_store, re=is_load, addr=word_index, wdata=new_word)

        result_value = is_load.select(load_value, exec_value)
        final_write = write_enable & ~is_store

        wb.async_called(rd=rd, value=result_value, enable=final_write, is_ebreak=is_ebreak)


def _byte_shift(offset: Value) -> Value:
    shift = Bits(5)(0)
    shift = (offset == Bits(2)(1)).select(Bits(5)(8), shift)
    shift = (offset == Bits(2)(2)).select(Bits(5)(16), shift)
    shift = (offset == Bits(2)(3)).select(Bits(5)(24), shift)
    return shift


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