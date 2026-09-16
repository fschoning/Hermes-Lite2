-- SPDX-License-Identifier: GPL-2.0-or-later
-- Copyright 2026 Franz Schöning, https://www.schoning.com
--
-- NEORV32 configuration for the Hermes-Lite 2 soft CPU system (hl2b5up_neo, rtl/hl2cpu.v CORE = 2).
--
-- rv32imc + Zicsr, machine mode only, no caches, no internal IMEM/DMEM, no bootloader ROM, no on-chip
-- debugger (it needs JTAG pins the HL2 does not have). Every CPU access outside the NEORV32 IO region
-- (0xFFE0_0000-0xFFFF_FFFF, only SYSINFO lives there in this configuration) goes to the external bus
-- (XBUS, Wishbone): boot ROM, RAM, packet buffer and the HL2 registers of rtl/hl2cpu.v.
-- The external bus has no timeout: the layer-1 bridge may hold a CPU access for as long as it halts
-- the CPU. Timer, packet and single-step interrupts come from rtl/hl2cpu.v (no CLINT).
--
-- Plain ports only (no generics), so that GHDL can convert this entity into one Verilog module
-- (rtl/neorv32/convert.sh -> neorv32_hl2.v) for the iverilog simulations.

library ieee;
use ieee.std_logic_1164.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_hl2 is
  port (
    clk_i      : in  std_ulogic;                     -- CPU clock
    rstn_i     : in  std_ulogic;                     -- reset, low-active, asynchronous
    -- external bus (Wishbone, byte addresses)
    xbus_adr_o : out std_ulogic_vector(31 downto 0);
    xbus_dat_o : out std_ulogic_vector(31 downto 0);
    xbus_we_o  : out std_ulogic;
    xbus_sel_o : out std_ulogic_vector(3 downto 0);
    xbus_stb_o : out std_ulogic;
    xbus_cyc_o : out std_ulogic;
    xbus_tag_o : out std_ulogic_vector(2 downto 0);  -- bit 2: instruction fetch
    xbus_dat_i : in  std_ulogic_vector(31 downto 0);
    xbus_ack_i : in  std_ulogic;
    xbus_err_i : in  std_ulogic;
    -- interrupts (levels)
    irq_msi_i  : in  std_ulogic;                     -- machine software interrupt (mcause 0x80000003)
    irq_mti_i  : in  std_ulogic;                     -- machine timer interrupt (mcause 0x80000007)
    irq_mei_i  : in  std_ulogic                      -- machine external interrupt (mcause 0x8000000B)
  );
end entity;

architecture neorv32_hl2_rtl of neorv32_hl2 is
begin

  neorv32_top_inst: neorv32_top
  generic map (
    CLOCK_FREQUENCY   => 25_000_000,       -- informational (SYSINFO); hl2b5up_neo runs the CPU at 25 MHz
    BOOT_MODE_SELECT  => 1,               -- start at BOOT_ADDR_CUSTOM
    BOOT_ADDR_CUSTOM  => x"00010000",     -- HL2 boot ROM
    RISCV_ISA_C       => true,
    RISCV_ISA_M       => true,
    CPU_FAST_MUL_EN   => false,           -- serial multiplier: no DSP blocks
    CPU_FAST_SHIFT_EN => false,           -- serial shifter
    CPU_RF_ARCH_SEL   => 0,               -- register file in one memory block (synchronous SRAM style)
    XBUS_EN           => true,
    XBUS_TIMEOUT      => 0,               -- no timeout: the bridge's halt holds CPU accesses
    XBUS_REGSTAGE_EN  => false
  )
  port map (
    clk_i      => clk_i,
    rstn_i     => rstn_i,
    rstn_ocd_o => open,
    rstn_wdt_o => open,
    xbus_adr_o => xbus_adr_o,
    xbus_dat_o => xbus_dat_o,
    xbus_cti_o => open,
    xbus_tag_o => xbus_tag_o,
    xbus_we_o  => xbus_we_o,
    xbus_sel_o => xbus_sel_o,
    xbus_stb_o => xbus_stb_o,
    xbus_cyc_o => xbus_cyc_o,
    xbus_dat_i => xbus_dat_i,
    xbus_ack_i => xbus_ack_i,
    xbus_err_i => xbus_err_i,
    irq_msi_i  => irq_msi_i,
    irq_mti_i  => irq_mti_i,
    irq_mei_i  => irq_mei_i
  );

end architecture;
