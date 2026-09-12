// gowin_prim_ts.v - gives the Gowin simulation library an explicit timescale so that the
// IODELAY model (delay_out <= #(0.0125*(step+1)) DI) means 12.5 ps per step under Icarus.
`timescale 1ns/1ps
`include "prim_sim.v"
