This directory contains the production-ready implementation of the RV32I CPU.

# Naive CPU

See [naive_cpu](./naive_cpu). This directory contains the implementation of the naive RV32I CPU. No bypassing / no branch prediction.

# Bypass CPU

See [bypass_cpu](./bypass_cpu). This directory contains the implementation of the bypass RV32I CPU. It includes fully bypassing logic from EX/MEM to EX stage. Some modules are reused from naive_cpu.

# Branch CPU

See [branch_cpu](./branch_cpu). This directory contains the implementation of the branch RV32I CPU. It includes branch instructions support on top of the bypass CPU. Branch prediction logic is implemented using the 2-bit saturating counter and a Branch Target Buffer (BTB). Some modules are reused from bypass_cpu.