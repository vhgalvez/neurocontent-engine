<#
.SYNOPSIS
    Script para obtener un resumen detallado del hardware y guardarlo en un .txt
#>

$ArchivoSalida = "Informe_Hardware.txt"
$ReporteTexto = New-Object System.Collections.Generic.List[string]

# Función para imprimir en pantalla y guardar en variable para el TXT
function Out-Both {
    param([string]$Texto, [string]$Color = "White")
    Write-Host $Texto -ForegroundColor $Color
    $ReporteTexto.Add($Texto)
}

Clear-Host
$Separador = "==========================================================="
Out-Both $Separador "Cyan"
Out-Both "      INFORME DE HARDWARE: $env:COMPUTERNAME" "Cyan"
Out-Both $Separador "Cyan"

# 1. Información del Sistema y Placa Base
$system = Get-CimInstance -ClassName Win32_ComputerSystem
$baseboard = Get-CimInstance -ClassName Win32_BaseBoard
Out-Both "`n[+] PLACA BASE Y SISTEMA" "Yellow"
$sysInfo = [PSCustomObject]@{
    Fabricante = $system.Manufacturer
    Modelo     = $system.Model
    SKU        = $baseboard.Product
    RAM_Total  = "$([Math]::Round($system.TotalPhysicalMemory / 1GB, 2)) GB"
} 
$sysInfo | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# 2. Procesador (CPU)
$cpu = Get-CimInstance -ClassName Win32_Processor
Out-Both "[+] PROCESADOR" "Yellow"
$cpu | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# 3. Memoria RAM
Out-Both "[+] MODULOS DE MEMORIA RAM" "Yellow"
Get-CimInstance -ClassName Win32_PhysicalMemory | Select-Object BankLabel, 
    @{Name="Capacidad(GB)"; Expression={$_.Capacity / 1GB}}, 
    Speed, PartNumber | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# 4. Tarjeta Grafica (GPU)
Out-Both "[+] TARJETA GRAFICA" "Yellow"
Get-CimInstance -ClassName Win32_VideoController | Select-Object Name, 
    @{Name="Version_Driver"; Expression={$_.DriverVersion}}, 
    VideoProcessor | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# 5. Almacenamiento (Discos)
Out-Both "[+] UNIDADES DE DISCO" "Yellow"
Get-CimInstance -ClassName Win32_DiskDrive | Select-Object Model, 
    @{Name="Tamano(GB)"; Expression={[Math]::Round($_.Size / 1GB, 2)}}, 
    MediaType, InterfaceType | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

# 6. Red
Out-Both "[+] INTERFACES DE RED ACTIVAS" "Yellow"
Get-NetAdapter | Where-Object Status -eq "Up" | Select-Object Name, InterfaceDescription, LinkSpeed | Format-Table -AutoSize | Out-String | ForEach-Object { Out-Both $_.TrimEnd() }

Out-Both $Separador "Cyan"
Out-Both "      FIN DEL INFORME - Archivo guardado como $ArchivoSalida" "Cyan"
Out-Both $Separador "Cyan"

# Guardar todo el contenido acumulado en el archivo TXT
$ReporteTexto | Out-File -FilePath $ArchivoSalida -Encoding utf8