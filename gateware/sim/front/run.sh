#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2026 Franz Schöning, https://www.schoning.com
# Testbenches for the raw front-end release image (docs/rawfront/PROTOCOL.md).
# Needs iverilog (oss-cad-suite) and the Quartus altera_mf.v simulation model.
#   ./run.sh         all
#   ./run.sh ilk     transmit interlock (every trip path) and the front-end register block
#   ./run.sh i2c     I2C pass-through, probes on all three buses, bias guard, status; AD9866 SPI commands
#   ./run.sh echo    echo mode and real-TX gating through the real network receive/send path
#   ./run.sh msg     message layer firmware on NEORV32 with the register block
set -e
cd "$(dirname "$0")"
QUARTUS_SIM=${QUARTUS_SIM:-/c/intelFPGA_lite/20.1.1/quartus/eda/sim_lib}
R=../../rtl
E=$R/ethernet
mkdir -p build
if [ -z "$1" ] || [ "$1" = "ilk" ]; then
  iverilog -g2012 -s tb_ilk -o build/tb_ilk.vvp tb_ilk.sv $R/hl2io.v $R/hl2bus.v $R/txsink.v 2> build/tb_ilk.iverilog.log || { cat build/tb_ilk.iverilog.log; exit 1; }
  vvp -n build/tb_ilk.vvp | tee build/tb_ilk.log
  grep -q "tb_ilk PASS" build/tb_ilk.log
fi
if [ -z "$1" ] || [ "$1" = "i2c" ]; then
  # iverilog is stricter than Quartus with the stock control files: simulate copies where control.v's
  # generate labels (named like its parameters) are renamed, procedurally driven outputs are declared
  # 'logic', and a declaration comes before its use
  sed -e 's/always @\* begin/always_comb begin/' -e 's/^module control (/module control_sim (/' -e 's/begin: PSSYNC/begin: PSSYNC_ON/' -e 's/begin: FAN$/begin: FAN_ON/' \
      -e 's/begin: ATU /begin: ATU_ON /' -e 's/^  output                     fan_pwm  /  output logic               fan_pwm  /' \
      -e 's/^logic         ptt_resp = 1.b0;/logic         ptt_resp;/' -e 's/^logic lost_clock;//' \
      -e 's/^logic slow_adc_sample;/logic slow_adc_sample; logic lost_clock;/' $R/control.v > build/control_sim.v
  cp $R/i2c_bus2.v build/i2c_bus2_sim.v
  sed -e 's/^output      led;/output logic led;/' $R/led_flash.v > build/led_flash_sim.v
  sed -e 's/always @\* begin/always_comb begin/' -e 's/^output            rffe_ad9866_s/output logic      rffe_ad9866_s/' $R/ad9866ctrl.v > build/ad9866ctrl_sim.v
  iverilog -g2012 -s tb_i2c -o build/tb_i2c.vvp tb_i2c.sv i2c_slave_model.sv build/control_sim.v $R/i2c.v build/i2c_bus2_sim.v \
    $R/i2c_master.v $R/slow_adc.v $R/debounce.v build/led_flash_sim.v build/ad9866ctrl_sim.v $R/extamp.v $R/exttuner.v \
    2> build/tb_i2c.iverilog.log || { grep -v warning build/tb_i2c.iverilog.log; exit 1; }
  vvp -n build/tb_i2c.vvp | tee build/tb_i2c.log
  grep -q "tb_i2c PASS" build/tb_i2c.log
fi
if [ -z "$1" ] || [ "$1" = "echo" ]; then
  # iverilog: dsopenhpsdr1.v outputs declared 'logic' (as ../rawstream/run.sh); ad9866.v's generate label is
  # named like its parameter, procedurally driven outputs declared 'logic', the free-running TX phase
  # register given a start value
  sed 's/^  output              ds/  output logic        ds/' $R/dsopenhpsdr1.v > build/dsopenhpsdr1_sim.v
  sed -e 's/begin: FAST_LNA/begin: FAST_LNA_ON/' -e 's/^output  \[5:0\]     rffe_ad9866_tx;/output logic [5:0] rffe_ad9866_tx;/' \
      -e 's/^output            rffe_ad9866_txsync;/output logic      rffe_ad9866_txsync;/' \
      -e 's/^output            rffe_ad9866_pga5;/output logic      rffe_ad9866_pga5;/' \
      -e 's/^output  \[11:0\]    rx_data;/output logic [11:0] rx_data;/' \
      -e 's/^logic             tx_sync;/logic             tx_sync = 0;/' $R/ad9866.v > build/ad9866_sim.v
  iverilog -g2012 -s tb_echo -o build/tb_echo.vvp tb_echo.sv $R/rawstream.v $R/txsink.v $R/hl2io.v build/ad9866_sim.v \
    build/dsopenhpsdr1_sim.v $R/sync.v $E/rgmii_recv.v $E/ddio_in.v $E/mac_recv.v $E/ip_recv.v $E/udp_recv.v \
    $E/udp_send.v $E/ip_send.v $E/mac_send.v $E/crc32.v $E/rgmii_send.v $QUARTUS_SIM/altera_mf.v \
    2> build/tb_echo.iverilog.log || { grep -v warning build/tb_echo.iverilog.log; exit 1; }
  vvp -n build/tb_echo.vvp | tee build/tb_echo.log
  grep -q "tb_echo PASS" build/tb_echo.log
fi
if [ -z "$1" ] || [ "$1" = "msg" ]; then
  [ -f msg_ram.hex ] || { echo "msg_ram.hex missing: run firmware/hl2neo/build.py"; exit 1; }
  iverilog -g2012 -s tb_msg -o build/tb_msg.vvp tb_msg.sv $R/hl2cpu.v $R/neorv32/neorv32_hl2.v $R/hl2bus.v $R/hl2io.v \
    $R/txsink.v $QUARTUS_SIM/altera_mf.v 2> build/tb_msg.iverilog.log || { grep -v warning build/tb_msg.iverilog.log; exit 1; }
  vvp -n build/tb_msg.vvp | tee build/tb_msg.log
  grep -q "tb_msg PASS" build/tb_msg.log
fi
