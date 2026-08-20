# Prompt profiles

Choose a profile without editing code.

```powershell
# Live single-frame analysis
$env:COSMOS_LIVE_PROMPT_PROFILE = "comprehensive"

# Playback/chunk analysis
$env:COSMOS_CHUNK_PROMPT_PROFILE = "comprehensive"
```

Available values: `comprehensive`, `security`, `safety`, `crowd_operations`, `traffic`, `admissions`.

`COSMOS_LIVE_PROMPT_PROFILE=admissions` remains the default to preserve the existing admissions-camera behaviour. For a general-purpose camera, use `comprehensive`. Prompt profiles are evidence-based: they improve what the model checks, but do not make an invisible event detectable.
