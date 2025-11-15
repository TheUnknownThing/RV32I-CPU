To fully understand how Assassyn works, I plan to write several toy projects.

- [x] Add
- [x] Select1Hot
- [ ] Memory
- [ ] Branch

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