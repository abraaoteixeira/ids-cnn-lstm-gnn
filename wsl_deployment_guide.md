# SPECTRE_GRID: Guia de Implantação e Validação (WSL2)

Este documento registra a jornada de implantação local do motor de inteligência artificial SPECTRE_GRID (ids-cnn-lstm-gnn) em um ambiente Microsoft Windows 11 com WSL2 e GPU NVIDIA RTX 3050.

## 1. Requisitos de Infraestrutura

Antes de iniciar qualquer implantação local com suporte a aceleração por hardware (CUDA), o *host* deve validar três pontos fundamentais:

- **Virtualização**: Tem de estar ativa na Firmware/BIOS (verificar usando `systeminfo` no PowerShell).
- **GPU Driver**: O host Windows tem de ter os controladores NVIDIA oficiais atualizados que expõem os hooks de computação para o WSL (verificar executando `nvidia-smi` no PowerShell do Windows).
- **Armazenamento Seguro (CRÍTICO)**: O ecossistema PyTorch com CUDA consome cerca de **5 GB a 7 GB** de armazenamento temporário durante a descompactação. O disco principal (`C:`) DEVE ter **no mínimo 15 GB livres** para acomodar o crescimento dinâmico do disco virtual (`ext4.vhdx`) do WSL.

> [!CAUTION]
> Durante a nossa implantação inicial, a falta de espaço no disco do Windows (`3.34 GB livres`) causou o colapso estrutural do disco virtual do WSL. O Kernel do Linux atirou o erro letal `[Errno 5] Input/output error` porque o arquivo `.vhdx` não conseguiu alocar mais blocos físicos no disco rígido do Windows, obrigando-nos a usar `wsl --shutdown` e limpar a Lixeira / Pastas Temp para recuperar estabilidade.

## 2. Preparação do Ambiente Nativo (Linux)

Uma das maiores lições na integração do WSL é a **velocidade de I/O (Input/Output)**. Nunca devemos instalar ambientes de machine learning Python atravessando a montagem `/mnt/c/`. A lentidão da ponte de rede (Protocolo 9P) fará a instalação de bibliotecas demorar horas.

**Passos corretos:**

1. **Migração para Raiz Nativa**: Copiamos o projeto da diretoria do Windows para a diretoria principal do próprio Linux (`~` ou `/home/usuario/`):
   ```bash
   mkdir -p ~/ids-cnn-lstm-gnn
   rsync -av --exclude='.venv' --exclude='__pycache__' /mnt/c/Users/abraa/Documents/ids-cnn-lstm-gnn/ ~/ids-cnn-lstm-gnn/
   ```

2. **Criação do Ambiente Virtual Seguro**:
   ```bash
   cd ~/ids-cnn-lstm-gnn
   python3 -m venv .venv_fast
   source .venv_fast/bin/activate
   ```

## 3. Instalação das Dependências (PyTorch + CUDA)

Com o disco virtual saudável e dentro do ambiente Linux de alta performance, instalamos as bibliotecas centrais da engine. Usamos a flag de repositório indexado para focar exclusivamente nos binários com aceleração CUDA 12.4.

```bash
# 1. Atualizar o PIP (crítico para pacotes grandes)
pip install --upgrade pip

# 2. Instalar a Stack base do PyTorch (Compute & Vision)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

# 3. Instalar extensões de Grafo (GNN) e bibliotecas de manipulação de dados
pip install torch_geometric pandas numpy
```

## 4. Validação e Dry-Run

O último passo na arquitetura de Python é acionar o script de inferência. O script `inference.py` carrega o arquivo de modelo treinado e atira tensores "falsos" preenchidos de ruído para testar a ponte entre o processador e a placa gráfica.

**Comando de Execução**:
```bash
python3 inference.py --model ./trained_super_ids_model.pt
```

**Resultado de Sucesso**:
Se o ambiente estiver perfeitamente calibrado, o log reportará que o arquivo foi detectado como `state_dict`, recriará a estrutura da Rede Neural Híbrida em tempo de execução, e listará as percentagens de "Probabilidade de Intrusão" a 0.00% nos logs de fluxo.
