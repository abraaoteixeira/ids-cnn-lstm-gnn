"""
tests/test_metrics_consistency.py

Testes automatizados de conciliação métrica e rastreabilidade documental do SPECTRE-GRID.
Garante que todas as métricas da cauda benigna, multi-seed, avaliação externa e manuscrito IEEE
sejam derivadas diretamente de arquivos JSON auditáveis.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.verify_metrics_consistency as vmc


def test_benign_tail_fpr_and_confusion_matrix_all_variants():
    """Valida 15.900 nós, 667 snapshots, FP, TN e FPR das 6 variantes na cauda benigna."""
    vmc.audit_benign_tail()


def test_multiseed_validation_statistics_and_conventions_all_variants():
    """Valida médias e desvios padrão (ddof=1 e ddof=0) para as 6 arquiteturas (seeds 42, 123, 1337)."""
    vmc.audit_multiseed_validation()


def test_external_evaluation_slice_and_concept_drift_metrics_all_variants():
    """Valida o recorte 400.000..600.000, 32.550 ataques e métricas das 6 variantes em UNSW-NB15_2."""
    vmc.audit_external_eval()


def test_chronology_attack_distribution_in_unsw_nb15():
    """Valida 22.215 ataques reais entre as linhas 13 e 186.807 e zero ataques na cauda."""
    vmc.audit_chronology()


def test_paper_central_tables_correspondence_with_json_reports():
    """Valida a correspondência entre os dados brutos JSON e as Tabelas II, III e Seção V-C de main.tex."""
    vmc.audit_paper_central_tables()


def test_documentation_tables_traceability_matrix_and_evidence_existence():
    """Valida os quadros em METHODOLOGY e TIMELINE e a tipificação ontológica na matriz de rastreabilidade."""
    vmc.audit_documentation_tables_and_traceability()
