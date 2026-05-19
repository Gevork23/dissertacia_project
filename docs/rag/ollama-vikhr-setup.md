# Ollama setup for Vikhr RAG chat

## Windows installation

1. Download Ollama for Windows from `https://ollama.com/download`.
2. Install it with the default options.
3. Start Ollama and verify the local API:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
```

## GGUF model

Recommended source:

- `TheBloke/Vikhr-Nemo-12B-Instruct-GGUF`
- preferred file: `vikhr-nemo-12b-instruct.Q4_K_M.gguf`

If this exact file is unavailable, use another `Q4_K_M` quant of the same model.

## Import into Ollama

1. Download the GGUF file to a local directory, for example:

```text
D:\models\vikhr-nemo-12b-instruct.Q4_K_M.gguf
```

2. Create a Modelfile from [Modelfile.vikhr-nemo](D:\DSTU\dissertacia_project\infra\ollama\Modelfile.vikhr-nemo).
3. Update the `FROM` path inside the file to the actual GGUF location.
4. Import the model:

```powershell
ollama create vikhr-nemo:12b-instruct -f D:\DSTU\dissertacia_project\infra\ollama\Modelfile.vikhr-nemo
```

5. Verify that the model is available:

```powershell
ollama list
```

## Runtime check

Start the Ollama server if it is not already running:

```powershell
ollama serve
```

Then test one generation:

```powershell
ollama run vikhr-nemo:12b-instruct
```

## Performance notes

- `i5-11400` CPU: expect roughly `10-30` seconds for grounded answers, depending on prompt size.
- `RTX 3070`: CUDA should be used automatically by Ollama, and latency should typically drop to `5-10` seconds.
- If CPU generation is too slow, reduce `RAG_MAX_TOKENS` to `256`.
