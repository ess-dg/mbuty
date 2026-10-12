# ESS VMM/Assister/Hybrid Remote Firmware Update

This repository programs the configuration flash of the Assister FPGA or a connected Hybrid FPGA through the ESS slow-control UDP interface.

The update uses bulk flash-command registers, page transfers, status polling, PROM verification, and optional FPGA warm reload.

## Repository layout

```text
firmware_remote_update_vmm/
├── vmm_firmware_update.py      Main firmware-update script
├── ess_firmware_update.lua     Wireshark dissector for ESS slow-control traffic
├── README.md
└── assister_flash/
    ├── __init__.py
    ├── axi_version.py          AxiVersion register access
    ├── micron_flash.py         Micron/SPI-NOR flash command handling
    └── register_axilite.py     ESS slow-control UDP / AXI-Lite register transport
```

## Supported targets

The same update script supports two targets.

```text
--hyb -1       Flash the Assister FPGA configuration PROM directly.
--hyb 0..5     Flash the selected Hybrid FPGA PROM through the Assister and HDMI bridge.
```

For Hybrid programming, the command is staged in the Assister flash-command registers and forwarded over the dedicated Hybrid flash slow-control path. The Hybrid executes the flash command locally through its AXI-Lite flash controller.

## Requirements

* Python 3
* Network access to the Assister ESS slow-control UDP interface
* A valid `.mcs` image for the selected target
* Correct ring, FEN/node, and Hybrid index

No external Python packages are required beyond the standard library.

## Basic usage

Just reading the firmware version of the assister:

```bash
python3 vmm_firmware_update.py \
    --ip 192.168.50.2 \
    --ring 0 \
    --fen 0 \
    --hyb -1 \
    --version-only
```

Program a the Hybrid flash:

```bash
python3 vmm_firmware_update.py \
    --ip 192.168.50.2 \
    --file hybrid_20260619.mcs \
    --ring 0 \
    --fen 0 \
    --hyb 0
```

Program the Assister PROM:

```bash
python3 vmm_firmware_update.py \
    --ip 192.168.50.2 \
    --file assister_nmx_20260619.mcs \
    --ring 0 \
    --fen 0 \
    --hyb -1
```

By default, the script reloads the FPGA from the programmed PROM image after a successful erase, program, and verify cycle.

## Command-line options

| Option                     |               Default | Description                                                    |
| -------------------------- | --------------------: | -------------------------------------------------------------- |
| `--ip`                     |        `192.168.50.2` | ESS slow-control IP address                                    |
| `--port`                   |               `65535` | ESS slow-control UDP port                                      |
| `--ring`                   |                   `0` | Logical ESS ring index                                         |
| `--fen`                    |                   `0` | FEN/node index                                                 |
| `--hyb`                    |                   `0` | Hybrid index `0..5`; use `-1` for the Assister                 |
| `--version-only`           |                   `0` | Just prints present version of firmware                        |
| `--file`                   | `hybrid_20260619.mcs` | Input MCS image                                                |
| `--stage-base-offset`      |          `0x00000f00` | Base address of flash stage register 0 before ring/FEN offsets |
| `--ring-stride`            |          `0x10000000` | Address stride between rings                                   |
| `--fen-stride`             |          `0x00800000` | Address stride between FENs/nodes                              |
| `--version-base`           |          `0x00000000` | AXI base address of `AxiVersion` behind the flash bridge       |
| `--prom-base`              |          `0x00010000` | AXI base address of the SPI-NOR flash controller               |
| `--reload-addr`            |          `0x00000000` | Flash byte address used for FPGA warm boot                     |
| `--timeout`                |               `1.0` s | UDP socket timeout                                             |
| `--retries`                |                   `3` | ESS packet retry count                                         |
| `--poll-timeout`           |               `1.0` s | Timeout for one flash-bridge command                           |
| `--poll-interval`          |               `10 µs` | Delay between bridge status polls                              |
| `--max-entries-per-packet` |                  `80` | Maximum ESS entries in one UDP packet                          |
| `--flash-timeout`          |              `10.0` s | Timeout while waiting for SPI-NOR ready status                 |

`--max-entries-per-packet 80` keeps one complete 67-word flash command frame in one ESS UDP packet.

## Flash command protocol

The host stages a command frame in the Flash command register block:

```text
register 0       opcode and target selection
register 1       AXI target address
register 2..65   64 data words
register 66      checksum / command completion
```

The bridge supports:

```text
0x01   WRITE32
0x02   READ32
0x10   WRITE_PAGE
0x11   READ_PAGE
0x7F   PING
```

A page contains 64 32-bit words, corresponding to one 256-byte SPI-NOR page.

For Hybrid updates, the upper byte of command register 0 selects the destination Hybrid. The lower byte is the flash opcode. `0x00` selects the local Assister flash controller.

## Update sequence

The script performs the following operations:

1. Read and print the currently running firmware version.
2. Parse the MCS image.
3. Erase all required PROM blocks.
4. Program the image in 256-byte pages.
5. Verify programmed PROM contents, unless `--no-verify` is used.
6. Issue FPGA warm reload, unless `--no-reload` is used.</br></br>

Step 7 Hybrid:</br> 
Read and print the firmware version after reboot. If the version reading gives an error, click warm-init in the assister slow control</br>
</br>
Step 7 Assister:</br>
Power cycle the assister, and do the ring bring-up again. Read and print the firmware version.


A successful reload is visible from the FPGA uptime resetting and, for a new image, the embedded firmware version changing.

Typical observed update durations:

```text
Hybrid image, about 2.2 MB:    about 45 s
Assister image:                about 200 s
```

Actual time depends on image size, flash erase time, flash page-program time, and the selected communication path.

## Errors and exceptions
**Hybrid**
* **Error during program or verify**<br>
Start the flash procedure again.<br>
DO NOT EVER POWER CYCLE THE HYBRID!
* **Error reading the new firmware version**<br>
Program and verify was successful, reload issued, but read back of new firmware version gives error. In this case the new version cannot be read back because the hybrid lost the link status. Do not re-flash the hybrid, but click warm-init in the assister slow control. If you have link status 4 again, read the version of the hybrid firmware. If the version is the expected version, all is good!

**Assister**
- **Error during program or verify**<br>
Start the flash procedure again.<br>
DO NOT EVER POWER CYCLE THE ASSISTER!
- **Ring bring up fails after update**<br>
Program and verify was successful, reload issued, and as expected the ring is broken. The next ring bring up fails. In this case power cycle the assister.

**General rule**<br>
Only power cycle after a successful update!


## Important notes

* Use a Hybrid `.mcs` image only for a Hybrid target and an Assister `.mcs` image only for `--hyb -1`.
* Do not interrupt power during erase or programming.
* A successful PROM verify does not itself prove the FPGA has booted the new image. Check the post-reload uptime and firmware version.
* For Hybrid programming, normal Hybrid configuration and flash transfer use separate slow-control paths in the Assister firmware. This avoids mixing short configuration writes with variable-length flash transactions.

## Flash devices

Both targets use 128 Mbit / 16 MB SPI-NOR configuration flash devices. The Hybrid uses a Spansion/Cypress/Infineon S25FL128L-family flash device, whereas the Assister uses a Micron/Numonyx N25Q128A-family flash device.

```
Hybrid:   S25FL128L   — JEDEC ID 0x01 0x60 0x18
Assister: N25Q128A    — JEDEC ID 0x20 0xBA 0x18
```

## Wireshark support

`ess_firmware_update.lua` can be used as a Wireshark Lua dissector for inspecting the ESS slow-control UDP traffic generated during firmware update.

This is useful for checking:

```text
- command register writes
- packet retries
- page transfer contents
- status polling
- readback traffic
```

## Recommended workflow

Before deploying a new image:

```text
1. Build the FPGA firmware and generate the MCS file.
2. Give the build a unique firmware version or build identifier.
3. Program one board.
4. Confirm erase, write, verify, reload, uptime reset, and new version.
5. Test normal detector control after reload.
6. Commit/tag the firmware, MCS image source revision, and update script together.
```
