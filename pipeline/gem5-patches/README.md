# gem5 SE-mode patches for agent-based modeling

All patches and the LD_PRELOAD shim are maintained in the
[gem5-BeSA](https://github.com/SAL-Research/gem5-BeSA) fork. The patches
are applied directly in the gem5-BeSA source tree, and the shim lives at `gem5-patches/` in that repo with a Makefile.

`setup_env.sh` clones gem5-BeSA and runs `util/abm/build_gem5.sh`, which
builds both `gem5.opt` and `gem5_system_shim.so` automatically.

## What the fork fixes

### 1. Syscall return-buffer overflow

`getsockname`, `accept`, and `recvfrom` copied `sizeof(struct sockaddr)`
bytes back to the guest regardless of the actual address size. For
`AF_NETLINK` sockets (12-byte `sockaddr_nl`), this overwrote adjacent
stack data, causing stack smashing at ~77-80M instructions.

Fix: use `sockaddr_storage` and copy `min(actual_len, guest_buffer_len)`.

### 2. Zeroed AT_RANDOM auxv entry

gem5 SE mode allocated stack space for `AT_RANDOM` but wrote no bytes.
Glibc's stack canary was zero-initialized, triggering `__stack_chk_fail`.

Fix: write 16 random bytes during process initialization.

### 3. Missing syscalls

`vfork`, `epoll_*`, and `timerfd_*` were unimplemented. `vfork` maps to
the existing `clone` emulation.

### 4. Multi-core interrupt wiring

Only core 0's interrupt controller was connected; other cores dropped
interrupts silently.

### 5. LD_PRELOAD system() shim

BioDynaMo calls `system("mkdir -p ...")` which requires `fork()+exec()`,
unsupported in gem5 SE mode. The shim intercepts `system()` and handles
`mkdir -p` with direct `mkdir()` syscalls.

Source: `gem5-BeSA/gem5-patches/03-biodynamo-system-shim.c`
Built by: `gem5-BeSA/util/abm/build_gem5.sh`
Loaded via: `LD_PRELOAD` in all gem5 configs (see `configs/gem5_common.py`)
