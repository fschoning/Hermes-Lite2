//
//  gl_train.v — Gowin control plane (50 MHz): forward link training, reverse link
//  bootstrap, HL2 mode control through the command channel, console commands.
//  See LINK_SPEC.md section 6.
//
//  Forward: PRBS mode -> per-lane IODELAY sweep (longest error-free run, centre) ->
//  ALIGN mode -> alignment search -> verification -> PRBS mode, LOCKED. If no lane shows
//  an eye the IDDR pair order is swapped once and the sweep repeated.
//
//  Reverse: the reverse transmitter sends the ALIGN pattern until the HL2 status frame
//  reports its reverse receiver locked (rev_state = 2); commands can only reach the HL2
//  once that is the case (they ride on the reverse cable), so forward training waits for
//  it. Then the transmitter follows the wanted mode and REV_MODE is sent to the HL2.
//
module gl_train #(
  parameter integer LANES            = 6,
  parameter integer SWEEP_LEN_LOG2   = 12,      // words per tap during the sweep
  parameter integer VERIFY_LEN_LOG2  = 12,      // words for the alignment verification
  parameter integer SETTLE_CYCLES    = 5000,    // after a command frame has left (100 us)
  parameter integer AUTOTRAIN_CYCLES = 12500000,// power-up delay before automatic training (250 ms)
  parameter integer CLK_TIMEOUT      = 50000,   // 1 ms without link clock activity -> NOCLK
  parameter integer STATUS_TIMEOUT   = 50000000,// 1 s without a status frame -> HL2 unknown
  parameter integer MIN_EYE          = 16       // taps
) (
  input                     clk,
  // console / key commands (pulses)
  input                     cmd_train,
  input                     cmd_prbs,
  input                     cmd_live,
  input                     cmd_counter,
  input                     cmd_toggle,
  input                     cmd_scr,
  input                     cmd_rst,
  input                     cmd_x,          // send test command: address 0x01, data 0x00ABCDEF
  // forward link clock activity (toggle from the lane domain)
  input                     alive_t,
  output                    clk_ok,
  // forward data plane
  output reg [8*LANES-1:0]  tap_val       = {(8*LANES){1'b0}},
  output reg                meas_start_t  = 1'b0,
  output reg [4:0]          meas_len_log2 = 5'd0,
  output reg [1:0]          meas_kind     = 2'd0,
  input                     meas_done_t,
  input  [16*LANES-1:0]     meas_err,
  input  [15:0]             meas_werr,
  output reg                align_start_t = 1'b0,
  input                     align_done_t,
  input                     align_ok,
  input  [1:0]              align_fail,
  output reg                pair_swap     = 1'b0,
  output reg                descr_en      = 1'b0,
  output reg                acc_prbs_en   = 1'b0,
  output reg                acc_wchk_en   = 1'b0,
  output reg                acc_clr_t     = 1'b0,
  // command transmitter
  output reg                ctx_req       = 1'b0,
  output reg [7:0]          ctx_addr      = 8'h00,
  output reg [31:0]         ctx_data      = 32'h0,
  input                     ctx_busy,
  // status frames from the HL2
  input                     st_ok,          // pulse: good frame received
  input  [3:0]              st_rev_state,   // byte 17 high nibble of the last frame
  // reverse transmitter
  output reg [2:0]          rev_mode      = 3'd4,   // ALIGN until the HL2 is locked
  // status
  output reg [2:0]          state         = 3'd1,   // 0 NOCLK 1 IDLE 2 SWEEP 3 ALIGN 4 LOCKED 5 FAIL
  output reg [2:0]          fail          = 3'd0,
  output reg [2:0]          hl2_mode      = 3'd0,
  output reg                scr_on        = 1'b0,
  output reg [8*LANES-1:0]  eye           = {(8*LANES){1'b0}},
  output                    st_alive,
  output                    rev_locked
);

localparam [2:0] MODE_LIVE = 3'd0, MODE_PRBS = 3'd1, MODE_TOGGLE = 3'd2,
                 MODE_COUNTER = 3'd3, MODE_ALIGN = 3'd4;
localparam [7:0] LL_MODE = 8'hC0, LL_SCR = 8'hC1, LL_REV_MODE = 8'hC5;

// ---------------------------------------------------------------- link clock detection
reg  [1:0]  alive_s = 2'b00;
reg         alive_d = 1'b0;
reg  [16:0] alive_to = 17'd0;
always @(posedge clk) begin
  alive_s <= {alive_s[0], alive_t};
  alive_d <= alive_s[1];
  if (alive_s[1] != alive_d) alive_to <= 17'd0;
  else if (alive_to != CLK_TIMEOUT) alive_to <= alive_to + 17'd1;
end
assign clk_ok = (alive_to != CLK_TIMEOUT);

// ---------------------------------------------------------------- status frame tracking
reg [31:0] st_to = 32'd0;
always @(posedge clk) begin
  if (st_ok) st_to <= 32'd0;
  else if (st_to != STATUS_TIMEOUT) st_to <= st_to + 32'd1;
end
assign st_alive   = (st_to != STATUS_TIMEOUT);
assign rev_locked = st_alive & (st_rev_state == 4'd2);

// reverse transmitter mode: ALIGN until the HL2 reports locked, then the wanted mode
reg [2:0] rev_want     = MODE_PRBS;
reg       rev_locked_d = 1'b0;
reg       rev_cmd_pend = 1'b0;    // REV_MODE must be sent
reg       rev_cmd_sent = 1'b0;
always @(posedge clk) begin
  rev_locked_d <= rev_locked;
  rev_mode     <= rev_locked ? rev_want : MODE_ALIGN;
  if (rev_locked && !rev_locked_d) rev_cmd_pend <= 1'b1;
  if (rev_cmd_sent) rev_cmd_pend <= 1'b0;
end

// ---------------------------------------------------------------- done pulses
wire meas_done, align_done;
gl_tog2pulse s_md (.clk(clk), .t(meas_done_t),  .p(meas_done));
gl_tog2pulse s_ad (.clk(clk), .t(align_done_t), .p(align_done));

// ---------------------------------------------------------------- states
localparam [4:0]
  S_NOCLK       = 5'd0,
  S_IDLE        = 5'd1,
  S_T_MODE      = 5'd2,
  S_SWEEP_START = 5'd3,
  S_SWEEP_WAIT  = 5'd4,
  S_PICK        = 5'd5,
  S_SETTAP      = 5'd6,
  S_SETTAP_WAIT = 5'd7,
  S_ALIGN_MODE  = 5'd8,
  S_ALIGN_GO    = 5'd9,
  S_ALIGN_WAIT  = 5'd10,
  S_VERIFY      = 5'd11,
  S_VERIFY_WAIT = 5'd12,
  S_LOCK_MODE   = 5'd13,
  S_LOCKED_INIT = 5'd14,
  S_LOCKED      = 5'd15,
  S_FAIL        = 5'd16,
  S_SEND_REQ    = 5'd17,
  S_SEND_WAIT   = 5'd18,
  S_SEND_SETTLE = 5'd19,
  S_CMD_APPLY   = 5'd20,
  S_CMD_APPLY2  = 5'd21,
  S_REV_CMD     = 5'd22;

reg [4:0]  s        = S_IDLE;
reg [4:0]  ret      = S_IDLE;      // state to return to after a send
reg [23:0] tmr      = 24'd0;
reg [8:0]  tap      = 9'd0;        // current sweep tap (0..255)
reg        swapped  = 1'b0;        // pair_swap retry already used
reg        auto_pend = 1'b1;
reg [31:0] auto_tmr = 32'd0;
reg [2:0]  want_mode = MODE_LIVE;  // mode requested by a console command
reg        cmd_is_mode = 1'b0;
reg        apply_local = 1'b0;     // apply local settings when the send completes

// per-lane run tracking (flattened)
reg [8*LANES-1:0] cur_start  = {(8*LANES){1'b0}};
reg [9*LANES-1:0] cur_len    = {(9*LANES){1'b0}};
reg [8*LANES-1:0] best_start = {(8*LANES){1'b0}};
reg [9*LANES-1:0] best_len   = {(9*LANES){1'b0}};

reg any_small, all_zero;
integer li;
always @* begin
  any_small = 1'b0;
  all_zero  = 1'b1;
  for (li = 0; li < LANES; li = li + 1) begin
    if (best_len[9*li +: 9] < MIN_EYE) any_small = 1'b1;
    if (best_len[9*li +: 9] != 9'd0)   all_zero  = 1'b0;
  end
end

wire cmd_any_mode = cmd_prbs | cmd_live | cmd_counter | cmd_toggle;
wire [2:0] cmd_mode_val = cmd_prbs ? MODE_PRBS : cmd_live ? MODE_LIVE : cmd_counter ? MODE_COUNTER : MODE_TOGGLE;

always @(posedge clk) begin
  ctx_req      <= 1'b0;
  rev_cmd_sent <= 1'b0;

  if (auto_tmr != AUTOTRAIN_CYCLES) auto_tmr <= auto_tmr + 32'd1;

  // loss of the forward link clock overrides everything except an in-flight command frame
  if (!clk_ok && s != S_SEND_REQ && s != S_SEND_WAIT && s != S_NOCLK) begin
    s           <= S_NOCLK;
    state       <= 3'd0;
    auto_pend   <= 1'b1;
    auto_tmr    <= 32'd0;
    acc_prbs_en <= 1'b0;
    acc_wchk_en <= 1'b0;
  end else begin
    case (s)
      S_NOCLK: begin
        if (clk_ok) begin
          s     <= S_IDLE;
          state <= 3'd1;
        end
      end

      // ------------------------------------------------ idle / failed / locked: commands
      S_IDLE, S_FAIL, S_LOCKED: begin
        if (rev_cmd_pend) begin
          ret <= s;
          s   <= S_REV_CMD;
        end else if (!rev_locked) begin
          // no command channel yet; nothing else can be done
          if (cmd_train) auto_pend <= 1'b1;
        end else if (cmd_train || (auto_pend && auto_tmr == AUTOTRAIN_CYCLES && s != S_LOCKED)) begin
          auto_pend <= 1'b0;
          swapped   <= 1'b0;
          s         <= S_T_MODE;
        end else if (cmd_any_mode) begin
          want_mode   <= cmd_mode_val;
          rev_want    <= cmd_mode_val;
          cmd_is_mode <= 1'b1;
          ret         <= s;
          s           <= S_CMD_APPLY;
        end else if (cmd_scr) begin
          cmd_is_mode <= 1'b0;
          ret         <= s;
          s           <= S_CMD_APPLY;
        end else if (cmd_rst) begin
          acc_clr_t <= ~acc_clr_t;
          ret       <= s;
          s         <= S_REV_CMD;       // REV_MODE also clears the HL2 reverse counters
        end else if (cmd_x) begin
          ctx_addr    <= 8'h01;
          ctx_data    <= 32'h00ABCDEF;
          apply_local <= 1'b0;
          ret         <= s;
          s           <= S_SEND_REQ;
        end
      end

      // ------------------------------------------------ forward training
      S_T_MODE: begin
        state       <= 3'd2;
        fail        <= 3'd0;
        acc_prbs_en <= 1'b0;
        acc_wchk_en <= 1'b0;
        ctx_addr    <= LL_MODE;
        ctx_data    <= {29'd0, MODE_PRBS};
        hl2_mode    <= MODE_PRBS;
        apply_local <= 1'b0;
        ret         <= S_SWEEP_START;
        s           <= S_SEND_REQ;
      end

      S_SWEEP_START: begin
        tap        <= 9'd0;
        cur_len    <= {(9*LANES){1'b0}};
        best_len   <= {(9*LANES){1'b0}};
        cur_start  <= {(8*LANES){1'b0}};
        best_start <= {(8*LANES){1'b0}};
        tap_val    <= {LANES{8'd0}};
        meas_len_log2 <= SWEEP_LEN_LOG2;
        meas_kind     <= 2'd0;
        meas_start_t  <= ~meas_start_t;
        s <= S_SWEEP_WAIT;
      end

      S_SWEEP_WAIT: begin
        if (meas_done) begin
          for (li = 0; li < LANES; li = li + 1) begin
            if (meas_err[16*li +: 16] == 16'd0) begin
              if (cur_len[9*li +: 9] == 9'd0) cur_start[8*li +: 8] <= tap[7:0];
              cur_len[9*li +: 9] <= cur_len[9*li +: 9] + 9'd1;
              if (cur_len[9*li +: 9] + 9'd1 > best_len[9*li +: 9]) begin
                best_len[9*li +: 9]   <= cur_len[9*li +: 9] + 9'd1;
                best_start[8*li +: 8] <= (cur_len[9*li +: 9] == 9'd0) ? tap[7:0] : cur_start[8*li +: 8];
              end
            end else begin
              cur_len[9*li +: 9] <= 9'd0;
            end
          end
          if (tap == 9'd255) begin
            s <= S_PICK;
          end else begin
            tap          <= tap + 9'd1;
            tap_val      <= {LANES{tap[7:0] + 8'd1}};
            meas_start_t <= ~meas_start_t;
          end
        end
      end

      S_PICK: begin
        for (li = 0; li < LANES; li = li + 1) begin
          eye[8*li +: 8]     <= (best_len[9*li +: 9] > 9'd255) ? 8'd255 : best_len[9*li +: 8];
          tap_val[8*li +: 8] <= best_start[8*li +: 8] + best_len[9*li + 1 +: 8];   // start + len/2
        end
        if (all_zero && !swapped) begin
          swapped   <= 1'b1;
          pair_swap <= ~pair_swap;
          s         <= S_SWEEP_START;
        end else if (any_small) begin
          fail  <= 3'd1;
          state <= 3'd5;
          s     <= S_FAIL;
        end else begin
          s <= S_SETTAP;
        end
      end

      S_SETTAP: begin
        meas_len_log2 <= 5'd4;
        meas_kind     <= 2'd0;
        meas_start_t  <= ~meas_start_t;
        s <= S_SETTAP_WAIT;
      end

      S_SETTAP_WAIT: begin
        if (meas_done) s <= S_ALIGN_MODE;
      end

      S_ALIGN_MODE: begin
        state       <= 3'd3;
        ctx_addr    <= LL_MODE;
        ctx_data    <= {29'd0, MODE_ALIGN};
        hl2_mode    <= MODE_ALIGN;
        apply_local <= 1'b0;
        ret         <= S_ALIGN_GO;
        s           <= S_SEND_REQ;
      end

      S_ALIGN_GO: begin
        align_start_t <= ~align_start_t;
        s <= S_ALIGN_WAIT;
      end

      S_ALIGN_WAIT: begin
        if (align_done) begin
          if (align_ok) begin
            s <= S_VERIFY;
          end else begin
            fail  <= {1'b0, align_fail};   // 1 or 2
            state <= 3'd5;
            s     <= S_FAIL;
          end
        end
      end

      S_VERIFY: begin
        meas_len_log2 <= VERIFY_LEN_LOG2;
        meas_kind     <= 2'd1;
        meas_start_t  <= ~meas_start_t;
        s <= S_VERIFY_WAIT;
      end

      S_VERIFY_WAIT: begin
        if (meas_done) begin
          if (meas_werr == 16'd0) begin
            s <= S_LOCK_MODE;
          end else begin
            fail  <= 3'd4;
            state <= 3'd5;
            s     <= S_FAIL;
          end
        end
      end

      S_LOCK_MODE: begin
        ctx_addr    <= LL_MODE;
        ctx_data    <= {29'd0, MODE_PRBS};
        hl2_mode    <= MODE_PRBS;
        apply_local <= 1'b0;
        ret         <= S_LOCKED_INIT;
        s           <= S_SEND_REQ;
      end

      S_LOCKED_INIT: begin
        acc_clr_t   <= ~acc_clr_t;
        acc_prbs_en <= 1'b1;
        acc_wchk_en <= 1'b0;
        rev_want    <= MODE_PRBS;
        state       <= 3'd4;
        s           <= S_LOCKED;
      end

      // ------------------------------------------------ mode / scrambler commands
      S_CMD_APPLY: begin
        acc_prbs_en <= 1'b0;
        acc_wchk_en <= 1'b0;
        if (cmd_is_mode) begin
          ctx_addr <= LL_MODE;
          ctx_data <= {29'd0, want_mode};
          hl2_mode <= want_mode;
        end else begin
          scr_on   <= ~scr_on;
          ctx_addr <= LL_SCR;
          ctx_data <= {31'd0, ~scr_on};
        end
        apply_local <= 1'b1;
        s <= S_SEND_REQ;
        // after the settle: S_CMD_APPLY2 sends REV_MODE for a mode change, then 'ret'
      end

      S_CMD_APPLY2: begin
        if (cmd_is_mode) begin
          s <= S_REV_CMD;
        end else begin
          s <= ret;
        end
      end

      S_REV_CMD: begin
        ctx_addr     <= LL_REV_MODE;
        ctx_data     <= {29'd0, rev_want};
        rev_cmd_sent <= 1'b1;
        apply_local  <= 1'b0;
        s            <= S_SEND_REQ;
        // ret already holds the state to return to
      end

      // ------------------------------------------------ command send helper
      S_SEND_REQ: begin
        if (!ctx_busy) begin
          ctx_req <= 1'b1;
          s       <= S_SEND_WAIT;
        end
      end

      S_SEND_WAIT: begin
        if (!ctx_req && !ctx_busy) begin
          tmr <= 24'd0;
          s   <= S_SEND_SETTLE;
        end
      end

      S_SEND_SETTLE: begin
        tmr <= tmr + 24'd1;
        if (tmr == SETTLE_CYCLES) begin
          if (apply_local) begin
            apply_local <= 1'b0;
            descr_en    <= scr_on;
            if (ret == S_LOCKED) begin
              acc_clr_t   <= ~acc_clr_t;
              acc_prbs_en <= (hl2_mode == MODE_PRBS);
              acc_wchk_en <= (hl2_mode == MODE_COUNTER);
            end
            s <= S_CMD_APPLY2;
          end else begin
            s <= ret;
          end
        end
      end

      default: s <= S_IDLE;
    endcase
  end
end

endmodule
