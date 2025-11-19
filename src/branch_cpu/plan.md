BTB entry:

* `valid      : 1 bit`
* `tag        : 22 bits`  // `PC[31:10]`
* `target_pc  : 32 bits`  // *taken* target address
* `counter    : 2 bits`   // 2-bit predictor (00..11)

BTB:

* SRAM with 256 entries, indexed by `PC[9:2]`.
* **Index**: `PC[9:2]`
* **Tag**: `PC[31:10]`

Control:

* **Write enable** (`btb_we`):

  * `on` only when the **executor** decides there is a BTB miss or a mispredict.
  * `off` otherwise.
* **Read enable**: implicit `~btb_we`.
* **Addr**:

  * When reading (normal fetch): `btb_addr = pc[9:2]` (held in fetcher’s PC register).
  * When writing (in execute): `btb_addr = branch_pc[9:2]` (PC of the branch in execute).
  * Mux: `btb_addr = btb_we ? branch_pc[9:2] : pc[9:2]`.

* **Write only on:**

  1. BTB **miss** for this branch.
  2. BTB **hit but mispredicted**.
* When `btb_we = on`, **fetcher stalls** that cycle (does not advance PC or consume a BTB read).

Semantics of fields:

* On a **BTB hit** (valid & tag match at fetch):

  * `counter[1]` (MSB) decides **predict taken / not taken**.
  * If predict taken → use `target_pc` as predicted next PC.
  * If predict not taken → ignore `target_pc` and go to `PC + 4`.
* `target_pc` always stores **the taken branch target**, never `PC + 4`.

---

## Global PC update rule (fixes the “two writers” problem)

There is **one** PC register, updated **once per cycle** based on a priority rule:

1. If `branch_mispredict = 1` (from executor):

   * Next PC = `correct_pc` (actual next PC after the branch).
2. Else if fetch is stalled (`stall_fetch = 1`) due to:

   * Hazard, or
   * `btb_we = 1` (BTB write this cycle),
   * Next PC = current `PC` (hold).
3. Else if current fetched instruction was predicted taken (BTB hit + MSB=1):

   * Next PC = `target_pc` from BTB.
4. Else:

   * Next PC = `PC + 4`.

So:

* **Fetcher never directly “writes PC”**; it just provides “sequential” (PC+4) and "predicted target" candidates.
* **Executor never directly “writes PC”**; it only supplies `branch_mispredict` and `correct_pc`.
* The “two writes in the same cycle” issue disappears: there’s a single logical `next_pc` chosen by this priority.

---

## 1. Fetch stage (cycle N)

When the instruction at `PC` is fetched:

1. **BTB access (read)**

   * `btb_we` is normally `off` in fetch, so:

     * `btb_addr = PC[9:2]`.
     * Read BTB entry: `valid`, `tag`, `target_pc`, `counter`.

2. **Tag & hit check**

   * `btb_hit = valid && (tag == PC[31:10])`.

3. **Direction prediction**

   * If `btb_hit`:

     * `predict_taken = (counter[1] == 1)` (MSB).
   * Else:

     * `predict_taken = 0` (predict not taken on miss).

4. **Predicted next PC** (used by the global PC logic):

   * If `predict_taken`:

     * Candidate next PC = `target_pc` from BTB.
   * Else:

     * Candidate next PC = `PC + 4`.

5. **Pipeline sideband info**
   Along with the instruction, fetcher passes downstream:

   * `PC` (of this instruction).
   * `btb_hit`.
   * `counter` value.
   * `predict_taken`.
   * `target_pc` (if hit; value irrelevant if not hit).

This information travels with the instruction into decoder and then executor (or through a separate F→X sideband).

6. **Special case: BTB write in same cycle**

   * If the executor has `btb_we = on` in this cycle:

     * Fetcher treats this cycle as **stalled**:

       * It does **not** advance PC.
       * It does **not** latch a new BTB read for `pc[9:2]`.
     * The BTB port is owned by executor for the write.
   * If, in the same cycle, there is also a `branch_mispredict` asserted:

     * The PC is redirected to `correct_pc` anyway.
     * IF/ID will be flushed, so any instruction speculatively fetched with wrong PC is discarded.

---

## 2. Decode stage (cycle N+1)

In decode, you don’t change prediction state — you just:

* Decode the instruction as usual.
* Identify whether this instruction is a **branch** (conditional) or **jump** (unconditional).
* Forward the sideband info from fetch to execute:

  * `PC_D`
  * `is_branch_D` / `is_jump_D`
  * `btb_hit_D`
  * `counter_D`
  * `predict_taken_D`
  * `target_pc_D`

Nothing else BTB-specific happens here.

---

## 3. Execute stage (cycle N+2)

When the branch reaches execute:

### a. Calculate the branch target address

* Use `PC_X` (branch’s PC) and immediate/offset to compute:

  * `branch_target = PC_X + offset` (or whatever your ISA specifies).

### b. Determine if the branch is taken or not

* Evaluate the branch condition:

  * `actual_taken = (condition evaluates true / false)`.

### c. Compare prediction vs actual

From sideband data:

* `btb_hit_X`
* `predict_taken_X`
* `target_pc_X` (predicted target)

Compute:

* **Predicted next PC** for this branch:

  * If `predict_taken_X == 1`:

    * `predicted_branch_pc = target_pc_X`
  * Else:

    * `predicted_branch_pc = PC_X + 4`

* **Correct next PC** based on actual outcome:

  * If `actual_taken == 1`:

    * `correct_pc = branch_target`
  * Else:

    * `correct_pc = PC_X + 4`

* **Mispredict detection**:

  * Direction mispredict: `actual_taken != predict_taken_X`.
  * Or target mispredict: `actual_taken == 1` and `predict_taken_X == 1` but `branch_target != target_pc_X`.

If either is true:

* `branch_mispredict = 1`
* Provide `correct_pc` to the global PC update logic.

### d. Update the 2-bit saturating counter (conceptually)

You maintain a standard 2-bit saturating counter per entry, but **you only apply the update when you actually do a BTB write** (below). In words:

* If `actual_taken = 1`: “turn the counter more taken” (towards 3).
* If `actual_taken = 0`: “turn the counter more not taken” (towards 0).

On a **new entry** (BTB miss): set to weak-taken (10) or weak-not-taken (01).

### e. Decide when to write BTB and construct write data

You only write the BTB in two cases:

1. **BTB miss (no entry for this branch)**

   * Condition: `is_branch_X` (or jump) and `btb_hit_X == 0`.
   * Action:

     * `btb_we = on`.
     * Write addr: `branch_pc[9:2]` = `PC_X[9:2]`.
     * Write data:

       * `valid = 1`.
       * `tag = PC_X[31:10]`.
       * `target_pc = branch_target`.  // The taken target
       * `counter` initialized, e.g.:

         * `10` if `actual_taken = 1`.
         * `01` if `actual_taken = 0`.

2. **BTB hit + mispredict**

   * Condition: `btb_hit_X == 1` and `branch_mispredict == 1`.
   * Action:

     * `btb_we = on`.
     * Write addr: `PC_X[9:2]`.
     * Write data:

       * `valid = 1`.
       * `tag = PC_X[31:10]`.
       * `target_pc = branch_target` (refresh with correct target).
       * `counter` = “old counter updated via saturating rule”.

3. **BTB hit + correct prediction**

   * Condition: `btb_hit_X == 1` and `branch_mispredict == 0`.
   * Action:

     * **No BTB write** (`btb_we = off`).
     * Fetcher continues to read BTB normally next cycle.

**Interaction with fetcher**:

* Whenever `btb_we = on` (cases 1 or 2):

  * The BTB port is used for **write**, not read.
  * Fetcher is stalled for that cycle:

    * It holds PC.
    * It doesn’t fetch a new instruction.
* On a mispredict cycle, you do both:

  * Assert `branch_mispredict` (flush wrong-path instructions, redirect PC to `correct_pc`).
  * Assert `btb_we` if needed (miss or mispredict case).
  * The next cycle fetch restarts from `correct_pc` and BTB is free again.

### f. Set `branch_mispredict` and pipeline flush

* If prediction was correct:

  * `branch_mispredict = 0`.
  * Pipeline continues normally.
* If prediction was incorrect:

  * `branch_mispredict = 1`.
  * Global PC logic chooses `correct_pc`.
  * You flush the instructions in:

    * Fetch → Decoder pipeline (IF/ID).
    * Decoder → Executor pipeline (ID/EX).

    `flush` is simply consuming the FIFO entries without executing them.
  * Then `branch_mispredict` returns to 0 after that recovery cycle.