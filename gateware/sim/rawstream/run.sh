#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2026 Franz Schöning, https://www.schoning.com
# Simulate rtl/rawstream.v (tb_rawstream), the duplex TX sink (tb_duplex), the aux channel (tb_aux) and the register bridge (tb_bridge) with the real
# HL2 send and receive paths. Needs iverilog (oss-cad-suite) and the Quartus altera_mf.v
# simulation model (dcfifo, altddio_in, altddio_out).
#   ./run.sh            all testbenches
#   ./run.sh rawstream  only tb_rawstream
#   ./run.sh duplex     only tb_duplex
#   ./run.sh aux        only tb_aux (aux data channel, rtl/auxchan.v)
#   ./run.sh bridge     only tb_bridge (register bridge, rtl/hl2bus.v)
set -e
cd "$(dirname "$0")"
QUARTUS_SIM=${QUARTUS_SIM:-/c/intelFPGA_lite/20.1.1/quartus/eda/sim_lib}
R=../../rtl
E=$R/ethernet
mkdir -p build
if [ -z "$1" ] || [ "$1" = "rawstream" ]; then
  iverilog -g2012 -s tb_rawstream -o build/tb_rawstream.vvp   tb_rawstream.sv $R/rawstream.v   $E/udp_send.v $E/ip_send.v $E/mac_send.v   $E/crc32.v $E/rgmii_send.v   $QUARTUS_SIM/altera_mf.v
  vvp -n build/tb_rawstream.vvp
fi
if [ -z "$1" ] || [ "$1" = "duplex" ] || [ "$1" = "aux" ] || [ "$1" = "bridge" ]; then
  # iverilog rejects procedural assignment to plain outputs; the sim copy only declares them 'logic'
  sed 's/^  output              ds/  output logic        ds/' $R/dsopenhpsdr1.v > build/dsopenhpsdr1_sim.v
fi
if [ -z "$1" ] || [ "$1" = "aux" ]; then
  iverilog -g2012 -s tb_aux -o build/tb_aux.vvp   tb_aux.sv $R/rawstream.v $R/txsink.v $R/auxchan.v build/dsopenhpsdr1_sim.v $R/sync.v   $E/rgmii_recv.v $E/ddio_in.v $E/mac_recv.v $E/ip_recv.v $E/udp_recv.v   $E/udp_send.v $E/ip_send.v $E/mac_send.v $E/crc32.v $E/rgmii_send.v   $QUARTUS_SIM/altera_mf.v
  vvp -n build/tb_aux.vvp
fi
if [ -z "$1" ] || [ "$1" = "bridge" ]; then
  iverilog -g2012 -s tb_bridge -o build/tb_bridge.vvp   tb_bridge.sv $R/hl2bus.v $R/rawstream.v $R/txsink.v $R/auxchan.v build/dsopenhpsdr1_sim.v $R/sync.v   $E/rgmii_recv.v $E/ddio_in.v $E/mac_recv.v $E/ip_recv.v $E/udp_recv.v   $E/udp_send.v $E/ip_send.v $E/mac_send.v $E/crc32.v $E/rgmii_send.v   $QUARTUS_SIM/altera_mf.v
  vvp -n build/tb_bridge.vvp
fi
if [ -z "$1" ] || [ "$1" = "duplex" ]; then
  iverilog -g2012 -s tb_duplex -o build/tb_duplex.vvp   tb_duplex.sv $R/rawstream.v $R/txsink.v build/dsopenhpsdr1_sim.v $R/sync.v   $E/rgmii_recv.v $E/ddio_in.v $E/mac_recv.v $E/ip_recv.v $E/udp_recv.v   $E/udp_send.v $E/ip_send.v $E/mac_send.v $E/crc32.v $E/rgmii_send.v   $QUARTUS_SIM/altera_mf.v
  vvp -n build/tb_duplex.vvp
fi
