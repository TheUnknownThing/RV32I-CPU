To fully understand how Assassyn works, I plan to write several toy projects.

- [x] Add
- [x] Select1Hot
- [ ] Memory
- [ ] Branch

# Note

When handling RAW Hazard, Assassyn would store the `async_called` in a FIFO. When simulating with Rust, the FIFO do not have limits (so examples like toy/add/tests/programs/chain_long would pass, which requires 7 slot FIFO, but I only give it 2 slots), but in verilog synthesis, the FIFO depth is limited. In the CPU written here as toy examples, I do not take care of the FIFO depth limit (I would need to add logic to handle FIFO full conditions in real RV32I CPU).

# Add

This is the simplest CPU that only support `add` and `addi` instructions. See [add/main.py](add/main.py) for more details. It is tested.

Key points here:

- The CPU implements a simple 4-stage pipeline.
- It has test framework.
- The RAW Hazard is detected and handled using the FIFO before the exec stage.

# Select1Hot

Now the `exec` stage supports more instructions and uses a one-hot selection mechanism for choosing the value.

It supports all the arithmetic instructions of RV32I, i.e., add, sub, sll, srl, sra, and, or, xor, slt, sltu, and their immediate variants.

Key points here:

- op_select initialization in decode.py
- The exec stage uses a select1hot mechanism to choose the ALU operation.

# Memory

Implement all the memory instructions of RV32I, i.e., lb, lh, lw, lbu, lhu, sb, sh, sw.