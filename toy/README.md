To fully understand how Assassyn works, I plan to write several toy projects.

- [x] Add
- [ ] Memory
- [ ] Branch
- [ ] Select1Hot

# Add

This is the simplest CPU that only support `add` and `addi` instructions. See [add/main.py](add/main.py) for more details.

# Memory

This CPU supports load and store instructions. It is harder than the `Add` CPU because it needs to RAW hazard detection and memory access delay handling.