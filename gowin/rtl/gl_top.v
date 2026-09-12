//
//  gl_top.v — Tang Mega 138K side of the HL2 <-> Gowin link. See LINK_SPEC.md.
//
//  Clock domains
//    clk50     on-board 50 MHz oscillator: control plane, UARTs, console
//    fwd_clk   forwarded clock from the HL2 (76.8 MHz for LANES = 6, 153.6 MHz for
//              LANES = 3): forward lane capture and the forward data plane
//    clk_w / clk_l / clk_c   PLL outputs locked to fwd_clk: reverse transmitter word
//              clock (76.8 MHz), lane clock (153.6 MHz) and forwarded reverse clock
//              (153.6 MHz, +90 degrees)
//
//  Cable 1 in : fwd_clk, link_d[LANES-1:0], status_rxd (UART), aux_in (reserved)
//  Cable 2 out: rev_clk_out, gl_rev[2:0] (DDR 153.6 MHz), fs_txd (fast serial with the
//               command packets) or cmd_txd (plain command UART when CMD_UART = 1)
//
module gl_top #(
  parameter integer LANES            = 6,
  parameter integer CMD_UART         = 0,
  parameter integer CMD_OPEN_DRAIN   = 0,
  parameter integer CLK50_HZ         = 50000000,
  parameter integer DEBUG_BAUD       = 115200,
  parameter integer STATUS_BAUD      = 115200,
  parameter integer CMD_BAUD         = 115200,
  parameter integer CONSOLE_PERIOD   = 50000000,   // clk50 cycles between console lines
  parameter integer SWEEP_LEN_LOG2   = 12,
  parameter integer VERIFY_LEN_LOG2  = 12,
  parameter integer SETTLE_CYCLES    = 5000,
  parameter integer AUTOTRAIN_CYCLES = 12500000,
  parameter integer CLK_TIMEOUT      = 50000,
  parameter integer STATUS_TIMEOUT   = 50000000,
  parameter integer FS_TEST_PERIOD   = 768000      // clk_w cycles between fast serial test packets
) (
  input              clk50,
  // cable 1 (HL2 -> Gowin)
  input              fwd_clk,
  input  [LANES-1:0] link_d,
  input              status_rxd,
  input              aux_in,
  // cable 2 (Gowin -> HL2)
  output             rev_clk_out,
  output [2:0]       gl_rev,
  output             fs_txd,
  output             cmd_txd,
  // debug
  output             dbg_txd,
  input              dbg_rxd,
  output [3:0]       led,
  input              key_n
);

localparam [2:0] MODE_LIVE = 3'd0, MODE_PRBS = 3'd1, MODE_COUNTER = 3'd3;

// ================================================================ forward lanes
wire [8*LANES-1:0] tap;
wire [LANES-1:0]   q0, q1;

genvar g;
generate
  for (g = 0; g < LANES; g = g + 1) begin : G_LANE
    gl_lane_rx lane_i (
      .pad (link_d[g]),
      .clk (fwd_clk),
      .tap (tap[8*g +: 8]),
      .q0  (q0[g]),
      .q1  (q1[g])
    );
  end
endgenerate

// ================================================================ forward data plane
wire               pair_swap, descr_en, acc_prbs_en, acc_wchk_en, acc_clr_t;
wire [8*LANES-1:0] tap_val;
wire               meas_start_t, meas_done_t, align_start_t, align_done_t, align_ok;
wire [4:0]         meas_len_log2;
wire [1:0]         meas_kind, align_fail;
wire [16*LANES-1:0] meas_err;
wire [15:0]        meas_werr;
wire [4*LANES-1:0] off, phase;
wire               snap_t, snap_done_t;
wire [32*LANES-1:0] snap_prbs;
wire [47:0]        snap_bits;
wire [39:0]        snap_words;
wire [31:0]        snap_werr;
wire               tick, sample_valid, alive;
wire [11:0]        sample;

gl_rx_datapath #(.LANES(LANES)) dp_i (
  .clk           (fwd_clk),
  .q0            (q0),
  .q1            (q1),
  .pair_swap     (pair_swap),
  .tap           (tap),
  .tap_val       (tap_val),
  .meas_start_t  (meas_start_t),
  .meas_len_log2 (meas_len_log2),
  .meas_kind     (meas_kind),
  .meas_done_t   (meas_done_t),
  .meas_err      (meas_err),
  .meas_werr     (meas_werr),
  .align_start_t (align_start_t),
  .align_done_t  (align_done_t),
  .align_ok      (align_ok),
  .align_fail    (align_fail),
  .off           (off),
  .phase         (phase),
  .descr_en      (descr_en),
  .acc_prbs_en   (acc_prbs_en),
  .acc_wchk_en   (acc_wchk_en),
  .acc_clr_t     (acc_clr_t),
  .snap_t        (snap_t),
  .snap_done_t   (snap_done_t),
  .snap_prbs     (snap_prbs),
  .snap_bits     (snap_bits),
  .snap_words    (snap_words),
  .snap_werr     (snap_werr),
  .tick          (tick),
  .sample        (sample),
  .sample_valid  (sample_valid),
  .alive         (alive),
  .sdr_q0        (1'b1),
  .sdr_q1        (1'b1),
  .ser_bit       (),
  .ser_valid     ()
);

// ================================================================ reverse link clocks
wire clk_w, clk_l, clk_c, pll_lock;
gl_pll #(.LANES(LANES)) pll_i (.fwd_clk(fwd_clk), .clk_w(clk_w), .clk_l(clk_l), .clk_c(clk_c), .lock(pll_lock));

// ================================================================ reverse transmitter
wire [2:0] rev_mode;          // clk50 domain, quasi-static
wire [2:0] rev_mode_w;
gl_sync2 #(.W(3)) s_rev_mode (.clk(clk_w), .d(rev_mode), .q(rev_mode_w));

reg  [11:0] rev_counter = 12'h000;
reg  [11:0] rev_word    = 12'h000;
reg         rev_wtog    = 1'b0;
always @(posedge clk_w) begin
  rev_counter <= rev_counter + 12'd1;
  rev_word    <= (rev_mode_w == MODE_COUNTER) ? rev_counter : 12'h000;   // LIVE: TX samples later
  rev_wtog    <= ~rev_wtog;
end

wire [2:0] rev_dh, rev_dl;
gowinlink_tx_lanes #(.LANES(3)) rev_tx_i (
  .lane_clk (clk_l),
  .word     (rev_word),
  .wtog     (rev_wtog),
  .mode     (rev_mode_w),
  .pat_rst  (1'b0),
  .dh       (rev_dh),
  .dl       (rev_dl)
);

wire [2:0] rev_q;
wire       rev_clk_q;
generate
  for (g = 0; g < 3; g = g + 1) begin : G_REV
    ODDR #(.TXCLK_POL(1'b0), .INIT(1'b0)) oddr_i (
      .Q0(rev_q[g]), .Q1(), .D0(rev_dh[g]), .D1(rev_dl[g]), .TX(1'b0), .CLK(clk_l)
    );
    OBUF obuf_i (.O(gl_rev[g]), .I(rev_q[g]));
  end
endgenerate
ODDR #(.TXCLK_POL(1'b0), .INIT(1'b0)) oddr_clk_i (
  .Q0(rev_clk_q), .Q1(), .D0(1'b1), .D1(1'b0), .TX(1'b0), .CLK(clk_c)
);
OBUF obuf_clk_i (.O(rev_clk_out), .I(rev_clk_q));

// ================================================================ command channel
wire        ctx_req, ctx_busy;
wire [7:0]  ctx_addr;
wire [31:0] ctx_data;
wire [15:0] fs_pkt_cnt;
wire        cmd_uart_txd;

generate
  if (CMD_UART != 0) begin : G_CMD_UART
    gl_cmd_tx #(.CLK_HZ(CLK50_HZ), .BAUD(CMD_BAUD)) cmd_tx_i (
      .clk(clk50), .req(ctx_req), .addr(ctx_addr), .data(ctx_data), .busy(ctx_busy), .txd(cmd_uart_txd)
    );
    assign fs_txd     = 1'b1;
    assign fs_pkt_cnt = 16'd0;
  end else begin : G_CMD_FS
    gl_cmd_fs #(.TEST_PERIOD(FS_TEST_PERIOD)) cmd_fs_i (
      .clk(clk50), .req(ctx_req), .addr(ctx_addr), .data(ctx_data), .busy(ctx_busy),
      .clk_w(clk_w), .txd(fs_txd), .pkt_cnt(fs_pkt_cnt)
    );
    assign cmd_uart_txd = 1'b1;
  end
endgenerate

assign cmd_txd = (CMD_OPEN_DRAIN != 0) ? (cmd_uart_txd ? 1'bz : 1'b0) : cmd_uart_txd;

// ================================================================ status frames
wire [255:0] st_frame;
wire [15:0]  st_frame_cnt, st_err_cnt;
wire         st_frame_ok;

gl_status_rx #(.CLK_HZ(CLK50_HZ), .BAUD(STATUS_BAUD)) status_rx_i (
  .clk(clk50), .rxd(status_rxd), .frame(st_frame), .frame_cnt(st_frame_cnt), .err_cnt(st_err_cnt), .frame_ok(st_frame_ok)
);

// ================================================================ control plane
wire c_train, c_prbs, c_live, c_counter, c_toggle, c_scr, c_rst, c_x;
wire clk_ok, st_alive, rev_locked, scr_on;
wire [2:0] state, fail, hl2_mode;
wire [8*LANES-1:0] eye;

// key: active low, debounced edge -> train
reg [19:0] key_cnt = 20'd0;
reg        key_s1 = 1'b1, key_s2 = 1'b1, key_db = 1'b1, key_db_d = 1'b1;
always @(posedge clk50) begin
  key_s1 <= key_n;
  key_s2 <= key_s1;
  if (key_s2 == key_db) key_cnt <= 20'd0;
  else if (key_cnt == 20'hFFFFF) begin key_db <= key_s2; key_cnt <= 20'd0; end
  else key_cnt <= key_cnt + 20'd1;
  key_db_d <= key_db;
end
wire key_train = key_db_d & ~key_db;

gl_train #(
  .LANES            (LANES),
  .SWEEP_LEN_LOG2   (SWEEP_LEN_LOG2),
  .VERIFY_LEN_LOG2  (VERIFY_LEN_LOG2),
  .SETTLE_CYCLES    (SETTLE_CYCLES),
  .AUTOTRAIN_CYCLES (AUTOTRAIN_CYCLES),
  .CLK_TIMEOUT      (CLK_TIMEOUT),
  .STATUS_TIMEOUT   (STATUS_TIMEOUT),
  .MIN_EYE          (16)
) train_i (
  .clk           (clk50),
  .cmd_train     (c_train | key_train),
  .cmd_prbs      (c_prbs),
  .cmd_live      (c_live),
  .cmd_counter   (c_counter),
  .cmd_toggle    (c_toggle),
  .cmd_scr       (c_scr),
  .cmd_rst       (c_rst),
  .cmd_x         (c_x),
  .alive_t       (alive),
  .clk_ok        (clk_ok),
  .tap_val       (tap_val),
  .meas_start_t  (meas_start_t),
  .meas_len_log2 (meas_len_log2),
  .meas_kind     (meas_kind),
  .meas_done_t   (meas_done_t),
  .meas_err      (meas_err),
  .meas_werr     (meas_werr),
  .align_start_t (align_start_t),
  .align_done_t  (align_done_t),
  .align_ok      (align_ok),
  .align_fail    (align_fail),
  .pair_swap     (pair_swap),
  .descr_en      (descr_en),
  .acc_prbs_en   (acc_prbs_en),
  .acc_wchk_en   (acc_wchk_en),
  .acc_clr_t     (acc_clr_t),
  .ctx_req       (ctx_req),
  .ctx_addr      (ctx_addr),
  .ctx_data      (ctx_data),
  .ctx_busy      (ctx_busy),
  .st_ok         (st_frame_ok),
  .st_rev_state  (st_frame[127:124]),     // byte 17, high nibble
  .rev_mode      (rev_mode),
  .state         (state),
  .fail          (fail),
  .hl2_mode      (hl2_mode),
  .scr_on        (scr_on),
  .eye           (eye),
  .st_alive      (st_alive),
  .rev_locked    (rev_locked)
);

// ================================================================ console
wire        pll_lock_s;
wire [15:0] fs_pkt_cnt_s;
gl_sync2         s_pll (.clk(clk50), .d(pll_lock),   .q(pll_lock_s));
gl_sync2 #(.W(16)) s_fs (.clk(clk50), .d(fs_pkt_cnt), .q(fs_pkt_cnt_s));   // display only

wire [47:0]  f_tap = {{(48-8*LANES){1'b0}},  tap};
wire [47:0]  f_eye = {{(48-8*LANES){1'b0}},  eye};
wire [23:0]  f_off = {{(24-4*LANES){1'b0}},  off};
wire [191:0] f_err = {{(192-32*LANES){1'b0}}, snap_prbs};

gl_console #(
  .CLK_HZ        (CLK50_HZ),
  .BAUD          (DEBUG_BAUD),
  .PERIOD_CYCLES (CONSOLE_PERIOD),
  .LANES         (LANES)
) console_i (
  .clk         (clk50),
  .rxd         (dbg_rxd),
  .txd         (dbg_txd),
  .cmd_train   (c_train),
  .cmd_prbs    (c_prbs),
  .cmd_live    (c_live),
  .cmd_counter (c_counter),
  .cmd_toggle  (c_toggle),
  .cmd_scr     (c_scr),
  .cmd_rst     (c_rst),
  .cmd_x       (c_x),
  .snap_t      (snap_t),
  .snap_done_t (snap_done_t),
  .f_st        ({1'b0, state}),
  .f_fail      ({1'b0, fail}),
  .f_mode      ({1'b0, hl2_mode}),
  .f_scr       ({3'b000, scr_on}),
  .f_clk       ({3'b000, clk_ok}),
  .f_pll       ({3'b000, pll_lock_s}),
  .f_swap      ({3'b000, pair_swap}),
  .f_rev       ({3'b000, rev_locked}),
  .f_salive    ({3'b000, st_alive}),
  .f_tap       (f_tap),
  .f_eye       (f_eye),
  .f_off       (f_off),
  .f_err       (f_err),
  .f_words     (snap_words),
  .f_werr      (snap_werr),
  .f_sf        (st_frame_cnt),
  .f_se        (st_err_cnt),
  .f_tx        (fs_pkt_cnt_s),
  .f_hl2       (st_frame)
);

// ================================================================ LEDs
reg [25:0] hb = 26'd0;
always @(posedge clk50) hb <= hb + 26'd1;
assign led = {clk_ok, rev_locked, (state == 3'd4), hb[25]};

endmodule
