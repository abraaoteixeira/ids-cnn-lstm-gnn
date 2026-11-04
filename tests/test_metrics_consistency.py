"""
tests/test_metrics_consistency.py

Testes automatizados de conciliação métrica e rastreabilidade documental do SPECTRE-GRID.
Garante que todas as métricas da cauda benigna, multi-seed e avaliação externa citadas na documentação
sejam derivadas diretamente de arquivos JSON auditáveis.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import tools.verify_metrics_consistency as vmc


def test_benign_tail_fpr_and_confusion_matrix():
    """Valida 15.900 nós, 667 snapshots, FP=91, TN=15809 e FPR=0,5723% na cauda benigna."""
    vmc.audit_benign_tail()


def test_multiseed_validation_statistics_and_conventions():
    """Valida médias e desvios padrão (ddof=1 e ddof=0) para as 3 seeds do Dell G15."""
    vmc.audit_multiseed_validation()


def test_external_evaluation_slice_and_concept_drift_metrics():
    """Valida o recorte 400.000..600.000, 32.550 ataques e 226 snapshots em UNSW-NB15_2."""
    vmc.audit_external_eval()


def test_chronology_attack_distribution_in_unsw_nb15():
    """Valida 22.215 ataques reais entre as linhas 13 e 186.807 e zero ataques na cauda."""
    vmc.audit_chronology()


def test_timeline_document_traceability_matrix_and_evidence_existence():
    """Valida a existência dos arquivos citados na matriz de rastreabilidade da timeline."""
    vmc.audit_timeline_document()
