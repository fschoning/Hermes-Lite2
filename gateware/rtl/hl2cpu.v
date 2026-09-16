// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Soft RISC-V CPU system for the HL2 raw front-end image (hl2b5up_raw). See docs/rawfront/RISCV.md.
// CORE = 2 (NEORV32) is the released configuration. CORE = 1 (VexRiscv Min) was used by an earlier
// development image and needs rtl/cpu/VexRiscv_Min.v, which is not part of this release
// (docs/rawfront/HISTORY.md).
//
//   hl2cpu    CPU core with boot ROM, RAM, system block (ID, 1 ms timer, IRQ, bridge-only
//             reset/halt), packet interface, flash-sector commands and a read-only mirror of the
//             bridge status registers. Everything runs on the CPU clock (12.5 MHz).
//   wb_cdc    Wishbone request from the layer-1 bridge (Ethernet send clock) into the CPU clock.
//             The bridge has priority on the CPU bus and does not depend on the CPU: it can halt
//             or reset the CPU and read/write RAM with the CPU held in reset, halted or crashed.
//   pbuf_ram  1,024-byte dual-clock packet buffer shared with the bridge: bridge replies (0-255),
//             CPU transmit buffer (256-511), CPU receive ring (512-1023).
//
// CPU memory map (byte addresses):
//   0x0000_0000  RAM (RAM_WORDS x 4 bytes); the boot ROM uses the first 2 kB, applications load at 0x800
//   0x0001_0000  boot ROM (ROM_WORDS x 4 bytes), reset vector
//   0x2000_0000  packet buffer, one byte per 32-bit word (byte n at 0x2000_0000 + 4n); the CPU writes only
//                the transmit part (bytes 0x100-0x1FF)
//   0x4000_0000  read-only mirror of the bridge status registers (ID, version, capabilities, slow ADC,
//                inputs, transmit-safety byte)
//   0x4001_0000  system block, 0x4002_0000 packet interface, 0x4003_0000 flash sector
//   0x4004_0000  (IO = 1) front-end I/O block and transmit interlock, rtl/hl2io.v (outside this module)
// Cores: CORE = 1 VexRiscv Min (rv32i, rtl/cpu/VexRiscv_Min.v), CORE = 2 NEORV32 rv32imc (rtl/neorv32,
// external bus). The memory map is the same; SYS_INFO bits 31:24 (map version) tell them apart (1, 2).
// VexRiscv Min has no WFI; a write to SYS_SLEEP (0x4001_0034) stops the CPU bus instead until an
// enabled interrupt is pending, so an idle CPU does not toggle its logic. NEORV32 has WFI and ignores
// SYS_SLEEP. SYS_STEP (0x4001_0038, NEORV32 only) holds the machine software interrupt active: the boot
// ROM's gdb single step (NEORV32 takes an interrupt only after the instruction it is executing).
// The CPU has no path to any transmit-related output.

module hl2cpu #(
  parameter        CORE          = 1,               // 1 VexRiscv Min, 2 NEORV32 rv32imc
  parameter        ROM_WORDS     = 1536,
  parameter        RAM_WORDS     = 4096,
  parameter        ROM_HEX       = "bootrom.hex",   // simulation; Quartus uses bootrom.mif (attribute below)
  parameter [7:0]  VERSION_MAJOR = 8'd0,
  parameter [7:0]  VERSION_MINOR = 8'd0,
  parameter [7:0]  DIAG_ID       = 8'd0,
  parameter [15:0] CAPS          = 16'd0,
  parameter        MS_DIV        = 12500,           // CPU clock cycles per millisecond (smaller in simulation)
  parameter        IO            = 0                // 1: bus port for rtl/hl2io.v at 0x4004_0000
) (
  input                clk          ,     // CPU clock
  input                rst_async    ,     // high while the clocks are not ready
  // layer-1 bridge request (from wb_cdc, clk domain)
  input                br_req       ,
  input         [29:0] br_adr       ,
  input         [31:0] br_dat_w     ,
  input         [ 3:0] br_sel       ,
  input                br_we        ,
  output logic         br_done  = 1'b0,
  output logic  [31:0] br_dat_r = 32'd0,
  output logic         br_err   = 1'b0,
  // status for the read-only mirror (other domains, synchronised here)
  input                clk_ctrl     ,
  input         [52:0] ctrl_status  ,     // clk_ctrl: {inputs[4:0], temperature, fwd, rev, bias}
  input                clk_eth      ,
  input         [ 7:0] tx_status    ,     // clk_eth: transmit-safety byte
  // packet buffer port A and packet interface state from the bridge (clk_eth values)
  output        [ 9:0] pb_adr       ,
  output               pb_we        ,
  output        [ 7:0] pb_wd        ,
  input         [ 7:0] pb_q         ,
  input         [ 9:0] eth_rx_wr    ,     // clk_eth
  output logic  [ 9:0] rx_rd    = 10'd0,
  output logic         tx_req   = 1'b0,
  output logic  [ 8:0] tx_len   = 9'd0,
  input                eth_tx_done  ,     // clk_eth
  input                eth_dest     ,     // clk_eth
  input         [31:0] eth_counts   ,     // clk_eth {sent, receive ring drops}
  // flash sector commands to asmi_interface (clk_ctrl, falling edge)
  output logic         fl_req   = 1'b0,
  output logic  [ 2:0] fl_cmd   = 3'd0,
  output logic  [23:0] fl_addr  = 24'd0,
  output logic  [ 7:0] fl_data  = 8'd0,
  input                fl_done      ,
  input         [ 2:0] fl_status    ,     // {illegal, locked, rejected}
  input         [ 7:0] fl_rdata     ,
  // LED D5 override (asynchronous to the pin)
  output logic         led_en   = 1'b0,
  output logic         led_on   = 1'b0,
  output               cpu_running  ,     // CPU out of reset and not halted (for status)
  // IO = 1: register block at 0x4004_0000 (answers combinationally, like the registers here)
  output               io_wstb      ,
  output        [ 5:0] io_adr       ,
  output        [31:0] io_dw        ,
  output               io_from_br   ,
  input         [31:0] io_rdata     ,
  input                io_hit       ,
  input                io_wr_ok     ,
  output logic         ms_tick = 1'b0,
  output               sys_rst_o
);

localparam ROM_AW = $clog2(ROM_WORDS);
localparam RAM_AW = $clog2(RAM_WORDS);

//////////////////////////////////////////////////////////////////////////////
// Resets

(* preserve *) logic [2:0] rst_s = 3'b111;
always @(posedge clk or posedge rst_async)
  if (rst_async) rst_s <= 3'b111;
  else           rst_s <= {rst_s[1:0], 1'b0};
wire sys_rst = rst_s[2];

logic [3:0] ctrl      = 4'd0;           // {boot RAM, stay in ROM, halt, reset}; bridge writes only
logic [31:0] boot_addr = 32'h00000800;
wire  cpu_rst = sys_rst | ctrl[0];
wire  halt    = ctrl[1];
assign cpu_running = ~cpu_rst & ~halt;

//////////////////////////////////////////////////////////////////////////////
// Synchronisers for other domains

logic [52:0] ctrl_status_c;
logic [ 7:0] tx_status_c;
logic [ 9:0] rx_wr_c;
logic [31:0] counts_c;
cdc_word #(.W(53)) cdc_ctrl_i   (.clk_a(clk_ctrl), .d_a(ctrl_status), .clk_b(clk), .q_b(ctrl_status_c));
cdc_word #(.W(8))  cdc_txst_i   (.clk_a(clk_eth),  .d_a(tx_status),   .clk_b(clk), .q_b(tx_status_c));
cdc_word #(.W(10)) cdc_rxwr_i   (.clk_a(clk_eth),  .d_a(eth_rx_wr),   .clk_b(clk), .q_b(rx_wr_c));
cdc_word #(.W(32)) cdc_counts_i (.clk_a(clk_eth),  .d_a(eth_counts),  .clk_b(clk), .q_b(counts_c));

(* preserve *) logic [1:0] tx_done_s = 2'b00;
(* preserve *) logic [1:0] dest_s    = 2'b00;
(* preserve *) logic [1:0] fl_done_s = 2'b00;
always @(posedge clk) begin
  tx_done_s <= {tx_done_s[0], eth_tx_done};
  dest_s    <= {dest_s[0], eth_dest};
  fl_done_s <= {fl_done_s[0], fl_done};
end

//////////////////////////////////////////////////////////////////////////////
// CPU

logic        i_cyc, i_we, d_cyc, d_we;
logic [29:0] i_adr, d_adr;
logic [31:0] i_dw, d_dw;
logic [ 3:0] i_sel, d_sel;
logic        timer_irq, pkt_irq;
logic        step_irq = 1'b0;           // SYS_STEP: machine software interrupt (NEORV32 single step)

logic        bus_ack = 1'b0, bus_err = 1'b0;
logic [31:0] bus_dat_r;
logic [ 1:0] cur;                       // 0 none, 1 bridge, 2 CPU data bus, 3 CPU instruction bus

generate if (CORE == 1) begin: VEX
VexRiscv cpu_i (
  .externalResetVector   (32'h00010000),
  .timerInterrupt        (timer_irq),
  .softwareInterrupt     (1'b0),
  .externalInterruptArray({31'd0, pkt_irq}),
  .iBusWishbone_CYC      (i_cyc),
  .iBusWishbone_STB      (),
  .iBusWishbone_ACK      (bus_ack & (cur == 2'd3)),
  .iBusWishbone_WE       (i_we),
  .iBusWishbone_ADR      (i_adr),
  .iBusWishbone_DAT_MISO (bus_dat_r),
  .iBusWishbone_DAT_MOSI (i_dw),
  .iBusWishbone_SEL      (i_sel),
  .iBusWishbone_ERR      (1'b0),
  .iBusWishbone_CTI      (),
  .iBusWishbone_BTE      (),
  .dBusWishbone_CYC      (d_cyc),
  .dBusWishbone_STB      (),
  .dBusWishbone_ACK      (bus_ack & (cur == 2'd2)),
  .dBusWishbone_WE       (d_we),
  .dBusWishbone_ADR      (d_adr),
  .dBusWishbone_DAT_MISO (bus_dat_r),
  .dBusWishbone_DAT_MOSI (d_dw),
  .dBusWishbone_SEL      (d_sel),
  .dBusWishbone_ERR      (1'b0),
  .dBusWishbone_CTI      (),
  .dBusWishbone_BTE      (),
  .clk                   (clk),
  .reset                 (cpu_rst)
);
end else begin: NEO
// NEORV32: one Wishbone-style external bus for fetches and data (byte addresses, word-aligned
// fetches); request fields stay stable until the acknowledge. No bus timeout inside the core, so
// the bridge and halt may hold an access for any time.
logic [31:0] x_adr;
neorv32_hl2 cpu_i (
  .clk_i      (clk),
  .rstn_i     (~cpu_rst),
  .xbus_adr_o (x_adr),
  .xbus_dat_o (d_dw),
  .xbus_we_o  (d_we),
  .xbus_sel_o (d_sel),
  .xbus_stb_o (),
  .xbus_cyc_o (d_cyc),
  .xbus_tag_o (),
  .xbus_dat_i (bus_dat_r),
  .xbus_ack_i (bus_ack & (cur == 2'd2)),
  .xbus_err_i (1'b0),
  .irq_msi_i  (step_irq),
  .irq_mti_i  (timer_irq),
  .irq_mei_i  (pkt_irq)
);
assign d_adr = x_adr[31:2];
assign i_cyc = 1'b0;
assign i_we  = 1'b0;
assign i_adr = 30'd0;
assign i_dw  = 32'd0;
assign i_sel = 4'd0;
end endgenerate

//////////////////////////////////////////////////////////////////////////////
// Bus arbiter: bridge first, then data bus, then instruction bus. A transfer keeps its master
// until the slave answers (always the next cycle). Halt stops new CPU transfers only.

logic       locked = 1'b0;
logic [1:0] own    = 2'd0;
logic       sleeping = 1'b0;             // SYS_SLEEP: CPU stopped until an interrupt line is active
wire        cpu_go = ~halt & ~cpu_rst & ~sleeping;
wire  [1:0] pick   = br_req & ~br_done ? 2'd1 :
                     cpu_go & d_cyc     ? 2'd2 :
                     cpu_go & i_cyc     ? 2'd3 : 2'd0;
assign cur = locked ? own : pick;

logic [29:0] adr;
logic [31:0] dw;
logic [ 3:0] sel;
logic        we, stb;
always @* begin
  case (cur)
    2'd1:    begin adr = br_adr; dw = br_dat_w; sel = br_sel; we = br_we; end
    2'd2:    begin adr = d_adr;  dw = d_dw;     sel = d_sel;  we = d_we;  end
    default: begin adr = i_adr;  dw = i_dw;     sel = i_sel;  we = i_we;  end
  endcase
  stb = (cur != 2'd0) & ~bus_ack & ~bus_err;
end

always @(posedge clk) begin
  if (bus_ack | bus_err)   locked <= 1'b0;
  else if (cur != 2'd0)  begin locked <= 1'b1; own <= cur; end
end

//////////////////////////////////////////////////////////////////////////////
// Address decode (word addresses)

wire from_br  = (cur == 2'd1);
wire in_ram   = (adr[29:RAM_AW] == '0);
wire in_rom   = (adr[29:14] == 16'h0001) & (adr[13:0] < ROM_WORDS);     // 0x0001_0000
wire in_pbuf  = (adr[29:10] == 20'h20000);                   // 0x2000_0000-0x2000_0FFF
wire in_stat  = (adr[29:13] == 17'h08000);                   // 0x4000_0000-0x4000_7FFF
wire in_sys   = (adr[29:6] == 24'h400100);                   // 0x4001_0000-0x4001_00FF
wire in_pkt   = (adr[29:6] == 24'h400200);
wire in_fl    = (adr[29:6] == 24'h400300);
wire in_io    = (IO != 0) & (adr[29:6] == 24'h400400);

assign io_wstb    = stb & we & in_io;
assign io_adr     = adr[5:0];
assign io_dw      = dw;
assign io_from_br = from_br;
assign sys_rst_o  = sys_rst;

//////////////////////////////////////////////////////////////////////////////
// Memories

(* ram_init_file = "bootrom.mif" *) logic [31:0] rom [0:ROM_WORDS-1];
// synthesis translate_off
initial $readmemh(ROM_HEX, rom);
// synthesis translate_on
logic [31:0] rom_q = 32'd0;
always @(posedge clk) rom_q <= rom[adr[ROM_AW-1:0]];

logic [3:0][7:0] ram [0:RAM_WORDS-1];
logic [31:0]     ram_q = 32'd0;
wire             ram_we = stb & we & in_ram;
always @(posedge clk) begin
  if (ram_we) begin
    if (sel[0]) ram[adr[RAM_AW-1:0]][0] <= dw[7:0];
    if (sel[1]) ram[adr[RAM_AW-1:0]][1] <= dw[15:8];
    if (sel[2]) ram[adr[RAM_AW-1:0]][2] <= dw[23:16];
    if (sel[3]) ram[adr[RAM_AW-1:0]][3] <= dw[31:24];
  end
  ram_q <= ram[adr[RAM_AW-1:0]];
end

// packet buffer: one byte per word address (the CPU reads whole words and picks bytes itself)
wire [9:0] pb_byte = adr[9:0];
assign pb_adr = pb_byte;
assign pb_wd  = dw[7:0];
assign pb_we  = stb & we & in_pbuf & (pb_byte[9:8] == 2'b01);   // transmit part only

//////////////////////////////////////////////////////////////////////////////
// Registers

logic [31:0] fw_status = 32'd0, fw_result = 32'd0, scratch = 32'd0;
logic [31:0] ms = 32'd0, timer_cmp = 32'hffffffff;
logic [15:0] presc = 16'd0;
logic [ 1:0] irq_en = 2'b00;
logic        tpend = 1'b0;                  // SYS_MS >= compare (level, like RISC-V mtime/mtimecmp)
logic [15:0] resets = 16'd0;
logic        cpu_rst_d = 1'b1;
logic [ 7:0] fl_rdata_r = 8'd0;
logic [ 2:0] fl_status_r = 3'd0;

wire tx_busy = tx_req | tx_done_s[1];
wire fl_busy = fl_req | fl_done_s[1];
wire pkt_pend = (rx_wr_c != rx_rd);

assign timer_irq = tpend & irq_en[0];
assign pkt_irq   = pkt_pend & irq_en[1];

localparam [7:0] ROM_KB = ROM_WORDS / 256;
localparam [7:0] RAM_KB = RAM_WORDS / 256;
localparam [7:0] MAP_VER = CORE;                 // SYS_INFO [31:24]: memory map version = core

logic [31:0] rdata;
logic        hit;
logic        wr_ok;
always @* begin
  rdata = 32'hffffffff;
  hit   = 1'b1;
  wr_ok = 1'b0;
  if (in_ram) begin
    wr_ok = 1'b1;
  end else if (in_rom) begin
  end else if (in_pbuf) begin
    wr_ok = (pb_byte[9:8] == 2'b01);
  end else if (in_stat) begin
    case (adr[12:0])
      13'h0000: rdata = 32'h484c3242;
      13'h0001: rdata = {VERSION_MAJOR, VERSION_MINOR, DIAG_ID, 8'h01};
      13'h0003: rdata = {16'd0, CAPS};
      13'h0c00: rdata = {20'd0, ctrl_status_c[47:36]};
      13'h0c01: rdata = {20'd0, ctrl_status_c[35:24]};
      13'h0c02: rdata = {20'd0, ctrl_status_c[23:12]};
      13'h0c03: rdata = {20'd0, ctrl_status_c[11:0]};
      13'h1000: rdata = {27'd0, ctrl_status_c[52:48]};
      13'h1c00: rdata = {24'd0, tx_status_c};
      default:  hit = 1'b0;
    endcase
  end else if (in_sys) begin
    case (adr[5:0])
      6'h00: rdata = 32'h52563332;                                    // "RV32"
      6'h01: rdata = {MAP_VER, ROM_KB, RAM_KB, 8'h00};
      6'h02: begin rdata = {28'd0, ctrl}; wr_ok = from_br; end
      6'h03: begin rdata = boot_addr;     wr_ok = from_br; end
      6'h04: begin rdata = fw_status;     wr_ok = 1'b1; end
      6'h05: begin rdata = fw_result;     wr_ok = 1'b1; end
      6'h06: rdata = ms;
      6'h07: begin rdata = timer_cmp;     wr_ok = 1'b1; end
      6'h08: begin rdata = {30'd0, irq_en}; wr_ok = 1'b1; end
      6'h09: begin rdata = {30'd0, pkt_pend, tpend}; wr_ok = 1'b1; end
      6'h0a: begin rdata = {30'd0, led_en, led_on}; wr_ok = 1'b1; end
      6'h0b: rdata = {14'd0, halt, cpu_rst, resets};
      6'h0c: begin rdata = scratch;       wr_ok = 1'b1; end
      6'h0d: begin rdata = 32'd0;         wr_ok = ~from_br; end
      6'h0e: begin rdata = {31'd0, step_irq}; wr_ok = 1'b1; end
      default: hit = 1'b0;
    endcase
  end else if (in_pkt) begin
    case (adr[5:0])
      6'h00: rdata = {22'd0, rx_wr_c};
      6'h01: begin rdata = {22'd0, rx_rd}; wr_ok = 1'b1; end
      6'h02: begin rdata = {tx_busy, dest_s[1], 21'd0, tx_len}; wr_ok = 1'b1; end
      6'h03: rdata = counts_c;
      default: hit = 1'b0;
    endcase
  end else if (in_io) begin
    rdata = io_rdata;
    hit   = io_hit;
    wr_ok = io_wr_ok;
  end else if (in_fl) begin
    case (adr[5:0])
      6'h00: begin rdata = {8'd0, fl_addr}; wr_ok = ~fl_busy; end
      6'h01: begin rdata = {24'd0, fl_rdata_r}; wr_ok = ~fl_busy; end
      6'h02: begin rdata = {28'd0, fl_status_r, fl_busy}; wr_ok = 1'b1; end
      default: hit = 1'b0;
    endcase
  end else begin
    hit = 1'b0;
  end
end

logic mem_rd = 1'b0;
logic [31:0] reg_q = 32'd0;
logic [2:0]  src = 3'd0;                // 0 register, 1 RAM, 2 ROM, 3 packet buffer

always @(posedge clk) begin
  bus_ack <= 1'b0;
  bus_err <= 1'b0;
  if (stb) begin
    // unmapped addresses and refused writes: error for the bridge, ignored (reads 0xFFFFFFFF) for the CPU
    if (hit & (~we | wr_ok)) bus_ack <= 1'b1;
    else if (from_br)        bus_err <= 1'b1;
    else                     bus_ack <= 1'b1;
    reg_q  <= rdata;
    src    <= in_ram ? 3'd1 : in_rom ? 3'd2 : in_pbuf ? 3'd3 : 3'd0;
  end

  // bridge request completes
  if (from_br & (bus_ack | bus_err)) begin
    br_done  <= 1'b1;
    br_dat_r <= bus_dat_r;
    br_err   <= bus_err;
  end
  if (~br_req) br_done <= 1'b0;

  // 1 ms timer
  presc   <= presc + 16'd1;
  ms_tick <= 1'b0;
  if (presc == MS_DIV - 1) begin
    presc   <= 16'd0;
    ms      <= ms + 32'd1;
    ms_tick <= 1'b1;
  end

  // timer IRQ once when the millisecond count reaches the compare value, also when the value
  // is already in the past (for example after a debugger stop)
  tpend <= (ms >= timer_cmp);    // the handler moves the compare value to clear it

  // transmit handshake
  if (tx_req & tx_done_s[1]) tx_req <= 1'b0;

  // flash handshake
  if (fl_req & fl_done_s[1]) begin
    fl_req      <= 1'b0;
    fl_status_r <= fl_status;
    fl_rdata_r  <= fl_rdata;
  end

  if (timer_irq | pkt_irq | cpu_rst) sleeping <= 1'b0;
  cpu_rst_d <= cpu_rst;
  if (cpu_rst & ~cpu_rst_d) resets <= resets + 16'd1;

  if (stb & we & wr_ok & hit) begin
    if (in_sys) case (adr[5:0])
      6'h02: ctrl      <= dw[3:0];
      6'h03: boot_addr <= dw;
      6'h04: fw_status <= dw;
      6'h05: fw_result <= dw;
      6'h07: timer_cmp <= dw;
      6'h08: irq_en    <= dw[1:0];
      6'h0a: {led_en, led_on} <= dw[1:0];
      6'h0c: scratch   <= dw;
      6'h0d: sleeping  <= (CORE == 1);
      6'h0e: step_irq  <= dw[0] & (CORE == 2);
      default: ;
    endcase
    if (in_pkt) case (adr[5:0])
      6'h01: rx_rd <= dw[9:0];
      6'h02: if (~tx_busy && dw[8:0] != 9'd0) begin
               tx_len <= (dw[15:0] > 16'd256) ? 9'd256 : dw[8:0];
               tx_req <= 1'b1;
             end
      default: ;
    endcase
    if (in_fl) case (adr[5:0])
      6'h00: fl_addr <= dw[23:0];
      6'h01: fl_data <= dw[7:0];
      6'h02: if (~fl_busy && dw[2:0] != 3'd0) begin
               fl_cmd <= dw[2:0];
               fl_req <= 1'b1;
             end
      default: ;
    endcase
  end

  // a CPU reset clears the CPU-owned settings (not the bridge's control, the receive pointer or
  // requests already handed to the network side or the flash)
  if (cpu_rst) begin
    irq_en    <= 2'b00;
    timer_cmp <= 32'hffffffff;
    led_en    <= 1'b0;
    led_on    <= 1'b0;
    step_irq  <= 1'b0;
  end
  if (sys_rst) ctrl <= 4'd0;
end

always @* begin
  case (src)
    3'd1:    bus_dat_r = ram_q;
    3'd2:    bus_dat_r = rom_q;
    3'd3:    bus_dat_r = {24'd0, pb_q};
    default: bus_dat_r = reg_q;
  endcase
end

endmodule


//////////////////////////////////////////////////////////////////////////////
// Wishbone request from the bridge (clk_m) into the CPU clock (clk_s), four-phase handshake.
// The bridge master sees one request at a time; its fields are held stable while it crosses.

module wb_cdc (
  input                clk_m        ,
  input         [29:0] m_adr        ,
  input         [31:0] m_dat_w      ,
  input         [ 3:0] m_sel        ,
  input                m_we         ,
  input                m_stb        ,
  output logic  [31:0] m_dat_r = 32'd0,
  output logic         m_ack   = 1'b0,
  output logic         m_err   = 1'b0,
  input                clk_s        ,
  output logic         s_req   = 1'b0,
  output logic  [29:0] s_adr   = 30'd0,
  output logic  [31:0] s_dat_w = 32'd0,
  output logic  [ 3:0] s_sel   = 4'd0,
  output logic         s_we    = 1'b0,
  input                s_done       ,
  input         [31:0] s_dat_r      ,
  input                s_err
);

logic req = 1'b0;
(* preserve *) logic [1:0] done_m = 2'b00;
(* preserve *) logic [1:0] req_s  = 2'b00;

always @(posedge clk_m) begin
  done_m <= {done_m[0], s_done};
  m_ack  <= 1'b0;
  m_err  <= 1'b0;
  if (~req & m_stb & ~m_ack & ~m_err & ~done_m[1]) begin
    req     <= 1'b1;
    s_adr   <= m_adr;
    s_dat_w <= m_dat_w;
    s_sel   <= m_sel;
    s_we    <= m_we;
  end
  if (req & done_m[1]) begin
    req     <= 1'b0;
    m_ack   <= ~s_err;
    m_err   <= s_err;
    m_dat_r <= s_dat_r;
  end
end

always @(posedge clk_s) begin
  req_s <= {req_s[0], req};
  s_req <= req_s[1];
end

endmodule


//////////////////////////////////////////////////////////////////////////////
// 1,024-byte true dual-port packet buffer, one clock per port

module pbuf_ram (
  input               clk_a,
  input        [9:0]  adr_a,
  input               we_a,
  input        [7:0]  wd_a,
  output logic [7:0]  q_a = 8'd0,
  input               clk_b,
  input        [9:0]  adr_b,
  input               we_b,
  input        [7:0]  wd_b,
  output logic [7:0]  q_b = 8'd0
);

logic [7:0] mem [0:1023];

always @(posedge clk_a) begin
  if (we_a) begin
    mem[adr_a] <= wd_a;
    q_a <= wd_a;
  end else begin
    q_a <= mem[adr_a];
  end
end

always @(posedge clk_b) begin
  if (we_b) begin
    mem[adr_b] <= wd_b;
    q_b <= wd_b;
  end else begin
    q_b <= mem[adr_b];
  end
end

endmodule
