// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Front-end I/O block and hardware transmit interlock for the HL2 raw front-end release image
// (hl2b5up_raw, see docs/rawfront/PROTOCOL.md).
//
//   hl2io         Register block at 0x4004_0000 on the soft CPU bus (CPU clock). Reached by the CPU and,
//                 through wb_cdc, by the layer-1 bridge, also with the CPU held in reset, halted or
//                 crashed. Holds the transmit permission (lease) and interlock limits, the CPU
//                 watchdog, the command-bus injector (every openHPSDR command register: filters, gains,
//                 AD9866 SPI, Versa sequences, raw stream, duplex/echo, I2C), the I2C transfer
//                 register with its status, the bias-pot unlock, LED and fan overrides, raw input pins.
//   tx_interlock  Transmit interlock on the 2.5 MHz control clock. The only driver of the PA supply,
//                 PA bias, op-amp supply, both T/R relays, the RF path switch and the AD9866 transmit
//                 enable. Transmit is on only while the far side renews its permission (lease) and no
//                 cut-off is present: over-temperature (slow ADC value compared in logic), stale
//                 temperature reading, TX-inhibit input, CPU watchdog expiry, maximum key-down time.
//                 A cut-off that happens while transmit is requested, or a lease that runs out while
//                 keyed, latches a trip reason until an explicit clear. Power-up: everything off.
//
// Register map (byte offsets from 0x4004_0000; all little details in docs/rawfront/PROTOCOL.md):
//   0x00 R  ID 0x494F3031 "IO01"
//   0x04 RW TX_PERMIT   write [31:16] = 0x5458 ("TX"), [0] key, [1] PTT input keys, [2] key (tip) input
//                       keys: renews the lease. Writes with another key are ignored. Read: [2:0]
//   0x08 R  ILK_STATUS  [0] transmit on (relays or PA) [1] PA stage + DAC on [2] lease valid
//                       [3] transmit requested [4] trip latched [5] cut-off present [6] key bit
//                       [15:8] latched trip reasons [23:16] cut-offs now (reason bit order:
//                       0 lease, 1 over-temperature, 2 TX inhibit, 3 watchdog, 4 max key-down,
//                       5 temperature reading stale) [24] PA enable [25] T/R disable [26] VNA (cmd 0x09)
//   0x0C W  ILK_CLEAR   0x434C5452 ("CLTR"): clear trip reasons whose cut-off is gone
//   0x10 RW LEASE_MS    lease length, 10..1000 ms (default 100)
//   0x14 RW MAXKEY_S    maximum key-down, 1..600 s (default 600)
//   0x18 RW TEMP_LIMIT  over-temperature code, can only be lowered below the built-in 55 C (0x527)
//   0x1C R  KEYTIME     [19:10] seconds, [9:0] ms of the current key-down
//   0x20 RW WDOG        write 0x57444F47 ("WDOG"): kick and arm. Read [31] fired [30] armed [15:0] ms left
//   0x24 RW WDOG_MS     watchdog timeout, 10..60000 ms (default 1000)
//   0x28 W  WDOG_DISARM bridge only: bit 0 disarms and clears "fired"
//   0x2C RW CMD_DATA    32-bit value for the command bus
//   0x30 RW CMD_ADDR    write [5:0]: put (address, CMD_DATA) on the command bus (refused while busy).
//                       Read [31] busy [15:8] commands sent [5:0] last address
//   0x34 W  I2C_XFER    [31:30] bus 1/2/3, [24] read, [23] probe (address only, one byte read),
//                       [22:16] 7-bit address, [15:8] register, [7:0] value (refused while busy)
//   0x38 R  I2C_STATUS  [0] I2C engine busy [1] last transfer NACK [2] last request refused by the
//                       bias guard [3] last request dropped (I2C engine was busy) [4] request not yet
//                       on the command bus [23:16] transfers done [31:24] requests refused or dropped
//   0x3C R  I2C_RDATA   bytes read (first byte in [7:0]; probe: [31:24])
//   0x40 RW BIAS_UNLOCK write 0x42494153 ("BIAS") to allow writes to the bias pots / EEPROM at 0x2C
//   0x44 RW LED         [3:0] override D2..D5, [7:4] LED on
//   0x48 RW FAN         [3:0] minimum fan duty in 16ths (15 = always on); read [11:8] HDL fan state,
//                       [12] band volts on the fan pin
//   0x4C R  INPUTS      pins: [0] tip [1] ring [2] CN8 [3] CN9 [4] CN10 [5] DB1-2 [6] DB1-5
//                       [8:7] hl2link rx [12:9] TP2 TP7 TP8 TP9; debounced (1 = active): [16] key
//                       [17] PTT [18] TX inhibit
//   0x50 R  ADC_SEQ     [15:0] slow ADC read cycles completed

module hl2io #(
  parameter [11:0] TEMP_MAX = 12'h527          // 55 C, as the stock fan logic
) (
  input                clk          ,     // CPU clock
  input                sys_rst      ,
  input                ms_tick      ,     // one cycle per millisecond (hl2cpu)
  // bus from hl2cpu (combinational, same cycle as its decode)
  input         [ 5:0] adr          ,     // word offset
  input         [31:0] dw           ,
  input                wstb         ,     // write strobe for this block
  input                from_br      ,
  output logic  [31:0] rdata        ,
  output logic         hit          ,
  output logic         wr_ok        ,
  // control clock domain
  input                clk_ctrl     ,
  input                msec_ctrl    ,     // control.v msec_pulse
  input         [11:0] temperature  ,
  input                adc_tick     ,     // slow ADC read cycle done
  input                fan_overheat ,
  input         [ 2:0] db_inputs    ,     // {inhibit, ptt, key}, debounced, 1 = active
  input         [ 2:0] pa_cfg       ,     // {vna, tr_disable, pa_enable} from command 0x09
  input         [55:0] i2c_status   ,     // {rdata 32, refused 8, done 8, 4'b0, missed, refused, nack, busy}
  input         [15:0] adc_seq      ,
  input         [ 3:0] fan_state    ,
  output               bias_unlock_c,     // clk_ctrl
  output        [ 7:0] led_c        ,     // clk_ctrl {on[3:0], override[3:0]}
  output        [ 3:0] fan_min_c    ,     // clk_ctrl
  // interlock outputs (clk_ctrl registers)
  output               pwr_envpa    ,
  output               pwr_envop    ,
  output               pwr_envbias  ,
  output               pa_inttr     ,
  output               pa_exttr     ,
  output               rffe_rfsw_sel,
  output               dac_en       ,     // AD9866 transmit enable (synchronise in the AD9866 domain)
  output               tx_on        ,
  output        [31:0] ilk_status   ,     // clk_ctrl
  // raw pins (asynchronous)
  input         [12:0] pins         ,
  // command bus injector (handshake into cmd_merge, Ethernet receive domain)
  output logic         inj_req  = 1'b0,
  output logic  [ 5:0] inj_addr = 6'd0,
  output logic  [31:0] inj_data = 32'd0,
  input                inj_ack          // cmd_merge domain, synchronised here
);

localparam [31:0] ID        = 32'h494F3031;
localparam [15:0] K_PERMIT  = 16'h5458;
localparam [31:0] K_CLEAR   = 32'h434C5452;
localparam [31:0] K_WDOG    = 32'h57444F47;
localparam [31:0] K_BIAS    = 32'h42494153;

//////////////////////////////////////////////////////////////////////////////
// Registers (CPU clock)

logic        permit_tog = 1'b0, clear_tog = 1'b0;
logic [ 2:0] permit_bits = 3'd0;               // {cw_en, ptt_en, key}
logic [ 9:0] lease_ms  = 10'd100;
logic [ 9:0] maxkey_s  = 10'd600;
logic [11:0] temp_lim  = TEMP_MAX;
logic        wd_armed  = 1'b0, wd_fired = 1'b0;
logic [15:0] wd_ms     = 16'd1000, wd_left = 16'd0;
logic [31:0] cmd_data  = 32'd0;
logic [ 5:0] cmd_last  = 6'd0;
logic [ 7:0] n_inj     = 8'd0;
logic        bias_unl  = 1'b0;
logic [ 7:0] led       = 8'd0;
logic [ 3:0] fan_min   = 4'd0;

(* preserve *) logic [1:0] ack_s = 2'b00;
always @(posedge clk) ack_s <= {ack_s[0], inj_ack};
wire inj_busy = inj_req | ack_s[1];

(* preserve *) logic [12:0] pins_s1 = 13'd0, pins_s2 = 13'd0;
always @(posedge clk) begin pins_s1 <= pins; pins_s2 <= pins_s1; end

// status from the control clock
logic [31:0] ilk_c;
logic [19:0] keytime_c;
logic [55:0] i2c_c;
logic [15:0] adc_seq_c;
logic [ 3:0] fan_state_c;
logic [ 2:0] db_c;
logic [19:0] keytime;
cdc_word #(.W(131)) cdc_from_ctrl_i (
  .clk_a(clk_ctrl), .d_a({ilk_status, keytime, i2c_status, adc_seq, fan_state, db_inputs}),
  .clk_b(clk),      .q_b({ilk_c, keytime_c, i2c_c, adc_seq_c, fan_state_c, db_c}));

// decoded I2C request: bus 1 -> 0x3C, bus 2 -> 0x3D, bus 3 -> 0x3E; format of the stock 0x3C/0x3D
// commands ([31:25] = 0x03, [24] read, [22:16] address, [15:8] register, [7:0] value), [23] probe
wire [1:0] i2c_bus = dw[31:30];

always @* begin
  hit   = 1'b1;
  wr_ok = 1'b0;
  rdata = 32'd0;
  case (adr)
    6'h00: rdata = ID;
    6'h01: begin rdata = {29'd0, permit_bits}; wr_ok = 1'b1; end
    6'h02: rdata = ilk_c;
    6'h03: wr_ok = 1'b1;
    6'h04: begin rdata = {22'd0, lease_ms}; wr_ok = 1'b1; end
    6'h05: begin rdata = {22'd0, maxkey_s}; wr_ok = 1'b1; end
    6'h06: begin rdata = {20'd0, temp_lim}; wr_ok = 1'b1; end
    6'h07: rdata = {12'd0, keytime_c};
    6'h08: begin rdata = {wd_fired, wd_armed, 14'd0, wd_left}; wr_ok = 1'b1; end
    6'h09: begin rdata = {16'd0, wd_ms}; wr_ok = 1'b1; end
    6'h0a: wr_ok = from_br;
    6'h0b: begin rdata = cmd_data; wr_ok = 1'b1; end
    6'h0c: begin rdata = {inj_busy, 15'd0, n_inj, 2'd0, cmd_last}; wr_ok = ~inj_busy; end
    6'h0d: wr_ok = ~inj_busy & (i2c_bus != 2'd0);
    6'h0e: rdata = {i2c_c[23:16], i2c_c[15:8], 11'd0, inj_busy, i2c_c[3:0]};
    6'h0f: rdata = i2c_c[55:24];
    6'h10: begin rdata = {31'd0, bias_unl}; wr_ok = 1'b1; end
    6'h11: begin rdata = {24'd0, led}; wr_ok = 1'b1; end
    6'h12: begin rdata = {19'd0, fan_state_c[3], fan_state_c[2:0], 4'd0, fan_min}; wr_ok = 1'b1; end
    6'h13: rdata = {13'd0, db_c, 3'd0, pins_s2};
    6'h14: rdata = {16'd0, adc_seq_c};
    default: hit = 1'b0;
  endcase
end

always @(posedge clk) begin
  if (inj_req & ack_s[1]) inj_req <= 1'b0;

  // watchdog
  if (wd_armed & ms_tick) begin
    if (wd_left != 16'd0) wd_left <= wd_left - 16'd1;
    else                  wd_fired <= 1'b1;
  end

  if (wstb & hit & wr_ok) begin
    case (adr)
      6'h01: if (dw[31:16] == K_PERMIT) begin
               permit_bits <= dw[2:0];
               permit_tog  <= ~permit_tog;
             end
      6'h03: if (dw == K_CLEAR) clear_tog <= ~clear_tog;
      6'h04: lease_ms <= (dw < 32'd10) ? 10'd10 : (dw > 32'd1000) ? 10'd1000 : dw[9:0];
      6'h05: maxkey_s <= (dw < 32'd1) ? 10'd1 : (dw > 32'd600) ? 10'd600 : dw[9:0];
      6'h06: temp_lim <= (dw > {20'd0, TEMP_MAX}) ? TEMP_MAX : dw[11:0];
      6'h08: if (dw == K_WDOG) begin
               wd_armed <= 1'b1;
               wd_fired <= 1'b0;
               wd_left  <= wd_ms;
             end
      6'h09: wd_ms <= (dw < 32'd10) ? 16'd10 : (dw > 32'd60000) ? 16'd60000 : dw[15:0];
      6'h0a: if (dw[0]) begin wd_armed <= 1'b0; wd_fired <= 1'b0; end
      6'h0b: cmd_data <= dw;
      6'h0c: begin
               inj_addr <= dw[5:0];
               inj_data <= cmd_data;
               inj_req  <= 1'b1;
               cmd_last <= dw[5:0];
               n_inj    <= n_inj + 8'd1;
             end
      6'h0d: begin
               inj_addr <= (i2c_bus == 2'd1) ? 6'h3c : (i2c_bus == 2'd2) ? 6'h3d : 6'h3e;
               inj_data <= {7'h03, dw[24:0]};
               inj_req  <= 1'b1;
               n_inj    <= n_inj + 8'd1;
             end
      6'h10: bias_unl <= (dw == K_BIAS);
      6'h11: led      <= dw[7:0];
      6'h12: fan_min  <= dw[3:0];
      default: ;
    endcase
  end

  if (sys_rst) begin
    wd_armed <= 1'b0;
    wd_fired <= 1'b0;
  end
end

//////////////////////////////////////////////////////////////////////////////
// To the control clock

logic        permit_tog_c, clear_tog_c, wd_fired_c;
logic [ 2:0] permit_bits_c;
logic [ 9:0] lease_ms_c, maxkey_s_c;
logic [11:0] temp_lim_c;
cdc_word #(.W(51)) cdc_to_ctrl_i (
  .clk_a(clk),      .d_a({permit_tog, permit_bits, clear_tog, lease_ms, maxkey_s, temp_lim, wd_fired, bias_unl, led, fan_min}),
  .clk_b(clk_ctrl), .q_b({permit_tog_c, permit_bits_c, clear_tog_c, lease_ms_c, maxkey_s_c, temp_lim_c, wd_fired_c, bias_unlock_c, led_c, fan_min_c}));

tx_interlock #(.TEMP_MAX(TEMP_MAX)) tx_interlock_i (
  .clk          (clk_ctrl         ),
  .msec         (msec_ctrl        ),
  .permit_tog   (permit_tog_c     ),
  .key_req      (permit_bits_c[0] ),
  .ptt_en       (permit_bits_c[1] ),
  .cw_en        (permit_bits_c[2] ),
  .clear_tog    (clear_tog_c      ),
  .lease_ms     (lease_ms_c       ),
  .maxkey_s     (maxkey_s_c       ),
  .temp_limit   (temp_lim_c       ),
  .temperature  (temperature      ),
  .adc_tick     (adc_tick         ),
  .fan_overheat (fan_overheat     ),
  .inhibit      (db_inputs[2]     ),
  .ptt_in       (db_inputs[1]     ),
  .key_in       (db_inputs[0]     ),
  .wdog_fired   (wd_fired_c       ),
  .pa_enable    (pa_cfg[0]        ),
  .tr_disable   (pa_cfg[1]        ),
  .vna          (pa_cfg[2]        ),
  .pwr_envpa    (pwr_envpa        ),
  .pwr_envop    (pwr_envop        ),
  .pwr_envbias  (pwr_envbias      ),
  .pa_inttr     (pa_inttr         ),
  .pa_exttr     (pa_exttr         ),
  .rfsw_sel     (rffe_rfsw_sel    ),
  .dac_en       (dac_en           ),
  .tx_on        (tx_on            ),
  .status       (ilk_status       ),
  .keytime      (keytime          )
);

endmodule


//////////////////////////////////////////////////////////////////////////////
// Transmit interlock (control clock, 2.5 MHz). See the header of this file.

module tx_interlock #(
  parameter        LEASE_MAX_MS = 1000,
  parameter        KEY_MAX_S    = 600,
  parameter [11:0] TEMP_MAX     = 12'h527,
  parameter        SEQ_MS       = 10,          // relays settle before the PA and DAC come on / after they go off
  parameter        STALE_MS     = 1000         // temperature reading older than this: cut-off
) (
  input                clk          ,
  input                msec         ,
  input                permit_tog   ,     // changes on every accepted permission write
  input                key_req      ,
  input                ptt_en       ,
  input                cw_en        ,
  input                clear_tog    ,
  input         [ 9:0] lease_ms     ,
  input         [ 9:0] maxkey_s     ,
  input         [11:0] temp_limit   ,
  input         [11:0] temperature  ,
  input                adc_tick     ,
  input                fan_overheat ,
  input                inhibit      ,
  input                ptt_in       ,
  input                key_in       ,
  input                wdog_fired   ,
  input                pa_enable    ,
  input                tr_disable   ,
  input                vna          ,
  output logic         pwr_envpa   = 1'b0,
  output logic         pwr_envop   = 1'b0,
  output logic         pwr_envbias = 1'b0,
  output logic         pa_inttr    = 1'b0,
  output logic         pa_exttr    = 1'b0,
  output logic         rfsw_sel    = 1'b0,
  output logic         dac_en      = 1'b0,
  output               tx_on        ,
  output        [31:0] status       ,
  output        [19:0] keytime
);

localparam S_OFF = 2'd0, S_REL = 2'd1, S_ON = 2'd2, S_DROP = 2'd3;

logic        pt_d = 1'b0, cl_d = 1'b0;
logic [ 9:0] lease_left = 10'd0;
logic [ 5:0] trip       = 6'd0;
logic [ 1:0] st         = S_OFF;
logic [ 3:0] seq_t      = 4'd0;
logic [ 9:0] k_ms       = 10'd0, k_s = 10'd0;
logic [10:0] stale_ms   = STALE_MS[10:0];

wire        lease_valid = (lease_left != 10'd0);
wire [11:0] tlim  = (temp_limit < TEMP_MAX) ? temp_limit : TEMP_MAX;
wire [ 9:0] kmax  = (maxkey_s == 10'd0) ? 10'd1 : (maxkey_s > KEY_MAX_S[9:0]) ? KEY_MAX_S[9:0] : maxkey_s;
wire        req   = lease_valid & (key_req | (ptt_en & ptt_in) | (cw_en & key_in));
wire        keyed = (st == S_REL) | (st == S_ON);
wire        stale = (stale_ms >= STALE_MS[10:0]);
wire [ 5:0] cause = {stale, (k_s >= kmax), wdog_fired, inhibit, (temperature >= tlim) | fan_overheat, ~lease_valid};
wire        allowed = req & (trip == 6'd0) & (cause[5:1] == 5'd0);

always @(posedge clk) begin
  pt_d <= permit_tog;
  cl_d <= clear_tog;

  // lease
  if (permit_tog != pt_d)
    lease_left <= (lease_ms < 10'd10) ? 10'd10 : (lease_ms > LEASE_MAX_MS[9:0]) ? LEASE_MAX_MS[9:0] : lease_ms;
  else if (msec & lease_valid)
    lease_left <= lease_left - 10'd1;

  // temperature reading age
  if (adc_tick)                                stale_ms <= 11'd0;
  else if (msec & (stale_ms < STALE_MS[10:0])) stale_ms <= stale_ms + 11'd1;

  // key-down time: counts while the PA stage is on, restarts when the request drops
  if (~req) begin
    k_ms <= 10'd0;
    k_s  <= 10'd0;
  end else if (msec & (st == S_ON) & (k_s < kmax)) begin
    if (k_ms == 10'd999) begin k_ms <= 10'd0; k_s <= k_s + 10'd1; end
    else k_ms <= k_ms + 10'd1;
  end

  // trips: a cut-off while transmit is requested; the lease running out while keyed
  if (clear_tog != cl_d) begin
    trip <= {trip[5:1] & cause[5:1], 1'b0};
  end else begin
    trip[5:1] <= trip[5:1] | (cause[5:1] & {5{req}});
    if (msec & (lease_left == 10'd1) & (permit_tog == pt_d) & keyed) trip[0] <= 1'b1;
  end

  // sequencer: relays first, PA and DAC SEQ_MS later; PA and DAC off first, relays SEQ_MS later
  case (st)
    S_OFF:  if (allowed) begin st <= S_REL; seq_t <= SEQ_MS[3:0]; end
    S_REL:  if (~allowed) st <= S_OFF;
            else if (msec) begin
              if (seq_t == 4'd0) st <= S_ON;
              else seq_t <= seq_t - 4'd1;
            end
    S_ON:   if (~allowed) begin st <= S_DROP; seq_t <= SEQ_MS[3:0]; end
    default: if (msec) begin
              if (seq_t == 4'd0) st <= S_OFF;
              else seq_t <= seq_t - 4'd1;
            end
  endcase

  // outputs, registered; the PA stage drops in the same cycle a cut-off appears
  begin : outs
    logic rel, pa;
    rel = (st != S_OFF) & ~((st == S_REL) & ~allowed);
    pa  = (st == S_ON) & allowed;
    pa_exttr    <= rel;
    pa_inttr    <= rel & ~vna & (pa_enable | ~tr_disable);
    pwr_envop   <= pa;
    pwr_envbias <= pa & ~vna & pa_enable;
    pwr_envpa   <= pa & ~vna & pa_enable;
    dac_en      <= pa;
    rfsw_sel    <= ~vna & pa_enable;
  end
end

assign tx_on   = pa_exttr | pwr_envop;
assign keytime = {k_s, k_ms};
assign status  = {5'd0, vna, tr_disable, pa_enable, 2'b00, cause, 2'b00, trip,
                  1'b0, key_req, (cause[5:1] != 5'd0), (trip != 6'd0), req, lease_valid, dac_en, tx_on};

endmodule


//////////////////////////////////////////////////////////////////////////////
// AD9866 transmit gate (AD9866 clock): the duplex TX samples reach the DAC only while the interlock
// enables the DAC stage and the sink is in real-DAC mode; otherwise the DAC input is 0 and its
// transmit enable is off.

module txdac_gate (
  input                clk_ad    ,
  input                dac_en    ,     // tx_interlock (control clock)
  input                mode_real ,     // txsink register 0x31 bit 1 (Ethernet send clock)
  input         [11:0] dac_in    ,     // txsink dac_out (clk_ad)
  output logic         tx_en   = 1'b0,
  output logic  [11:0] tx_data = 12'd0
);

(* preserve *) logic [1:0] dac_en_s = 2'b00, real_s = 2'b00;
always @(posedge clk_ad) begin
  dac_en_s <= {dac_en_s[0], dac_en};
  real_s   <= {real_s[0], mode_real};
  tx_en    <= dac_en_s[1] & real_s[1];
  tx_data  <= (dac_en_s[1] & real_s[1]) ? dac_in : 12'd0;
end

endmodule
