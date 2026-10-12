#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################

from __future__ import annotations

import socket

###############################################################################
###############################################################################

class AxiVersionLite:
    
	FW_VERSION_OFF = 0x000
	SCRATCHPAD_OFF = 0x004
	UPTIME_OFF = 0x008

	HALT_RELOAD_OFF = 0x100
	FPGA_RELOAD_OFF = 0x104
	FPGA_ADDR_OFF = 0x108
	USER_RESET_OFF = 0x10C

	GIT_HASH_OFF = 0x600
	DEVICE_DNA_OFF = 0x700

	def __init__(self, bus, base:int, hyb: int=-1):
		self.bus = bus
		self.base = int(base)
		self.hyb = hyb

	def _wr(self, off: int, value: int) -> None:
		self.bus.write_reg(self.base + off, value)

	def _wr_no_reply(self, off: int, value: int) -> None:
		self.bus.write_reg_no_reply(self.base + off, value)
 
	def _rd(self, off: int) -> int:
		return self.bus.read_reg(self.base + off)

	def print_status(self) -> None:
		try:
			fw = self._rd(self.FW_VERSION_OFF)
			up = self._rd(self.UPTIME_OFF)
			git_hash = self._rd(self.GIT_HASH_OFF)
			device_dna = self._rd(self.DEVICE_DNA_OFF)

			print(f"FW Version : 0x{fw:08X}")
			print(f"Up Time    : {up} s")
			print(f"Git Hash   : 0x{git_hash:08X}")

			if self.hyb == -1:
				print(f"Device DNA : 0x{device_dna:08X}")
			else:
				if device_dna == 0x00000000:
					tag = "Standard Hit based firmware"
				else:
					raw = device_dna.to_bytes(4, byteorder="big")
					tag = raw.decode("ascii", errors="replace").strip()
				print(f"Firmware Type : {tag}")

		except Exception as exc:
			print(f"Could not read full AxiVersion status: {exc}")

	def fpga_reload(self, image_byte_addr: int) -> None:
		boot_addr = (int(image_byte_addr) >> 8) & 0xFFFFFFFF
		self._wr(self.FPGA_ADDR_OFF, boot_addr)
		try:
			if self.hyb >= 0 and self.hyb <= 5:
				self._wr(self.FPGA_RELOAD_OFF, 1)
		except Exception:
			# Expected: after reload the FPGA/ESS ring may stop answering immediately.
			pass
