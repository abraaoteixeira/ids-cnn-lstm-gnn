import argparse
import torch
import torch.nn as nn
from model import SPECTRE_GRID


def parse_args():
    parser = argparse.ArgumentParser(description="Validar paridade entre modelo Python e TorchScript")
    parser.add_argument("--script-path", default="spectre_model_scripted.pt", help="Caminho para o modelo TorchScript")
    parser.add_argument("--checkpoint", default="trained_super_ids_model.pt", help="Caminho para o checkpoint de pesos (.pt)")
    parser.add_argument("--seed", type=int, default=42, help="Semente determinística")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size para teste")
    parser.add_argument("--seq-len", type=int, default=10, help="Comprimento da sequência")
    parser.add_argument("--num-features", type=int, default=20, help="Número de features de entrada")
    return parser.parse_args()


def main():
    args = parse_args()

    torch.manual_seed(args.seed)
    torch.use_deterministic_algorithms(True)

    try:
        scripted = torch.jit.load(args.script_path)
    except Exception as e:
        raise SystemExit(f"Erro ao carregar modelo TorchScript '{args.script_path}': {e}")

    model = SPECTRE_GRID(num_features=args.num_features, seq_len=args.seq_len)
    
    if args.checkpoint:
        import os
        if os.path.exists(args.checkpoint):
            print(f"[INFO] Carregando pesos do checkpoint para o modelo Python: {args.checkpoint}")
            state = torch.load(args.checkpoint, map_location="cpu")
            if isinstance(state, dict):
                model.load_state_dict(state)
            else:
                model.load_state_dict(state.state_dict())
        else:
            print(f"[AVISO] Checkpoint '{args.checkpoint}' não encontrado. Usando pesos aleatórios.")
            
    model.eval()

    x = torch.randn(args.batch_size, args.seq_len, args.num_features)
    edge_index = torch.tensor([[i for i in range(args.batch_size - 1)], [i + 1 for i in range(args.batch_size - 1)]], dtype=torch.long)

    with torch.no_grad():
        py_out = model(x, edge_index)
        script_out = scripted(x, edge_index)

    if not isinstance(script_out, torch.Tensor):
        raise SystemExit("O modelo TorchScript não retornou um tensor.")

    diff = (py_out - script_out).abs()
    max_diff = diff.max().item()
    mean_diff = diff.mean().item()
    all_close = torch.allclose(py_out, script_out, atol=1e-6, rtol=1e-5)

    print("=== Validação de Paridade ===")
    print(f"Batch size: {args.batch_size}")
    print(f"Shape: {py_out.shape}")
    print(f"Max abs diff: {max_diff:.6e}")
    print(f"Mean abs diff: {mean_diff:.6e}")
    print(f"Passou: {'SIM' if all_close else 'NÃO'}")

    if not all_close:
        print("Diferenças acima do limite aceitável. Verifique a exportação do TorchScript e a compatibilidade de parâmetros.")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
