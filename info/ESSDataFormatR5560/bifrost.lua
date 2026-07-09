
-- Copyright (C) 2019 - 2023 European Spallation Source ERIC
-- Wireshark plugin for dissecting ESS Readout data for BIFROST

function i64_ax(h,l)
 local o = {}; o.l = l; o.h = h; return o;
end -- +assign 64-bit v.as 2 regs

function i64u(x)
 return ( ( (bit.rshift(x,1) * 2) + bit.band(x,1) ) % (0xFFFFFFFF+1));
end -- keeps [1+0..0xFFFFFFFFF]


function i64_toInt(a)
  return (a.l + (a.h * (0xFFFFFFFF+1)));
end

function i64_toString(a)
  local s1=string.format("%x",a.l);
  local s2=string.format("%x",a.h);
  return "0x"..string.upper(s2)..string.upper(s1);
end

resolution = 11.35686096363 -- ns per clock tick for 88.052500 MHz
-- -----------------------------------------------------------------------------------------------
-- the protocol dissector
-- -----------------------------------------------------------------------------------------------
essbifrost_proto = Proto("essreadout","ESSR Protocol")

min_time_s = 0
max_time_s = 0
min_time_ns = 0
max_time_ns = 0
total_cnt=0
--total_cnt_last = 0
function essbifrost_proto.dissector(buffer, pinfo, tree)
  -- helper variable and functions
  total_cnt_last = total_cnt

  esshdrsize = 30
  datasize = 20
  dataheadersize = 4

  pinfo.cols.protocol = "ESSR/BIFROST"

  protolen = buffer():len()
  esshdr = tree:add(essbifrost_proto,buffer(),"ESSR Header")

  padding = buffer(0,1):uint()
  version = buffer(1,1):uint()
  cookie = buffer(2,3):uint()
  datatype = buffer(5,1):uint()
  length = buffer(6,2):le_uint()
  oq = buffer(8,1):uint()
  tmsrc = buffer(9,1):uint()

  pth = buffer(10, 4):le_uint()
  ptl = buffer(14, 4):le_uint()
  ppth = buffer(18, 4):le_uint()
  pptl = buffer(22, 4):le_uint()
  seqno = buffer(26, 4):le_uint()

  esshdr:add(buffer( 0,1),string.format("Padding  0x%02x", padding))
  esshdr:add(buffer( 1,1),string.format("Version  %d", version))
  esshdr:add(buffer( 2,3),string.format("Cookie   0x%x", cookie))
  esshdr:add(buffer( 5,1),string.format("Type     0x%02x", datatype))
  esshdr:add(buffer( 6,2),string.format("Length   %d", length))
  esshdr:add(buffer( 8,1),string.format("OutputQ  %d", oq))
  esshdr:add(buffer( 9,1),string.format("TimeSrc  %d", tmsrc))

  trig = pth*1e9 + ptl*resolution
  esshdr:add(buffer(10,8),string.format("PulseT   0x%04x%04x, %d s %.1f ns", pth, ptl, pth,ptl*resolution))
  prevtrig = ppth*1e9 + pptl*resolution
  esshdr:add(buffer(18,8),string.format("PrevPT   0x%04x%04x, %d s %.1f ns", ppth, pptl, ppth,pptl*resolution))
  esshdr:add(buffer(26,4),string.format("SeqNo    %d", seqno))
  if version == 1 then
  	padding2 = buffer(30, 2):uint()
  	esshdr:add(buffer(30,2),string.format("Padding  0x%02x", padding2))	
  	esshdrsize = 32
  end 	
  bytesleft = protolen - esshdrsize
  offset = esshdrsize
  
  if bytesleft%6 > 0 then
  	pinfo.cols.info = "error length"
  end
   

  negTof = 0
  negPrevTof = 0
  cnt = 0
  
  
  while (bytesleft >= 24 )
  do
    cnt=cnt+1
    total_cnt=total_cnt+1
    fiber = buffer(offset, 1):uint()
    ringid = fiber/2
    fenid = buffer(offset + 1, 1):uint()
    dlen = buffer(offset + 2, 2):le_uint()
    readouts = (dlen - dataheadersize) / datasize
    dtree = esshdr:add(buffer(offset, 4),string.format("Fiber %d, Ring %d, FEN %d, Length %d, Readouts %d",
               fiber, ringid, fenid, dlen, readouts))

    bytesleft = bytesleft - dataheadersize
    offset = offset + dataheadersize

    if (readouts * datasize > bytesleft) then
      return
    end

    if (readouts > 0) then
      for i=1,readouts
      do
      	th = buffer(offset + 0, 4):le_uint()
        tl = buffer(offset + 4, 4):le_uint()
        tl_ns    = tl*resolution
		theTime = th*1e9 + tl*resolution
         
        
      if min_time_s > th or (min_time_s == th and min_time_ns > tl_ns)then
		min_time_s = th
		min_time_ns = tl_ns
  	end
  	if max_time_s < th or (max_time_s == th and max_time_ns < tl_ns)then
		max_time_s = th
		max_time_ns = tl_ns
  	end
	
		ampa = 0
		ampb = 0
		ampc=0
		ampd=0
		counter = 0
		om=0
		group=0
		seq=0
		instrument_bits=0
		tube=0
		instrument=0
		purB=0
		purA=0
		ovrA=0
		ovrB=0
		
	
    	  
      	 if theTime-prevtrig < 0 then
      	 	negPrevTof = negPrevTof + 1
      	 else
      	 	if theTime-trig < 0 then
      	 		negTof = negTof + 1
      	 	end
      	end

		
		if datatype == 0x30 then
			om = buffer(offset + 8, 1):uint()
			group = buffer(offset + 9, 1):uint()
			seq = buffer(offset + 10, 2):le_uint()
			ampa = buffer(offset + 12, 2):le_uint()
			ampb = buffer(offset + 14, 2):le_uint()
			ampc = buffer(offset + 16, 2):le_uint()
			ampd = buffer(offset + 18, 2):le_uint()
			dtree:add(buffer(offset + 0, datasize),string.format(
            "Time %d s %.1f ns, ToF %.1f ns, PrevToF %.1f ns, OM %3d, Group %3d, Seq %5d, A:%5d, B:%5d, C:%5d, D:%5d",
             th, tl_ns, theTime-trig, theTime-prevtrig, om, group, seq, ampa, ampb, ampc, ampd))

		
		else
		instrument_bits = buffer(offset + 8, 1):uint()
			tube = buffer(offset + 9, 1):uint()
			counter = buffer(offset + 10, 2):le_uint()
			instrument = bit.band(instrument_bits, 0x0F)
	
			purB = bit.band(bit.rshift(instrument_bits, 4), 1)
			purA = bit.band(bit.rshift(instrument_bits, 5), 1)
			ovrB = bit.band(bit.rshift(instrument_bits, 6), 1)
			ovrA = bit.band(bit.rshift(instrument_bits, 7), 1)
			ampa = buffer(offset + 12, 2):le_uint()
			ampb = buffer(offset + 14, 2):le_uint()
			counter = buffer(offset + 16, 4):le_uint()
        	dtree:add(buffer(offset + 0, datasize),string.format(
            "Time %d s %.1f ns, ToF %.1f ns, PrevToF %.1f ns, ovr A: %1d, OVR B: %1d, PUR A: %1d, PUR B: %1d, Tube: %1d, energy A: %5d, energy B: %5d, counter: %d",
             th, tl_ns, theTime-trig, theTime-prevtrig, ovrA,ovrB, purA, purB, tube, ampa, ampb, counter))
             
					end
		
        bytesleft = bytesleft - datasize
        offset = offset + datasize

      end
    end
   
  end
  	
  if cnt > 0 then
	pinfo.cols.info = string.format("Neg TOF %d, neg. prev. TOF %d rate %f hits %d", negTof, negPrevTof, (total_cnt-total_cnt_last)*1e+9/((max_time_s-min_time_s)*1e+9 + (max_time_ns-min_time_ns)),(total_cnt-total_cnt_last) )   
   else
	pinfo.cols.info = string.format("rate %f hits %d", (total_cnt-total_cnt_last)*1e+9/((max_time_s-min_time_s)*1e+9 + (max_time_ns-min_time_ns)), (total_cnt-total_cnt_last))  
	end


end

-- Register the protocol
udp_table = DissectorTable.get("udp.port")
udp_table:add(51001, essbifrost_proto)
udp_table:add(8997, essbifrost_proto)
udp_table:add(9000, essbifrost_proto)
udp_table:add(9001, essbifrost_proto)

