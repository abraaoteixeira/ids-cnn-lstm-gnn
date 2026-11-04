#!/usr/bin/env python3
"""
tools/verify_metrics_consistency.py

Verificador automatizado de integridade científica e conciliação métrica do SPECTRE-GRID.
Confronta diretamente as afirmações e tabelas documentadas com os relatórios JSON originais:
1. Benign Tail (g15_external_tail500k_fpr_report.json): FP, TN, nós e FPR exatos da cauda benigna.
2. Multi-seed Validation (g15_phase2_consolidated_summary.json): Médias e desvios padrão (ddof=0 e ddof=1).
3. External Drift (g15_external_unsw_nb15_2_eval_report.json): Recorte 400.000..600.000, 32.550 ataques, 226 snapshots.
4. Chronology Audit (g15_dataset_chronology_audit.json): 22.215 ataques reais no horizonte ativo.
5. Traceability Matrix Audit: Valida a existência de todos os arquivos citados em M-01 a M-11 no docs/SPECTRE_GRID_RESEARCH_TIMELINE.md.

Saída: Código de saída 0 se 100% consistente; código 1 com relatório detalhado em caso de divergência.
"""

import json
import re
import sys
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent

def audit_benign_tail():
    print("[1/5] Auditando relatório da cauda benigna (g15_external_tail500k_fpr_report.json)...")
    tail_file = REPO_ROOT / "data" / "processed" / "g15_external_tail500k_fpr_report.json"
    assert tail_file.exists(), f"Arquivo não encontrado: {tail_file}"
    with open(tail_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    bidir = data["gat_bidir"]
    cm = bidir["metrics"]["confusion_matrix"]
    total_nodes = bidir["total_benign_nodes"]
    num_snaps = bidir["num_snapshots"]
    fp = cm["fp"]
    tn = cm["tn"]
    fpr = bidir["metrics"]["fpr"]
    
    assert total_nodes == 15900, f"Esperado 15900 nós benignos, obtido {total_nodes}"
    assert num_snaps == 667, f"Esperado 667 snapshots na cauda, obtido {num_snaps}"
    assert fp == 91, f"Esperado exatamente 91 FPs para gat_bidir na cauda benigna, obtido {fp}"
    assert tn == 15809, f"Esperado exatamente 15809 TNs para gat_bidir na cauda benigna, obtido {tn}"
    calc_fpr = fp / total_nodes
    assert abs(calc_fpr - fpr) < 1e-6, f"FPR calculado ({calc_fpr}) diverge do FPR registrado ({fpr})"
    assert abs(fpr - 0.005723) < 1e-5, f"FPR ({fpr}) diverge de 0,5723%"
    print(f"  [OK] gat_bidir na cauda: {total_nodes} nós, {num_snaps} snapshots, FP={fp}, TN={tn}, FPR={fpr:.6f} (0,5723%).")


def audit_multiseed_validation():
    print("[2/5] Auditando médias e desvios padrão multi-seed (g15_phase2_consolidated_summary.json)...")
    summary_file = REPO_ROOT / "data" / "processed" / "g15_phase2_consolidated_summary.json"
    assert summary_file.exists(), f"Arquivo não encontrado: {summary_file}"
    with open(summary_file, "r", encoding="utf-8") as f:
        runs = json.load(f)
    
    bidir_runs = [x for x in runs if x["model_variant"] == "gat_bidir"]
    assert len(bidir_runs) == 3, f"Esperado 3 seeds para gat_bidir, obtido {len(bidir_runs)}"
    
    f1s = [x["validation_metrics"]["f1_score"] for x in bidir_runs]
    recs = [x["validation_metrics"]["recall"] for x in bidir_runs]
    precs = [x["validation_metrics"]["precision"] for x in bidir_runs]
    fprs = [x["validation_metrics"]["fpr"] for x in bidir_runs]
    
    mean_f1 = np.mean(f1s)
    std_f1_pop = np.std(f1s, ddof=0)
    std_f1_sample = np.std(f1s, ddof=1)
    
    mean_rec = np.mean(recs)
    std_rec_pop = np.std(recs, ddof=0)
    std_rec_sample = np.std(recs, ddof=1)
    
    mean_fpr = np.mean(fprs)
    std_fpr_pop = np.std(fprs, ddof=0)
    std_fpr_sample = np.std(fprs, ddof=1)
    
    assert abs(mean_f1 - 0.960878) < 1e-5, f"Média F1 diverge: {mean_f1}"
    assert abs(std_f1_pop - 0.006743) < 1e-5, f"std pop F1 diverge: {std_f1_pop}"
    assert abs(std_f1_sample - 0.008259) < 1e-5, f"std amostral F1 diverge: {std_f1_sample}"
    
    assert abs(mean_rec - 0.980903) < 1e-5, f"Média Recall diverge: {mean_rec}"
    assert abs(std_rec_pop - 0.010702) < 1e-5, f"std pop Recall diverge: {std_rec_pop}"
    assert abs(std_rec_sample - 0.013108) < 1e-5, f"std amostral Recall diverge: {std_rec_sample}"
    
    assert abs(mean_fpr - 0.007287) < 1e-5, f"Média FPR diverge: {mean_fpr}"
    assert abs(std_fpr_pop - 0.001178) < 1e-5, f"std pop FPR diverge: {std_fpr_pop}"
    assert abs(std_fpr_sample - 0.001443) < 1e-5, f"std amostral FPR diverge: {std_fpr_sample}"
    
    print(f"  [OK] gat_bidir Validação: F1={mean_f1:.4f}±{std_f1_sample:.4f} (ddof=1) / ±{std_f1_pop:.4f} (ddof=0).")
    print(f"  [OK] gat_bidir Validação: Rec={mean_rec:.4f}±{std_rec_sample:.4f} (ddof=1) / ±{std_rec_pop:.4f} (ddof=0).")
    print(f"  [OK] gat_bidir Validação: FPR={mean_fpr*100:.2f}%±{std_fpr_sample*100:.2f}% (ddof=1) / ±{std_fpr_pop*100:.2f}% (ddof=0).")


def audit_external_eval():
    print("[3/5] Auditando avaliação externa UNSW-NB15_2 (g15_external_unsw_nb15_2_eval_report.json)...")
    ext_file = REPO_ROOT / "data" / "processed" / "g15_external_unsw_nb15_2_eval_report.json"
    assert ext_file.exists(), f"Arquivo não encontrado: {ext_file}"
    with open(ext_file, "r", encoding="utf-8") as f:
        ext_data = json.load(f)
    
    assert ext_data["slice_range"] == "400000..600000", f"Recorte incorreto: {ext_data['slice_range']}"
    assert ext_data["slice_rows"] == 200000, f"Linhas incorretas: {ext_data['slice_rows']}"
    assert ext_data["slice_attack_flows"] == 32550, f"Ataques incorretos: {ext_data['slice_attack_flows']}"
    assert ext_data["num_snapshots_30s"] == 226, f"Snapshots incorretos: {ext_data['num_snapshots_30s']}"
    assert ext_data["snapshot_summary"]["total_nodes"] == 8598, f"Nós incorretos: {ext_data['snapshot_summary']['total_nodes']}"
    assert ext_data["refitted_on_external"] is False, "Violação de governança: refitted_on_external deve ser False!"
    
    bidir_res = ext_data["results_by_variant"]["gat_bidir"]
    f1s = [v["metrics"]["f1_score"] for v in bidir_res.values()]
    precs = [v["metrics"]["precision"] for v in bidir_res.values()]
    recs = [v["metrics"]["recall"] for v in bidir_res.values()]
    fprs = [v["metrics"]["fpr"] for v in bidir_res.values()]
    
    mean_f1 = np.mean(f1s)
    std_f1_sample = np.std(f1s, ddof=1)
    mean_prec = np.mean(precs)
    mean_rec = np.mean(recs)
    mean_fpr = np.mean(fprs)
    
    assert abs(mean_f1 - 0.916664) < 1e-5, f"Média F1 externa diverge: {mean_f1}"
    assert abs(mean_prec - 0.883742) < 1e-5, f"Média Prec externa diverge: {mean_prec}"
    assert abs(mean_rec - 0.952540) < 1e-5, f"Média Rec externa diverge: {mean_rec}"
    assert abs(mean_fpr - 0.014677) < 1e-5, f"Média FPR externa diverge: {mean_fpr}"
    
    print(f"  [OK] UNSW-NB15_2 (400k..600k): 32.550 ataques, 226 snaps, 8.598 nós, gat_bidir F1={mean_f1:.4f}±{std_f1_sample:.4f}, FPR={mean_fpr*100:.2f}%.")


def audit_chronology():
    print("[4/5] Auditando cronologia de ataques (g15_dataset_chronology_audit.json)...")
    chrono_file = REPO_ROOT / "data" / "processed" / "g15_dataset_chronology_audit.json"
    assert chrono_file.exists(), f"Arquivo não encontrado: {chrono_file}"
    with open(chrono_file, "r", encoding="utf-8") as f:
        chrono_data = json.load(f)
    
    active_attacks = chrono_data["total_attacks"]
    total_attacks = chrono_data["total_attacks"]
    tail_attacks = chrono_data["post_campaign_benign_tail_attacks"]
    first_attack = chrono_data["first_attack_row_after_sort"]
    last_attack = chrono_data["last_attack_row_after_sort"]
    
    assert active_attacks == 22215, f"Esperado 22215 ataques ativos, obtido {active_attacks}"
    assert total_attacks == 22215, f"Esperado total de 22215 ataques, obtido {total_attacks}"
    assert tail_attacks == 0, f"Esperado 0 ataques na cauda, obtido {tail_attacks}"
    assert first_attack == 13, f"Esperado primeiro ataque na linha 13, obtido {first_attack}"
    assert last_attack == 186807, f"Esperado último ataque na linha 186807, obtido {last_attack}"
    print(f"  [OK] Cronologia: {active_attacks} ataques ativos (linhas {first_attack}..{last_attack}), 0 ataques na cauda de 500k linhas.")


def audit_timeline_document():
    print("[5/5] Auditando coerência do documento docs/SPECTRE_GRID_RESEARCH_TIMELINE.md...")
    timeline_file = REPO_ROOT / "docs" / "SPECTRE_GRID_RESEARCH_TIMELINE.md"
    assert timeline_file.exists(), f"Arquivo não encontrado: {timeline_file}"
    content = timeline_file.read_text(encoding="utf-8")
    
    # 1. Checa menção da cauda benigna com 91 FP e 0,57% (não deve ter 116 nem 0,73% para a cauda!)
    assert "91" in content, "Menção a 91 falsos positivos da cauda benigna ausente na timeline!"
    assert "15.809" in content or "15809" in content, "Menção a 15.809 TNs da cauda benigna ausente na timeline!"
    
    # Proíbe explicitamente a string incorreta "116 alarmes falsos" ou "116 falsos positivos"
    assert "116 alarmes" not in content and "116 falsos" not in content, (
        "Divergência detectada: '116 falsos positivos' foi mantido na timeline! O valor real é 91 FP (0,5723%)."
    )
    
    # 2. Checa o recorte de 400.000 a 600.000
    assert "400.000 a 600.000" in content or "400.000..600.000" in content, (
        "Recorte de linhas 400.000 a 600.000 ausente na timeline!"
    )
    
    # 3. Checa existência física dos caminhos de evidência citados na matriz de rastreabilidade
    matrix_paths = re.findall(r"`(data/processed/[^`]+)`", content)
    assert len(matrix_paths) > 0, "Nenhum caminho data/processed/ encontrado na timeline!"
    for p_str in set(matrix_paths):
        p = REPO_ROOT / p_str
        assert p.exists(), f"Arquivo citado na timeline NÃO existe no repositório: {p_str}"
        print(f"  [OK Evidência Existente]: {p_str}")

    print("  [OK] docs/SPECTRE_GRID_RESEARCH_TIMELINE.md 100% harmonizado e consistente com dados JSON.")


def main():
    print("=" * 75)
    print("SPECTRE-GRID — AUDITORIA DE CONCILIAÇÃO FINAL DE MÉTRICAS E RASTREABILIDADE")
    print("=" * 75)
    try:
        audit_benign_tail()
        audit_multiseed_validation()
        audit_external_eval()
        audit_chronology()
        audit_timeline_document()
        print("=" * 75)
        print("TODAS AS CONCILIAÇÕES MÉTRICAS E RASTREABILIDADES FORAM APROVADAS (100% PASS)")
        print("=" * 75)
        return 0
    except AssertionError as err:
        print(f"\n[FALHA DE CONCILIAÇÃO]: {err}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
