# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Franz Schöning, https://www.schoning.com
<#
.SYNOPSIS
  Print (and, with -Apply, set) the Windows NIC settings recommended
  for receiving the HL2 raw ADC stream (docs/rawfront/TOOLCHAIN.md, "Network card setup").
  Written for Realtek adapters; other drivers may name the properties differently.

.DESCRIPTION
  Settings applied:
    - Jumbo Frame          9014   (fewer packets/sec; use -JumboSize to try 4088 or Disabled
                                    for smaller frames)
    - Receive Buffers      max offered by the driver (survives short CPU stalls)
    - Flow Control         Disabled (the HL2 does not decode PAUSE frames)
    - Interrupt Moderation left as the driver's current/default "Enabled" setting:
                            -Apply does not touch it; it is only reported.
    - Energy Efficient Ethernet / Green Ethernet, if present, disabled
    - IP address           static 169.254.1.1 / 255.255.0.0, no gateway -- same subnet as the
                            HL2's automatic no-DHCP fallback address

  -Apply requires an elevated (Administrator) PowerShell. Without -Apply this script only
  prints current values and what it WOULD change.

  -Restore saves the adapter's current advanced-property and IP settings to a JSON file
  before -Apply changes anything (default: nic_setup_backup.json next to this script), and
  can restore them later with -Restore -RestoreFile <path>.

.PARAMETER Apply
  Actually change the settings. Needs Administrator. Without this, dry-run only.

.PARAMETER AdapterName
  NIC to configure. Default "Ethernet".

.PARAMETER JumboSize
  Jumbo Frame value to request: 9014 (default), 4088, or Disabled.

.PARAMETER Restore
  Restore previously saved settings from -RestoreFile instead of applying new ones.

.PARAMETER RestoreFile
  Path to the backup JSON file. Default: nic_setup_backup.json next to this script.

.PARAMETER Counters
  Just print Get-NetAdapterStatistics and netstat -s -p udp for the adapter and exit --
  run this before and after a capture to tell link drops from PC drops.

.EXAMPLE
  .\nic_setup.ps1
  Dry run: show current settings and what would change.

.EXAMPLE
  .\nic_setup.ps1 -Apply
  Apply the recommended settings (elevated PowerShell required). Saves a backup first.

.EXAMPLE
  .\nic_setup.ps1 -Restore
  Put the adapter back the way it was before -Apply.

.EXAMPLE
  .\nic_setup.ps1 -Counters
  Print NIC and UDP counters (run before and after a capture, diff by eye).
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$AdapterName = "Ethernet",
    [ValidateSet("9014", "4088", "Disabled")]
    [string]$JumboSize = "9014",
    [switch]$Restore,
    [string]$RestoreFile = "$PSScriptRoot\nic_setup_backup.json",
    [switch]$Counters
)

function Assert-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "This action needs an elevated (Administrator) PowerShell. Re-run as Administrator." -ForegroundColor Yellow
        exit 1
    }
}

function Get-Adapter {
    param([string]$Name)
    $a = Get-NetAdapter -Name $Name -ErrorAction SilentlyContinue
    if (-not $a) {
        Write-Host "Adapter '$Name' not found. Available adapters:" -ForegroundColor Red
        Get-NetAdapter | Format-Table Name, InterfaceDescription, Status | Out-String | Write-Host
        exit 1
    }
    return $a
}

# ---- known Realtek advanced-property display names this script tries, in order ----
# Realtek's driver UI wording differs slightly between driver versions; the script tries
# each candidate name and skips ones the installed driver doesn't expose.
$JumboNames        = @("Jumbo Frame", "Jumbo Packet")
$RxBufferNames     = @("Receive Buffers", "Receive Buffer Size", "Receive Descriptors")
$FlowControlNames  = @("Flow Control")
$EeeNames          = @("Energy Efficient Ethernet", "Green Ethernet", "Advanced EEE")
$InterruptModNames = @("Interrupt Moderation", "Interrupt Moderation Rate")

$StaticIp     = "169.254.1.1"
$StaticPrefix = 16   # 255.255.0.0

function Get-AdvProp {
    param($Adapter, [string[]]$Candidates)
    foreach ($n in $Candidates) {
        $p = Get-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $n -ErrorAction SilentlyContinue
        if ($p) { return $p }
    }
    return $null
}

function Show-Current {
    param($Adapter)
    Write-Host "`n==== Current state of '$($Adapter.Name)' ====" -ForegroundColor Cyan

    foreach ($group in @(
        @{ Label = "Jumbo Frame";          Names = $JumboNames },
        @{ Label = "Receive Buffers";      Names = $RxBufferNames },
        @{ Label = "Flow Control";         Names = $FlowControlNames },
        @{ Label = "EEE / Green Ethernet"; Names = $EeeNames },
        @{ Label = "Interrupt Moderation"; Names = $InterruptModNames }
    )) {
        $p = Get-AdvProp -Adapter $Adapter -Candidates $group.Names
        if ($p) {
            Write-Host ("  {0,-22} = {1}  (registry name: {2})" -f $group.Label, $p.DisplayValue, $p.DisplayName)
        } else {
            Write-Host ("  {0,-22} = <not exposed by this driver>" -f $group.Label) -ForegroundColor DarkGray
        }
    }

    $ip = Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    if ($ip) {
        foreach ($a in $ip) {
            Write-Host ("  IPv4 address          = {0}/{1}  (DHCP: {2})" -f $a.IPAddress, $a.PrefixLength, $a.PrefixOrigin)
        }
    } else {
        Write-Host "  IPv4 address          = <none>"
    }
}

function Backup-Settings {
    param($Adapter, [string]$Path)
    $backup = [ordered]@{
        AdapterName = $Adapter.Name
        Timestamp   = (Get-Date).ToString("o")
        AdvProps    = @{}
        IPv4        = @()
    }
    foreach ($names in @($JumboNames, $RxBufferNames, $FlowControlNames, $EeeNames, $InterruptModNames)) {
        $p = Get-AdvProp -Adapter $Adapter -Candidates $names
        if ($p) { $backup.AdvProps[$p.DisplayName] = $p.RegistryValue -join "," }
    }
    $ip = Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    foreach ($a in $ip) {
        $backup.IPv4 += @{ IPAddress = $a.IPAddress; PrefixLength = $a.PrefixLength; PrefixOrigin = $a.PrefixOrigin.ToString() }
    }
    $backup | ConvertTo-Json -Depth 5 | Set-Content -Path $Path
    Write-Host "Backed up current settings to $Path" -ForegroundColor Green
}

function Restore-Settings {
    param($Adapter, [string]$Path)
    if (-not (Test-Path $Path)) {
        Write-Host "No backup file at $Path" -ForegroundColor Red
        exit 1
    }
    Assert-Admin
    $backup = Get-Content $Path -Raw | ConvertFrom-Json
    foreach ($prop in $backup.AdvProps.PSObject.Properties) {
        try {
            Set-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $prop.Name -RegistryValue $prop.Value -ErrorAction Stop
            Write-Host "Restored $($prop.Name) = $($prop.Value)"
        } catch {
            Write-Host "Could not restore $($prop.Name): $_" -ForegroundColor Yellow
        }
    }
    # Remove any static IP we may have set, then re-apply whatever was backed up (DHCP or static).
    Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    foreach ($a in $backup.IPv4) {
        if ($a.PrefixOrigin -eq "Dhcp" -or $a.PrefixOrigin -eq "WellKnown") {
            Set-NetIPInterface -InterfaceIndex $Adapter.ifIndex -Dhcp Enabled -ErrorAction SilentlyContinue
        } else {
            New-NetIPAddress -InterfaceIndex $Adapter.ifIndex -IPAddress $a.IPAddress -PrefixLength $a.PrefixLength -ErrorAction SilentlyContinue | Out-Null
        }
    }
    Write-Host "Restore complete." -ForegroundColor Green
}

function Apply-Settings {
    param($Adapter)
    Assert-Admin
    if (Test-Path $RestoreFile) {
        Write-Host "Backup $RestoreFile already exists; keeping it (it holds the original settings)." -ForegroundColor Yellow
    } else {
        Backup-Settings -Adapter $Adapter -Path $RestoreFile
    }

    $jumboTarget = if ($JumboSize -eq "Disabled") { "Disabled" } else { $JumboSize }
    $p = Get-AdvProp -Adapter $Adapter -Candidates $JumboNames
    if ($p) {
        try {
            $jumboReg = if ($jumboTarget -eq "Disabled") { ($p.ValidRegistryValues | Sort-Object { [int]$_ } | Select-Object -First 1) } else { $jumboTarget }
            Set-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $p.DisplayName -RegistryValue $jumboReg -ErrorAction Stop
            Write-Host "Set Jumbo Frame -> $jumboTarget"
        } catch {
            Write-Host "Could not set Jumbo Frame to '$jumboTarget': $_. Check Get-NetAdapterAdvancedProperty for the exact allowed values on this driver." -ForegroundColor Yellow
        }
    } else {
        Write-Host "This driver does not expose a Jumbo Frame property under any known name; set it manually in Device Manager -> Advanced." -ForegroundColor Yellow
    }

    $p = Get-AdvProp -Adapter $Adapter -Candidates $RxBufferNames
    if ($p) {
        $maxVal = ($p.ValidRegistryValues | Sort-Object { [int]$_ } -Descending | Select-Object -First 1)
        if (-not $maxVal) { $maxVal = $p.NumericParameterMaxValue }
        if ($maxVal) {
            try {
                Set-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $p.DisplayName -RegistryValue $maxVal -ErrorAction Stop
                Write-Host "Set $($p.DisplayName) -> $maxVal (highest offered)"
            } catch {
                Write-Host "Could not set $($p.DisplayName): $_" -ForegroundColor Yellow
            }
        } else {
            Write-Host "Could not determine the maximum value for $($p.DisplayName); set it manually to the highest option." -ForegroundColor Yellow
        }
    }

    $p = Get-AdvProp -Adapter $Adapter -Candidates $FlowControlNames
    if ($p) {
        try {
            Set-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $p.DisplayName -DisplayValue "Disabled" -ErrorAction Stop
            Write-Host "Set Flow Control -> Disabled"
        } catch {
            Write-Host "Could not disable Flow Control: $_" -ForegroundColor Yellow
        }
    }

    $p = Get-AdvProp -Adapter $Adapter -Candidates $EeeNames
    if ($p) {
        try {
            Set-NetAdapterAdvancedProperty -Name $Adapter.Name -DisplayName $p.DisplayName -DisplayValue "Disabled" -ErrorAction Stop
            Write-Host "Set $($p.DisplayName) -> Disabled"
        } catch {
            Write-Host "Could not disable $($p.DisplayName): $_" -ForegroundColor Yellow
        }
    }

    Write-Host "Interrupt Moderation left as-is (leave it Enabled)."

    Write-Host "Setting static IP $StaticIp/$StaticPrefix (no gateway), matching the HL2's no-DHCP fallback subnet..."
    $have = Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue
    if ($have | Where-Object { $_.IPAddress -eq $StaticIp -and $_.PrefixOrigin -eq 'Manual' }) {
        Write-Host "IPv4 already $StaticIp/$StaticPrefix"
    } else {
        $have | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
        Set-NetIPInterface -InterfaceIndex $Adapter.ifIndex -Dhcp Disabled -ErrorAction SilentlyContinue
        New-NetIPAddress -InterfaceIndex $Adapter.ifIndex -IPAddress $StaticIp -PrefixLength $StaticPrefix -ErrorAction SilentlyContinue | Out-Null
        if (Get-NetIPAddress -InterfaceIndex $Adapter.ifIndex -IPAddress $StaticIp -ErrorAction SilentlyContinue) {
            Write-Host "IPv4 set to $StaticIp/$StaticPrefix"
        } else {
            Write-Host "Could not set IPv4 $StaticIp/$StaticPrefix" -ForegroundColor Yellow
        }
    }

    Write-Host "`nAlso do by hand (not scripted here):" -ForegroundColor Cyan
    Write-Host "  - Windows power plan: High performance"
    Write-Host "  - Allow rawcap.exe through Windows Firewall when prompted (or add a rule)"
    Write-Host "`nDone. Re-run with -Restore to put everything back." -ForegroundColor Green
}

function Show-Counters {
    param($Adapter)
    Write-Host "==== NetAdapterStatistics: $($Adapter.Name) ====" -ForegroundColor Cyan
    Get-NetAdapterStatistics -Name $Adapter.Name | Format-List *
    Write-Host "==== netstat -s -p udp ====" -ForegroundColor Cyan
    netstat -s -p udp
}

# ---- main ----
$adapter = Get-Adapter -Name $AdapterName

if ($Counters) {
    Show-Counters -Adapter $adapter
    exit 0
}

if ($Restore) {
    Restore-Settings -Adapter $adapter -Path $RestoreFile
    Show-Current -Adapter $adapter
    exit 0
}

Show-Current -Adapter $adapter

if ($Apply) {
    Apply-Settings -Adapter $adapter
    Write-Host "`n---- after ----"
    Show-Current -Adapter $adapter
} else {
    Write-Host "`n(dry run -- pass -Apply, from an elevated PowerShell, to actually change these)" -ForegroundColor Yellow
    Write-Host "Would set: Jumbo Frame=$JumboSize, Receive Buffers=<max>, Flow Control=Disabled, EEE=Disabled, IPv4=$StaticIp/$StaticPrefix"
}
