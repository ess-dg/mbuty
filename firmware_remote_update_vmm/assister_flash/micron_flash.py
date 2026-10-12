#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################


from __future__ import annotations

import math
import time
from pathlib import Path


###############################################################################
###############################################################################

class McsException(Exception):
    pass


class McsReader:
    def __init__(self):
        self.entry: list[tuple[int, int]] = []
        self.startAddr = 0
        self.endAddr = 0
        self.size = 0

    def open(self, filename: str | Path) -> None:
        upper_addr = 0
        data: dict[int, int] = {}

        with open(filename, "r", encoding="ascii") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if not line.startswith(":"):
                    raise McsException(f"Invalid MCS line: {line}")

                count = int(line[1:3], 16)
                addr = int(line[3:7], 16)
                rectype = int(line[7:9], 16)
                payload = bytes.fromhex(line[9:9 + count * 2])

                if rectype == 0x00:
                    base = upper_addr + addr
                    for i, b in enumerate(payload):
                        data[base + i] = b
                elif rectype == 0x01:
                    break
                elif rectype == 0x04:
                    if count != 2:
                        raise McsException(f"Bad extended linear address record: {line}")
                    upper_addr = int.from_bytes(payload, "big") << 16

        if not data:
            raise McsException(f"No data records found in {filename}")

        self.entry = sorted(data.items())
        self.startAddr = self.entry[0][0]
        self.endAddr = self.entry[-1][0]
        self.size = len(self.entry)


class AxiMicronN25Q:
    ADDR_REG_OFF = 0x08
    CMD_REG_OFF  = 0x0C
    DATA_REG_OFF = 0x200

    READ_MASK  = 0x00000000
    WRITE_MASK = 0x80000000

    STATUS_REG_RD_CMD = 0x05 << 16
    FLAG_STATUS_REG   = 0x70 << 16
    DEV_ID_RD_CMD     = 0x9F << 16
    WRITE_ENABLE_CMD  = 0x06 << 16
    ADDR_EXIT_CMD     = 0xE9 << 16
    ERASE_3BYTE_CMD   = 0xD8 << 16
    READ_3BYTE_CMD    = 0x03 << 16
    WRITE_3BYTE_CMD   = 0x02 << 16
    RESET_ENABLE_CMD  = 0x66 << 16
    RESET_MEMORY_CMD  = 0x99 << 16

    FLAG_STATUS_RDY = 0x80

    PAGE_SIZE = 256
    PAGE_WORDS = 64
    ERASE_SIZE = 0x10000

    # Keep small but nonzero by default. Try 0.0 only if the PC/FPGA link remains stable.
    READY_POLL_INTERVAL_S = 0.00001

    def __init__(self, bus, base_addr: int = 0, timeout_s: float = 10.0):
        self.bus = bus
        self.base_addr = int(base_addr)
        self.timeout_s = float(timeout_s)
        self.mcs = McsReader()
        self.start_time = 0.0

    def _addr(self, offset: int) -> int:
        return (self.base_addr + int(offset)) & 0xFFFFFFFF

    def _write32(self, offset: int, value: int) -> None:
        self.bus.write_reg(self._addr(offset), value & 0xFFFFFFFF)

    def _read32(self, offset: int) -> int:
        return self.bus.read_reg(self._addr(offset)) & 0xFFFFFFFF

    def _issue_flash_cmd(self, value: int) -> None:
        """
        Issue one SURF flash command.

        No wait_ready() here. Callers place waits explicitly to avoid
        double-polling in tight erase/program/read loops.
        """
        value &= 0xFFFFFFFF

        if value & self.WRITE_MASK:
            self._write32(self.CMD_REG_OFF, self.WRITE_MASK | self.WRITE_ENABLE_CMD)

        self._write32(self.CMD_REG_OFF, value)

    def _page_program_opcode(self) -> int:
        return self.WRITE_MASK | self.WRITE_3BYTE_CMD | 0x103

    def _page_read_opcode(self) -> int:
        return self.READ_MASK | self.READ_3BYTE_CMD | 0x103

    def _erase_opcode(self) -> int:
        return self.WRITE_MASK | self.ERASE_3BYTE_CMD | 0x3

    def _status_opcode(self) -> int:
        return self.READ_MASK | self.STATUS_REG_RD_CMD | 0x1

    def _flag_status_opcode(self) -> int:
        return self.READ_MASK | self.FLAG_STATUS_REG | 0x1

    def _id_opcode(self, index: int) -> int:
        if index < 0:
            raise ValueError(f"ID byte index must be >= 0, got {index}")
        return self.READ_MASK | self.DEV_ID_RD_CMD | (index + 1)

    def wait_ready(self) -> None:
        deadline = time.time() + self.timeout_s
        last = 0

        while True:
            self._issue_flash_cmd(self._flag_status_opcode())
            last = self._read32(self.CMD_REG_OFF) & 0xFF

            if last & self.FLAG_STATUS_RDY:
                return

            if time.time() > deadline:
                raise TimeoutError(
                    f"Flash not ready after {self.timeout_s} s, flag status=0x{last:02X}"
                )

            if self.READY_POLL_INTERVAL_S > 0:
                time.sleep(self.READY_POLL_INTERVAL_S)
            else:
                time.sleep(0)

    def reset_flash(self) -> None:
        self._issue_flash_cmd(self.WRITE_MASK | self.RESET_ENABLE_CMD)
        time.sleep(self.READY_POLL_INTERVAL_S)

        self._issue_flash_cmd(self.WRITE_MASK | self.RESET_MEMORY_CMD)
        time.sleep(self.READY_POLL_INTERVAL_S)

        self.wait_ready()

        self._issue_flash_cmd(self.WRITE_MASK | self.ADDR_EXIT_CMD)
        self.wait_ready()

    def erase_block(self, address: int) -> None:
        # Wait for previous erase/program before changing address/command.
        self.wait_ready()
        self._write32(self.ADDR_REG_OFF, address)
        self._issue_flash_cmd(self._erase_opcode())
        # No bottom wait: next erase_block() or phase-end wait handles it.

    def program_page(self, address: int, words: list[int]) -> None:
        if len(words) != self.PAGE_WORDS:
            raise ValueError(f"program_page needs {self.PAGE_WORDS} words, got {len(words)}")

        # Wait for previous program before touching page RAM/address/command.
        self.wait_ready()
        self.bus.write_page(self._addr(self.DATA_REG_OFF), words)
        self._write32(self.ADDR_REG_OFF, address)
        self._issue_flash_cmd(self._page_program_opcode())
        # No bottom wait: next program_page() or phase-end wait handles it.

    def read_page(self, address: int) -> list[int]:
        # verify_prom() and phase boundaries already ensure previous operation is done.
        # Do not add a redundant top wait per page; wait only after issuing the read,
        # because the page RAM is consumed immediately.
        self._write32(self.ADDR_REG_OFF, address)
        self._issue_flash_cmd(self._page_read_opcode())
        self.wait_ready()
        return self.bus.read_page(self._addr(self.DATA_REG_OFF))

    def read_status(self) -> int:
        self.wait_ready()
        self._issue_flash_cmd(self._status_opcode())
        return self._read32(self.CMD_REG_OFF) & 0xFF

    def read_flag_status(self) -> int:
        self._issue_flash_cmd(self._flag_status_opcode())
        return self._read32(self.CMD_REG_OFF) & 0xFF

    def read_id_byte(self, index: int) -> int:
        self.wait_ready()
        self._issue_flash_cmd(self._id_opcode(index))
        return self._read32(self.CMD_REG_OFF) & 0xFF

    def print_info(self) -> None:
        print(f"PROM Manufacturer ID Code  = 0x{self.read_id_byte(0):02X}")
        print(f"PROM Manufacturer Type     = 0x{self.read_id_byte(1):02X}")
        print(f"PROM Manufacturer Capacity = 0x{self.read_id_byte(2):02X}")
        print(f"PROM Status Register       = 0x{self.read_status():02X}")
        print(f"PROM Flag Status Register  = 0x{self.read_flag_status():02X}")

    @staticmethod
    def _words_from_bytes(page_bytes: list[int]) -> list[int]:
        if len(page_bytes) != 256:
            raise ValueError("page_bytes must contain exactly 256 bytes")

        return [
            ((page_bytes[i + 0] & 0xFF) << 24)
            | ((page_bytes[i + 1] & 0xFF) << 16)
            | ((page_bytes[i + 2] & 0xFF) << 8)
            | ((page_bytes[i + 3] & 0xFF) << 0)
            for i in range(0, 256, 4)
        ]

    def erase_prom(self) -> None:
        first = self.mcs.startAddr & ~(self.ERASE_SIZE - 1)
        last = self.mcs.endAddr
        n_blocks = math.ceil((last - first + 1) / self.ERASE_SIZE)

        print(f"Erasing PROM: {n_blocks} block(s)")

        # One initial wait is not needed because erase_block waits at the top.
        for i in range(n_blocks):
            addr = first + i * self.ERASE_SIZE

            if i == 0 or (i + 1) % 10 == 0 or i + 1 == n_blocks:
                elapsed = int(time.time() - self.start_time)
                print(f"  erase {i + 1}/{n_blocks}: addr=0x{addr:08X} - {elapsed} s")

            self.erase_block(addr)

        # Wait for last erase before programming.
        self.wait_ready()

    def write_prom(self) -> None:
        print(f"Writing PROM: {self.mcs.size} byte(s)")

        page = [0xFF] * self.PAGE_SIZE
        current_page_base = None
        pages_written = 0

        # No initial wait needed because program_page waits at the top.
        for addr, byte in self.mcs.entry:
            page_base = addr & ~(self.PAGE_SIZE - 1)
            page_off = addr & (self.PAGE_SIZE - 1)

            if current_page_base is None:
                current_page_base = page_base

            if page_base != current_page_base:
                if not all(b == 0xFF for b in page):
                    self.program_page(current_page_base, self._words_from_bytes(page))
                    pages_written += 1

                    if pages_written == 1 or pages_written % 1024 == 0:
                        elapsed = int(time.time() - self.start_time)
                        print(f"  write page {pages_written}: addr=0x{current_page_base:08X} - {elapsed} s")

                page = [0xFF] * self.PAGE_SIZE
                current_page_base = page_base

            page[page_off] = byte & 0xFF

        if current_page_base is not None and not all(b == 0xFF for b in page):
            self.program_page(current_page_base, self._words_from_bytes(page))
            pages_written += 1

        # Wait for last program before verify/reload.
        self.wait_ready()

        elapsed = int(time.time() - self.start_time)
        print(f"  write done: {pages_written} page(s) - {elapsed} s")

    def verify_prom(self) -> None:
        # One phase-boundary wait is enough. read_page() waits only after issuing read.
        self.wait_ready()
        print(f"Verifying PROM: {self.mcs.size} byte(s)")

        current_page_base = None
        page_words: list[int] | None = None

        for idx, (addr, expected) in enumerate(self.mcs.entry):
            page_base = addr & ~(self.PAGE_SIZE - 1)
            page_off = addr & (self.PAGE_SIZE - 1)

            if page_base != current_page_base:
                page_words = self.read_page(page_base)
                current_page_base = page_base

                if idx == 0 or (idx & 0xFFFFF) == 0:
                    elapsed = int(time.time() - self.start_time)
                    print(f"  verify addr=0x{addr:08X} - {elapsed} s")

            assert page_words is not None
            word = page_words[page_off // 4]
            actual = (word >> (8 * (3 - (page_off & 3)))) & 0xFF

            if actual != expected:
                raise McsException(
                    f"Verify failed at addr=0x{addr:08X}: "
                    f"MCS=0x{expected:02X}, PROM=0x{actual:02X}"
                )

        elapsed = int(time.time() - self.start_time)
        print(f"  verify done - {elapsed} s")

    def load_mcs_file(self, filename: str | Path, verify: bool = True) -> None:
        filename = str(Path(filename))
        print(f"LoadMcsFile: {filename}")
        self.start_time = time.time()

        self.reset_flash()
        self.print_info()

        self.mcs.open(filename)
        print(
            f"MCS address range: 0x{self.mcs.startAddr:08X}..0x{self.mcs.endAddr:08X}, "
            f"{self.mcs.size} byte(s)"
        )

        self.erase_prom()
        self.write_prom()

        if verify:
            self.verify_prom()

class AxiCypressS25FL(AxiMicronN25Q):
    """
    Cypress/Infineon S25FL-style PROM using the same SURF AxiMicronN25QCore
    firmware interface.

    For S25FL128, 3-byte addressing is enough because it is 16 MiB.
    """

    # Same standard SPI commands for 3-byte mode
    ERASE_3BYTE_CMD = 0xD8 << 16   # 64 kB sector erase
    READ_3BYTE_CMD  = 0x03 << 16   # read data
    WRITE_3BYTE_CMD = 0x02 << 16   # page program

    # S25FL status register: command 0x05, WIP bit0
    FLAG_STATUS_REG = 0x05 << 16
    FLAG_STATUS_RDY = 0x01         # actually WIP/busy bit, ready when 0

    # Cypress reset sequence from SURF example
    MODE_BIT_RESET_CMD = 0xFF << 16
    SOFTWARE_RESET_CMD = 0xF0 << 16

    def _flag_status_opcode(self) -> int:
        # Read one byte from status register 1
        return self.READ_MASK | self.FLAG_STATUS_REG | 0x1

    def wait_ready(self) -> None:
        deadline = time.time() + self.timeout_s
        last = 0

        while True:
            self._issue_flash_cmd(self._flag_status_opcode())
            last = self._read32(self.CMD_REG_OFF) & 0xFF

            # S25FL: status bit0 = WIP. Ready when WIP == 0.
            if (last & self.FLAG_STATUS_RDY) == 0:
                return

            if time.time() > deadline:
                raise TimeoutError(
                    f"S25FL flash not ready after {self.timeout_s} s, status=0x{last:02X}"
                )

            if self.READY_POLL_INTERVAL_S > 0:
                time.sleep(self.READY_POLL_INTERVAL_S)
            else:
                time.sleep(0)

    def reset_flash(self) -> None:
        # Mode bit reset
        self._issue_flash_cmd(self.WRITE_MASK | self.MODE_BIT_RESET_CMD)
        time.sleep(0.001)

        # Software reset
        self._issue_flash_cmd(self.WRITE_MASK | self.SOFTWARE_RESET_CMD)
        time.sleep(0.001)

        self.wait_ready()
