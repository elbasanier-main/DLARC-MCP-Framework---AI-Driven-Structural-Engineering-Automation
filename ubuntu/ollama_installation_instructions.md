# Ollama Installation and Setup for Ubuntu

## 1. Install Ollama

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

Verify installation:
```bash
ollama --version
```

## 2. Pull Required Models

```bash
# CodeLlama for structural engineering code generation
ollama pull codellama:34b

# Alternative lighter models
ollama pull codellama:13b
ollama pull codellama:7b

# For general conversation
ollama pull llama2:13b
```

## 3. Start Ollama Service

```bash
# Start the Ollama server (runs on port 11434 by default)
ollama serve

# Or run as a background service
systemctl start ollama
```

## 4. Configure SSH to Windows

The Ubuntu clients connect to Windows MCP servers via SSH.

```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519

# Copy key to Windows machine (requires OpenSSH server on Windows)
ssh-copy-id username@WINDOWS_IP

# Test connection
ssh username@WINDOWS_IP "echo Connected"
```

### Enable OpenSSH Server on Windows

1. Settings > Apps > Optional Features > Add a Feature
2. Find "OpenSSH Server" and install
3. Start service: `Start-Service sshd`
4. Set to auto-start: `Set-Service -Name sshd -StartupType Automatic`

## 5. Install Python Dependencies

```bash
pip install -r requirements_ubuntu.txt
```

## 6. Run Clients

```bash
# AutoCAD Ollama client
python autocad_ollama_client.py

# ETABS Ollama client
python etabs_ollama_client.py

# Unified client (both AutoCAD + ETABS)
python unified_ollama_client.py
```

## 7. Troubleshooting

### Ollama not responding
```bash
# Check if service is running
systemctl status ollama

# Check port
curl http://localhost:11434/api/tags
```

### SSH connection issues
```bash
# Test SSH with verbose output
ssh -v username@WINDOWS_IP

# Check Windows firewall allows port 22
```

### Dependency conflicts
```bash
# Run the fix script
python ubuntu_install_fix.py
```

### GPU not detected (for faster inference)
```bash
# Check NVIDIA GPU
nvidia-smi

# Ollama automatically uses GPU if CUDA is available
# For AMD GPUs, ensure ROCm is installed
```
