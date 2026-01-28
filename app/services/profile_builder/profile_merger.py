"""
Consolidação de múltiplos perfis parciais em um perfil completo.
Usa campos em português: identidade, classificacao, contato, ofertas, reputacao, fontes.
"""

import logging
from typing import List, Optional
from app.schemas.profile import CompanyProfile
from .constants import llm_config

logger = logging.getLogger(__name__)

SECOES_SIMPLES = ["identidade", "classificacao", "contato"]
CAMPOS_CONCATENAVEIS = ["descricao"]


def merge_profiles(profiles: List[CompanyProfile]) -> CompanyProfile:
    """
    Consolida múltiplos perfis parciais em um único perfil completo.
    Prioriza informações mais completas e remove duplicatas.
    """
    logger.debug(f"🔄 Merge de {len(profiles)} perfis")

    valid_profiles = [p for p in profiles if p is not None and isinstance(p, CompanyProfile)]
    invalid_count = len(profiles) - len(valid_profiles)

    if invalid_count > 0:
        logger.warning(f"⚠️ {invalid_count} perfis inválidos/None foram filtrados")

    if not valid_profiles:
        logger.warning("❌ Nenhum profile válido para mergear")
        return CompanyProfile()

    if len(valid_profiles) == 1:
        return valid_profiles[0]

    profiles_dicts = [p.model_dump() for p in valid_profiles]
    base_idx = max(range(len(profiles_dicts)), key=lambda i: _score_completeness(profiles_dicts[i]))
    merged = profiles_dicts[base_idx].copy()
    base_score = _score_completeness(merged)
    logger.info(f"📌 Usando perfil {base_idx+1} como base (score: {base_score})")

    for i, profile in enumerate(valid_profiles):
        if i == base_idx:
            continue
        p_dict = profile.model_dump()
        _merge_simple_sections(merged, p_dict)
        _merge_ofertas(merged, p_dict)
        _merge_reputacao(merged, p_dict)
        _merge_fontes(merged, p_dict)

    _clean_merged_profile(merged)

    filled = sum(
        1
        for k, v in merged.items()
        if v and (isinstance(v, dict) and any(v.values()) or isinstance(v, list) and len(v) > 0)
    )
    logger.info(f"✅ Merge concluído: {filled} campos preenchidos")

    try:
        return CompanyProfile(**merged)
    except Exception as e:
        logger.error(f"❌ Erro ao criar CompanyProfile após merge: {e}")
        raise


def _score_completeness(profile_dict: dict) -> int:
    """Calcula score de completude do perfil."""
    score = 0
    for key, value in profile_dict.items():
        if isinstance(value, dict):
            for sub_value in value.values():
                if sub_value:
                    if isinstance(sub_value, list):
                        score += len(sub_value)
                    elif isinstance(sub_value, str):
                        score += len(sub_value) // llm_config.text_score_divisor
                    else:
                        score += 1
        elif isinstance(value, list) and len(value) > 0:
            score += len(value)
        elif value:
            score += 1
    return score


def _are_texts_complementary(text1: str, text2: str) -> bool:
    """Detecta se dois textos são complementares (não duplicados)."""
    if not text1 or not text2:
        return False
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    if t1 in t2 or t2 in t1:
        return False
    w1 = set(t1.split())
    w2 = set(t2.split())
    if not w1 or not w2:
        return False
    sim = len(w1 & w2) / max(len(w1), len(w2))
    return sim < llm_config.similarity_threshold


def _merge_text_fields(current: Optional[str], new: Optional[str], field_name: str) -> str:
    """Merge inteligente de campos de texto."""
    if not new:
        return current or ""
    if not current:
        return new
    if field_name in CAMPOS_CONCATENAVEIS and _are_texts_complementary(current, new):
        return f"{current.strip()}. {new.strip()}"
    return new if len(new) > len(current) else current


def _merge_simple_sections(merged: dict, p_dict: dict) -> None:
    """Mergeia identidade, classificacao, contato."""
    for section in SECOES_SIMPLES:
        if section not in merged or section not in p_dict:
            continue
        for key, value in p_dict[section].items():
            if not value:
                continue
            cur = merged[section].get(key)
            if isinstance(value, str) and isinstance(cur, str):
                merged[section][key] = _merge_text_fields(cur, value, key)
            elif value and not cur:
                merged[section][key] = value
            elif isinstance(value, str) and len(value) > len(str(cur or "")):
                merged[section][key] = value


def _merge_ofertas(merged: dict, p_dict: dict) -> None:
    """Mergeia ofertas (produtos, servicos)."""
    if "ofertas" not in merged or "ofertas" not in p_dict:
        return
    _merge_servicos(merged, p_dict)
    _merge_produtos(merged, p_dict)


def _merge_servicos(merged: dict, p_dict: dict) -> None:
    """Mergeia ofertas.servicos (nome, descricao)."""
    of = merged.get("ofertas") or {}
    po = p_dict.get("ofertas") or {}
    svc_list = of.get("servicos") or []
    new_list = po.get("servicos") or []
    svc_dict = {}
    for s in svc_list:
        if isinstance(s, dict) and s.get("nome"):
            svc_dict[s["nome"]] = s.copy()
        elif hasattr(s, "nome") and s.nome:
            svc_dict[s.nome] = s.model_dump() if hasattr(s, "model_dump") else {"nome": s.nome, "descricao": getattr(s, "descricao", None)}
    for s in new_list:
        nome = s.get("nome") if isinstance(s, dict) else (getattr(s, "nome", None) if s else None)
        if not nome or not isinstance(nome, str):
            continue
        if nome in svc_dict:
            ex = svc_dict[nome]
            for f in ["descricao"]:
                cur = ex.get(f)
                nv = s.get(f) if isinstance(s, dict) else getattr(s, f, None)
                if nv:
                    ex[f] = _merge_text_fields(cur, nv, f)
        else:
            svc_dict[nome] = s.copy() if isinstance(s, dict) else (s.model_dump() if hasattr(s, "model_dump") else {"nome": nome, "descricao": getattr(s, "descricao", None)})
    merged.setdefault("ofertas", {})["servicos"] = list(svc_dict.values())


def _merge_produtos(merged: dict, p_dict: dict) -> None:
    """Mergeia ofertas.produtos (categoria, produtos)."""
    of = merged.get("ofertas") or {}
    po = p_dict.get("ofertas") or {}
    cat_list = of.get("produtos") or []
    new_list = po.get("produtos") or []
    cat_dict = {}
    for c in cat_list:
        if isinstance(c, dict) and c.get("categoria"):
            cat_dict[c["categoria"]] = c.copy()
        elif hasattr(c, "categoria") and c.categoria:
            cat_dict[c.categoria] = c.model_dump() if hasattr(c, "model_dump") else {"categoria": c.categoria, "produtos": getattr(c, "produtos", [])}
    for c in new_list:
        cat = c.get("categoria") if isinstance(c, dict) else (getattr(c, "categoria", None) if c else None)
        if not cat or not isinstance(cat, str):
            continue
        prods = c.get("produtos") if isinstance(c, dict) else (getattr(c, "produtos", []) if c else [])
        prods = [x for x in (prods or []) if isinstance(x, str) and x.strip()]
        if cat in cat_dict:
            ex_prods = set(cat_dict[cat].get("produtos") or [])
            ex_prods |= set(prods)
            cat_dict[cat]["produtos"] = list(ex_prods)
        else:
            cat_dict[cat] = {"categoria": cat, "produtos": prods} if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else {"categoria": cat, "produtos": prods})
    merged.setdefault("ofertas", {})["produtos"] = list(cat_dict.values())


def _merge_reputacao(merged: dict, p_dict: dict) -> None:
    """Mergeia reputacao (certificacoes, premios, parcerias, lista_clientes, estudos_caso)."""
    if "reputacao" not in merged or "reputacao" not in p_dict:
        return
    rep = merged["reputacao"]
    pre = p_dict["reputacao"]
    for field in ["certificacoes", "premios", "parcerias", "lista_clientes"]:
        rep[field] = list(set((rep.get(field) or []) + (pre.get(field) or [])))
    _merge_estudos_caso(merged, p_dict)


def _merge_estudos_caso(merged: dict, p_dict: dict) -> None:
    """Mergeia reputacao.estudos_caso (titulo, nome_cliente, etc.)."""
    rep = merged.get("reputacao") or {}
    pre = p_dict.get("reputacao") or {}
    cases = rep.get("estudos_caso") or []
    new_cases = pre.get("estudos_caso") or []
    case_dict = {}
    for cs in cases:
        t = cs.get("titulo") if isinstance(cs, dict) else (getattr(cs, "titulo", None) if cs else None)
        if t and isinstance(t, str):
            case_dict[t] = cs.copy() if isinstance(cs, dict) else (cs.model_dump() if hasattr(cs, "model_dump") else {})
    for cs in new_cases:
        t = cs.get("titulo") if isinstance(cs, dict) else (getattr(cs, "titulo", None) if cs else None)
        if not t or not isinstance(t, str):
            continue
        if t in case_dict:
            ex = case_dict[t]
            for f in ["desafio", "solucao", "resultado"]:
                nv = cs.get(f) if isinstance(cs, dict) else getattr(cs, f, None)
                if nv:
                    ex[f] = _merge_text_fields(ex.get(f), nv, f)
            for f in ["nome_cliente", "industria"]:
                nv = cs.get(f) if isinstance(cs, dict) else getattr(cs, f, None)
                if nv and (not ex.get(f) or len(str(nv)) > len(str(ex.get(f, "")))):
                    ex[f] = nv
        else:
            case_dict[t] = cs.copy() if isinstance(cs, dict) else (cs.model_dump() if hasattr(cs, "model_dump") else {})
    rep["estudos_caso"] = list(case_dict.values())


def _merge_fontes(merged: dict, p_dict: dict) -> None:
    """Mergeia fontes."""
    existing = set(merged.get("fontes") or [])
    merged["fontes"] = list(merged.get("fontes") or []) + [
        s for s in (p_dict.get("fontes") or []) if s not in existing and isinstance(s, str) and s.strip()
    ]


def _clean_merged_profile(merged: dict) -> None:
    """Limpa e valida o perfil mergeado."""
    of = merged.get("ofertas")
    if isinstance(of, dict):
        invalid = {"outras categorias", "outras", "marcas", "marca", "geral", "diversos", "outros", "categorias", "categoria", "produtos", "produto"}
        if isinstance(of.get("produtos"), list):
            valid = []
            for cat in of["produtos"]:
                if not isinstance(cat, dict) or not cat.get("categoria"):
                    continue
                if (cat.get("categoria") or "").strip().lower() in invalid:
                    continue
                if not isinstance(cat.get("produtos"), list):
                    cat["produtos"] = []
                else:
                    cat["produtos"] = [x for x in cat["produtos"] if isinstance(x, str) and x.strip()]
                valid.append(cat)
            of["produtos"] = valid
        if isinstance(of.get("servicos"), list):
            of["servicos"] = [s for s in of["servicos"] if isinstance(s, dict) and s.get("nome")]

    rep = merged.get("reputacao")
    if isinstance(rep, dict):
        for f in ["certificacoes", "premios", "parcerias", "lista_clientes"]:
            if isinstance(rep.get(f), list):
                rep[f] = [x for x in rep[f] if isinstance(x, str) and x.strip()]
        if isinstance(rep.get("estudos_caso"), list):
            rep["estudos_caso"] = [c for c in rep["estudos_caso"] if isinstance(c, dict) and c.get("titulo")]

    cont = merged.get("contato")
    if isinstance(cont, dict):
        for f in ["emails", "telefones", "localizacoes"]:
            if isinstance(cont.get(f), list):
                cont[f] = [x for x in cont[f] if isinstance(x, str) and x.strip()]

    if isinstance(merged.get("fontes"), list):
        merged["fontes"] = [s for s in merged["fontes"] if isinstance(s, str) and s.strip()]
