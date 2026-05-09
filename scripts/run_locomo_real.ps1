param(
    [string]$ApiKey = $env:MEMMARK_API_KEY,
    [string]$Conversation = "0",
    [string]$Model = "qwen/qwen3-14b",
    [string]$Backend = "amem",
    [string]$LocomoPath = "C:\桌面\agent-mem\watermark\locomo\data\locomo10.json",
    [string]$AMemModelName = "C:\桌面\models\all-MiniLM-L6-v2",
    [string]$Output = ".\results\amem\conv0_real.json",
    [int]$MaxSessions = 5,
    [int]$MaxQa = 50
)

if (-not $ApiKey) {
    throw "Set MEMMARK_API_KEY first or pass -ApiKey '<your OpenRouter key>'."
}

$env:MEMMARK_API_KEY = $ApiKey
$env:MEMMARK_BASE_URL = "https://openrouter.ai/api/v1"
$env:MEMMARK_MODEL = $Model

$env:OPENAI_API_KEY = $env:MEMMARK_API_KEY
$env:OPENAI_BASE_URL = $env:MEMMARK_BASE_URL
$env:OPENAI_MODEL = $env:MEMMARK_MODEL

$env:TARGET_LLM_BASE = $env:MEMMARK_BASE_URL
$env:TARGET_LLM_MODEL = $env:MEMMARK_MODEL

$env:MEMMARK_LOCOMO_PATH = $LocomoPath

if (-not (Test-Path $env:MEMMARK_LOCOMO_PATH)) {
    throw "LoCoMo file not found: $env:MEMMARK_LOCOMO_PATH"
}

New-Item -ItemType Directory -Force (Split-Path $Output) | Out-Null

python -c "from memmark.llm import OpenAIChatClient; c=OpenAIChatClient(); print(c.model); print(c.complete([{'role':'user','content':'reply only ok'}], temperature=0))"

python -m memmark.examples.run_locomo_full `
    --locomo $env:MEMMARK_LOCOMO_PATH `
    --conversation $Conversation `
    --backend $Backend `
    --amem-model-name $AMemModelName `
    --llm-mode real `
    --progress `
    --baselines watermark no_watermark signed_metadata_only `
    --output $Output
