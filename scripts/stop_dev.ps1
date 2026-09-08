$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$StatePath = Join-Path $ProjectRoot "logs\dev-state.json"

function Stop-ProcessTree {
  param([int]$RootProcessId)

  $allProcesses = Get-CimInstance Win32_Process
  $toStop = New-Object System.Collections.Generic.List[int]
  $queue = New-Object System.Collections.Generic.Queue[int]
  $queue.Enqueue($RootProcessId)

  while ($queue.Count -gt 0) {
    $current = $queue.Dequeue()
    if ($toStop.Contains($current)) {
      continue
    }
    $toStop.Add($current)
    $children = $allProcesses | Where-Object { $_.ParentProcessId -eq $current }
    foreach ($child in $children) {
      $queue.Enqueue([int]$child.ProcessId)
    }
  }

  [array]::Reverse($toStop)
  foreach ($processId in $toStop) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
      Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
      Write-Host "Stopped process $processId"
    }
  }
}

function Stop-ListeningPortOwners {
  param([int[]]$Ports)

  $portPattern = (($Ports | ForEach-Object { [regex]::Escape(":$_") }) -join "|")
  $owners = netstat -ano |
    Select-String "LISTENING" |
    Where-Object { $_.Line -match "($portPattern)\s" } |
    ForEach-Object {
      $columns = $_.Line.Trim() -split "\s+"
      if ($columns.Length -ge 5) {
        [int]$columns[4]
      }
    } |
    Sort-Object -Unique

  foreach ($processId in $owners) {
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) {
      Stop-ProcessTree -RootProcessId $processId
    }
  }
}

if (Test-Path $StatePath) {
  $state = Get-Content -Encoding UTF8 -Path $StatePath | ConvertFrom-Json
  foreach ($processId in @($state.backend_pid, $state.frontend_pid)) {
    if ($processId) {
      Stop-ProcessTree -RootProcessId ([int]$processId)
    }
  }
  Remove-Item -LiteralPath $StatePath -Force
} else {
  Write-Host "No dev state file found."
}

Stop-ListeningPortOwners -Ports @(8001, 5173)
Write-Host "Dev processes stopped."
