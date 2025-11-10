'''
This is a toy CPU only support add and addi instructions.
'''

from assassyn.frontend import *
from assassyn.backend import *
from assassyn import utils

class Fetcher(Module): 
    def __init__(self):
        super().__init__(
            ports={}
        )
        self.name = "Fetcher"
    
    @module.combinational
    def build(self):
        pc = RegArray(Bits(32), 1)
        return pc

class Decoder(Module): 
    def __init__(self):
        super().__init__(
            ports={
                "instr": Port(Bits(32))
            }
        )
        self.name = "Decoder"
    
    @module.combinational
    def build(self):
        instr = self.pop_all_ports(False)
        pass


class Executor(Module): 
    def __init__(self):
        super().__init__(
            ports={}
        )
        self.name = "Executor"
    
    @module.combinational
    def build(self):
        pass

