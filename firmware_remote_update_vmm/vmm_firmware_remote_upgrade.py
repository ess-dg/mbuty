#!/usr/bin/env python3
# -*- coding: utf-8 -*-

###############################################################################
###############################################################################

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
	sys.path.insert(0, str(SCRIPT_DIR))

from assister_flash import AxiVersionLite, AxiMicronN25Q, AxiCypressS25FL, RegisterAxiLite
from assister_flash import register_axilite as _register_axilite_module

###############################################################################
###############################################################################

def parse_int(text: str) -> int:
	return int(text, 0)


def fw_upgrader_vmm(
	ip: str = "192.168.50.2",
	port: int = 65535,
	file: str = "hybrid.mcs",
	ring: int = 0,
	fen: int = 0,
	hyb: int = 0,
	stage_base_offset: int = 0x00000f00,
	ring_stride: int = 0x10000000,
	fen_stride: int = 0x00800000,
	version_base: int = 0x00000000,
	prom_base: int = 0x00010000,
	reload_addr: int = 0x00000000,
	version_only: bool = False,
	timeout: float = 1.0,
	retries: int = 3,
	poll_timeout: float = 1.0,
	poll_interval: float = 0.00001,
	max_entries_per_packet: int = 80,
	flash_timeout: float = 10.0,
) -> int:
	try:
		with RegisterAxiLite(
			ip,
			port,
			ring=ring,
			fen=fen,
			hyb=hyb,
			base_offset=stage_base_offset,
			ring_stride=ring_stride,
			fen_stride=fen_stride,
			timeout=timeout,
			retries=retries,
			poll_timeout=poll_timeout,
			poll_interval=poll_interval,
			max_entries_per_packet=max_entries_per_packet,
		) as bus:

			axi_version = AxiVersionLite(bus, version_base, hyb)
			if hyb == -1:
				prom = AxiMicronN25Q(bus, base_addr=prom_base, timeout_s=flash_timeout)
			else:
				prom = AxiCypressS25FL(bus, base_addr=prom_base, timeout_s=flash_timeout)

			bus.ping()
			if hyb == -1:
				print("###################################################")
				print("			Present Firmware Assister				")
				print("###################################################")
			else:
				if hyb >= 0 and hyb <= 5:
					print("###################################################")
					print(f"		 Present Firmware Hybrid {hyb}")
					print("###################################################")
				else:
					print(f"Hybrid {hyb} does not exist, hyb has to be -1 (assister) or 0 to 5 (hybrids)!")
					return 1	
			axi_version.print_status()
			
			if version_only:
				if hyb == -1:
					bus.print_regbank_info()
				return 0	
			print(f"\nProgramming image: {file}")
			file_path = Path(file)
			prom.load_mcs_file(str(file_path), verify=True)

			print("\nReloading FPGA firmware from PROM ....")
			axi_version.fpga_reload(reload_addr)
			if hyb == -1:
				print("\nReload command issued")
				print("The assister will drop off the ESS ring during reload.")
				print("Power cycle the board, and run ESS ring bringup again before reading the new firmware version.")
			else:
				time.sleep(3)
				print("###################################################")
				print(f"		 New Firmware Hybrid {hyb}")
				print("###################################################")
				axi_version.print_status()
				print("If the version print-out gave an error (reason loss of hybrid link status), click warm-init in the assister slow control.")
			return 0

	except KeyboardInterrupt:
		print("\nFirmware update aborted by user.")
		return 130

	except Exception as exc:
		print("\n###################################################")
		print("#	\t\t\t Firmware update failed \t\t\t#")
		print("###################################################")
		print(f"{type(exc).__name__}: {exc}")
		print("\nNo FPGA reload was issued.")
		print("PROM contents may be partially erased/programmed.")
		print("Run the update again after fixing the problem.")
		return 1

###############################################################################
###############################################################################
###############################################################################
###############################################################################

if __name__ == "__main__":
	parser = argparse.ArgumentParser(
		description="Program FPGA configuration flash through ESS slow-control bulk command registers."
	)

	parser.add_argument("--ip", type=str, default="192.168.50.2", help="ESS slow-control IP address")
	parser.add_argument("--port", type=int, default=65535, help="ESS slow-control UDP port")
	parser.add_argument("--file", type=str, default="hybrid.mcs", help="Flash file (.mcs)")
	parser.add_argument("--ring", type=int, default=0, help="Logical ring index")
	parser.add_argument("--fen", type=int, default=0, help="FEN/node index")
	parser.add_argument("--hyb", type=int, default=0, help="Hybrid index (0-5), if -1 flash assister")
	parser.add_argument(
		"--stage-base-offset",
		type=parse_int,
		default=0x00000f00,
		help="Base offset of mem_flash/stage[0] before ring/fen address offsets",
	)
	parser.add_argument("--ring-stride", type=parse_int, default=0x10000000)
	parser.add_argument("--fen-stride", type=parse_int, default=0x00800000)

	parser.add_argument(
		"--version-base",
		type=parse_int,
		default=0x00000000,
		help="Target AXI base address of AxiVersion behind the bridge",
	)
	parser.add_argument(
		"--prom-base",
		type=parse_int,
		default=0x00010000,
		help="Target AXI base address of AxiMicronN25QCore behind the bridge",
	)
	parser.add_argument(
		"--reload-addr",
		type=parse_int,
		default=0x00000000,
		help="Flash byte address of application image for warm boot",
	)
	parser.add_argument(
		"--version-only",
		action="store_true",
		help="Just print the firmware version.",
	)

	parser.add_argument("--timeout", type=float, default=1.0, help="UDP socket timeout in seconds")
	parser.add_argument("--retries", type=int, default=3, help="Retry count for ESS packets")
	parser.add_argument(
		"--poll-timeout",
		type=float,
		default=1.0,
		help="Timeout for one internal bridge command completion",
	)
	parser.add_argument(
		"--poll-interval",
		type=float,
		default=0.00001,
		help="Polling interval in seconds while waiting for bridge completion",
	)
	parser.add_argument(
		"--max-entries-per-packet",
		type=int,
		default=80,
		help="Maximum ESS entries per UDP packet. 80 keeps one 67-word frame in one packet.",
	)
	parser.add_argument(
		"--flash-timeout",
		type=float,
		default=10.0,
		help="Timeout in seconds while waiting for flash ready flag.",
	)

	args = parser.parse_args()
	raise SystemExit(fw_upgrader_vmm(**vars(args)))