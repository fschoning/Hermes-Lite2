#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2026 Franz Schöning, https://www.schoning.com
# Simulate the soft CPU system (tb_neo: NEORV32 with the real boot ROM and demo) and the ASMI flash path
# (tb_asmi). Needs iverilog (oss-cad-suite), the Quartus altera_mf.v / 220model.v simulation models and the
# firmware built by firmware/hl2neo/build.py (bootrom_neo.hex here, demo.elf/demo.bin in firmware/hl2neo/build).
# The NEORV32 is the Verilog conversion rtl/neorv32/neorv32_hl2.v (rtl/neorv32/convert.sh).
#   ./run.sh         both
#   ./run.sh asmi    ASMI megafunction + flash model: erase range, CPU sector guard, lock-out
#   ./run.sh neo     SoC: boot ROM, console, bridge, reset/halt, RAM load, flash save/boot, gdb stub, single step
set -e
cd "$(dirname "$0")"
QUARTUS_SIM=${QUARTUS_SIM:-/c/intelFPGA_lite/20.1.1/quartus/eda/sim_lib}
R=../../rtl
mkdir -p build
if [ -z "$1" ] || [ "$1" = "asmi" ]; then
  iverilog -g2012 -s tb_asmi -o build/tb_asmi.vvp tb_asmi.sv epcs_model.v $R/asmi_interface.v $R/asmi_asmi_parallel_0.v \
    $QUARTUS_SIM/altera_mf.v $QUARTUS_SIM/220model.v 2> build/tb_asmi.iverilog.log || { cat build/tb_asmi.iverilog.log; exit 1; }
  vvp -n build/tb_asmi.vvp
fi
if [ -z "$1" ] || [ "$1" = "neo" ]; then
  WFI=$(${RISCV_NM:-/c/tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-nm} ../../../firmware/hl2neo/build/demo.elf | awk '$3=="cpu_wfi"{print $1}')
  OUT=$(${RISCV_NM:-/c/tools/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-nm} ../../../firmware/hl2neo/build/demo.elf | awk '$3=="out"{print $1}')
  iverilog -g2012 -s tb_neo -o build/tb_neo.vvp tb_neo.sv epcs_model.v $R/hl2cpu.v $R/neorv32/neorv32_hl2.v $R/hl2bus.v $R/txsink.v $R/asmi_interface.v $R/asmi_asmi_parallel_0.v $QUARTUS_SIM/altera_mf.v $QUARTUS_SIM/220model.v 2> build/tb_neo.iverilog.log || { grep -v "warning" build/tb_neo.iverilog.log; exit 1; }
  vvp -n build/tb_neo.vvp +demo_wfi=$WFI +demo_out=$OUT
fi
