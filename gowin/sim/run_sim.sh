#!/bin/sh
# Runs the gowinlink simulations with Icarus Verilog (bash / Git Bash).
#   ./run_sim.sh            all testbenches (tb_uart, tb_link LANES=6, tb_link LANES=3)
#   ./run_sim.sh uart       only tb_uart
#   ./run_sim.sh link 6     tb_link with LANES=6
# Build products go to gowin/sim/build (ignored by git).
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
IVERILOG=${IVERILOG:-/c/tools/oss-cad-suite/bin/iverilog.exe}
VVP=${VVP:-/c/tools/oss-cad-suite/bin/vvp.exe}
GOWIN_SIMLIB=${GOWIN_SIMLIB:-/c/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw5a/prim_sim.v}
export PATH="$(dirname "$IVERILOG")":"$(dirname "$IVERILOG")/../lib":$PATH
SIMLIB_DIR=$(dirname "$GOWIN_SIMLIB")
BUILD="$HERE/build"
mkdir -p "$BUILD"

SHARED="$ROOT/gateware/rtl/gowinlink"
GRTL="$ROOT/gowin/rtl"
SHARED_SRC="$SHARED/gowinlink_uart_rx.v $SHARED/gowinlink_uart_tx.v $SHARED/gowinlink_crc8.v \
 $SHARED/gowinlink_cmd_rx.v $SHARED/gl_fastserial_tx.v $SHARED/gl_fastserial_rx.v"
SRC="$SHARED/gowinlink_uart_rx.v $SHARED/gowinlink_uart_tx.v $SHARED/gowinlink_crc8.v \
 $SHARED/gowinlink_prbs23.v $SHARED/gowinlink_scrambler.v $SHARED/gowinlink_ddr_out.v \
 $SHARED/gowinlink_ddr_in.v $SHARED/gowinlink_tx_lanes.v $SHARED/gowinlink_cmd_rx.v \
 $SHARED/gowinlink_cmd_mux.v $SHARED/gowinlink_status_tx.v $SHARED/gowinlink_rxpll.v \
 $SHARED/gowinlink_rev_train.v $SHARED/gowinlink_fs_cmd.v $SHARED/gowinlink_hl2.v \
 $SHARED/gl_cdc.v $SHARED/gl_rx_datapath.v $SHARED/gl_fastserial_tx.v $SHARED/gl_fastserial_rx.v \
 $GRTL/gl_lane_rx.v $GRTL/gl_pll.v $GRTL/gl_cmd_tx.v $GRTL/gl_cmd_fs.v $GRTL/gl_status_rx.v \
 $GRTL/gl_train.v $GRTL/gl_console.v $GRTL/gl_top.v"

run_uart() {
  echo "== tb_uart"
  "$IVERILOG" -g2012 -DSIM -s tb_uart -o "$BUILD/tb_uart.vvp" $SHARED_SRC "$HERE/tb_uart.v"
  "$VVP" -n "$BUILD/tb_uart.vvp" | tee "$BUILD/tb_uart.log"
}

run_rev() {
  echo "== tb_rev"
  "$IVERILOG" -g2012 -DSIM -s tb_rev -o "$BUILD/tb_rev.vvp" -I "$GRTL" $SRC "$GOWIN_SIMLIB"       "$HERE/tb_cable.v" "$HERE/tb_rev.v" 2>&1 | grep -v "prim_sim.v.*warning" || true
  "$VVP" -n "$BUILD/tb_rev.vvp" | tee "$BUILD/tb_rev.log"
}

run_link() {
  L=$1
  echo "== tb_link LANES=$L"
  "$IVERILOG" -g2012 -DSIM -s tb_link -Ptb_link.LANES=$L -o "$BUILD/tb_link_$L.vvp" -I "$GRTL" \
      $SRC -I "$SIMLIB_DIR" "$HERE/gowin_prim_ts.v" "$HERE/tb_cable.v" "$HERE/tb_link.v" 2>&1 | grep -v "prim_sim.v.*warning" || true
  "$VVP" -n "$BUILD/tb_link_$L.vvp" | tee "$BUILD/tb_link_$L.log"
}

case "${1:-all}" in
  uart) run_uart ;;
  rev)  run_rev ;;
  link) run_link "${2:-6}" ;;
  all)  run_uart; run_rev; run_link 6; run_link 3 ;;
  *) echo "usage: $0 [all|uart|rev|link [6|3]]"; exit 1 ;;
esac
