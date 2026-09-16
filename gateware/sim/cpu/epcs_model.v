// SPDX-License-Identifier: GPL-2.0-or-later
// Copyright 2026 Franz Schöning, https://www.schoning.com
//
// Simulation only: replaces the Quartus cycloneive_asmiblock atom (which has no flash model) with
// an EPCS16-style SPI flash (M25P16 command set) so the generated ASMI megafunction netlist
// (rtl/asmi_asmi_parallel_0.v) can be simulated with real flash behaviour.
//
// Commands: 06 WREN, 04 WRDI, 05 RDSR, 01 WRSR, 03 READ, 0B FAST_READ, 02 PP, D8 SE, C7 BE,
// AB RES (signature 0x14), 9F RDID. Page program ANDs data into the memory. Erase and program
// set WIP for ERASE_TIME / PROG_TIME. Counters and a sector bitmap let a testbench check which
// sectors and pages were touched.

`timescale 1 ps / 1 ps

module cycloneive_asmiblock (
  input  dclkin,
  input  scein,
  input  oe,
  input  sdoin,
  output data0out
);
  epcs_flash flash (.dclk(oe === 1'b0 ? dclkin : 1'b0), .ncs(oe === 1'b0 ? scein : 1'b1),
                    .mosi(sdoin), .miso(data0out));
endmodule

module epcs_flash #(
  parameter SIZE       = 24'h200000,
  parameter ERASE_TIME = 64'd2_000_000_000,     // 2 ms in ps
  parameter PROG_TIME  = 64'd200_000_000        // 0.2 ms
) (
  input      dclk,
  input      ncs,
  input      mosi,
  output reg miso = 1'b0
);
  reg [7:0] mem [0:SIZE-1];
  integer i;
  initial for (i = 0; i < SIZE; i = i + 1) mem[i] = 8'hff;

  reg        wel = 1'b0;
  reg        wip = 1'b0;
  reg [7:0]  cmd = 8'h00;
  integer    nbits = 0;
  reg [7:0]  sh_in = 8'h00;
  reg [7:0]  sh_out = 8'h00;
  reg [23:0] addr = 24'h0;
  reg [23:0] rd_addr = 24'h0;
  reg [7:0]  pbuf [0:255];
  integer    pcount = 0;

  // statistics for testbenches
  integer    n_erase = 0, n_prog = 0, n_bad = 0, n_read = 0;
  reg [23:0] last_erase = 24'hffffff;
  reg [255:0] erased_sectors = 256'd0;   // bit s: sector s (s * 64 kB) erased
  reg [23:0] prog_min = 24'hffffff, prog_max = 24'h000000;

  wire is_read = (cmd == 8'h03) || (cmd == 8'h0b);
  wire [31:0] data_start = (cmd == 8'h0b) ? 40 : 32;

  always @(negedge ncs) begin
    nbits  = 0;
    pcount = 0;
  end

  // sample on the rising edge
  always @(posedge dclk) if (!ncs) begin
    sh_in = {sh_in[6:0], mosi};
    nbits = nbits + 1;
    if (nbits == 8) begin
      cmd = sh_in;
      case (cmd)
        8'h06: wel = 1'b1;
        8'h04: wel = 1'b0;
        8'h05: sh_out = {6'd0, wel, wip};
        8'hab: sh_out = 8'h14;
        8'h9f: sh_out = 8'h20;
        default: ;
      endcase
    end else if (nbits > 8 && nbits <= 32) begin
      addr = {addr[22:0], mosi};
      if (nbits == 32) begin
        rd_addr = addr;
        if (cmd == 8'h03) begin sh_out = mem[addr % SIZE]; n_read = n_read + 1; end
      end
    end else if (nbits > 32) begin
      if (cmd == 8'h0b && nbits == 40) begin sh_out = mem[rd_addr % SIZE]; n_read = n_read + 1; end
      if (cmd == 8'h02 && (nbits % 8) == 0) begin
        pbuf[pcount % 256] = sh_in;
        pcount = pcount + 1;
      end
    end
  end

  // drive on the falling edge, MSB first
  always @(negedge dclk) if (!ncs) begin
    if (is_read && nbits >= data_start) begin
      miso = sh_out[7];
      sh_out = {sh_out[6:0], 1'b0};
      if (((nbits - data_start) % 8) == 7) begin
        rd_addr = rd_addr + 1;
        sh_out = mem[rd_addr % SIZE];
      end
    end else if ((cmd == 8'h05 || cmd == 8'hab || cmd == 8'h9f) && nbits >= 8) begin
      miso = sh_out[7];
      sh_out = {sh_out[6:0], 1'b0};
      if ((nbits % 8) == 7 && cmd == 8'h05) sh_out = {6'd0, wel, wip};
    end
  end

  // commands that act when chip select rises
  always @(posedge ncs) begin
    if (nbits >= 8) begin
      case (cmd)
        8'h02: if (wel && !wip && nbits >= 40) begin
          n_prog = n_prog + 1;
          if (addr < prog_min) prog_min = addr;
          if (addr + pcount - 1 > prog_max) prog_max = addr + pcount - 1;
          for (i = 0; i < pcount && i < 256; i = i + 1) mem[(addr + i) % SIZE] = mem[(addr + i) % SIZE] & pbuf[i];
          wel = 1'b0;
          wip = 1'b1;
          #(PROG_TIME) wip = 1'b0;
        end else n_bad = n_bad + 1;
        8'hd8: if (wel && !wip && nbits == 32) begin
          n_erase = n_erase + 1;
          last_erase = addr;
          erased_sectors[addr[23:16]] = 1'b1;
          for (i = {addr[23:16], 16'h0000}; i <= {addr[23:16], 16'hffff}; i = i + 1) mem[i % SIZE] = 8'hff;
          wel = 1'b0;
          wip = 1'b1;
          #(ERASE_TIME) wip = 1'b0;
        end else n_bad = n_bad + 1;
        8'hc7: if (wel && !wip) begin
          n_erase = n_erase + 1;
          for (i = 0; i < SIZE; i = i + 1) mem[i] = 8'hff;
          wel = 1'b0;
          wip = 1'b1;
          #(ERASE_TIME) wip = 1'b0;
        end
        8'h01: wel = 1'b0;
        default: ;
      endcase
    end
  end
endmodule
