#!/command/with-contenv bash
# Ollama (CPU) — локальные эмбеддинги bge-m3, 1024 измерения.
# Слушает только loopback: наружу не выставляется.
export OLLAMA_HOST=127.0.0.1:11434
export OLLAMA_MODELS=/opt/ollama/models
export OLLAMA_KEEP_ALIVE=10m
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_NUM_PARALLEL=1
export HOME=/opt/data
exec s6-setuidgid hermes /usr/local/bin/ollama serve