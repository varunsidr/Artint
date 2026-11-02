<#
.SYNOPSIS
Starts a native Windows Ollama server on loopback with an NVIDIA CUDA profile.
.DESCRIPTION
Uses the only NVIDIA GPU, or an explicit UUID on a multi-GPU machine. Does not
stop existing servers, download models or change persistent environment settings.
Actual model residency still depends on available VRAM; inspect ollama ps.
The default f16 cache preserves precision. q8_0 is an opt-in experiment with
lower cache memory use and a model/task-dependent precision tradeoff.
#>
[CmdletBinding()]
param(
    [string]$GpuUuid,
    [ValidateSet('f16', 'q8_0')]
    [string]$KvCacheType = 'f16'
)

$ErrorActionPreference = 'Stop'
$gpuTool = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $gpuTool) { throw 'nvidia-smi is unavailable. Install/check the NVIDIA driver first.' }
$gpuIds = @(& $gpuTool.Source --query-gpu=uuid --format=csv,noheader)
if ($LASTEXITCODE -ne 0) { throw 'NVIDIA GPU discovery failed.' }
$gpuIds = @($gpuIds | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^GPU-[a-fA-F0-9-]+$' })
if (-not $GpuUuid) {
    if ($gpuIds.Count -ne 1) {
        throw 'Specify -GpuUuid from nvidia-smi --query-gpu=name,uuid --format=csv on a multi-GPU machine.'
    }
    $GpuUuid = $gpuIds[0]
}
if ($GpuUuid -notin $gpuIds) { throw 'The requested NVIDIA GPU UUID was not detected.' }

$gpuOllama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $gpuOllama) { throw 'Ollama is unavailable on PATH. Install Ollama and reopen PowerShell.' }
$gpuListener = Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue
if ($gpuListener) {
    throw 'Port 11434 is already in use. Quit the existing Ollama tray app/server before using this launcher. No process was stopped.'
}

$gpuRoot = Split-Path $PSScriptRoot -Parent
$gpuLogDirectory = Join-Path $gpuRoot ('output/ollama-gpu/' + [Guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $gpuLogDirectory
$gpuEnvironment = @{
    OLLAMA_HOST = '127.0.0.1:11434'
    CUDA_VISIBLE_DEVICES = $GpuUuid
    OLLAMA_VULKAN = '0'
    OLLAMA_FLASH_ATTENTION = '1'
    OLLAMA_KV_CACHE_TYPE = $KvCacheType
    OLLAMA_NUM_PARALLEL = '1'
}
$gpuPrevious = @{}
try {
    foreach ($gpuName in $gpuEnvironment.Keys) {
        $gpuPrevious[$gpuName] = [Environment]::GetEnvironmentVariable($gpuName, 'Process')
        [Environment]::SetEnvironmentVariable($gpuName, $gpuEnvironment[$gpuName], 'Process')
    }
    $gpuProcess = Start-Process -FilePath $gpuOllama.Source -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $gpuLogDirectory 'stdout.log') `
        -RedirectStandardError (Join-Path $gpuLogDirectory 'stderr.log')
} finally {
    foreach ($gpuName in $gpuPrevious.Keys) {
        [Environment]::SetEnvironmentVariable($gpuName, $gpuPrevious[$gpuName], 'Process')
    }
}
$gpuProcess.Id | Set-Content -LiteralPath (Join-Path $gpuLogDirectory 'server.pid')
$gpuProfile = [ordered]@{
    schema_version = 1
    started_at = [DateTime]::UtcNow.ToString('o')
    server_pid = $gpuProcess.Id
    endpoint = 'http://127.0.0.1:11434'
    gpu_uuid = $GpuUuid
    requested_kv_cache_type = $KvCacheType
    flash_attention = $true
    num_parallel = 1
    note = 'Requested server settings; verify actual model cache type and offload in stderr.log.'
}
[System.IO.File]::WriteAllText((Join-Path $gpuLogDirectory 'profile.json'),
    ($gpuProfile | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
$gpuDeadline = [DateTime]::UtcNow.AddSeconds(45)
$gpuReady = $false
while ([DateTime]::UtcNow -lt $gpuDeadline) {
    $gpuProcess.Refresh()
    if ($gpuProcess.HasExited) { throw "Ollama exited. Inspect logs in $gpuLogDirectory" }
    try {
        $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 2
        $gpuReady = $true
        break
    } catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $gpuReady) {
    throw "Ollama did not become ready within 45 seconds; PID $($gpuProcess.Id) may still be starting. Inspect $gpuLogDirectory"
}
Write-Output "Ollama ready on 127.0.0.1:11434; PID $($gpuProcess.Id); CUDA GPU $GpuUuid."
Write-Output "Flash Attention enabled; requested KV cache: $KvCacheType. Use ollama ps during research to inspect GPU/CPU residency."
if ($KvCacheType -eq 'q8_0') {
    Write-Output 'q8_0 is experimental: lower cache memory use with a model/task-dependent precision tradeoff.'
}
Write-Output "Logs and server PID: $gpuLogDirectory"
