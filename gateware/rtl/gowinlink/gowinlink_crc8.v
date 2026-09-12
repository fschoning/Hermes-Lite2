//
//  gowinlink_crc8.v — one byte step of CRC-8, polynomial 0x07, init 0x00, no reflection,
//  no final xor (the plain "CRC-8" / CRC-8/ATM-style table). Combinational.
//
//  crc_out = crc8_step(crc_in, data). Feed bytes in order starting from crc_in = 0.
//
module gowinlink_crc8 (
  input  [7:0] crc_in,
  input  [7:0] data,
  output [7:0] crc_out
);

function [7:0] crc8_step;
  input [7:0] crc;
  input [7:0] d;
  integer i;
  reg [7:0] c;
  begin
    c = crc ^ d;
    for (i = 0; i < 8; i = i + 1)
      c = c[7] ? ({c[6:0], 1'b0} ^ 8'h07) : {c[6:0], 1'b0};
    crc8_step = c;
  end
endfunction

assign crc_out = crc8_step(crc_in, data);

endmodule
