#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################

from __future__ import annotations


import socket
import struct
import time
from dataclasses import dataclass
from typing import Sequence

###############################################################################
###############################################################################

# ESS slow-control packet protocol, matching the working ESS helper script:
#
#   WRITE request:
#	  WRITE_HEAD, then N x (addr, data)
#	  length = 4 + N*8
#
#   WRITE reply:
#	  WRITE_RESP, then N x (addr, data, status)
#	  length = 4 + N*12
#
#   READ request:
#	  READ_HEAD, then N x (addr)
#	  length = 4 + N*4
#
#   READ reply:
#	  READ_RESP, then N x (addr, data, status)
#	  length = 4 + N*12
#
# The 0xE55Cxxxx word is a packet command/header, not repeated per entry.

###############################################################################
###############################################################################


PROTOCOL_VERSION = "ESS_HEADER_COMPACT_ENTRIES_V1"

WRITE_HEAD = 0xE55C0003
READ_HEAD  = 0xE55C0001
WRITE_RESP = 0xE55C0004
READ_RESP  = 0xE55C0002

WRITE_ENTRY_FMT = ">II"	 # addr, data
READ_ENTRY_FMT  = ">I"	  # addr
REPLY_ENTRY_FMT = ">III"	# addr, data, status
REPLY_ENTRY_LEN = struct.calcsize(REPLY_ENTRY_FMT)

# Bridge opcodes. Must match register_axi_bridge.vhd.
OP8_WRITE32	   = 0x00000001
OP8_READ32	   = 0x00000002
OP8_WRITE_PAGE = 0x00000010
OP8_READ_PAGE  = 0x00000011
OP8_PING	       = 0x0000007F


PAGE_WORDS = 64
FRAME_WORDS = 67
CHECKSUM_INDEX = 66

DONE_PREFIX = 0x8
STATUS_OK = 0x0

REGBANK_INFO_REGS = (
	("REGBANK_VERSION", 0x00000000),
	("PHASH",           0x00000004),
	("GIT_HASH2",       0x00000008),
	("GIT_HASH1",       0x0000000C),
	("GIT_HASH0",       0x00000010),
	("TYPE1_USR",       0x00000014),
	("TYPE2_USR",       0x00000018),
	("VERS_USR",        0x0000001C),
)


class SlowControlStatusError(RuntimeError):
	pass


@dataclass(frozen=True)
class SlowControlReplyEntry:
	addr: int
	data: int
	status: int


class RegisterAxiLite:
	def __init__(
		self,
		ip: str,
		port: int,
		*,
		ring: int = 0,
		fen: int = 0,
		hyb: int = 0,
		base_offset: int = 0x00000F20,
		ring_stride: int = 0x10000000,
		fen_stride: int = 0x00800000,
		timeout: float = 1.0,
		retries: int = 3,
		poll_timeout: float = 1.0,
		poll_interval: float = 0.001,
		max_entries_per_packet: int = 80,
	):
		self.server = (ip, int(port))
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
		self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4 * 1024 * 1024)
		self.sock.settimeout(float(timeout))

		self.retries = int(retries)
		if self.retries < 1:
			raise ValueError(f"retries must be >= 1, got {self.retries}")

		self.poll_timeout = float(poll_timeout)
		self.poll_interval = float(poll_interval)
		self.max_entries_per_packet = int(max_entries_per_packet)
		if self.max_entries_per_packet < 1:
			raise ValueError("max_entries_per_packet must be >= 1")

		self.stage_base = self._u32(
			int(base_offset)
			+ int(ring) * int(ring_stride)
			+ int(fen) * int(fen_stride)
		)
		self.ring_fen_offset = self._u32(
			int(ring) * int(ring_stride)
			+ int(fen) * int(fen_stride)
		)
		self.hyb = int(hyb)

		self.op_prefix = self._u32(self._target_prefix(self.hyb))
		self.op_write32	= self._u32(self.op_prefix | OP8_WRITE32)
		self.op_read32	 = self._u32(self.op_prefix | OP8_READ32)
		self.op_write_page = self._u32(self.op_prefix | OP8_WRITE_PAGE)
		self.op_read_page  = self._u32(self.op_prefix | OP8_READ_PAGE)
		self.op_ping	   = self._u32(self.op_prefix | OP8_PING)

	def debug_ping_write_packet_hex(self) -> tuple[int, str]:
		fields = self.command_fields(self.op_ping, 0, [0])
		indices = (0, 1, 2, CHECKSUM_INDEX)
		packet = self._make_write_packet([(self.stage_addr(i), fields[i]) for i in indices])
		return len(packet), packet.hex(" ")

	def close(self) -> None:
		self.sock.close()

	def __enter__(self) -> "RegisterAxiLite":
		return self

	def __exit__(self, exc_type, exc, tb) -> None:
		self.close()

	@staticmethod
	def _u32(value: int) -> int:
		return int(value) & 0xFFFFFFFF

	@staticmethod
	def _check_aligned(addr: int) -> None:
		if addr & 0x3:
			raise ValueError(f"Address is not 32-bit aligned: 0x{addr:08X}")

	@staticmethod
	def _rol32(value: int, shift: int) -> int:
		value &= 0xFFFFFFFF
		shift &= 31
		if shift == 0:
			return value
		return ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF

	def _target_prefix(self, hyb: int) -> int:
		if hyb == -1:
			return 0x00000000
		if 0 <= hyb <= 5:
			return (1 << hyb) << 24
		raise ValueError("hyb must be -1 for assister or 0..5 for hybrids")

	def stage_addr(self, index: int) -> int:
		index = int(index)
		if not 0 <= index < FRAME_WORDS:
			raise ValueError(f"staging index out of range: {index}")
		return self._u32(self.stage_base + 4 * index)

	def stage_addrs(self) -> list[int]:
		return [self.stage_addr(i) for i in range(FRAME_WORDS)]

	def checksum(self, opcode: int, addr: int, data_words: Sequence[int]) -> int:
		words = [self._u32(w) for w in data_words]
		if len(words) != PAGE_WORDS:
			raise ValueError(f"checksum requires {PAGE_WORDS} data words, got {len(words)}")

		csum = 0xA5A55A5A
		csum ^= self._rol32(self._u32(opcode & 0xFF), 1)
		csum ^= self._rol32(self._u32(addr), 7)

		for i, word in enumerate(words):
			csum ^= self._rol32(word, (i % 31) + 1)
			csum &= 0xFFFFFFFF

		return csum

	def command_fields(
		self,
		opcode: int,
		addr: int = 0,
		data_words: Sequence[int] | None = None,
	) -> list[int]:
		payload = [self._u32(w) for w in (data_words or [])]
		if len(payload) > PAGE_WORDS:
			raise ValueError(f"payload too long: {len(payload)} > {PAGE_WORDS}")
		payload.extend([0] * (PAGE_WORDS - len(payload)))

		fields = [self._u32(opcode), self._u32(addr)]
		fields.extend(payload)
		fields.append(self.checksum(opcode, addr, payload))

		if len(fields) != FRAME_WORDS:
			raise AssertionError(f"internal frame length error: {len(fields)}")
		return fields

	def _make_write_packet(self, entries: Sequence[tuple[int, int]]) -> bytes:
		packet = bytearray(struct.pack(">I", WRITE_HEAD))
		for addr, value in entries:
			addr = self._u32(addr)
			self._check_aligned(addr)
			packet += struct.pack(WRITE_ENTRY_FMT, addr, self._u32(value))
		return bytes(packet)

	def _make_read_packet(self, addrs: Sequence[int]) -> bytes:
		packet = bytearray(struct.pack(">I", READ_HEAD))
		for addr in addrs:
			addr = self._u32(addr)
			self._check_aligned(addr)
			packet += struct.pack(READ_ENTRY_FMT, addr)
		return bytes(packet)

	@staticmethod
	def _parse_reply(packet: bytes, expected_header: int) -> list[SlowControlReplyEntry]:
		if len(packet) < 4:
			raise RuntimeError(f"Reply too short: {len(packet)} byte(s)")

		header = struct.unpack(">I", packet[:4])[0]
		if header != expected_header:
			raise RuntimeError(
				f"Wrong reply header: got 0x{header:08X}, expected 0x{expected_header:08X}"
			)

		payload = packet[4:]
		if len(payload) == 0 or len(payload) % REPLY_ENTRY_LEN != 0:
			raise RuntimeError(
				f"Malformed reply payload length {len(payload)} byte(s), expected N*{REPLY_ENTRY_LEN}"
			)

		entries: list[SlowControlReplyEntry] = []
		for offset in range(0, len(payload), REPLY_ENTRY_LEN):
			addr, data, status = struct.unpack(
				REPLY_ENTRY_FMT,
				payload[offset:offset + REPLY_ENTRY_LEN],
			)
			entries.append(SlowControlReplyEntry(addr, data, status))
		return entries

	def _send_recv(
		self,
		packet: bytes,
		*,
		expected_header: int,
		expected_addrs: Sequence[int],
		expected_write_data: Sequence[int] | None,
		label: str,
	) -> list[SlowControlReplyEntry]:
		expected_addrs = [self._u32(a) for a in expected_addrs]
		if expected_write_data is not None:
			expected_write_data = [self._u32(d) for d in expected_write_data]
			if len(expected_write_data) != len(expected_addrs):
				raise ValueError("expected_write_data length mismatch")

		last_exc: BaseException | None = None

		for attempt in range(1, self.retries + 1):
			try:
				sent = self.sock.sendto(packet, self.server)
				if sent != len(packet):
					raise RuntimeError(f"Only sent {sent} of {len(packet)} bytes")

				reply, addr = self.sock.recvfrom(65535)
				if addr[0] != self.server[0]:
					raise RuntimeError(f"Reply from unexpected endpoint {addr}")

				entries = self._parse_reply(reply, expected_header)
				if len(entries) != len(expected_addrs):
					raise RuntimeError(
						f"Reply contains {len(entries)} entries, expected {len(expected_addrs)}"
					)

				for i, (expected_addr, entry) in enumerate(zip(expected_addrs, entries)):
					if self._u32(entry.addr) != expected_addr:
						raise RuntimeError(
							f"Reply address mismatch at entry {i}: "
							f"got 0x{entry.addr:08X}, expected 0x{expected_addr:08X}"
						)
					if expected_write_data is not None and self._u32(entry.data) != expected_write_data[i]:
						raise RuntimeError(
							f"Write reply data mismatch at entry {i}, addr 0x{entry.addr:08X}: "
							f"got 0x{entry.data:08X}, expected 0x{expected_write_data[i]:08X}"
						)
					if entry.status != 0:
						raise SlowControlStatusError(
							f"ESS status error at 0x{entry.addr:08X}: "
							f"status=0x{entry.status:08X}, data=0x{entry.data:08X}"
						)

				return entries

			except (socket.timeout, RuntimeError, SlowControlStatusError) as exc:
				last_exc = exc
				if attempt < self.retries:
					print(f"Retry {attempt}/{self.retries}: {label} failed: {exc}")
					time.sleep(self.poll_interval)
					continue
				break

		raise TimeoutError(f"{label} failed after {self.retries} attempts") from last_exc

	def sc_bulk_write(self, addrs_and_values: Sequence[tuple[int, int]], *, label: str) -> None:
		if not addrs_and_values:
			raise ValueError("empty ESS write request")

		for offset in range(0, len(addrs_and_values), self.max_entries_per_packet):
			chunk = [(self._u32(a), self._u32(v)) for a, v in addrs_and_values[offset:offset + self.max_entries_per_packet]]
			packet = self._make_write_packet(chunk)
			self._send_recv(
				packet,
				expected_header=WRITE_RESP,
				expected_addrs=[addr for addr, _value in chunk],
				expected_write_data=[value for _addr, value in chunk],
				label=label,
			)

	def sc_bulk_read(self, addrs: Sequence[int], *, label: str) -> list[SlowControlReplyEntry]:
		if not addrs:
			raise ValueError("empty ESS read request")

		out: list[SlowControlReplyEntry] = []
		for offset in range(0, len(addrs), self.max_entries_per_packet):
			chunk = [self._u32(a) for a in addrs[offset:offset + self.max_entries_per_packet]]
			packet = self._make_read_packet(chunk)
			out.extend(
				self._send_recv(
					packet,
					expected_header=READ_RESP,
					expected_addrs=chunk,
					expected_write_data=None,
					label=label,
				)
			)
		return out

	def write_stage_fields(self, fields: Sequence[int], *, label: str, full_payload: bool) -> None:
		fields = [self._u32(f) for f in fields]
		if len(fields) != FRAME_WORDS:
			raise ValueError(f"command frame needs {FRAME_WORDS} fields, got {len(fields)}")

		indices = range(FRAME_WORDS) if full_payload else (0, 1, 2, CHECKSUM_INDEX)
		self.sc_bulk_write([(self.stage_addr(i), fields[i]) for i in indices], label=label)

	def read_stage_indices(self, indices: Sequence[int], *, label: str) -> list[int]:
		indices = [int(i) for i in indices]
		for i in indices:
			if not 0 <= i < FRAME_WORDS:
				raise ValueError(f"staging index out of range: {i}")

		entries = self.sc_bulk_read([self.stage_addr(i) for i in indices], label=label)
		return [self._u32(entry.data) for entry in entries]

	def read_stage_fields(self) -> list[int]:
		return self.read_stage_indices(range(FRAME_WORDS), label="ESS read bridge response frame")

	def read_status_word(self) -> int:
		return self.read_stage_indices([CHECKSUM_INDEX], label="ESS read bridge status")[0]

	@staticmethod
	def _status_done(status: int) -> bool:
		return ((status >> 4) & 0xF) == DONE_PREFIX

	@staticmethod
	def _status_code(status: int) -> int:
		return status & 0xF

	def _poll_done(self, *, label: str) -> int:
		deadline = time.monotonic() + self.poll_timeout
		last_status = 0

		while True:
			last_status = self.read_status_word()

			if self._status_done(last_status):
				code = self._status_code(last_status)
				if code != STATUS_OK:
					raise SlowControlStatusError(
						f"Bridge command failed: status=0x{last_status:08X}, code=0x{code:04X}"
					)
				return last_status

			if time.monotonic() >= deadline:
				raise TimeoutError(f"{label} did not complete, last status=0x{last_status:08X}")

			time.sleep(self.poll_interval)

	def _run_command(
		self,
		opcode: int,
		addr: int,
		data_words: Sequence[int],
		*,
		label: str,
		full_payload_write: bool,
		result_indices: Sequence[int] | None,
	) -> list[int] | None:
		fields = self.command_fields(opcode, addr, data_words)
		self.write_stage_fields(fields, label=label, full_payload=full_payload_write)
		self._poll_done(label=label)
		if result_indices is None:
			return None
		return self.read_stage_indices(result_indices, label=f"{label} result read")

	def write_reg(self, addr: int, value: int) -> None:
		self._run_command(
			self.op_write32,
			self._u32(addr),
			[self._u32(value)],
			label="AXI write32",
			full_payload_write=False,
			result_indices=None,
		)

	def read_reg(self, addr: int) -> int:
		result = self._run_command(
			self.op_read32,
			self._u32(addr),
			[0],
			label="AXI read32",
			full_payload_write=False,
			result_indices=[2],
		)
		assert result is not None
		return self._u32(result[0])

	def write_page(self, addr: int, words: Sequence[int]) -> None:
		words = [self._u32(w) for w in words]
		if len(words) != PAGE_WORDS:
			raise ValueError(f"write_page needs {PAGE_WORDS} words, got {len(words)}")

		self._run_command(
			self.op_write_page,
			self._u32(addr),
			words,
			label="AXI write page",
			full_payload_write=True,
			result_indices=range(FRAME_WORDS),
		)

	def read_page(self, addr: int) -> list[int]:
		result = self._run_command(
			self.op_read_page,
			self._u32(addr),
			[0] * PAGE_WORDS,
			label="AXI read page",
			full_payload_write=True,
			result_indices=range(FRAME_WORDS),
		)
		assert result is not None
		return [self._u32(w) for w in result[2:2 + PAGE_WORDS]]

	def ping(self) -> None:
		result = self._run_command(
			self.op_ping,
			0,
			[0],
			label="AXI ping",
			full_payload_write=False,
			result_indices=[2],
		)
		assert result is not None
		if self._u32(result[0]) != 0xCAFECAFE:
			raise RuntimeError(f"Bad ping reply: 0x{result[0]:08X}")
			
			
			
	def read_ess_register_once(self, addr: int) -> int:
		"""Read one ESS register through the normal ESS read-request path."""
		addr = self._u32(addr)

		entry = self.sc_bulk_read(
			[addr],
			label=f"ESS read register 0x{addr:08X}",
		)[0]

		return self._u32(entry.data) 

	def print_regbank_info(self) -> None:
		"""Read and print ESS slow-control register-bank information."""

		registers = (
			("REGBANK_VERSION", 0x00000000),
			("PHASH",           0x00000004),
			("GIT_HASH2",       0x00000008),
			("GIT_HASH1",       0x0000000C),
			("GIT_HASH0",       0x00000010),
			("TYPE1_USR",       0x00000014),
			("TYPE2_USR",       0x00000018),
			("VERS_USR",        0x0000001C),
		)

		def ascii_word_le(value: int) -> str:
			raw = (value & 0xFFFFFFFF).to_bytes(4, byteorder="little")
			return "".join(chr(b) if 32 <= b <= 126 else "." for b in raw)

		regs: dict[str, int] = {}

		print("\n------------------------------")
		print("ESS register-bank information")
		print("------------------------------")

		for name, offset in registers:
			ring_fen_addr = self._u32(self.ring_fen_offset + offset)
			value = self.read_ess_register_once(ring_fen_addr)
			regs[name] = value

		git_hash = (
			(regs["GIT_HASH2"] << 64)
			| (regs["GIT_HASH1"] << 32)
			| regs["GIT_HASH0"]
		)
		def regbank_version_string(value: int) -> str:
			bank = chr((value >> 24) & 0xFF)   # 0x41 -> A
			major = (value >> 16) & 0xFF       # 0
			minor = value & 0xFF               # 1
			return f"{bank}{major}v{minor}"

		user_type = (
			ascii_word_le(regs["TYPE1_USR"])
			+ ascii_word_le(regs["TYPE2_USR"])
		)

		print(
			f"REGBANK VERSION  : "
			f"{regbank_version_string(regs['REGBANK_VERSION'])}"
		)
		print(f"PHASH            : 0x{regs['PHASH']:08X}")
		print(f"USER TYPE        : {user_type}")
		print(f"USER VERSION     : 0x{regs['VERS_USR']:08X}")
		print(f"GIT_HASH         : 0x{git_hash:024X}")
