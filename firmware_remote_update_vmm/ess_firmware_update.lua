-- ess_firmware_update_header_protocol.lua
--
-- Wireshark Lua dissector for ESS slow-control firmware-update / AXI-Lite bridge.
--
-- Confirmed ESS slow-control framing:
--
--   WRITE request:
--      u32 WRITE_HEAD = 0xE55C0003
--      N x entries:   u32 addr, u32 data
--
--   WRITE reply:
--      u32 WRITE_RESP = 0xE55C0004
--      N x entries:   u32 addr, u32 data, u32 status
--
--   READ request:
--      u32 READ_HEAD = 0xE55C0001
--      N x entries:  u32 addr
--
--   READ reply:
--      u32 READ_RESP = 0xE55C0002
--      N x entries:  u32 addr, u32 data, u32 status
--
-- Firmware-update staging frame:
--   stage[0]      opcode
--   stage[1]      AXI/flash address
--   stage[2..65]  payload/result words 0..63
--   stage[66]     checksum on write, bridge status on read

local essfw = Proto("essfwup", "ESS Firmware Update Slow Control")

local f = essfw.fields

f.header        = ProtoField.uint32("essfwup.header", "Packet Command", base.HEX)
f.msg_type      = ProtoField.string("essfwup.msg_type", "Message Type")
f.entry_index   = ProtoField.uint32("essfwup.entry.index", "Entry Index", base.DEC)
f.addr          = ProtoField.uint32("essfwup.addr", "Address", base.HEX)
f.data          = ProtoField.uint32("essfwup.data", "Data", base.HEX)
f.status        = ProtoField.uint32("essfwup.status", "ESS/AXI Status", base.HEX)
f.status_axi    = ProtoField.uint8("essfwup.status.axi_resp", "AXI Response", base.HEX)
f.status_fwmask = ProtoField.uint16("essfwup.status.firewall_mask", "Firewall Mask", base.HEX)

f.stage_index   = ProtoField.uint32("essfwup.stage.index", "Stage Index", base.DEC)
f.cmd_word      = ProtoField.string("essfwup.cmd.word", "Command Word")
f.cmd_opcode    = ProtoField.uint32("essfwup.cmd.opcode", "Bridge Opcode", base.HEX)
f.cmd_opcode_s  = ProtoField.string("essfwup.cmd.opcode_name", "Bridge Opcode Name")
f.cmd_axi_addr  = ProtoField.uint32("essfwup.cmd.axi_addr", "Target AXI/Flash Address", base.HEX)
f.cmd_payload   = ProtoField.uint32("essfwup.cmd.payload", "Payload/Result Word", base.HEX)
f.cmd_payload_i = ProtoField.uint32("essfwup.cmd.payload.index", "Payload/Result Index", base.DEC)
f.cmd_checksum  = ProtoField.uint32("essfwup.cmd.checksum", "Command Checksum", base.HEX)
f.cmd_status    = ProtoField.uint32("essfwup.cmd.status", "Bridge Status", base.HEX)
f.cmd_state     = ProtoField.string("essfwup.cmd.state", "Bridge State")
f.cmd_code      = ProtoField.uint16("essfwup.cmd.code", "Bridge Status Code", base.HEX)
f.cmd_code_s    = ProtoField.string("essfwup.cmd.code_name", "Bridge Status Name")
f.cmd_csum_calc = ProtoField.uint32("essfwup.cmd.checksum_calc", "Calculated Checksum", base.HEX)
f.cmd_csum_ok   = ProtoField.bool("essfwup.cmd.checksum_ok", "Checksum OK")

essfw.prefs.udp_port = Pref.uint("UDP port", 65535, "ESS slow-control UDP port")
essfw.prefs.cmd_base = Pref.uint("Command register base", 0x00000000, "Base address of mem_flash/stage[0]")
essfw.prefs.decode_cmd = Pref.bool("Decode command frame", true, "Decode mem_flash/stage[0..66]")
essfw.prefs.try_heuristic = Pref.bool("Try heuristic decode", true, "Decode ESS packets even when not on configured UDP port")

local WRITE_HEAD = 0xE55C0003
local READ_HEAD  = 0xE55C0001
local WRITE_RESP = 0xE55C0004
local READ_RESP  = 0xE55C0002

local OP_WRITE32    = 0x00000001
local OP_READ32     = 0x00000002
local OP_WRITE_PAGE = 0x00000010
local OP_READ_PAGE  = 0x00000011
local OP_PING       = 0x0000007F

local STS_OK          = 0x0000
local STS_BAD_OPCODE  = 0x0001
local STS_CSUM_ERR    = 0x0002
local STS_AXI_TIMEOUT = 0x0003
local STS_AXI_RESP    = 0x0004

local udp_table = DissectorTable.get("udp.port")
local registered_port = nil

local bit = bit32

local function u32(x)
   return bit.band(x, 0xFFFFFFFF)
end

local function rol32(x, n)
   x = u32(x)
   n = n % 32
   if n == 0 then return x end
   return u32(bit.bor(bit.lshift(x, n), bit.rshift(x, 32 - n)))
end

local function calc_checksum(opcode, addr, payload)
   local csum = 0xA5A55A5A
   csum = bit.bxor(csum, rol32(opcode, 1))
   csum = bit.bxor(csum, rol32(addr, 7))
   for i = 0, 63 do
      local word = payload[i] or 0
      csum = bit.bxor(csum, rol32(word, (i % 31) + 1))
      csum = u32(csum)
   end
   return csum
end

local function opcode_name(opcode)
   if opcode == OP_WRITE32 then
      return "WRITE32"
   elseif opcode == OP_READ32 then
      return "READ32"
   elseif opcode == OP_WRITE_PAGE then
      return "WRITE_PAGE"
   elseif opcode == OP_READ_PAGE then
      return "READ_PAGE"
   elseif opcode == OP_PING then
      return "PING"
   else
      return string.format("UNKNOWN(0x%08X)", opcode)
   end
end

local function cmd_status_state(status)
   local top = bit.band(bit.rshift(status, 24), 0xFF)
   if top == 0x01 then
      return "busy/running"
   elseif top == 0x10 then
      return "done/not busy"
   else
      return string.format("unknown state 0x%02X", top)
   end
end

local function cmd_status_code_name(code)
   if code == STS_OK then
      return "OK"
   elseif code == STS_BAD_OPCODE then
      return "Bad opcode"
   elseif code == STS_CSUM_ERR then
      return "Checksum error"
   elseif code == STS_AXI_TIMEOUT then
      return "AXI timeout"
   elseif code == STS_AXI_RESP then
      return "AXI response error"
   else
      return string.format("Unknown 0x%04X", code)
   end
end

local function axi_status_name(status)
   local axi = bit.band(status, 0x3)
   if axi == 0 then
      return "OKAY"
   elseif axi == 1 then
      return "EXOKAY"
   elseif axi == 2 then
      return "SLVERR"
   elseif axi == 3 then
      return "DECERR"
   end
   return "UNKNOWN"
end

local function stage_index(addr)
   local base_addr = essfw.prefs.cmd_base
   if addr < base_addr then return nil end
   local off = addr - base_addr
   if bit.band(off, 0x3) ~= 0 then return nil end
   local idx = off / 4
   if idx < 0 or idx > 66 then return nil end
   return idx
end

local function cmd_word_name_from_index(idx)
   if idx == nil then return nil end
   if idx == 0 then
      return "opcode"
   elseif idx == 1 then
      return "address"
   elseif idx >= 2 and idx <= 65 then
      return string.format("payload/result[%d]", idx - 2)
   elseif idx == 66 then
      return "checksum/status"
   end
   return nil
end

local function looks_like_ess_packet(tvb)
   local len = tvb:len()
   if len < 8 then return false end
   local h = tvb(0, 4):uint()
   if h == WRITE_HEAD then return (len >= 12 and ((len - 4) % 8 == 0)) end
   if h == READ_HEAD  then return (len >= 8  and ((len - 4) % 4 == 0)) end
   if h == WRITE_RESP then return (len >= 16 and ((len - 4) % 12 == 0)) end
   if h == READ_RESP  then return (len >= 16 and ((len - 4) % 12 == 0)) end
   return false
end

local function add_ess_status_fields(tree_item, status_tvb, status)
   tree_item:add(f.status, status_tvb)
   tree_item:add(f.status_axi, bit.band(status, 0x3))
   tree_item:add(f.status_fwmask, bit.band(bit.rshift(status, 16), 0x0FFF))
end

local function add_stage_decode(et, addr, data, is_readback)
   local idx = stage_index(addr)
   local word = cmd_word_name_from_index(idx)
   if not word then return idx end

   et:add(f.stage_index, idx)
   et:add(f.cmd_word, word)

   if idx == 0 then
      et:add(f.cmd_opcode, data)
      et:add(f.cmd_opcode_s, opcode_name(data))
   elseif idx == 1 then
      et:add(f.cmd_axi_addr, data)
   elseif idx >= 2 and idx <= 65 then
      et:add(f.cmd_payload_i, idx - 2)
      et:add(f.cmd_payload, data)
   elseif idx == 66 then
      if is_readback then
         et:add(f.cmd_status, data)
         et:add(f.cmd_state, cmd_status_state(data))
         et:add(f.cmd_code, bit.band(data, 0xFFFF))
         et:add(f.cmd_code_s, cmd_status_code_name(bit.band(data, 0xFFFF)))
      else
         et:add(f.cmd_checksum, data)
      end
   end
   return idx
end

local function collect_stage_words(entries)
   local words = {}
   local present = {}
   for _, e in ipairs(entries) do
      local idx = stage_index(e.addr)
      if idx ~= nil then
         words[idx] = e.data
         present[idx] = true
      end
   end
   return words, present
end

local function decode_command_write_from_entries(tree, entries)
   if not essfw.prefs.decode_cmd then return end

   local words, present = collect_stage_words(entries)
   if not (present[0] and present[1] and present[66]) then return end

   local payload = {}
   for i = 0, 63 do
      payload[i] = words[i + 2] or 0
   end

   local calc = calc_checksum(words[0], words[1], payload)
   local got = words[66]
   local full = true
   for i = 0, 66 do
      if not present[i] then full = false end
   end

   local cmd_tree = tree:add(essfw, string.format(
      "Bridge Command Write: %s addr=0x%08X %s checksum=%s",
      opcode_name(words[0]), words[1], full and "67-word frame" or "short frame",
      (calc == got) and "OK" or "BAD"
   ))

   cmd_tree:add(f.cmd_opcode, words[0])
   cmd_tree:add(f.cmd_opcode_s, opcode_name(words[0]))
   cmd_tree:add(f.cmd_axi_addr, words[1])
   cmd_tree:add(f.cmd_checksum, got)
   cmd_tree:add(f.cmd_csum_calc, calc)
   cmd_tree:add(f.cmd_csum_ok, calc == got)

   if calc ~= got then
      cmd_tree:add_expert_info(PI_CHECKSUM, PI_ERROR,
         string.format("Command checksum mismatch: got 0x%08X expected 0x%08X", got, calc))
   end
end

local function decode_command_readback_from_entries(tree, entries)
   if not essfw.prefs.decode_cmd then return end

   local words, present = collect_stage_words(entries)
   if not (present[66] or present[2] or present[0]) then return end

   local status = words[66]
   local title
   if status then
      local code = bit.band(status, 0xFFFF)
      title = string.format("Bridge Readback: status=0x%08X (%s, %s)",
         status, cmd_status_state(status), cmd_status_code_name(code))
   else
      title = "Bridge Readback"
   end

   local cmd_tree = tree:add(essfw, title)

   if present[0] then
      cmd_tree:add(f.cmd_opcode, words[0])
      cmd_tree:add(f.cmd_opcode_s, opcode_name(words[0]))
   end
   if present[1] then
      cmd_tree:add(f.cmd_axi_addr, words[1])
   end
   if present[2] then
      cmd_tree:add(f.cmd_payload_i, 0)
      cmd_tree:add(f.cmd_payload, words[2])
   end
   if status then
      local code = bit.band(status, 0xFFFF)
      cmd_tree:add(f.cmd_status, status)
      cmd_tree:add(f.cmd_state, cmd_status_state(status))
      cmd_tree:add(f.cmd_code, code)
      cmd_tree:add(f.cmd_code_s, cmd_status_code_name(code))
      if code ~= STS_OK then
         cmd_tree:add_expert_info(PI_RESPONSE_CODE, PI_WARN,
            string.format("Bridge command status: %s", cmd_status_code_name(code)))
      end
   end
end

function essfw.dissector(tvb, pinfo, tree)
   local len = tvb:len()
   if len < 8 then return 0 end

   local h = tvb(0, 4):uint()

   local is_write_req   = (h == WRITE_HEAD and len >= 12 and ((len - 4) % 8 == 0))
   local is_read_req    = (h == READ_HEAD  and len >= 8  and ((len - 4) % 4 == 0))
   local is_write_reply = (h == WRITE_RESP and len >= 16 and ((len - 4) % 12 == 0))
   local is_read_reply  = (h == READ_RESP  and len >= 16 and ((len - 4) % 12 == 0))

   if not is_write_req and not is_read_req and not is_write_reply and not is_read_reply then
      return 0
   end

   pinfo.cols.protocol = "ESS-FWUP"
   local root = tree:add(essfw, tvb(), "ESS Firmware Update / Slow Control")
   root:add(f.header, tvb(0, 4))

   if is_write_req then
      local count = (len - 4) / 8
      pinfo.cols.info = string.format("ESS slow-control WRITE request, %d entr%s", count, count == 1 and "y" or "ies")
      root:add(f.msg_type, "WRITE request: header + N x (addr, data)")

      local entries = {}
      local off = 4
      for i = 0, count - 1 do
         local addr = tvb(off, 4):uint()
         local data = tvb(off + 4, 4):uint()

         local et = root:add(essfw, tvb(off, 8),
            string.format("Write entry %d: addr=0x%08X data=0x%08X", i, addr, data))
         et:add(f.entry_index, i)
         et:add(f.addr, tvb(off, 4))
         et:add(f.data, tvb(off + 4, 4))

         add_stage_decode(et, addr, data, false)
         table.insert(entries, { addr = addr, data = data })
         off = off + 8
      end

      decode_command_write_from_entries(root, entries)
      return len
   end

   if is_read_req then
      local count = (len - 4) / 4
      pinfo.cols.info = string.format("ESS slow-control READ request, %d entr%s", count, count == 1 and "y" or "ies")
      root:add(f.msg_type, "READ request: header + N x addr")

      local off = 4
      for i = 0, count - 1 do
         local addr = tvb(off, 4):uint()

         local et = root:add(essfw, tvb(off, 4),
            string.format("Read entry %d: addr=0x%08X", i, addr))
         et:add(f.entry_index, i)
         et:add(f.addr, tvb(off, 4))

         local idx = stage_index(addr)
         local word = cmd_word_name_from_index(idx)
         if word then
            et:add(f.stage_index, idx)
            et:add(f.cmd_word, word)
         end
         off = off + 4
      end

      return len
   end

   local is_write = is_write_reply
   local count = (len - 4) / 12
   pinfo.cols.info = string.format("ESS slow-control %s reply, %d entr%s",
      is_write and "WRITE" or "READ", count, count == 1 and "y" or "ies")
   root:add(f.msg_type, is_write and "WRITE reply: header + N x (addr, data, status)" or "READ reply: header + N x (addr, data, status)")

   local entries = {}
   local off = 4
   for i = 0, count - 1 do
      local addr   = tvb(off, 4):uint()
      local data   = tvb(off + 4, 4):uint()
      local status = tvb(off + 8, 4):uint()

      local et = root:add(essfw, tvb(off, 12),
         string.format("%s reply entry %d: addr=0x%08X data=0x%08X status=0x%08X (%s)",
            is_write and "Write" or "Read", i, addr, data, status, axi_status_name(status)))
      et:add(f.entry_index, i)
      et:add(f.addr, tvb(off, 4))
      et:add(f.data, tvb(off + 4, 4))
      add_ess_status_fields(et, tvb(off + 8, 4), status)

      add_stage_decode(et, addr, data, not is_write)

      if status ~= 0 then
         et:add_expert_info(PI_RESPONSE_CODE, PI_WARN,
            string.format("ESS/AXI status is non-zero: 0x%08X (%s)", status, axi_status_name(status)))
      end

      table.insert(entries, { addr = addr, data = data, status = status })
      off = off + 12
   end

   if not is_write then
      decode_command_readback_from_entries(root, entries)
   end
   return len
end

function essfw.init()
   if registered_port ~= nil then
      udp_table:remove(registered_port, essfw)
   end
   registered_port = essfw.prefs.udp_port
   udp_table:add(registered_port, essfw)
end

essfw:register_heuristic("udp", function(tvb, pinfo, tree)
   if not essfw.prefs.try_heuristic then return false end
   if not looks_like_ess_packet(tvb) then return false end
   local consumed = essfw.dissector(tvb, pinfo, tree)
   return consumed ~= 0
end)
