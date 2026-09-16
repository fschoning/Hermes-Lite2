// Modified 2026 by Franz Schöning
`timescale 1ns / 1ps

module i2c_bus2
(
  clk,
  rst,

  cmd_addr,
  cmd_data,
  cmd_rqst,
  cmd_ack,
  cmd_resp_data,

  read_done,
  en_i2c2,
  ready,

  scl_i,
  scl_o,
  scl_t,
  sda_i,
  sda_o,
  sda_t,

  xfer_done,
  xfer_nack,
  xfer_accept,
  busy_o
);

input         clk;
input         rst;

// Command slave interface
input  [5:0]  cmd_addr;
input  [31:0] cmd_data;
input         cmd_rqst;
output        cmd_ack;
output [31:0] cmd_resp_data;

output  logic read_done;
output  logic en_i2c2;
output        ready;

input         scl_i;
output        scl_o;
output        scl_t;
input         sda_i;
output        sda_o;
output        sda_t;

// Pass-through status (raw front-end image): a 0x3C/0x3D request was accepted (same cycle as cmd_rqst),
// the transfer finished (the I2C master is idle again), whether any byte of it was not acknowledged.
// Probe (cmd_data[24] and [23] set): address with the read bit, one byte read, stop.
output logic  xfer_done = 1'b0;
output logic  xfer_nack = 1'b0;
output logic  xfer_accept;
output        busy_o;

logic [6:0]   cmd_address;
logic         cmd_start;
logic         cmd_read;
logic         cmd_write;
logic         cmd_write_multiple;
logic         cmd_stop;
logic         cmd_valid;
logic         cmd_ready;

logic [7:0]   data_in;
logic         data_in_valid;
logic         data_in_ready;
logic         data_in_last;

logic [7:0]   data_out;
logic         data_out_valid;
logic         data_out_ready;
logic         data_out_last;

logic [3:0]   state, state_next;
logic         busy, missed_ack, bus_control;

logic [6:0]   cmd_reg, cmd_next;
logic [7:0]   data0_reg, data0_next, data1_reg, data1_next;

logic         cmd_ack_reg, cmd_ack_next;

logic [6:0]   filter_select_reg, filter_select_next;
logic         rx_antenna_reg, rx_antenna_next;

logic         en_i2c2_next;

logic [31:0]  resp_data_next, resp_data=32'h00000000;

logic         xfer_pend = 1'b0;

`ifdef AK4951
logic         ak4951_spon_reg, ak4951_spon_next;
logic         ak4951_micboost_reg, ak4951_micboost_next;
`endif



// Control
localparam [3:0]
  STATE_IDLE          = 4'h0,
  STATE_CMDADDR       = 4'h1,
  STATE_WRITE_DATA0   = 4'h2,
  STATE_WRITE_DATA1   = 4'h3,
  STATE_FCMDADDR      = 4'h5,
  STATE_WRITE_FDATA0  = 4'h6,
  STATE_WRITE_FDATA1  = 4'h7,
  STATE_WRITE_FDATA2  = 4'h4,
  STATE_READ_CMDADDR  = 4'h8,
  STATE_READ_DATA0    = 4'h9,
  STATE_READ_DATA1    = 4'ha,
  STATE_READ_DATA2    = 4'hb,
  STATE_READ_DATA3    = 4'hc,
  STATE_READ_DATA4    = 4'hd;

always @(posedge clk) begin
  if (rst) begin
    state <= STATE_IDLE;
    cmd_reg <= 'h0;
    data0_reg <= 'h0;
    data1_reg <= 'h0;
    cmd_ack_reg <= 1'b0;
    filter_select_reg <= 'h0;
    rx_antenna_reg <= 1'b0;
`ifdef AK4951
    ak4951_spon_reg <= 1'b0;
    ak4951_micboost_reg <= 1'b0;
`endif
  end else begin
    state <= state_next;
    cmd_reg <= cmd_next;
    data0_reg <= data0_next;
    data1_reg <= data1_next;
    cmd_ack_reg <= cmd_ack_next;
    filter_select_reg <= filter_select_next;
    rx_antenna_reg <= rx_antenna_next;
`ifdef AK4951
    ak4951_spon_reg <= ak4951_spon_next;
    ak4951_micboost_reg <= ak4951_micboost_next;
`endif
    en_i2c2 <= en_i2c2_next;
  end
  resp_data <= resp_data_next;
end

always @(posedge clk) begin
  xfer_done <= 1'b0;
  if (xfer_accept) begin
    xfer_pend <= 1'b1;
    xfer_nack <= 1'b0;
  end else begin
    if (xfer_pend & missed_ack) xfer_nack <= 1'b1;
    // done when the master has released the bus (after the stop condition)
    if (xfer_pend & (state == STATE_IDLE) & ~busy & ~bus_control & ~missed_ack) begin
      xfer_pend <= 1'b0;
      xfer_done <= 1'b1;
    end
  end
end

assign busy_o = xfer_pend | (state != STATE_IDLE);

assign cmd_address = cmd_reg;
assign cmd_start = 1'b0;
assign cmd_write_multiple = 1'b0;

assign data_in_last = 1'b1;

assign data_out_ready = 1'b1;

assign cmd_ack = cmd_ack_reg;

assign cmd_resp_data = resp_data;

// continuous (was a default-then-override in the state block, which makes iverilog oscillate between
// this block and i2c.v's; same logic)
assign ready = (state == STATE_IDLE) & ~busy;


always @* begin
  state_next = state;
  resp_data_next = resp_data;
  cmd_ack_next = cmd_ack;
  filter_select_next = filter_select_reg;
  rx_antenna_next = rx_antenna_reg;
`ifdef AK4951
  ak4951_spon_next = ak4951_spon_reg;
  ak4951_micboost_next = ak4951_micboost_reg;
`endif
  cmd_next = cmd_reg;
  data0_next = data0_reg;
  data1_next = data1_reg;
  en_i2c2_next = en_i2c2;


  cmd_valid = 1'b1;
  cmd_write = 1'b0;
  cmd_read  = 1'b0;
  cmd_stop = 1'b0;
  read_done = 1'b0;

  data_in = data0_reg;
  data_in_valid = 1'b0;

  xfer_accept = 1'b0;

  case(state)

    STATE_IDLE: begin
      cmd_valid = 1'b0;
      cmd_ack_next = 1'b1;
      if (cmd_rqst) begin
        if (((cmd_addr == 6'h3d) | (cmd_addr == 6'h3c)) & (cmd_data[31:25] == 7'h03)) begin
          // Must send
          if (~busy) begin
            cmd_next = cmd_data[22:16];
            data0_next  = cmd_data[15:8];
            data1_next = cmd_data[7:0];
            en_i2c2_next = (cmd_addr == 6'h3d);
            xfer_accept = 1'b1;
            if (cmd_data[24] & cmd_data[23]) begin
              // probe: one byte read at the address, no register pointer write
              cmd_ack_next = 1'b0;
              state_next = STATE_READ_DATA4;
            end else begin
              state_next = cmd_data[24] ? STATE_READ_CMDADDR : STATE_CMDADDR;
            end
          end else begin
            cmd_ack_next = 1'b0; // Missed
          end
        end

        // Filter select update
        if (cmd_addr == 6'h00) begin
          if ((cmd_data[23:17] != filter_select_reg) | (cmd_data[13] != rx_antenna_reg)) begin
            // Must send
            if (~busy) begin
              filter_select_next = cmd_data[23:17];
              rx_antenna_next = cmd_data[13];
              cmd_next = 'h20;
              data0_next = 'h0a;
              // Alex rx antenna option passed to GP7 on MCP23008 GP7
              data1_next = {cmd_data[13],cmd_data[23:17]};
              en_i2c2_next = 1'b1;
              state_next = STATE_FCMDADDR;
            end else begin
              cmd_ack_next = 1'b0; // Missed
            end
          end

`ifdef AK4951
          // AK4951 speaker on/off setting update
          if (cmd_data[11] != ak4951_spon_reg) begin
            // Must send
            if (~busy) begin
              ak4951_spon_next = cmd_data[11]; // reuse Dither
              cmd_next = 'h12;
              data0_next = 'h02;
              data1_next = 8'h2e | (cmd_data[11]? 8'h80 : 8'h00);
              en_i2c2_next = 1'b0;
              state_next = STATE_FCMDADDR;
            end else begin
              cmd_ack_next = 1'b0; // Missed
            end
          end
`endif          
        end

`ifdef AK4951
        // AK4951 mic boost setting update
        if (cmd_addr == 6'h09) begin
          if (cmd_data[16] != ak4951_micboost_reg) begin
            // Must send
            if (~busy) begin
              ak4951_micboost_next = cmd_data[16];
              cmd_next = 'h12;
              data0_next = 'h0d;
              data1_next = cmd_data[16]? 8'hc7: 8'h91; // 20.25dB : 0dB
              en_i2c2_next = 1'b0;
              state_next = STATE_FCMDADDR;
            end else begin
              cmd_ack_next = 1'b0; // Missed
            end
          end
        end
`endif
      end
    end

    STATE_CMDADDR: begin
      cmd_write = 1'b1;
      if (cmd_ready) state_next = STATE_WRITE_DATA0;
    end

    STATE_WRITE_DATA0: begin
      cmd_write = 1'b1;
      data_in_valid = 1'b1;
      data_in = data0_reg;
      if (data_in_ready) state_next = STATE_WRITE_DATA1;
    end

    STATE_WRITE_DATA1: begin
      cmd_write = 1'b1;
      data_in_valid = 1'b1;
      data_in = data1_reg;
      if (data_in_ready) state_next = STATE_IDLE;
    end

    STATE_READ_CMDADDR: begin
      cmd_ack_next = 1'b0; // Hold ack low until read data is ready
      cmd_write = 1'b1;
      cmd_stop = 1'b1;
      if (cmd_ready) state_next = STATE_READ_DATA0;
    end

    STATE_READ_DATA0: begin
      cmd_read = 1'b1;
      data_in_valid = 1'b1;
      data_in = data0_reg;
      if (data_in_ready) state_next = STATE_READ_DATA1;
    end

    STATE_READ_DATA1: begin
      cmd_read = 1'b1;
      resp_data_next = {resp_data[31:8],data_out};
      if (data_out_valid) state_next = STATE_READ_DATA2;
    end

    STATE_READ_DATA2: begin
      cmd_read = 1'b1;
      resp_data_next = {resp_data[31:16],data_out,resp_data[7:0]};
      if (data_out_valid) state_next = STATE_READ_DATA3;
    end

    STATE_READ_DATA3: begin
      cmd_read = 1'b1;
      resp_data_next = {resp_data[31:24],data_out,resp_data[15:0]};
      if (data_out_valid) state_next = STATE_READ_DATA4;
    end

    STATE_READ_DATA4: begin
      cmd_stop = 1'b1;
      cmd_read = 1'b1;
      resp_data_next = {data_out,resp_data[23:0]};
      if (data_out_valid) begin
        read_done = 1'b1;
        state_next = STATE_IDLE;
      end
    end

    STATE_FCMDADDR: begin
      cmd_write = 1'b1;
      if (cmd_ready) state_next = STATE_WRITE_FDATA0;
    end

    STATE_WRITE_FDATA0: begin
      cmd_write = 1'b1;
      data_in_valid = 1'b1;
      data_in = data0_reg;
      if (data_in_ready) state_next = STATE_WRITE_FDATA1;
    end

    STATE_WRITE_FDATA1: begin
      cmd_write = 1'b1;
      data_in_valid = 1'b1;
      data_in = data1_reg;
      if (data_in_ready) state_next = STATE_WRITE_FDATA2;
    end

    STATE_WRITE_FDATA2: begin
      cmd_write = 1'b1;
      data_in_valid = 1'b1;
      data_in = 'h00;
      if (data_in_ready) state_next = STATE_IDLE;
    end

  endcase
end


i2c_master i2c_master_i (
  .clk(clk),
  .rst(rst),
  /*
   * Host interface
   */
  .cmd_address(cmd_address),
  .cmd_start(cmd_start),
  .cmd_read(cmd_read),
  .cmd_write(cmd_write),
  .cmd_write_multiple(cmd_write_multiple),
  .cmd_stop(cmd_stop),
  .cmd_valid(cmd_valid),
  .cmd_ready(cmd_ready),

  .data_in(data_in),
  .data_in_valid(data_in_valid),
  .data_in_ready(data_in_ready),
  .data_in_last(data_in_last),

  .data_out(data_out),
  .data_out_valid(data_out_valid),
  .data_out_ready(data_out_ready),
  .data_out_last(data_out_last),

  // I2C
  .scl_i(scl_i),
  .scl_o(scl_o),
  .scl_t(scl_t),
  .sda_i(sda_i),
  .sda_o(sda_o),
  .sda_t(sda_t),

  // Status
  .busy(busy),
  .bus_control(bus_control),
  .bus_active(),
  .missed_ack(missed_ack),

  // Configuration
  .prescale(16'h0002),
  .stop_on_idle(1'b1)
);

endmodule


