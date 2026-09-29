#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@authors: Dorothea Pfeiffer, Francesco Piscitelli
"""
###############################################################################

import json
import os 

###############################################################################

def loadConfig(cfg_vmm):
	with open(cfg_vmm, "r") as f:
		return json.load(f)


# def saveConfig(cfg, cfg_vmm):
# 	with open(cfg_vmm, "w") as f:
# 		json.dump(cfg, f, indent="\t")


# def asConfig(cfg_or_file):
# 	if isinstance(cfg_or_file, str):
# 		return loadConfig(cfg_or_file)
# 	return cfg_or_file


def b(value, width):
	return format(int(value) & ((1 << width) - 1), f"0{width}b")


def setBits(reg, pos, bits):
	reg = list(reg)
	for i, bit in enumerate(str(bits)):
		reg[pos + i] = bit
	return "".join(reg)


def setBit(reg, pos, value):
	return setBits(reg, pos, str(int(value)))


def get(vmm, name):
	if name not in vmm:
		raise KeyError(f"Missing VMM config value: {name}")
	return vmm[name]


def getCh(vmm, ch, name):
	return vmm[f"channel{ch:02d}"][name]


def findFen(cfg, ring, fen):
	for the_fen in cfg["fecs"]:
		if the_fen["fen"] == fen and the_fen["ring"]  == ring:
			return the_fen
	raise KeyError(f"FEN: ring {ring} node {fen} not found")


def findHybrid(the_fen, hybrid):
	for the_hybrid in the_fen["hybrids"]:
		if the_hybrid["hybrid"] == hybrid:
			return the_hybrid
	raise KeyError(f"Hybrid {hybrid} not found in FEN {the_fen['fen']}")


def findVmm(cfg, ring, fen, hybrid, vmm_index):
	the_fen    = findFen(cfg, ring, fen)
	the_hybrid = findHybrid(the_fen, hybrid)
	return the_hybrid[f"vmm{vmm_index}"]


# def setVmmConfig(cfg, fen, hybrid, vmm_index, name, value):
# 	vmm = findVmm(cfg, fen, hybrid, vmm_index)
# 	vmm[name] = value
# 	return cfg


# def setChannelConfig(cfg, fen, hybrid, vmm_index, ch, name, value):
# 	vmm = findVmm(cfg, fen, hybrid, vmm_index)
# 	vmm[f"channel{ch:02d}"][name] = value
# 	return cfg


# def updateVmmConfig(cfg, fen, hybrid, vmm_index, values):
# 	vmm = findVmm(cfg, fen, hybrid, vmm_index)
# 	vmm.update(values)
# 	return cfg


# def updateChannelConfig(cfg, fen, hybrid, vmm_index, ch, values):
# 	vmm = findVmm(cfg, fen, hybrid, vmm_index)
# 	vmm[f"channel{ch:02d}"].update(values)
# 	return cfg

# def setAssisterConfig(cfg, fen, name, value):
# 	the_fen = findFen(cfg, fen)
# 	the_fen[name] = value
# 	return cfg


# def updateAssisterConfig(cfg, fen, values):
# 	the_fen = findFen(cfg, fen)
# 	the_fen.update(values)
# 	return cfg

def fillGlobalRegisters(vmm):
	regs = []

	spi0 = "0" * 32
	s = 4

	for name in [
		"slvs", "s32", "stcr", "ssart", "srec", "stlc", "sbip", "srat",
		"sfrst", "slvsbc", "slvstp", "slvstk", "slvsdt", "slvsart",
		"slvstki", "slvsena", "slvs6b",
	]:
		spi0 = setBit(spi0, s, get(vmm, name))
		s += 1

	spi0 = setBit(spi0, s, get(vmm, "sL0enaV"))
	s += 1

	for name in ["slh", "slxh", "stgc"]:
		spi0 = setBit(spi0, s, get(vmm, name))
		s += 1

	s += 5

	spi0 = setBit(spi0, s, get(vmm, "reset1"))
	s += 1
	spi0 = setBit(spi0, s, get(vmm, "reset2"))

	regs.append(spi0)

	spi1 = "0" * 32
	s = 0

	tmp = b(get(vmm, "sdt"), 10)
	spi1 = setBits(spi1, s, tmp[4:10])
	s += 6

	spi1 = setBits(spi1, s, b(get(vmm, "sdp10"), 10))
	s += 10

	for name, width in [
		("sc10b", 2),
		("sc8b", 2),
		("sc6b", 3),
	]:
		spi1 = setBits(spi1, s, b(get(vmm, name), width))
		s += width

	for name in ["s8b", "s6b", "s10b", "sdcks", "sdcka", "sdck6b", "sdrv", "stpp"]:
		spi1 = setBit(spi1, s, get(vmm, name))
		s += 1

	regs.append(spi1)

	spi2 = "0" * 32
	s = 0

	for name in ["sp", "sdp", "sbmx", "sbft", "sbfp", "sbfm", "slg"]:
		spi2 = setBit(spi2, s, get(vmm, name))
		s += 1

	channel = get(vmm, "sm5_sm0")
	if channel >= 0 and channel <= 63:
		sm5_sm0 = channel
		scmx = 1
	elif channel >= 64 and channel <= 67:
		sm5_sm0 = channel - 63
		scmx = 0
	else:
		raise ValueError(f"Invalid sm5_sm0 value: {channel}")
		
	spi2 = setBits(spi2, s, b(sm5_sm0, 6))
	s += 6
	
	spi2 = setBit(spi2, s, scmx)
	s += 1
			 
	for name in ["sfa", "sfam"]:
		spi2 = setBit(spi2, s, get(vmm, name))
		s += 1

	spi2 = setBits(spi2, s, b(get(vmm, "st"), 2))
	s += 2

	spi2 = setBit(spi2, s, get(vmm, "sfm"))
	s += 1

	spi2 = setBits(spi2, s, b(get(vmm, "sg"), 3))
	s += 3

	for name in ["sng", "stot", "sttt", "ssh"]:
		spi2 = setBit(spi2, s, get(vmm, name))
		s += 1

	spi2 = setBits(spi2, s, b(get(vmm, "stc"), 2))
	s += 2

	tmp = b(get(vmm, "sdt"), 10)
	spi2 = setBits(spi2, s, tmp[0:4])

	regs.append(spi2)

	return regs


def fillChannelRegisters(vmm):
	regs = []

	for ch in range(64):
		reg = "0" * 32
		s = 8

		for name in ["sc", "sl", "st", "sth", "sm", "smx"]:
			reg = setBit(reg, s, getCh(vmm, ch, name))
			s += 1

		reg = setBits(reg, s, b(getCh(vmm, ch, "sd"), 5)[::-1])
		s += 5

		reg = setBits(reg, s, b(getCh(vmm, ch, "sz10b"), 5)[::-1])
		s += 5

		reg = setBits(reg, s, b(getCh(vmm, ch, "sz08b"), 4)[::-1])
		s += 4

		reg = setBits(reg, s, b(getCh(vmm, ch, "sz06b"), 3)[::-1])
		s += 3

		assert s == 31

		regs.append(reg)

	return regs
	

def fillGlobalRegisters2(vmm):
	regs = []

	spi0 = "0" * 32
	spi0 = setBit(spi0, 31, get(vmm, "nskipm_i"))
	regs.append(spi0)

	spi1 = "0" * 32
	s = 0

	spi1 = setBit(spi1, s, get(vmm, "sL0cktest"))
	s += 1

	for name in ["sL0dckinv", "sL0ckinv"]:
		spi1 = setBit(spi1, s, get(vmm, name))
		s += 1

	spi1 = setBit(spi1, s, get(vmm, "sL0ena"))
	s += 1

	for name, width in [
		("truncate_i", 6),
		("nskip_i", 7),
		("window_i", 3),
		("rollover_i", 12),
	]:
		spi1 = setBits(spi1, s, b(get(vmm, name), width))
		s += width

	regs.append(spi1)

	spi2 = "0" * 32
	s = 0

	spi2 = setBits(spi2, s, b(get(vmm, "L0offset_i"), 12))
	s += 12

	spi2 = setBits(spi2, s, b(get(vmm, "offset_i"), 12))

	regs.append(spi2)

	return regs
						
						
def configVmm(fen_portal, ring, fen, hybrid, vmm_index, cfg):
   
	vmm = findVmm(cfg, ring, fen, hybrid, vmm_index)

	idx = hybrid * 2 + vmm_index
	s_vmm = f"{idx:02d}" if idx < 10 else str(idx)

	bank2    = fillGlobalRegisters2(vmm)
	channels = fillChannelRegisters(vmm)
	bank1    = fillGlobalRegisters(vmm)

	for i, word in enumerate(bank2):
		fen_portal.userRegWrite(ring, fen, f"vmm_global_bank2_sp{i}{s_vmm}", int(word, 2))

	for ch, word in enumerate(channels):
		fen_portal.userRegWrite(ring, fen, f"vmm_ch{ch:02d}{s_vmm}", int(word, 2))

	for i, word in enumerate(bank1):
		fen_portal.userRegWrite(ring, fen, f"vmm_global_bank1_sp{i}{s_vmm}", int(word, 2))

	fen_portal.userRegWrite(ring, fen, "sc_cfg_vmm", 0)
	fen_portal.userRegWrite(ring, fen, "sc_cfg_vmm", 1 << idx)
	fen_portal.userRegWrite(ring, fen, "sc_cfg_vmm", 0)


def configHybrid(fen_portal, ring, fen, hybrid, cfg):
    
	the_fen    = findFen(cfg, ring, fen)

	the_hybrid = findHybrid(the_fen, hybrid)

	param = the_hybrid["TP_pol"]

	fen_portal.userRegWrite(ring, fen, f"hyb_tp_skew0{hybrid}", the_hybrid["TP_skew"])
	fen_portal.userRegWrite(ring, fen, f"hyb_tp_width0{hybrid}", the_hybrid["TP_width"])
	fen_portal.userRegWrite(ring, fen, f"hyb_tp_polarity0{hybrid}", param)

	fen_portal.userRegWrite(ring, fen, "sc_cfg_hyb", 0)
	fen_portal.userRegWrite(ring, fen, "sc_cfg_hyb", 1 << hybrid)
	fen_portal.userRegWrite(ring, fen, "sc_cfg_hyb", 0)


def configAssister(fen_portal, ring, fen, cfg, mask):
	the_fen = findFen(cfg, ring, fen)

	writes = [
		("app_debug_data_format", 0),
		("app_latency_reset", the_fen["latency_reset"]),
		("app_tp_offset_first", the_fen["tp_offset_first"]),
		("app_tp_offset", the_fen["tp_offset"]),
		("app_tp_offset_long", 0),
		("app_tp_period_long", 0),
		("app_tp_latency", the_fen["tp_latency"]),
		("app_tp_number", the_fen["tp_number"]),
		("app_chmask", mask),
		("sc_cfg_app", 0),
		("sc_cfg_app", 1),
		("sc_cfg_app", 0),
	]

	for reg, value in writes:
		fen_portal.userRegWrite(ring, fen, reg, value)


def resetFec(fen_portal, ring, fen):    # this is warm init 

		print(f"Resetting ring {ring}, fen {fen}")

		fen_portal.userRegWrite(ring, fen, "sc_app_reset_assister", 0)
		fen_portal.userRegWrite(ring, fen, "sc_app_reset_assister", 1)
		fen_portal.userRegWrite(ring, fen, "sc_app_reset_assister", 0)
        
# add reset all wqith loop 


        # 
# VMM Hard reset:

# else if(QObject::sender() == m_ui->vmmReset){
#         for (unsigned short j=0; j < FECS_PER_DAQ; j++){
#             if (m_daq.GetFEC(j) ){
#                 m_daq.m_fecs[m_fecIndex].m_fecConfigModule->ACQoff();
#             }
#         }
#         m_ui->offACQ->setCheckable(true);
#         m_ui->offACQ->setChecked(true);
#         m_ui->onACQ->setChecked(false);
#         SetVMM(“reset1”, 1);
#         SetVMM(“reset2", 1);
#         m_daq.m_fecs[m_fecIndex].m_fecConfigModule->ConfigVMM(m_hybridIndex, m_vmmIndex);
#         QThread::sleep(1);
#         SetVMM(“reset1”, 0);
#         SetVMM(“reset2", 0);
#         m_daq.m_fecs[m_fecIndex].m_fecConfigModule->ConfigVMM(m_hybridIndex, m_vmmIndex);
#         m_ui->Send->setEnabled(true);
#     }        


def acqOnOff(fen_portal, ring, fen, on=True):
# 	cfg = asConfig(cfg_or_file)
# 	checkConfigNames(cfg)

    if on:
        print(f"Starting acquisition on ring {ring}, fen {fen}")
        fen_portal.userRegWrite(ring, fen, "app_acq_enable", 1)
    else:
        print(f"Stopping acquisition on ring {ring}, fen {fen}")
        fen_portal.userRegWrite(ring, fen, "app_acq_enable", 0)

    fen_portal.userRegWrite(ring, fen, "sc_acq_on_off", 0)
    fen_portal.userRegWrite(ring, fen, "sc_acq_on_off", 1)
    fen_portal.userRegWrite(ring, fen, "sc_acq_on_off", 0)

def acqOnOff_global(fen_portal, cfg, on=True):
    # checkConfigNames(cfg)
    if on:
        print(f"Starting acquisition on all rings all fens")
    else:
        print(f"Stopping acquisition on all rings all fens")	
        
    for the_fen in enumerate(cfg["fecs"]):
        acqOnOff(fen_portal, the_fen['ring'], the_fen['fen'], on=on)


def checkConfigNames(cfg):
	for fec_index, fen in enumerate(cfg["fecs"]):
		for hybrid_index, hybrid in enumerate(fen["hybrids"]):
			for vmm_index in [0, 1]:
				vmm_name = f"vmm{vmm_index}"

				if vmm_name not in hybrid:
					raise KeyError(f"Missing {vmm_name} in fen {fen}, hybrid {hybrid}")

				vmm = hybrid[vmm_name]

				fillGlobalRegisters(vmm)
				fillGlobalRegisters2(vmm)
				fillChannelRegisters(vmm)

	print("JSON config check passed.")


def configDetector(fen_portal, cfg):
    
# 	cfg = asConfig(cfg_or_file)
# 	checkConfigNames(cfg)

	for the_fen in cfg["fecs"]:
		fen  = the_fen["fen"]
		ring = the_fen["ring"]
		channel_mask = 0

		print(f"Configuring ring {ring}, fen {fen}")

		for the_hybrid in the_fen["hybrids"]:
			hybrid = the_hybrid["hybrid"]
			print(f"  Configuring hybrid {hybrid}")

			configHybrid(fen_portal, ring, fen, hybrid, cfg)

			for vmm_index in [0, 1]:
				print(f"\tConfiguring VMM {vmm_index}")

				configVmm(fen_portal, ring, fen, hybrid, vmm_index, cfg)
				channel_mask = channel_mask | (1 << (hybrid * 2 + vmm_index))

		configAssister(fen_portal, ring, fen, cfg, channel_mask)

	return cfg

###############################################################################
###############################################################################
###############################################################################

if __name__ == "__main__":
    
    VMMcfgFile  = 'MB.FREIA.diagonalNoSymm.json'
    
    VMMcfgPath  = '/Users/francescopiscitelli/gitlab_repos/mb_configs/VMM slow ctrl/' 
    
    current_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) + os.sep
    
    VMMcfgPath  = current_dir + 'config_slowCtrlVMM'

    cfg         = os.path.join(VMMcfgPath, VMMcfgFile)
    
    # fen_portal = 
    
    # configDetector(fen_portal,cfg)
    


