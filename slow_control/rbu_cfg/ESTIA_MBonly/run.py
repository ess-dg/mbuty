import asyncio, argparse, time

from essrmmdriverlib.ReadoutMasterModule import ReadoutMasterModule



##############################################################################################
# Warm bringup of ring
##############################################################################################
def ringRetry(ring:int):
    """Teardown and Bringup a single ring. Requires Common Ring Setup to have completed"""
    if ring not in rmm.RMMRings.topology.keys():
        raise ValueError(f"Ring {ring} has no front end nodes defined in the topology!")
    asyncio.run(rmm.RMMRings._teardownRing(ring))
    asyncio.run(rmm.RMMRings.ringSetup(ring))

    # Inform FEs on that ring that they can start accepting bulk data from userspace
    nodes = rmm.RMMRings.topology[ring]["nodes"]
    for node in range(nodes):
        rmm.RMMRegs.feafwRegWrite("MRDY_SLV", ring, node, 0xffff_ffff, "S")

###############################################################################################
# Useful Funcs for Interactive Mode 
# (can also tab-complete from rmm. to access other RMM driver internal funcs)
###############################################################################################
def waitForOverflow():
    """Continuously check for overflow on any fibre, once every second. Can exit with CTRL+C"""
    print(f"\n===== Starting to check for overflow =====")
    oflow = False
    while not oflow:
        counters = rmm.getPacketCounts()
        for fibre, count in counters["fibre_overflow"].items():
            if int(fibre) in range(24):
                if count != 0:
                    oflow = True
        if oflow == False:
            time.sleep(1)
    printRMMCounters()
    print(f"\n===== Overflow has been detected! =====")

def printRMMCounters():
    """Pretty-prints the RMM Bulk Data Packet Counters"""
    counters = rmm.getPacketCounts()
    print("")
    print("=== Fibre Packet Counts (rx_engine_mstr) ===")
    for fibre, count in counters["fibre"].items():
        if int(fibre) in range(24):        
            if count != 0:
                print(f"fibre {fibre} = {count} packets")
    for fibre, count in counters["fibre_overflow"].items():
        if int(fibre) in range(24):
            if count != 0:
                print(f"ALERT: fibre overflow {fibre} = {count} words")
    for ring, ring_counts in counters["per-node"].items():
        if int(ring) in range(13):
            print("")
            print(f"=== Ring {ring} Packets arriving at Output Queue ===")
            for node, count in ring_counts.items():
                if count != 0:
                    print(f"node {node} = {count} packets")

def updateRMMDataGenEnable(val:int):
    """val(int) : New value for per-fibre data generators to enable (eg 0xf to enable fibres 0-3 and disable all others)"""
    rmm.RMMRegs.regWrite(f"PDPL", 0x0, "M")
    rmm.RMMRegs.regWrite(f"RGTY", 0x0, "M")
    rmm.RMMRegs.regWrite(f"pkt_gen_enable", val, "E")
    en_str = " "
    for i in range(24):
        if val & (0x1 << i):
            en_str += f"{i} " 
    print(f"RMM Packet generators for{en_str} are enabled, all others disabled")

def updateRMMDataGenIdles(fibre:int, val:int):
    """Updates the IDLES reg for a specific fibre data generator"""
    print(f"update IDLES for fibre {fibre} gen to {val} cycles")
    rmm.RMMRegs.regWrite(f"pkt_gen_idles{fibre:02d}", val, "E")

def updateAllRMMDataGenIdles(val:int):
    for i in range(24):
        rmm.RMMRegs.regWrite(f"pkt_gen_idles{i:02d}", val, "E")


def cycleTestDataGenerators(val:int=0xfff_fff):
    rmm.RMMRegs.regWrite(f"pkt_gen_enable", 0x0, "E")
    rmm.resetPacketCounts()
    rmm.RMMRegs.regWrite(f"pkt_gen_enable", val, "E")

def cycleOutputQueues(val:int=0x1fff):
    rmm.RMMRegs.regWrite(f"eng_enable", 0x0, "E")
    rmm.resetPacketCounts()
    rmm.RMMRegs.regWrite(f"eng_enable", val, "E")

def testDataGenerators(cfg:dict, data_gen_enable=0xfff_fff, oq_enable=0x1fff):
    """Run an RMM datapath throughput test using the RMM data generators

    Args:
        cfg (dict): Dictionary of {(burst, idles), fibres} to configure data generators. consecutive $fibres generators are assigned to produce continuous bursts of $bursts packets with $idle_cycles between bursts. All $counts should add up to 24
        data_gen_enable (int):  one bit per fibre, enables the corresponding data generator
        oq_enable (int): one bit per ring, enables the corresponding output queue
    """
    # 1. Update idles based on input list
    fibre = 0
    for gen_cfg, count in cfg.items():
        print(f"{gen_cfg=}")
        burst_len = gen_cfg[0]
        idle_cycles = gen_cfg[1]
        PKT_DATA_CYCLES = 6
        CLK_FREQ = 158494500 # cycles per second
        burst_cycles = PKT_DATA_CYCLES * burst_len + idle_cycles
        bursts_per_sec = CLK_FREQ / burst_cycles
        
        avg_pkts_per_sec = bursts_per_sec / burst_len
        avg_bits_per_sec = avg_pkts_per_sec * PKT_DATA_CYCLES * 32 # 32b words
        
        total_bits_per_sec = 0
        for i in range(count):
            print(f"updated fibre gen {fibre} to bursts of {burst_len} packets with {idle_cycles} idle cycles between bursts (avg {avg_pkts_per_sec} FEN packets/sec")
            total_bits_per_sec += avg_bits_per_sec
            rmm.RMMRegs.regWrite(f"pkt_gen_length{fibre:02d}", burst_len, "E")
            rmm.RMMRegs.regWrite(f"pkt_gen_idles{fibre:02d}", idle_cycles, "E")
            fibre += 1
        print(f"Updated Total FEN data throughput = {total_bits_per_sec/1000000} Mbps")

    # 2. Disable packet generators
    rmm.RMMRegs.regWrite(f"PDPL", 0x0, "M")
    rmm.RMMRegs.regWrite(f"RGTY", 0x0, "M")
    rmm.RMMRegs.regWrite(f"pkt_gen_enable", 0x0, "E")

    # 3. Reset output queues to clear any previous overflow logjam
    rmm.RMMRegs.regWrite(f"eng_enable", 0x0, "E")
    rmm.RMMRegs.regWrite(f"eng_enable", oq_enable, "E")
    
    # 4. Reset packet counts
    rmm.resetPacketCounts()

    # 5. Enable packet generators
    rmm.RMMRegs.regWrite(f"pkt_gen_enable", data_gen_enable, "E")
    
    # 6. print packet counts
    printRMMCounters()
    # 7. wait a few secs
    time.sleep(3)
    # 8. print packet counts
    printRMMCounters()

def spamCmds():
    """Attempt to reproduce firewall lockup by spamming many slow control commands until failure"""
    cmds = 0
    start = time.time()
    print(f"Start spamming at {time.ctime(start)}")
    try:
        while True:
            rmm.RMMRegs.regRead("eng_enable")   # use any old register for now
            cmds += 1
    finally:
        end = time.time()
        print(f"Spamming ended at {time.ctime(end)}")
        print(f"Succesful commands : {cmds}")
        duration=end-start
        days = int(duration/(3600*24))
        duration -= days*3600*24
        hours = int(duration/3600)
        duration -= hours*3600
        minutes = int(duration/60)
        duration -= minutes*60
        print(f"Spam Duration      : {days} days {hours}:{minutes}:{int(duration)}")
        print(f"Avg Spam Rate      : {cmds / (end-start)}/s")


###############################################################################################
# Actual RMM Bringup 
###############################################################################################
if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="slow_control_driver Example")
    parser.add_argument("-c", "--cfg_json", required=True, type=str, help="JSON config file")
    args = parser.parse_args()
    rmm = ReadoutMasterModule(cfg_json=args.cfg_json)

    # Brings up the RMM and all rings in the configuration file
    # Does not perform any Front End "userspace" config
    asyncio.run(rmm.configRMM(timing_mode="mrf"))   # 'mrf', 'lcl' or 'ext'

    # i=0
    # while(1):
    #     ringRetry(11)
    #     i += 1
    #     print(f"============ Completed {i} bringups ============")
