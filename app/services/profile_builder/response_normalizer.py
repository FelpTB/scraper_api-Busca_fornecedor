"""
Normalização de respostas do LLM.
Garante que as respostas estejam no formato correto para CompanyProfile (campos em português).
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

SECOES = ["identidade", "classificacao", "contato", "ofertas", "reputacao"]


def normalize_llm_response(data: Any) -> dict:
    """
    Normaliza e valida a resposta do LLM para CompanyProfile.
    Usa campos em português: identidade, classificacao, contato, ofertas, reputacao, fontes.
    """
    if isinstance(data, list):
        logger.warning("LLM retornou array ao invés de objeto. Tentando extrair primeiro item...")
        if len(data) > 0 and isinstance(data[0], dict):
            data = data[0]
            logger.info("✅ Array convertido para objeto (primeiro item extraído)")
        else:
            raise ValueError("LLM retornou array vazio ou inválido")

    if not isinstance(data, dict):
        raise ValueError(f"LLM retornou tipo inválido: {type(data)}")

    _normalize_ofertas(data)
    _normalize_reputacao(data)
    _normalize_contato(data)
    _normalize_root_fields(data)

    return data


def _normalize_ofertas(data: dict) -> None:
    """Normaliza ofertas (produtos, servicos)."""
    if "ofertas" not in data:
        return
    if not isinstance(data["ofertas"], dict):
        data["ofertas"] = {}
    of = data["ofertas"]
    _normalize_produtos(of)
    _normalize_servicos(of)


def _normalize_produtos(ofertas: dict) -> None:
    """Normaliza ofertas.produtos (categoria, produtos)."""
    if ofertas.get("produtos") is None:
        ofertas["produtos"] = []
    elif not isinstance(ofertas["produtos"], list):
        ofertas["produtos"] = []
    else:
        valid = []
        for cat in ofertas["produtos"]:
            if not isinstance(cat, dict):
                continue
            cat_name = cat.get("categoria")
            if not cat_name or not isinstance(cat_name, str):
                continue
            if cat.get("produtos") is None:
                cat["produtos"] = []
            elif not isinstance(cat["produtos"], list):
                cat["produtos"] = []
            else:
                cat["produtos"] = [x for x in cat["produtos"] if isinstance(x, str) and x.strip()]
            valid.append(cat)
        ofertas["produtos"] = valid


def _normalize_servicos(ofertas: dict) -> None:
    """Normaliza ofertas.servicos (nome, descricao)."""
    if ofertas.get("servicos") is None:
        ofertas["servicos"] = []
    elif not isinstance(ofertas["servicos"], list):
        ofertas["servicos"] = []
    else:
        valid = []
        for s in ofertas["servicos"]:
            if not isinstance(s, dict):
                continue
            if not s.get("nome") or not isinstance(s.get("nome"), str):
                continue
            valid.append(s)
        ofertas["servicos"] = valid


def _normalize_reputacao(data: dict) -> None:
    """Normaliza reputacao (certificacoes, premios, parcerias, lista_clientes, estudos_caso)."""
    if "reputacao" not in data:
        return
    if not isinstance(data["reputacao"], dict):
        data["reputacao"] = {}
    rep = data["reputacao"]

    for field in ["certificacoes", "premios", "parcerias", "lista_clientes"]:
        if rep.get(field) is None:
            rep[field] = []
        elif not isinstance(rep[field], list):
            if isinstance(rep[field], str) and rep[field].strip():
                rep[field] = [rep[field].strip()]
            else:
                rep[field] = []
        else:
            valid = []
            for item in rep[field]:
                if isinstance(item, str) and item.strip():
                    valid.append(item.strip())
                elif isinstance(item, dict):
                    extracted = (
                        item.get("nome") or item.get("name") or item.get("title")
                        or item.get("partner_name") or item.get("company")
                        or item.get("client_name") or item.get("certification") or item.get("award")
                    )
                    if extracted and isinstance(extracted, str) and extracted.strip():
                        valid.append(extracted.strip())
            rep[field] = valid

    _normalize_estudos_caso(rep)


def _normalize_estudos_caso(reputacao: dict) -> None:
    """Normaliza reputacao.estudos_caso (titulo, nome_cliente, etc.)."""
    if reputacao.get("estudos_caso") is None:
        reputacao["estudos_caso"] = []
    elif not isinstance(reputacao["estudos_caso"], list):
        reputacao["estudos_caso"] = []
    else:
        valid = []
        for case in reputacao["estudos_caso"]:
            if not isinstance(case, dict):
                continue
            if not case.get("titulo"):
                if case.get("desafio"):
                    case["titulo"] = f"Desafio: {str(case['desafio'])[:50]}..."
                elif case.get("solucao"):
                    case["titulo"] = f"Solução: {str(case['solucao'])[:50]}..."
                elif case.get("nome_cliente"):
                    case["titulo"] = f"Caso: {case['nome_cliente']}"
                elif any(v for k, v in case.items() if v):
                    case["titulo"] = "Estudo de Caso (Sem Título)"
                else:
                    continue
            valid.append(case)
        reputacao["estudos_caso"] = valid


def _normalize_contato(data: dict) -> None:
    """Normaliza contato (emails, telefones, url_linkedin, url_site, endereco_matriz, localizacoes)."""
    if "contato" not in data:
        return
    if not isinstance(data["contato"], dict):
        data["contato"] = {}
    cont = data["contato"]

    for field in ["emails", "telefones", "localizacoes"]:
        if cont.get(field) is None:
            cont[field] = []
        elif isinstance(cont[field], list):
            cont[field] = [x for x in cont[field] if isinstance(x, str) and x.strip()]
        elif isinstance(cont[field], str) and cont[field].strip():
            cont[field] = [cont[field].strip()]
        else:
            cont[field] = []

    for url_field, check in [("url_site", lambda u: u.startswith("http")), ("url_linkedin", lambda u: "linkedin" in u.lower())]:
        val = cont.get(url_field)
        if val is None:
            pass
        elif isinstance(val, list):
            found = None
            for u in val:
                if isinstance(u, str) and u.strip() and check(u):
                    found = u.strip()
                    break
            cont[url_field] = found
            if found and len(val) > 1:
                logger.warning(f"{url_field} era lista, extraído: {found[:50]}...")
        elif isinstance(val, str) and val.strip():
            cont[url_field] = val.strip()
        else:
            cont[url_field] = None

    addr = cont.get("endereco_matriz")
    if addr is not None and not isinstance(addr, str):
        if isinstance(addr, list) and addr:
            cont["endereco_matriz"] = str(addr[0]) if addr[0] else None
        else:
            cont["endereco_matriz"] = None


def _normalize_root_fields(data: dict) -> None:
    """Normaliza fontes e garante seções como objetos válidos."""
    if data.get("fontes") is None:
        data["fontes"] = []

    for section in SECOES:
        if data.get(section) is None or not isinstance(data.get(section), dict):
            data[section] = {}
