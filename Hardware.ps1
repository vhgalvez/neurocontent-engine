<#
.SYNOPSIS
    Script para obtener un resumen detallado del hardware del sistema.
#>

Clear-Host
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "      INFORME DE HARDWARE: $env:COMPUTERNAME" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan

# 1. Información del Sistema y Placa Base
$system = Get-CimInstance -ClassName Win32_ComputerSystem
$baseboard = Get-CimInstance -ClassName Win32_BaseBoard
Write-Host "`n[+] PLACA BASE Y SISTEMA" -ForegroundColor Yellow
[PSCustomObject]@{
    Fabricante = $system.Manufacturer
    Modelo     = $system.Model
    SKU        = $baseboard.Product
    RAM_Total  = "$([Math]::Round($system.TotalPhysicalMemory / 1GB, 2)) GB"
} | Format-Table -AutoSize

# 2. Procesador (CPU)
$cpu = Get-CimInstance -ClassName Win32_Processor
Write-Host "[+] PROCESADOR" -ForegroundColor Yellow
$cpu | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-Table -AutoSize

# 3. Memoria RAM (Detalle de módulos)
Write-Host "[+] MÓDULOS DE MEMORIA RAM" -ForegroundColor Yellow
Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object BankLabel, 
    @{Name="Capacidad(GB)"; Expression={$_.Capacity / 1GB}}, 
    Speed, PartNumber | Format-Table -AutoSize

# 4. Tarjeta Gráfica (GPU)
Write-Host "[+] TARJETA GRÁFICA" -ForegroundColor Yellow
Get-CimInstance -ClassName Win32_VideoController | Select-Object Name, 
    @{Name="Versión_Driver"; Expression={$_.DriverVersion}}, 
    VideoProcessor | Format-Table -AutoSize

# 5. Almacenamiento (Discos Físicos)
Write-Host "[+] UNIDADES DE DISCO" -ForegroundColor Yellow
Get-CimInstance -ClassName Win32_DiskDrive | Select-Object Model, 
    @{Name="Tamaño(GB)"; Expression={[Math]::Round($_.Size / 1GB, 2)}}, 
    MediaType, InterfaceType | Format-Table -AutoSize

# 6. Red (Interfaces Activas)
Write-Host "[+] INTERFACES DE RED ACTIVAS" -ForegroundColor Yellow
Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object Name, InterfaceDescription, LinkSpeed | Format-Table -AutoSize

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host "      FIN DEL INFORME" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan