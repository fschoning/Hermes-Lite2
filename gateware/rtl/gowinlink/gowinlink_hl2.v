//
//  gowinlink_hl2.v — HL2 side of the HL2 <-> Tang Mega 138K link.
//  See gateware/gowinlink/LINK_SPEC.md.
//
//  clk      = clk_ad9866 (76.8 MHz): word clock, control logic, UARTs, command bus.
//  lane_clk = clk_ad9866_2x (153.6 MHz) for LANES = 3, or clk itself for LANES = 6.
//
//  Cable 1 (HL2 -> Gowin): forwarded clock + LANES data lanes (DDR), status UART, aux.
//  Cable 2 (Gowin -> HL2): forwarded 153.6 MHz clock (rev_clk_pin -> PLL), 3 DDR data
//  lanes gl_rev[2:0], and the fast serial line fs_rxd that carries the command packets
//  (or a plain command UART on the same pin when CMD_UART = 1).
//
module gowinlink_hl2 #(
  parameter integer LANES          = 6,
  parameter integer CMD_UART       = 0,
  parameter integer CLK_HZ         = 76800000,
  parameter integer STATUS_BAUD    = 115200,
  parameter integer CMD_BAUD       = 115200,
  parameter integer CMD_GAP_CYCLES = 512,
  parameter integer CYCLES_10MS    = 768000,   // clk cycles per 10 ms (shorter in simulation)
  parameter [7:0]   STATUS_PERIOD_DEFAULT = 8'd10,
  parameter integer REV_VERIFY_LEN_LOG2 = 10
) (
  input                  clk,
  input                  lane_clk,
  input  [11:0]          adc_data,
  // cable 1 pins
  output                 link_clk_pin,
  output [LANES-1:0]     link_d_pin,
  output                 status_txd,
  output                 aux_out,
  // cable 2 pins
  input                  rev_clk_pin,
  input  [2:0]           gl_rev,
  input                  fs_rxd,
  // Ethernet-originated command bus in (clk domain)
  input  [5:0]           eth_cmd_addr,
  input  [31:0]          eth_cmd_data,
  input                  eth_cmd_cnt,
  input                  eth_cmd_resprqst,
  input                  eth_cmd_is_alt,
  // arbitrated command bus out
  output [5:0]           cmd_addr,
  output [31:0]          cmd_data,
  output                 cmd_cnt,
  output                 cmd_resprqst,
  output                 cmd_is_alt,
  // status inputs (clk domain unless noted)
  input                  run,
  input                  tx_on,
  input                  cw_on,
  input                  ptt,
  input                  key,
  input  [11:0]          temperature,   // clk_ctrl domain, quasi-static
  input  [11:0]          fwdpwr,        // clk_ctrl domain, quasi-static
  input  [11:0]          revpwr,        // clk_ctrl domain, quasi-static
  input  [11:0]          bias,          // clk_ctrl domain, quasi-static
  output reg             link_ptt = 1'b0,
  // reverse-link sample stream (reverse clock domain; future TX samples)
  output                 rev_clk,
  output [11:0]          rev_sample,
  output                 rev_sample_valid
);

localparam [2:0] MODE_LIVE = 3'd0, MODE_PRBS = 3'd1, MODE_TOGGLE = 3'd2,
                 MODE_COUNTER = 3'd3, MODE_ALIGN = 3'd4;

assign aux_out = 1'b0;   // reserved (PIN_87)

// ================================================================ reverse clock + capture
wire        rev_locked;
gowinlink_rxpll rxpll_i (.inclk(rev_clk_pin), .areset(1'b0), .c0(rev_clk), .locked(rev_locked));

wire [2:0]  rev_q0, rev_q1;
wire        fs_q0, fs_q1;
gowinlink_ddr_in #(.W(3)) ddr_rev_i (.clk(rev_clk), .d(gl_rev), .qh(rev_q0), .ql(rev_q1));
gowinlink_ddr_in #(.W(1)) ddr_fs_i  (.clk(rev_clk), .d(fs_rxd), .qh(fs_q0),  .ql(fs_q1));

// reverse data plane (3 lanes, 153.6 MHz DDR) with the fast serial SDR line
wire        rv_meas_start_t, rv_align_start_t, rv_acc_clr_t, rv_snap_t, rv_pair_swap;
wire [4:0]  rv_meas_len_log2;
wire [1:0]  rv_meas_kind;
wire        rv_meas_done_t, rv_align_done_t, rv_align_ok, rv_snap_done_t;
wire [1:0]  rv_align_fail;
wire [15:0] rv_meas_werr;
wire [47:0] rv_meas_err;
wire [11:0] rv_off, rv_phase;
wire        rv_acc_prbs_en, rv_acc_wchk_en;
wire [95:0] rv_snap_prbs;
wire [47:0] rv_snap_bits;
wire [39:0] rv_snap_words;
wire [31:0] rv_snap_werr;
wire        rv_tick, rv_alive;
wire        ser_bit, ser_valid;

gl_rx_datapath #(.LANES(3)) rev_dp_i (
  .clk           (rev_clk),
  .q0            (rev_q0),
  .q1            (rev_q1),
  .pair_swap     (rv_pair_swap),
  .tap           (),
  .tap_val       (24'd0),
  .meas_start_t  (rv_meas_start_t),
  .meas_len_log2 (rv_meas_len_log2),
  .meas_kind     (rv_meas_kind),
  .meas_done_t   (rv_meas_done_t),
  .meas_err      (rv_meas_err),
  .meas_werr     (rv_meas_werr),
  .align_start_t (rv_align_start_t),
  .align_done_t  (rv_align_done_t),
  .align_ok      (rv_align_ok),
  .align_fail    (rv_align_fail),
  .off           (rv_off),
  .phase         (rv_phase),
  .descr_en      (1'b0),
  .acc_prbs_en   (rv_acc_prbs_en),
  .acc_wchk_en   (rv_acc_wchk_en),
  .acc_clr_t     (rv_acc_clr_t),
  .snap_t        (rv_snap_t),
  .snap_done_t   (rv_snap_done_t),
  .snap_prbs     (rv_snap_prbs),
  .snap_bits     (rv_snap_bits),
  .snap_words    (rv_snap_words),
  .snap_werr     (rv_snap_werr),
  .tick          (rv_tick),
  .sample        (rev_sample),
  .sample_valid  (rev_sample_valid),
  .alive         (rv_alive),
  .sdr_q0        (fs_q0),
  .sdr_q1        (fs_q1),
  .ser_bit       (ser_bit),
  .ser_valid     (ser_valid)
);

// ================================================================ command input
wire        cmd_valid;
wire [7:0]  cmd_a;
wire [31:0] cmd_d;
wire [7:0]  cnt_ok, cnt_err, cnt_drop;
wire [15:0] fs_ok, fs_err;

generate
  if (CMD_UART != 0) begin : G_CMD_UART
    wire [7:0] rx_byte;
    wire       rx_byte_valid;
    gowinlink_uart_rx #(.CLK_HZ(CLK_HZ), .BAUD(CMD_BAUD)) uart_rx_i (
      .clk(clk), .rxd(fs_rxd), .data(rx_byte), .valid(rx_byte_valid)
    );
    gowinlink_cmd_rx #(.TIMEOUT_CYCLES(40 * (CLK_HZ / CMD_BAUD))) cmd_rx_i (
      .clk(clk), .rx_data(rx_byte), .rx_valid(rx_byte_valid),
      .cmd_valid(cmd_valid), .cmd_addr(cmd_a), .cmd_data(cmd_d),
      .cnt_ok(cnt_ok), .cnt_err(cnt_err)
    );
    assign fs_ok  = 16'd0;
    assign fs_err = 16'd0;
  end else begin : G_CMD_FS
    wire [7:0] fs_rd_data;
    wire       fs_rd_last, fs_empty, fs_rd_en;
    gl_fastserial_rx #(.FIFO_LOG2(9)) fs_rx_i (
      .clk(rev_clk), .bit_valid(ser_valid), .bit_in(ser_bit),
      .rd_data(fs_rd_data), .rd_last(fs_rd_last), .empty(fs_empty), .rd_en(fs_rd_en),
      .pkt_ok(fs_ok), .pkt_err(fs_err)
    );
    gowinlink_fs_cmd fs_cmd_i (
      .rx_clk(rev_clk), .rd_data(fs_rd_data), .rd_last(fs_rd_last), .empty(fs_empty), .rd_en(fs_rd_en),
      .clk(clk), .cmd_valid(cmd_valid), .cmd_addr(cmd_a), .cmd_data(cmd_d), .cnt_ok(cnt_ok)
    );
    assign cnt_err = fs_err[7:0];
  end
endgenerate

// link-local registers
reg [2:0] mode          = MODE_LIVE;
reg       scr_en        = 1'b0;
reg [7:0] status_period = STATUS_PERIOD_DEFAULT;
reg       pat_rst       = 1'b0;    // toggle
reg [7:0] echo          = 8'h00;
reg       rev_train_p   = 1'b0;
reg       rev_mode_p    = 1'b0;

wire link_local = (cmd_a[7:6] == 2'b11);
wire hpsdr_cmd  = (cmd_a[7:6] == 2'b00);

always @(posedge clk) begin
  rev_train_p <= 1'b0;
  rev_mode_p  <= 1'b0;
  if (cmd_valid && link_local) begin
    case (cmd_a[5:0])
      6'h00: if (cmd_d[3:0] <= 4'd4) mode <= cmd_d[2:0];
      6'h01: scr_en        <= cmd_d[0];
      6'h02: status_period <= cmd_d[7:0];
      6'h03: pat_rst       <= ~pat_rst;
      6'h04: link_ptt      <= cmd_d[0];
      6'h05: rev_mode_p    <= 1'b1;
      6'h06: rev_train_p   <= 1'b1;
      6'h0F: echo          <= cmd_d[7:0];
      default: ;
    endcase
  end
end

gowinlink_cmd_mux #(.GAP_CYCLES(CMD_GAP_CYCLES)) cmd_mux_i (
  .clk          (clk),
  .eth_addr     (eth_cmd_addr),
  .eth_data     (eth_cmd_data),
  .eth_cnt      (eth_cmd_cnt),
  .eth_resprqst (eth_cmd_resprqst),
  .eth_is_alt   (eth_cmd_is_alt),
  .link_push    (cmd_valid & hpsdr_cmd),
  .link_addr    (cmd_a[5:0]),
  .link_data    (cmd_d),
  .cmd_addr     (cmd_addr),
  .cmd_data     (cmd_data),
  .cmd_cnt      (cmd_cnt),
  .cmd_resprqst (cmd_resprqst),
  .cmd_is_alt   (cmd_is_alt),
  .cnt_drop     (cnt_drop)
);

// reverse PLL lock, synchronised
wire rev_locked_s;
gl_sync2 s_lock (.clk(clk), .d(rev_locked), .q(rev_locked_s));

// reverse-link controller
wire [3:0] rev_state, rev_fail, rev_step;
wire [7:0] rev_nonce;
wire [2:0] rev_mode;

gowinlink_rev_train #(.VERIFY_LEN_LOG2(REV_VERIFY_LEN_LOG2), .RETRY_CYCLES(CYCLES_10MS)) rev_train_i (
  .clk           (clk),
  .pll_locked    (rev_locked_s),
  .cmd_train     (rev_train_p),
  .cmd_step      (cmd_d[3:0]),
  .cmd_nonce     (cmd_d[15:8]),
  .cmd_mode      (rev_mode_p),
  .cmd_mode_val  (cmd_d[2:0]),
  .meas_start_t  (rv_meas_start_t),
  .meas_len_log2 (rv_meas_len_log2),
  .meas_kind     (rv_meas_kind),
  .meas_done_t   (rv_meas_done_t),
  .meas_werr     (rv_meas_werr),
  .align_start_t (rv_align_start_t),
  .align_done_t  (rv_align_done_t),
  .align_ok      (rv_align_ok),
  .align_fail    (rv_align_fail),
  .pair_swap     (rv_pair_swap),
  .acc_prbs_en   (rv_acc_prbs_en),
  .acc_wchk_en   (rv_acc_wchk_en),
  .acc_clr_t     (rv_acc_clr_t),
  .rev_state     (rev_state),
  .rev_fail      (rev_fail),
  .rev_nonce     (rev_nonce),
  .rev_step      (rev_step),
  .rev_mode      (rev_mode)
);

// ================================================================ forward word path
reg [11:0] counter = 12'h000;
reg [11:0] word_in = 12'h000;
reg        wtog    = 1'b0;
wire [11:0] word_scr;

always @(posedge clk) begin
  counter <= counter + 12'd1;
  word_in <= (mode == MODE_COUNTER) ? counter : adc_data;
  wtog    <= ~wtog;
end

gowinlink_scrambler #(.DESCRAMBLE(0)) scr_i (
  .clk(clk), .en(1'b1), .bypass(~scr_en), .din(word_in), .dout(word_scr)
);

wire [LANES-1:0] dh, dl;

gowinlink_tx_lanes #(.LANES(LANES)) tx_lanes_i (
  .lane_clk (lane_clk),
  .word     (word_scr),
  .wtog     (wtog),
  .mode     (mode),
  .pat_rst  (pat_rst),
  .dh       (dh),
  .dl       (dl)
);

gowinlink_ddr_out #(.W(LANES)) ddr_data_i (.clk(lane_clk), .dh(dh), .dl(dl), .q(link_d_pin));
gowinlink_ddr_out #(.W(1))     ddr_clk_i  (.clk(lane_clk), .dh(1'b1), .dl(1'b0), .q(link_clk_pin));

// ================================================================ status channel
reg [23:0] tick_cnt  = 24'd0;
reg        tick_10ms = 1'b0;
always @(posedge clk) begin
  if (tick_cnt == CYCLES_10MS - 1) begin
    tick_cnt  <= 24'd0;
    tick_10ms <= 1'b1;
  end else begin
    tick_cnt  <= tick_cnt + 24'd1;
    tick_10ms <= 1'b0;
  end
end

// ADC clip counter (saturating, cleared per frame)
wire        clip     = (adc_data == 12'h7FF) | (adc_data == 12'h800);
reg  [15:0] clip_cnt = 16'd0;

// sensor values from clk_ctrl: double register, accept only when two samples
// 32 cycles apart agree (they change at most every 64 ms)
reg [47:0] sens_s1 = 48'h0, sens_s2 = 48'h0, sens_hold = 48'h0, sens_ok = 48'h0;
reg [4:0]  sens_cnt = 5'd0;
always @(posedge clk) begin
  sens_s1  <= {temperature, fwdpwr, revpwr, bias};
  sens_s2  <= sens_s1;
  sens_cnt <= sens_cnt + 5'd1;
  if (sens_cnt == 5'd0) begin
    sens_hold <= sens_s2;
    if (sens_hold == sens_s2) sens_ok <= sens_s2;
  end
end

// saturate 32-bit accumulators to 16 bits for the frame
function [15:0] sat16;
  input [31:0] v;
  begin
    sat16 = (v[31:16] != 16'd0) ? 16'hFFFF : v[15:0];
  end
endfunction

reg [7:0] seq = 8'h00;
wire      frame_start;
wire [255:0] payload = {
  run, tx_on, cw_on, ptt, key, scr_en, link_ptt, rev_locked_s,   // byte 1  flags
  1'b0, rev_mode, 1'b0, mode,                                    // byte 2
  clip_cnt,                                                      // bytes 3-4
  4'h0, sens_ok[47:36],                                          // bytes 5-6   temperature
  4'h0, sens_ok[35:24],                                          // bytes 7-8   forward power
  4'h0, sens_ok[23:12],                                          // bytes 9-10  reverse power
  4'h0, sens_ok[11:0],                                           // bytes 11-12 bias
  cnt_ok,                                                        // byte 13
  cnt_err,                                                       // byte 14
  echo,                                                          // byte 15
  seq,                                                           // byte 16
  rev_state, rev_fail,                                           // byte 17
  rev_nonce,                                                     // byte 18
  rv_pair_swap, 3'b000, rev_step,                                // byte 19
  rv_off[7:4], rv_off[3:0],                                      // byte 20  off1, off0
  4'h0, rv_off[11:8],                                            // byte 21  off2
  sat16(rv_snap_prbs[31:0]),                                     // bytes 22-23
  sat16(rv_snap_prbs[63:32]),                                    // bytes 24-25
  sat16(rv_snap_prbs[95:64]),                                    // bytes 26-27
  sat16(rv_snap_werr),                                           // bytes 28-29
  fs_ok[7:0],                                                    // byte 30
  fs_err[7:0],                                                   // byte 31
  cnt_drop                                                       // byte 32
};

always @(posedge clk) begin
  if (frame_start) begin
    clip_cnt <= 16'd0;
    seq      <= seq + 8'd1;
  end else if (clip && clip_cnt != 16'hFFFF) begin
    clip_cnt <= clip_cnt + 16'd1;
  end
end

wire [7:0] st_byte;
wire       st_valid, st_ready;

gowinlink_status_tx #(.SNAPSHOT(1)) status_tx_i (
  .clk(clk), .tick_10ms(tick_10ms), .period(status_period), .payload(payload),
  .snap_req(rv_snap_t), .snap_done_t(rv_snap_done_t),
  .frame_start(frame_start), .tx_data(st_byte), .tx_valid(st_valid), .tx_ready(st_ready)
);

gowinlink_uart_tx #(.CLK_HZ(CLK_HZ), .BAUD(STATUS_BAUD)) uart_tx_i (
  .clk(clk), .data(st_byte), .valid(st_valid), .ready(st_ready), .txd(status_txd)
);

endmodule
