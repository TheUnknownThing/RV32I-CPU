from assassyn.frontend import *

class WriteBack(Module):
    """Writes results into the architectural register file."""

    def __init__(self):
        super().__init__(
            ports={
                "rd": Port(Bits(5)),
                "value": Port(Bits(32)),
                "enable": Port(Bits(1)),
                "is_ebreak": Port(Bits(1)),
            }
        )
        self.name = "WriteBack"

    @module.combinational
    def build(self, reg_file: Array, reg_avail: Array):
        rd, value, enable, is_ebreak = self.pop_all_ports(False)
        reg_avail[rd] = Bits(1)(1)

        with Condition(enable):
            reg_file[rd] = value
            log("toy-wb     | x{:02} <= 0x{:08x}", rd, value)

        with Condition(is_ebreak):
            log("toy-wb     | ebreak encountered")
            finish()

