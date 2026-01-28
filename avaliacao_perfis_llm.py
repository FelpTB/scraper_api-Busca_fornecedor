#!/usr/bin/env python3
"""
Avaliação de performance das execuções LLM - análise do CSV de 100 execuções.
Avalia completude vs schema profile.py, estatísticas e comportamentos repetitivos.
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

# Campos do schema CompanyProfile (app/schemas/profile.py) para completude
CAMPOS_IDENTIDADE = ["nome_empresa", "cnpj", "descricao", "ano_fundacao", "faixa_funcionarios"]
CAMPOS_CLASSIFICACAO = ["industria", "modelo_negocio", "publico_alvo", "cobertura_geografica"]
CAMPOS_OFERTAS_PRODUTOS = ["categoria", "produtos"]  # por CategoriaProduto
CAMPOS_OFERTAS_SERVICOS = ["nome", "descricao"]  # por Servico
CAMPOS_REPUTACAO = ["certificacoes", "premios", "parcerias", "lista_clientes", "estudos_caso"]
CAMPOS_CONTATO = ["emails", "telefones", "url_linkedin", "url_site", "endereco_matriz", "localizacoes"]
SECOES = ["identidade", "classificacao", "ofertas", "reputacao", "contato", "fontes"]


def extrair_json_assistant(output_messages_str: str) -> dict | None:
    """Extrai o JSON do content do role assistant em output_messages."""
    if not output_messages_str or output_messages_str.strip() == "":
        return None
    try:
        # Formato: "[{'role': 'assistant', 'content': '{...}'}]"
        # Usar ast.literal_eval para a lista, depois pegar content
        import ast
        msg_list = ast.literal_eval(output_messages_str)
        if not msg_list:
            return None
        for m in msg_list:
            if m.get("role") == "assistant" and "content" in m:
                raw = m["content"].strip()
                # Remover markdown se houver
                if raw.startswith("```"):
                    raw = re.sub(r"^```\w*\n?", "", raw)
                    raw = re.sub(r"\n?```\s*$", "", raw)
                return json.loads(raw)
        return None
    except (json.JSONDecodeError, SyntaxError, ValueError) as e:
        return {"_parse_error": str(e)}


def contar_campo_preenchido(val) -> bool:
    """Retorna True se o campo tem valor considerado preenchido."""
    if val is None:
        return False
    if isinstance(val, (list, dict)):
        return len(val) > 0
    if isinstance(val, str):
        return val.strip() != ""
    return True


def avaliar_completude(perfil: dict) -> dict:
    """Conta campos preenchidos por seção conforme schema profile.py."""
    out = {
        "identidade": 0,
        "classificacao": 0,
        "ofertas": 0,
        "reputacao": 0,
        "contato": 0,
        "fontes": 0,
        "total_campos": 0,
        "secoes_preenchidas": 0,
    }
    total_possivel = 0

    # Identidade
    ident = perfil.get("identidade") or {}
    for c in CAMPOS_IDENTIDADE:
        total_possivel += 1
        if contar_campo_preenchido(ident.get(c)):
            out["identidade"] += 1
            out["total_campos"] += 1
    if out["identidade"] > 0:
        out["secoes_preenchidas"] += 1

    # Classificação
    clas = perfil.get("classificacao") or {}
    for c in CAMPOS_CLASSIFICACAO:
        total_possivel += 1
        if contar_campo_preenchido(clas.get(c)):
            out["classificacao"] += 1
            out["total_campos"] += 1
    if out["classificacao"] > 0:
        out["secoes_preenchidas"] += 1

    # Ofertas (produtos + serviços)
    ofertas = perfil.get("ofertas") or {}
    cats = ofertas.get("produtos") or []
    for cat in cats:
        if isinstance(cat, dict):
            if contar_campo_preenchido(cat.get("categoria")):
                out["ofertas"] += 1
                out["total_campos"] += 1
            prods = cat.get("produtos") or []
            if isinstance(prods, list):
                out["total_campos"] += min(len(prods), 1)  # conta como 1 se tem lista
                if prods:
                    out["ofertas"] += 1
    servicos = ofertas.get("servicos") or []
    for s in servicos:
        if isinstance(s, dict) and (contar_campo_preenchido(s.get("nome")) or contar_campo_preenchido(s.get("descricao"))):
            out["ofertas"] += 1
            out["total_campos"] += 1
    if out["ofertas"] > 0:
        out["secoes_preenchidas"] += 1

    # Reputação
    rep = perfil.get("reputacao") or {}
    for c in CAMPOS_REPUTACAO:
        total_possivel += 1
        if contar_campo_preenchido(rep.get(c)):
            out["reputacao"] += 1
            out["total_campos"] += 1
    if out["reputacao"] > 0:
        out["secoes_preenchidas"] += 1

    # Contato
    cont = perfil.get("contato") or {}
    for c in CAMPOS_CONTATO:
        total_possivel += 1
        if contar_campo_preenchido(cont.get(c)):
            out["contato"] += 1
            out["total_campos"] += 1
    if contar_campo_preenchido(perfil.get("fontes")):
        out["fontes"] = 1
        out["total_campos"] += 1
    if out["contato"] > 0 or out["fontes"] > 0:
        out["secoes_preenchidas"] += 1

    out["total_possivel_aproximado"] = total_possivel
    return out


def normalizar_item(s: str) -> str:
    """Normaliza string para comparação (lower, strip, colapsa espaços)."""
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def avaliar_repeticao_itens_perfil(perfil: dict) -> dict:
    """
    Analisa repetição de produtos e serviços dentro de um único perfil.
    Retorna totais, únicos (após normalização), repetidos e exemplos.
    """
    out = {
        "total_produtos": 0,
        "unicos_produtos": 0,
        "repetidos_produtos": 0,
        "taxa_repeticao_produtos": 0.0,
        "exemplos_duplicatas_produtos": [],  # [(item_norm, count), ...]
        "total_servicos": 0,
        "unicos_servicos": 0,
        "repetidos_servicos": 0,
        "taxa_repeticao_servicos": 0.0,
        "exemplos_duplicatas_servicos": [],
    }
    ofertas = perfil.get("ofertas") or {}

    # Produtos: juntar todos de todas as categorias
    lista_produtos = []
    for cat in ofertas.get("produtos") or []:
        if isinstance(cat, dict):
            prods = cat.get("produtos") or []
            for p in prods:
                if isinstance(p, str) and p.strip():
                    lista_produtos.append(p.strip())
    out["total_produtos"] = len(lista_produtos)
    if lista_produtos:
        contagem = Counter(normalizar_item(p) for p in lista_produtos)
        out["unicos_produtos"] = len(contagem)
        out["repetidos_produtos"] = out["total_produtos"] - out["unicos_produtos"]
        if out["total_produtos"] > 0:
            out["taxa_repeticao_produtos"] = round(out["repetidos_produtos"] / out["total_produtos"] * 100, 1)
        # Exemplos: itens que aparecem mais de uma vez (duplicatas)
        out["exemplos_duplicatas_produtos"] = [
            (norm, cnt) for norm, cnt in contagem.most_common(15) if cnt > 1 and norm
        ]

    # Serviços: duplicatas por nome do serviço
    lista_servicos_nome = []
    for s in ofertas.get("servicos") or []:
        if isinstance(s, dict):
            nome = s.get("nome") if isinstance(s.get("nome"), str) else None
            if nome and nome.strip():
                lista_servicos_nome.append(nome.strip())
    out["total_servicos"] = len(lista_servicos_nome)
    if lista_servicos_nome:
        contagem_s = Counter(normalizar_item(x) for x in lista_servicos_nome)
        out["unicos_servicos"] = len(contagem_s)
        out["repetidos_servicos"] = out["total_servicos"] - out["unicos_servicos"]
        if out["total_servicos"] > 0:
            out["taxa_repeticao_servicos"] = round(out["repetidos_servicos"] / out["total_servicos"] * 100, 1)
        out["exemplos_duplicatas_servicos"] = [
            (norm, cnt) for norm, cnt in contagem_s.most_common(15) if cnt > 1 and norm
        ]

    return out


def agregar_repeticao_itens(perfis: list[dict]) -> dict:
    """Agrega estatísticas de repetição de itens em todos os perfis válidos."""
    perfis_validos = [p for p in perfis if "_parse_error" not in p]
    resultados = [avaliar_repeticao_itens_perfil(p) for p in perfis_validos]

    perfis_com_produtos = [r for r in resultados if r["total_produtos"] > 0]
    perfis_com_servicos = [r for r in resultados if r["total_servicos"] > 0]

    perfis_com_repeticao_produto = [r for r in perfis_com_produtos if r["repetidos_produtos"] > 0]
    perfis_com_repeticao_servico = [r for r in perfis_com_servicos if r["repetidos_servicos"] > 0]

    taxas_prod = [r["taxa_repeticao_produtos"] for r in perfis_com_produtos]
    taxas_serv = [r["taxa_repeticao_servicos"] for r in perfis_com_servicos]

    # Exemplos globais: perfis com maior taxa de repetição
    exemplos_piores_produtos = sorted(
        [r for r in perfis_com_produtos if r["repetidos_produtos"] > 0],
        key=lambda x: -x["taxa_repeticao_produtos"],
    )[:5]
    exemplos_piores_servicos = sorted(
        [r for r in perfis_com_servicos if r["repetidos_servicos"] > 0],
        key=lambda x: -x["taxa_repeticao_servicos"],
    )[:5]

    return {
        "n_perfis_validos": len(perfis_validos),
        "n_perfis_com_produtos": len(perfis_com_produtos),
        "n_perfis_com_servicos": len(perfis_com_servicos),
        "n_perfis_com_repeticao_produto": len(perfis_com_repeticao_produto),
        "n_perfis_com_repeticao_servico": len(perfis_com_repeticao_servico),
        "taxa_repeticao_produtos_media": round(sum(taxas_prod) / len(taxas_prod), 1) if taxas_prod else 0,
        "taxa_repeticao_servicos_media": round(sum(taxas_serv) / len(taxas_serv), 1) if taxas_serv else 0,
        "taxa_repeticao_produtos_max": max(taxas_prod) if taxas_prod else 0,
        "taxa_repeticao_servicos_max": max(taxas_serv) if taxas_serv else 0,
        "total_itens_repetidos_produtos": sum(r["repetidos_produtos"] for r in resultados),
        "total_itens_repetidos_servicos": sum(r["repetidos_servicos"] for r in resultados),
        "exemplos_piores_produtos": exemplos_piores_produtos,
        "exemplos_piores_servicos": exemplos_piores_servicos,
        "resultados": resultados,
    }


def detectar_estrutura_repetida(perfis: list[dict]) -> dict:
    """Detecta estruturas idênticas ou muito parecidas (só ofertas+contato+fontes)."""
    estruturas = []
    apenas_ofertas_contato_fontes = 0
    vazios_ou_minimos = 0
    for p in perfis:
        if "_parse_error" in p:
            continue
        keys = set(p.keys()) - {"_parse_error"}
        estruturas.append(tuple(sorted(keys)))
        c = avaliar_completude(p)
        if c["identidade"] == 0 and c["classificacao"] == 0 and c["reputacao"] == 0 and (c["ofertas"] > 0 or c["contato"] > 0 or c["fontes"] > 0):
            apenas_ofertas_contato_fontes += 1
        if c["total_campos"] <= 2:
            vazios_ou_minimos += 1
    contagem_estrutura = Counter(estruturas)
    return {
        "estruturas_mais_comuns": contagem_estrutura.most_common(10),
        "apenas_ofertas_contato_fontes_sem_identidade_classificacao_reputacao": apenas_ofertas_contato_fontes,
        "perfis_vazios_ou_minimos_ate_2_campos": vazios_ou_minimos,
    }


def main():
    csv_path = Path(__file__).parent / "teste_100_results-1355.csv"
    if not csv_path.exists():
        print(f"Arquivo não encontrado: {csv_path}")
        return

    perfis = []
    erros_parse = 0
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            out_msg = row.get("output_messages", "")
            p = extrair_json_assistant(out_msg)
            if p is None:
                erros_parse += 1
                continue
            if "_parse_error" in p:
                erros_parse += 1
            perfis.append(p)

    n = len(perfis)
    n_validos = len([p for p in perfis if "_parse_error" not in p])
    print("=" * 60)
    print("AVALIAÇÃO DE PERFORMANCE - 100 EXECUÇÕES LLM (API)")
    print("=" * 60)
    print(f"\nTotal de linhas de dados no CSV: {n}")
    print(f"Perfis extraídos (lista): {n}")
    print(f"Perfis válidos (JSON ok): {n_validos}")
    print(f"Erros de parse (JSON/extração): {erros_parse}")

    # Estatísticas de completude
    completudes = [avaliar_completude(p) for p in perfis if "_parse_error" not in p]
    if not completudes:
        print("\nNenhum perfil válido para análise de completude.")
        return

    secao_preenchida_count = defaultdict(int)
    for c in completudes:
        for sec in SECOES:
            if c.get(sec, 0) > 0:
                secao_preenchida_count[sec] += 1

    print("\n--- COMPLETUDE (baseado em app/schemas/profile.py) ---")
    print("\nSeções do schema e quantas execuções preencheram ao menos um campo:")
    for sec in SECOES:
        print(f"  {sec}: {secao_preenchida_count[sec]}/{n} ({100*secao_preenchida_count[sec]/n:.1f}%)")

    campos_por_exec = [c["total_campos"] for c in completudes]
    print(f"\nCampos preenchidos por execução:")
    print(f"  Mínimo: {min(campos_por_exec)}")
    print(f"  Máximo: {max(campos_por_exec)}")
    print(f"  Média:  {sum(campos_por_exec)/len(campos_por_exec):.1f}")

    secoes_por_exec = [c["secoes_preenchidas"] for c in completudes]
    print(f"\nSeções distintas preenchidas por execução (máx 6):")
    print(f"  Média: {sum(secoes_por_exec)/len(secoes_por_exec):.1f}")

    # Comportamentos repetitivos
    rep = detectar_estrutura_repetida(perfis)
    print("\n--- COMPORTAMENTOS REPETITIVOS ---")
    print(f"  Perfis com apenas ofertas/contato/fontes (sem identidade, classificação, reputação): {rep['apenas_ofertas_contato_fontes_sem_identidade_classificacao_reputacao']}/{n}")
    print(f"  Perfis vazios ou mínimos (≤2 campos): {rep['perfis_vazios_ou_minimos_ate_2_campos']}/{n}")
    print("  Estruturas de chaves mais comuns (top 5):")
    for est, cnt in rep["estruturas_mais_comuns"][:5]:
        print(f"    {est}: {cnt} vezes")

    # Repetição de itens dentro do perfil (produtos e serviços duplicados)
    rep_itens = agregar_repeticao_itens(perfis)
    print("\n--- REPETIÇÃO DE ITENS DENTRO DO PERFIL ---")
    print("  (itens idênticos ou normalizados iguais no mesmo perfil)")
    print(f"  Perfis com produtos: {rep_itens['n_perfis_com_produtos']}/{rep_itens['n_perfis_validos']}")
    print(f"  Perfis com ao menos 1 produto repetido: {rep_itens['n_perfis_com_repeticao_produto']}/{rep_itens['n_perfis_com_produtos'] or 1}")
    print(f"  Taxa média de repetição (produtos): {rep_itens['taxa_repeticao_produtos_media']}%")
    print(f"  Taxa máxima de repetição (produtos): {rep_itens['taxa_repeticao_produtos_max']}%")
    print(f"  Total de itens repetidos (produtos, soma em todos os perfis): {rep_itens['total_itens_repetidos_produtos']}")
    print(f"  Perfis com serviços: {rep_itens['n_perfis_com_servicos']}/{rep_itens['n_perfis_validos']}")
    print(f"  Perfis com ao menos 1 serviço repetido: {rep_itens['n_perfis_com_repeticao_servico']}/{rep_itens['n_perfis_com_servicos'] or 1}")
    print(f"  Taxa média de repetição (serviços): {rep_itens['taxa_repeticao_servicos_media']}%")
    print(f"  Taxa máxima de repetição (serviços): {rep_itens['taxa_repeticao_servicos_max']}%")
    print(f"  Total de itens repetidos (serviços): {rep_itens['total_itens_repetidos_servicos']}")
    if rep_itens["exemplos_piores_produtos"]:
        print("  Exemplos de perfis com maior taxa de repetição em produtos:")
        for i, r in enumerate(rep_itens["exemplos_piores_produtos"], 1):
            ex = r["exemplos_duplicatas_produtos"][:3]
            ex_str = ", ".join(f'"{n[:40]}..." ({c}x)' if len(n) > 40 else f'"{n}" ({c}x)' for n, c in ex)
            print(f"    {i}. Taxa {r['taxa_repeticao_produtos']}% (total {r['total_produtos']}, únicos {r['unicos_produtos']}) — ex: {ex_str}")
    if rep_itens["exemplos_piores_servicos"]:
        print("  Exemplos de perfis com maior taxa de repetição em serviços:")
        for i, r in enumerate(rep_itens["exemplos_piores_servicos"], 1):
            ex = r["exemplos_duplicatas_servicos"][:3]
            ex_str = ", ".join(f'"{n[:40]}..." ({c}x)' if len(n) > 40 else f'"{n}" ({c}x)' for n, c in ex)
            print(f"    {i}. Taxa {r['taxa_repeticao_servicos']}% (total {r['total_servicos']}, únicos {r['unicos_servicos']}) — ex: {ex_str}")

    # Qualidade: descrições idênticas ou muito curtas
    descricoes = []
    for p in perfis:
        if "_parse_error" in p:
            continue
        ident = p.get("identidade") or {}
        d = ident.get("descricao")
        if d and isinstance(d, str):
            descricoes.append(d.strip())
    if descricoes:
        desc_counter = Counter(descricoes)
        repetidas = [(t, c) for t, c in desc_counter.items() if c > 1]
        print("\n--- QUALIDADE ---")
        print(f"  Execuções com descrição (identidade) preenchida: {len(descricoes)}/{n}")
        if repetidas:
            print(f"  Descrições idênticas repetidas: {len(repetidas)} textos repetidos")
            for t, c in sorted(repetidas, key=lambda x: -x[1])[:5]:
                print(f"    ({c}x) \"{t[:60]}...\"" if len(t) > 60 else f"    ({c}x) \"{t}\"")

    # Conformidade com schema: quais chaves raiz o LLM retorna
    chaves_raiz = defaultdict(int)
    for p in perfis:
        if "_parse_error" in p:
            continue
        for k in p.keys():
            chaves_raiz[k] += 1
    print("\n--- CONFORMIDADE COM SCHEMA (chaves raiz retornadas) ---")
    schema_esperado = {"identidade", "classificacao", "ofertas", "reputacao", "contato", "fontes"}
    for k in sorted(chaves_raiz.keys()):
        status = " (esperado)" if k in schema_esperado else " (fora do schema)"
        print(f"  {k}: {chaves_raiz[k]}/{n_validos}{status}")

    # Totais de produtos e serviços
    total_produtos = 0
    total_categorias = 0
    total_servicos = 0
    for p in perfis:
        if "_parse_error" in p:
            continue
        ofertas = p.get("ofertas") or {}
        for cat in ofertas.get("produtos") or []:
            if isinstance(cat, dict):
                total_categorias += 1
                total_produtos += len(cat.get("produtos") or [])
        total_servicos += len(ofertas.get("servicos") or [])
    print("\n--- VOLUME EXTRAÍDO ---")
    print(f"  Total categorias de produtos: {total_categorias}")
    print(f"  Total itens de produtos: {total_produtos}")
    print(f"  Total serviços: {total_servicos}")

    # Amostra de erros de parse
    if erros_parse > 0:
        amostra_erros = [p.get("_parse_error", "?") for p in perfis if "_parse_error" in p][:5]
        print("\n--- AMOSTRA DE ERROS DE PARSE ---")
        for i, e in enumerate(amostra_erros, 1):
            print(f"  {i}. {e[:120]}...")

    # Resumo qualitativo
    print("\n--- RESUMO QUALITATIVO ---")
    identidade_ok = secao_preenchida_count["identidade"]
    classificacao_ok = secao_preenchida_count["classificacao"]
    ofertas_ok = secao_preenchida_count["ofertas"]
    contato_ok = secao_preenchida_count["contato"]
    if identidade_ok < n * 0.5:
        print("- Identidade está subpreenchida: menos da metade das execuções preenchem nome/descrição/CNPJ.")
    if classificacao_ok < n * 0.5:
        print("- Classificação (indústria, modelo, público, cobertura) está subpreenchida.")
    if ofertas_ok > n * 0.7 and identidade_ok < n * 0.5:
        print("- Padrão repetitivo: muitas execuções retornam apenas ofertas/contato/fontes, sem identidade ou classificação.")
    if rep["perfis_vazios_ou_minimos_ate_2_campos"] > n * 0.2:
        print("- Grande proporção de perfis vazios ou mínimos; pode indicar páginas sem conteúdo ou falha na extração.")
    if rep_itens["total_itens_repetidos_produtos"] > 0 or rep_itens["total_itens_repetidos_servicos"] > 0:
        print("- Repetição de itens: muitos perfis contêm produtos ou serviços duplicados (mesmo item várias vezes); reforçar regra de deduplicação no prompt.")
    print("\nFim da avaliação.")


if __name__ == "__main__":
    main()
