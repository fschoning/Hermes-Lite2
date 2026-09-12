//
//  gowinlink_rev_train.v — HL2-side controller for the reverse (Gowin -> HL2) lanes.
//  Runs in clk_ad9866; talks to a gl_rx_datapath instance in the reverse clock domain.
//
//  The Gowin centres its forwarded reverse clock on its data, so there is no delay sweep
//  here, only word alignment. The controller is autonomous so that the command channel
//  (which rides on the reverse cable) can bootstrap:
//
//     once the reverse PLL is locked: ALIGN search (retry once with the IDDR pair order
//     swapped) -> VERIFY (2^VERIFY_LEN_LOG2 words of the ALIGN pattern error free)
//     -> rev_state = 2 (locked). On failure wait RETRY_CYCLES and start again.
//     The Gowin keeps its reverse transmitter in ALIGN mode until the status frame
//     reports rev_state = 2, then switches to the wanted mode and sends REV_MODE.
//
//  Link-local commands: REV_TRAIN step 1 restarts the alignment (any other step is
//  ignored); REV_MODE selects which accumulator runs (PRBS mismatches or counter word
//  errors) and clears them. rev_nonce echoes the last REV_TRAIN nonce.
//
module gowinlink_rev_train #(
  parameter integer VERIFY_LEN_LOG2 = 10,
  parameter integer RETRY_CYCLES    = 768000     // 10 ms
) (
  input             clk,
  input             pll_locked,      // synchronised
  // from the command decoder
  input             cmd_train,       // pulse: REV_TRAIN received
  input  [3:0]      cmd_step,
  input  [7:0]      cmd_nonce,
  input             cmd_mode,        // pulse: REV_MODE received
  input  [2:0]      cmd_mode_val,
  // data plane (reverse clock domain, toggle interface)
  output reg        meas_start_t  = 1'b0,
  output reg [4:0]  meas_len_log2 = 5'd0,
  output reg [1:0]  meas_kind     = 2'd0,
  input             meas_done_t,
  input  [15:0]     meas_werr,
  output reg        align_start_t = 1'b0,
  input             align_done_t,
  input             align_ok,
  input  [1:0]      align_fail,
  output reg        pair_swap     = 1'b0,
  output reg        acc_prbs_en   = 1'b0,
  output reg        acc_wchk_en   = 1'b0,
  output reg        acc_clr_t     = 1'b0,
  // report
  output reg [3:0]  rev_state = 4'd0,   // 0 no clock, 1 aligning, 2 locked, 3 failed (retrying)
  output reg [3:0]  rev_fail  = 4'd0,   // 1 no phase, 2 offsets out of range, 4 verification errors
  output reg [7:0]  rev_nonce = 8'h00,
  output reg [3:0]  rev_step  = 4'd0,
  output reg [2:0]  rev_mode  = 3'd0
);

localparam [2:0] MODE_PRBS = 3'd1, MODE_COUNTER = 3'd3;

wire meas_done, align_done;
gl_tog2pulse s_md (.clk(clk), .t(meas_done_t),  .p(meas_done));
gl_tog2pulse s_ad (.clk(clk), .t(align_done_t), .p(align_done));

localparam [2:0] S_NOCLK = 3'd0, S_ALIGN = 3'd1, S_ALIGN_WAIT = 3'd2, S_VERIFY = 3'd3,
                 S_VERIFY_WAIT = 3'd4, S_LOCKED = 3'd5, S_RETRY = 3'd6;
reg [2:0]  s       = S_NOCLK;
reg        retried = 1'b0;
reg [23:0] tmr     = 24'd0;

always @(posedge clk) begin
  if (cmd_mode) begin
    rev_mode    <= cmd_mode_val;
    acc_prbs_en <= (cmd_mode_val == MODE_PRBS);
    acc_wchk_en <= (cmd_mode_val == MODE_COUNTER);
    acc_clr_t   <= ~acc_clr_t;
  end
  if (cmd_train) begin
    rev_nonce <= cmd_nonce;
    rev_step  <= cmd_step;
  end

  if (!pll_locked) begin
    s         <= S_NOCLK;
    rev_state <= 4'd0;
  end else begin
    case (s)
      S_NOCLK: begin
        rev_state <= 4'd1;
        retried   <= 1'b0;
        s         <= S_ALIGN;
      end

      S_ALIGN: begin
        align_start_t <= ~align_start_t;
        s <= S_ALIGN_WAIT;
      end

      S_ALIGN_WAIT: begin
        if (align_done) begin
          if (align_ok) begin
            s <= S_VERIFY;
          end else if (!retried) begin
            retried   <= 1'b1;
            pair_swap <= ~pair_swap;
            s         <= S_ALIGN;
          end else begin
            rev_state <= 4'd3;
            rev_fail  <= {2'b00, align_fail};
            tmr       <= 24'd0;
            s         <= S_RETRY;
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
            rev_state <= 4'd2;
            rev_fail  <= 4'd0;
            s         <= S_LOCKED;
          end else begin
            rev_state <= 4'd3;
            rev_fail  <= 4'd4;
            tmr       <= 24'd0;
            s         <= S_RETRY;
          end
        end
      end

      S_LOCKED: begin
        if (cmd_train && cmd_step == 4'd1) begin
          rev_state <= 4'd1;
          retried   <= 1'b0;
          s         <= S_ALIGN;
        end
      end

      S_RETRY: begin
        tmr <= tmr + 24'd1;
        if (tmr == RETRY_CYCLES || (cmd_train && cmd_step == 4'd1)) begin
          rev_state <= 4'd1;
          retried   <= 1'b0;
          s         <= S_ALIGN;
        end
      end

      default: s <= S_NOCLK;
    endcase
  end
end

endmodule
