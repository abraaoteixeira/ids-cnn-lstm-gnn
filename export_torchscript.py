import argparse
from pathlib import Path

import torch
from model import SPECTRE_GRID


def parse_args():
    parser = argparse.ArgumentParser(description="Exporta o modelo SPECTRE_GRID para TorchScript")
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Caminho para os pesos do modelo (.pth)"
    )
    parser.add_argument(
        "--output",
        default="spectre_model_scripted.pt",
        help="Caminho de saída para o modelo TorchScript"
    )
    parser.add_argument(
        "--num-features",
        type=int,
        default=20,
        help="Número de features por timestep (default: 20)"
    )
    parser.add_argument(
        "--seq-len",
        type=int,
        default=10,
        help="Comprimento da sequência temporal (default: 10)"
    )
    return parser.parse_args()


def load_model_weights(model: SPECTRE_GRID, checkpoint_path: Path) -> SPECTRE_GRID:
    state = torch.load(str(checkpoint_path), map_location="cpu")
    if isinstance(state, dict):
        model.load_state_dict(state)
    else:
        try:
            model.load_state_dict(state.state_dict())
        except Exception as exc:
            raise RuntimeError("Checkpoint inválido: não foi possível carregar os pesos do modelo") from exc
    return model


def main():
    args = parse_args()

    checkpoint_path = Path(args.checkpoint)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint não encontrado: {checkpoint_path}")

    model = SPECTRE_GRID(num_features=args.num_features, seq_len=args.seq_len)
    model = load_model_weights(model, checkpoint_path)
    model.eval()

    # Exemplo de entrada para exportação TorchScript
    example_x = torch.randn(1, args.seq_len, args.num_features)
    example_edge_index = torch.tensor([[0], [0]], dtype=torch.long)

    # Forçar o uso de JIT Trace, pois GATConv tem incompatibilidades de tipos estáticos no JIT Script
    # (Union[Tensor, SparseTensor]) que falham no compilador JIT do LibTorch C++ nativo.
    print("[INFO] Usando torch.jit.trace para exportar o modelo de forma estatica...")
    scripted_model = torch.jit.trace(model, (example_x, example_edge_index))

    scripted_model.save(args.output)
    print(f"Modelo TorchScript (Traced) salvo em: {args.output}")


if __name__ == "__main__":
    main()
