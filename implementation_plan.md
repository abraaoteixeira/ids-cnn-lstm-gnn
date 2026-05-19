# Plano de Implementação SPECTRE_GRID v1.1

## Objetivo
Estabilizar o código raiz do projeto, alinhar o nome do modelo ao codinome oficial `SPECTRE_GRID`, e fornecer artefatos de validação e documentação para o motor nativo.

## O que foi feito
1. Renomeado o modelo Python em `model.py` para `SPECTRE_GRID`.
2. Mantido `Super_IDS_Net` como alias de compatibilidade legada.
3. Atualizado `train.py` para importar e instanciar `SPECTRE_GRID` corretamente.
4. Adicionado `README.md` com instruções de uso, treino e build C++.
5. Criado `validate_parity.py` para comparar a saída Python com o modelo TorchScript.
6. Enriquecido `project_state.md` com o codinome oficial e regras operacionais.

## Componentes disponíveis
- `model.py`: implementação principal do modelo.
- `train.py`: procedimento de treino com `BCEWithLogitsLoss`.
- `inference.py`: inferência de demonstração em Python.
- `main.cpp`: wrapper nativo que carrega um modelo TorchScript.
- `CMakeLists.txt`: build do binário nativo.
- `cross_validation_report.md`: relatório de paridade.
- `validate_parity.py`: script de validação de saída.

## Próximos passos sugeridos
- Executar `python validate_parity.py --script-path spectre_model_scripted.pt`.
- Rodar `cmake` e `cmake --build` no diretório `build` para validar o wrapper C++.
- Verificar o modelo finalizado na pasta `SPECTRE_GRID_v1.1_Final` como referência de release.
