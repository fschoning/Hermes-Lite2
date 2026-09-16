#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2026 Franz Schöning, https://www.schoning.com
# Fitter seed trial: ./seed_try.sh <seed>. Uses the existing synthesis; appends to seeds.txt.
set -e
cd "$(dirname "$0")"
sed -i "s/^set_global_assignment -name SEED .*/set_global_assignment -name SEED $1/" hermeslite.qsf
quartus_fit hermeslite -c hermeslite > fit_seed.log 2>&1
quartus_sta hermeslite -c hermeslite > sta_seed.log 2>&1
r=build/hermeslite.sta.rpt
get() { awk -v s="; $1" -v c="$2" 'index($0,s)==1{f=1;next} f&&index($0,"; "c" ")==1{print $4; exit}' $r; }
printf "seed %-3s  setup85: ethtx %s ethrx %s | setup0: ethtx %s ethrx %s | hold85: ethtx %s ethrx %s\n" "$1" \
  "$(get 'Slow 1200mV 85C Model Setup Summary' clock_ethtxintfast)" "$(get 'Slow 1200mV 85C Model Setup Summary' clock_ethrxintfast)" \
  "$(get 'Slow 1200mV 0C Model Setup Summary' clock_ethtxintfast)" "$(get 'Slow 1200mV 0C Model Setup Summary' clock_ethrxintfast)" \
  "$(get 'Slow 1200mV 85C Model Hold Summary' clock_ethtxintfast)" "$(get 'Slow 1200mV 85C Model Hold Summary' clock_ethrxintfast)" | tee -a seeds.txt
