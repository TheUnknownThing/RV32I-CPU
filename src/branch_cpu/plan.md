Implement branch prediction in the CPU by adding a 2-bit saturating counter to the BTB entries. Update the counter based on whether branches are taken or not, and use it to predict future branch behavior.

BTB entry: 
        valid        : 1 bit
        tag          : 22 bits    // PC[31:10]
        target_pc    : 32 bits
        counter      : 2 bits     // 2-bit predictor

BTB is a SRAM, with 256 entries (indexed by PC[9:2]).

Write enable: `on` state set by executor; `off` state set by fetcher.
Read enable: ~we
Addr: btb_addr_reg, when reading, is pc[9:2]; when writing, is the branch instruction's address[9:2]. = write_enable.select(btb_write_reg[9:2], btb_read_reg[9:2])
Write data: constructed by executor.

When executing a branch instruction:

1. Fetch the instr as well as the BTB entry (because the addr is synchronized with pc[9:2] when reading BTB).

    Check if the BTB entry is valid and the tag matches PC[31:10]. If not, predict anything else (just 0x00000 as not taken).

2. Next cycle go to decoder stage, nothing special.

3. Next cycle go to executor stage:

    a. Calculate the branch target address.

    b. Determine if the branch is taken or not.

    c. Update the 2-bit saturating counter based on whether the branch was taken or not.

    d. Construct the BTB write data:
        - valid = 1
        - tag = PC[31:10]
        - target_pc = branch target address if taken, else PC + 4
        - counter = updated 2-bit counter

    e. Set the BTB write enable signal to `on`.

    but I have 2 question here:

    (1) Note that the BTB addr is always updated by `fetcher` stage, and it is now synchronized with PC[9:2]. If I change it to the branch instruction's addr[9:2], it causes 2 writes to the same reg in the same cycle. this is bad. How to solve this?

    (2) Even if the branch pred is correct, I still need to update the BTB entry because the 2-bit counter may change. So I have to set the write enable signal to `on`. In this way, the `fetcher` wouldn't be able to read the BTB in the next cycle. 


4. If the branch prediction was correct, continue as normal. 

    If the branch prediction was incorrect, set the `branch_mispredict` signal, this would let `executor` and `decoder` to consume 1 cycle doing nothing, then set branch_mispredict to 0 again to continue normal execution.