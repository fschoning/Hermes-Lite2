// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Behavioural I2C slave for the testbenches: 7-bit address, 256 register bytes, register pointer set
// by the first written byte, sequential reads from the pointer. Counts write bytes that reach it.
`timescale 1 ps / 1 ps

module i2c_slave_model #(
  parameter [6:0] ADDR = 7'h20
) (
  inout scl,
  inout sda
);

logic sda_drive = 1'b0;
assign sda = sda_drive ? 1'b0 : 1'bz;

logic [7:0] mem [0:255];
logic [7:0] ptr = 8'd0;
integer     writes = 0;                 // data bytes written (after the pointer byte)
integer     addressed = 0;              // times this address was selected

localparam S_IDLE = 0, S_ADDR = 1, S_AACK = 2, S_WDATA = 3, S_WACK = 4, S_RDATA = 5, S_RACK = 6;
integer     state = S_IDLE;
integer     bitc = 0;
logic [7:0] sh = 8'd0, rbyte = 8'd0;
logic       rw = 1'b0, first = 1'b0, mnack = 1'b0;

initial for (int i = 0; i < 256; i++) mem[i] = i[7:0] ^ 8'h5a;

always @(negedge sda) if (scl === 1'b1) begin
  state = S_ADDR; bitc = 0; sda_drive = 1'b0;
end

always @(posedge sda) if (scl === 1'b1) begin
  state = S_IDLE; sda_drive = 1'b0;
end

always @(posedge scl) begin
  case (state)
    S_ADDR, S_WDATA: begin sh = {sh[6:0], (sda === 1'b0) ? 1'b0 : 1'b1}; bitc = bitc + 1; end
    S_RACK: mnack = (sda === 1'b0) ? 1'b0 : 1'b1;
    default: ;
  endcase
end

always @(negedge scl) begin
  case (state)
    S_ADDR: if (bitc == 8) begin
      if (sh[7:1] == ADDR) begin rw = sh[0]; sda_drive = 1'b1; state = S_AACK; addressed = addressed + 1; end
      else state = S_IDLE;
    end
    S_AACK: begin
      if (rw) begin rbyte = mem[ptr]; bitc = 0; sda_drive = ~rbyte[7]; state = S_RDATA; end
      else begin sda_drive = 1'b0; bitc = 0; first = 1'b1; state = S_WDATA; end
    end
    S_WDATA: if (bitc == 8) begin
      if (first) ptr = sh;
      else begin mem[ptr] = sh; ptr = ptr + 8'd1; writes = writes + 1; end
      first = 1'b0; sda_drive = 1'b1; state = S_WACK;
    end
    S_WACK: begin sda_drive = 1'b0; bitc = 0; state = S_WDATA; end
    S_RDATA: begin
      bitc = bitc + 1;
      if (bitc == 8) begin sda_drive = 1'b0; ptr = ptr + 8'd1; state = S_RACK; end
      else sda_drive = ~rbyte[7 - bitc];
    end
    S_RACK: begin
      if (mnack) state = S_IDLE;
      else begin rbyte = mem[ptr]; bitc = 0; sda_drive = ~rbyte[7]; state = S_RDATA; end
    end
    default: ;
  endcase
end

endmodule
