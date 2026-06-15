import numpy as np
from instrument_registry import get_readout_spec


class BaseHardwareDecoder:
    """
    Abstract base for all ESS hardware readout decoders.

    Each concrete subclass handles the bit-level payload structure of one
    electronics type. Decoder instances are created once in _read_packets()
    and reused across all packets of that type.
    """

    def __init__(self, ns_per_clock_tick: float, reader, readout_size: int) -> None:
        self.ns_per_clock_tick = np.float64(ns_per_clock_tick)
        self._reader           = reader
        self.readout_size      = int(readout_size)

    def decode_common_fields(self, raw: np.ndarray, dest_block: np.ndarray) -> None:
        """
        Vectorised extraction of the five wire fields present in every readout type.

        Byte layout (identical across all hw types):
            [0]    physical ring byte  →  ring = byte // 2
            [1]    fen
            [2:4]  length (uint16 LE)
            [4:8]  timeHI (uint32 LE, seconds)
            [8:12] timeLO (uint32 LE, clock ticks)

        pulse_t / prev_pt / instrID are broadcast by _read_packets() before
        decode() is called and are not written here.
        """
        dest_block['ring']   = (raw['ring_raw'] // 2).astype(np.int64)
        dest_block['fen']    = raw['fen'].astype(np.int64)
        dest_block['length'] = raw['length'].astype(np.int64)

        time_hi_ns = np.round(raw['timeHI'].astype(np.float64) * 1_000_000_000.0).astype(np.int64)
        time_lo_ns = np.round(raw['timeLO'].astype(np.float64) * self.ns_per_clock_tick).astype(np.int64)
        dest_block['timeStamp'] = time_hi_ns + time_lo_ns

    def decode(
        self,
        packet_data:    bytes,
        data_start_idx: int,
        n_readouts:     int,
        dest_block:     np.ndarray,
    ) -> None:
        raise NotImplementedError(f"{self.__class__.__name__}.decode() is not implemented.")


class VMMNormalDecoder(BaseHardwareDecoder):
    """
    Decoder for VMM3A electronics in normal hit mode.

    Readout layout (20 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length    uint16 LE
        [4:8]   timeHI    uint32 LE
        [8:12]  timeLO    uint32 LE
        [12:14] BC        uint16 LE
        [14:16] OTADC     uint16 LE  →  adc = & 0x3FF, oth = >> 15
        [16]    G0GEO     uint8      →  geo = & 0x3F, g0 via mode bits
        [17]    tdc       uint8
        [18]    vmm       uint8      →  asic = & 0x1, hybrid = (& 0xE) >> 1
        [19]    channel   uint8
    """

    _CANONICAL_INSTR_ID = 72  # FREIA — all VMM instruments share 20-byte readouts

    _READOUT_DTYPE = np.dtype([
        ('ring_raw', '<u1'),
        ('fen',      '<u1'),
        ('length',   '<u2'),
        ('timeHI',   '<u4'),
        ('timeLO',   '<u4'),
        ('bc',       '<u2'),
        ('otadc',    '<u2'),
        ('g0geo',    '<u1'),
        ('tdc',      '<u1'),
        ('vmm',      '<u1'),
        ('channel',  '<u1'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        dest_block['bc'] = raw['bc'].astype(np.int64)

        otadc = raw['otadc'].astype(np.int64)
        dest_block['adc'] = otadc & 0x3FF
        dest_block['oth'] = otadc >> 15

        g0geo = raw['g0geo'].astype(np.int64)
        dest_block['geo'] = g0geo & 0x3F
        temp    = (g0geo & 0xC0) >> 6
        geoBit6 = temp & 0x1
        geoBit7 = (temp & 0x2) >> 1
        dest_block['g0'] = np.where(
            geoBit6 == 1, np.int64(2),
            np.where(geoBit7 == 1, np.int64(1), np.int64(0))
        )

        dest_block['tdc']     = raw['tdc'].astype(np.int64)
        vmm = raw['vmm'].astype(np.int64)
        
        dest_block['vmm']     = vmm
        dest_block['asic']    = vmm & 0x1
        dest_block['hybrid']  = (vmm & 0xE) >> 1
        dest_block['channel'] = raw['channel'].astype(np.int64)


class VMMClusteredDecoder(BaseHardwareDecoder):
    """
    Decoder for VMM3A electronics in clustered mode.

    Readout layout (20 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length    uint16 LE
        [4:8]   timeHI    uint32 LE
        [8:12]  timeLO    uint32 LE
        [12:14] ADC0temp  uint16 LE  →  adc0 = & 0x1FFF, mult0 = >> 13
        [14:16] ADC1temp  uint16 LE  →  adc1 = & 0x1FFF, mult1 = >> 13
        [16]    G0GEO     uint8      →  geo = & 0x3F, g0 via mode bits
        [17]    hybrid    uint8
        [18]    channel0  uint8
        [19]    channel1  uint8
    """

    _CANONICAL_INSTR_ID = 72  # FREIA — all VMM instruments share 20-byte readouts

    _READOUT_DTYPE = np.dtype([
        ('ring_raw', '<u1'),
        ('fen',      '<u1'),
        ('length',   '<u2'),
        ('timeHI',   '<u4'),
        ('timeLO',   '<u4'),
        ('adc0temp', '<u2'),
        ('adc1temp', '<u2'),
        ('g0geo',    '<u1'),
        ('hybrid',   '<u1'),
        ('channel0', '<u1'),
        ('channel1', '<u1'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        adc0temp = raw['adc0temp'].astype(np.int64)
        dest_block['adc0']  = adc0temp & 0x1FFF
        dest_block['mult0'] = adc0temp >> 13

        adc1temp = raw['adc1temp'].astype(np.int64)
        dest_block['adc1']  = adc1temp & 0x1FFF
        dest_block['mult1'] = adc1temp >> 13

        g0geo = raw['g0geo'].astype(np.int64)
        dest_block['geo'] = g0geo & 0x3F
        temp    = (g0geo & 0xC0) >> 6
        geoBit6 = temp & 0x1
        geoBit7 = (temp & 0x2) >> 1
        dest_block['g0'] = np.where(
            geoBit6 == 1, np.int64(2),
            np.where(geoBit7 == 1, np.int64(1), np.int64(0))
        )
        
        dest_block['hybrid']   = raw['hybrid'].astype(np.int64)
        dest_block['channel0'] = raw['channel0'].astype(np.int64)
        dest_block['channel1'] = raw['channel1'].astype(np.int64)


class R5560Decoder(BaseHardwareDecoder):
    """
    Decoder for CAEN R5560 electronics (Helium-3 gas tubes).

    Readout layout (24 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length    uint16 LE
        [4:8]   timeHI    uint32 LE
        [8:12]  timeLO    uint32 LE
        [12]    padding   (unused)
        [13]    tube      uint8
        [14:16] counter1  uint16 LE
        [16:18] ampA      uint16 LE
        [18:20] ampB      uint16 LE
        [20:24] counter2  uint32 LE
    """

    _CANONICAL_INSTR_ID = 60  # CSPEC — all R5560 instruments share 24-byte readouts

    _READOUT_DTYPE = np.dtype([
        ('ring_raw', '<u1'),
        ('fen',      '<u1'),
        ('length',   '<u2'),
        ('timeHI',   '<u4'),
        ('timeLO',   '<u4'),
        ('pad',      '<u1'),
        ('tube',     '<u1'),
        ('counter1', '<u2'),
        ('ampA',     '<u2'),
        ('ampB',     '<u2'),
        ('counter2', '<u4'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        dest_block['tube']     = raw['tube'].astype(np.int64)
        dest_block['counter1'] = raw['counter1'].astype(np.int64)
        dest_block['ampA']     = raw['ampA'].astype(np.int64)
        dest_block['ampB']     = raw['ampB'].astype(np.int64)
        dest_block['counter2'] = raw['counter2'].astype(np.int64)


class SkadiDecoder(BaseHardwareDecoder):
    """
    Decoder for SKADI detector electronics.

    Readout layout (20 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length       uint16 LE
        [4:8]   timeHI       uint32 LE
        [8:12]  timeLO       uint32 LE
        [12]    opModeFlags  uint8  →  opMode = (& 0xF0) >> 4, flag = & 0x0F
        [13]    sysID        uint8
        [14]    IP           uint8
        [15]    channel      uint8
        [16]    column       uint8
        [17]    row          uint8
        [18:20] adc          uint16 LE
    """

    _CANONICAL_INSTR_ID = 32  # SKADI

    _READOUT_DTYPE = np.dtype([
        ('ring_raw',    '<u1'),
        ('fen',         '<u1'),
        ('length',      '<u2'),
        ('timeHI',      '<u4'),
        ('timeLO',      '<u4'),
        ('opModeFlags', '<u1'),
        ('sysID',       '<u1'),
        ('IP',          '<u1'),
        ('channel',     '<u1'),
        ('column',      '<u1'),
        ('row',         '<u1'),
        ('adc',         '<u2'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        opModeFlags = raw['opModeFlags'].astype(np.int64)
        dest_block['opMode']  = (opModeFlags & 0xF0) >> 4
        dest_block['flag']    = opModeFlags & 0x0F
        dest_block['sysID']   = raw['sysID'].astype(np.int64)
        dest_block['IP']      = raw['IP'].astype(np.int64)
        dest_block['channel'] = raw['channel'].astype(np.int64)
        dest_block['column']  = raw['column'].astype(np.int64)
        dest_block['row']     = raw['row'].astype(np.int64)
        dest_block['adc']     = raw['adc'].astype(np.int64)


class BMDecoder(BaseHardwareDecoder):
    """
    Decoder for Generic Beam Monitor hardware.

    Readout layout (20 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length  uint16 LE
        [4:8]   timeHI  uint32 LE
        [8:12]  timeLO  uint32 LE
        [12]    type    uint8
        [13]    channel uint8
        [14:16] adc     uint16 LE
        [16:18] posX    uint16 LE
        [18:20] posY    uint16 LE
    """

    _CANONICAL_INSTR_ID = 16  # BM

    _READOUT_DTYPE = np.dtype([
        ('ring_raw', '<u1'),
        ('fen',      '<u1'),
        ('length',   '<u2'),
        ('timeHI',   '<u4'),
        ('timeLO',   '<u4'),
        ('type',     '<u1'),
        ('channel',  '<u1'),
        ('adc',      '<u2'),
        ('posX',     '<u2'),
        ('posY',     '<u2'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        dest_block['type']    = raw['type'].astype(np.int64)
        dest_block['channel'] = raw['channel'].astype(np.int64)
        dest_block['adc']     = raw['adc'].astype(np.int64)
        dest_block['posX']    = raw['posX'].astype(np.int64)
        dest_block['posY']    = raw['posY'].astype(np.int64)


class IBMMonitorDecoder(BaseHardwareDecoder):
    """
    Decoder for IBM-variant Beam Monitor hardware.

    Readout layout (20 bytes):
        [0]     physical ring  →  ring = byte // 2
        [1]     fen
        [2:4]   length   uint16 LE
        [4:8]   timeHI   uint32 LE
        [8:12]  timeLO   uint32 LE
        [12]    type     uint8
        [13]    channel  uint8
        [14:16] debug    uint16 LE
        [16:19] temp     3-byte LE  (no native numpy type; split into three uint8 fields)
        [19]    mcaSum   uint8
        adc = temp // mcaSum  if mcaSum > 0, else 0
    """

    _CANONICAL_INSTR_ID = 16  # BM — IBM shares the same 20-byte readout size

    _READOUT_DTYPE = np.dtype([
        ('ring_raw', '<u1'),
        ('fen',      '<u1'),
        ('length',   '<u2'),
        ('timeHI',   '<u4'),
        ('timeLO',   '<u4'),
        ('type',     '<u1'),
        ('channel',  '<u1'),
        ('debug',    '<u2'),
        ('temp0',    '<u1'),   # byte 16 — LSB of 3-byte temp
        ('temp1',    '<u1'),   # byte 17
        ('temp2',    '<u1'),   # byte 18 — MSB of 3-byte temp
        ('mcaSum',   '<u1'),
    ], align=False)

    def __init__(self, ns_per_clock_tick: float, reader) -> None:
        readout_size, _ = get_readout_spec(self._CANONICAL_INSTR_ID)
        super().__init__(ns_per_clock_tick, reader, readout_size)

    def decode(self, packet_data, data_start_idx, n_readouts, dest_block):
        raw = np.frombuffer(packet_data, dtype=self._READOUT_DTYPE,
                            count=n_readouts, offset=data_start_idx)

        self.decode_common_fields(raw, dest_block)

        dest_block['type']    = raw['type'].astype(np.int64)
        dest_block['channel'] = raw['channel'].astype(np.int64)
        dest_block['debug']   = raw['debug'].astype(np.int64)

        # ---------------------------------------------------------------------
        # RECONSTRUCTION PASS: Rebuild the total 24-bit integrated charge.
        # Cast to int64 FIRST before execution to prevent intermediate int32 overflow.
        # ---------------------------------------------------------------------
        t0 = raw['temp0'].astype(np.int64)
        t1 = raw['temp1'].astype(np.int64) << 8
        t2 = raw['temp2'].astype(np.int64) << 16
        temp = t0 + t1 + t2

        mcaSum = raw['mcaSum'].astype(np.int64)
        dest_block['mcaSum'] = mcaSum
        
        # ---------------------------------------------------------------------
        # HISTOGRAM ALIGNMENT MATH: Calculate Average Pulse Height
        #
        # NOTE: 'temp' holds the true, cumulative 24-bit ADC value accumulated 
        # over the exposure window. However, downstream MBUTY analysis scripts 
        # expect the ['adc'] column to contain the AVERAGE charge per neutron hit.
        # We divide the total charge ('temp') by the total trigger count ('mcaSum') 
        # to log this average pulse height and maintain historical pipeline compatibility.
        # ---------------------------------------------------------------------
        dest_block['adc'] = np.where(mcaSum > 0, temp // mcaSum, np.int64(0))