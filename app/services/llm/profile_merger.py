"""
Consolidação de múltiplos perfis parciais em um perfil completo.
"""

import json
import logging
from typing import List, Optional
from app.schemas.profile import CompanyProfile
from .constants import llm_config

logger = logging.getLogger(__name__)


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
    
    # Encontrar perfil mais completo como base
    profiles_dicts = [p.model_dump() for p in valid_profiles]
    base_idx = max(range(len(profiles_dicts)), key=lambda i: _score_completeness(profiles_dicts[i]))
    merged = profiles_dicts[base_idx].copy()
    base_score = _score_completeness(merged)
    logger.info(f"📌 Usando perfil {base_idx+1} como base (score: {base_score})")
    
    # Mergear outros perfis
    for i, profile in enumerate(valid_profiles):
        if i == base_idx:
            continue
        
        p_dict = profile.model_dump()
        _merge_simple_sections(merged, p_dict)
        _merge_offerings(merged, p_dict)
        _merge_reputation(merged, p_dict)
        _merge_sources(merged, p_dict)
    
    # Validação e limpeza final
    _clean_merged_profile(merged)
    
    filled_fields = sum(1 for k, v in merged.items() 
                       if v and (isinstance(v, dict) and any(v.values()) or isinstance(v, list) and len(v) > 0))
    logger.info(f"✅ Merge concluído: {filled_fields} campos preenchidos")
    
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
    
    text1_lower = text1.lower().strip()
    text2_lower = text2.lower().strip()
    
    if text1_lower in text2_lower or text2_lower in text1_lower:
        return False
    
    words1 = set(text1_lower.split())
    words2 = set(text2_lower.split())
    if len(words1) == 0 or len(words2) == 0:
        return False
    
    common_words = words1 & words2
    similarity = len(common_words) / max(len(words1), len(words2))
    
    return similarity < llm_config.similarity_threshold


def _merge_text_fields(current: Optional[str], new: Optional[str], field_name: str) -> str:
    """Merge inteligente de campos de texto."""
    if not new:
        return current or ""
    if not current:
        return new
    
    concatenatable_fields = ["description", "methodology", "tagline"]
    
    if field_name in concatenatable_fields:
        if _are_texts_complementary(current, new):
            return f"{current.strip()}. {new.strip()}"
        else:
            return new if len(new) > len(current) else current
    else:
        return new if len(new) > len(current) else current


def _merge_simple_sections(merged: dict, p_dict: dict) -> None:
    """Mergeia seções simples (identity, classification, team, contact)."""
    for section in ["identity", "classification", "team", "contact"]:
        if section in merged and section in p_dict:
            for key, value in p_dict[section].items():
                if not value:
                    continue
                
                current_value = merged[section].get(key)
                
                if isinstance(value, str) and isinstance(current_value, str):
                    merged[section][key] = _merge_text_fields(current_value, value, key)
                elif value and not current_value:
                    merged[section][key] = value
                elif isinstance(value, str) and len(value) > len(str(current_value or "")):
                    merged[section][key] = value


def _merge_offerings(merged: dict, p_dict: dict) -> None:
    """Mergeia seção offerings."""
    if "offerings" not in merged or "offerings" not in p_dict:
        return
    
    for field in ["products", "services", "engagement_models", "key_differentiators"]:
        merged["offerings"][field] = list(set(
            merged["offerings"].get(field, []) + p_dict["offerings"].get(field, [])
        ))
    
    _merge_service_details(merged, p_dict)
    _merge_product_categories(merged, p_dict)


def _merge_service_details(merged: dict, p_dict: dict) -> None:
    """Mergeia service_details."""
    service_dict = {s["name"]: s for s in merged["offerings"].get("service_details", [])}
    
    for service in p_dict["offerings"].get("service_details", []):
        service_name = service.get("name")
        if not service_name or not isinstance(service_name, str):
            continue
        
        if service_name in service_dict:
            existing = service_dict[service_name]
            for field in ["description", "methodology", "ideal_client_profile"]:
                existing[field] = _merge_text_fields(
                    existing.get(field), service.get(field), field
                )
            existing_deliverables = set(existing.get("deliverables", []))
            new_deliverables = set(service.get("deliverables", []))
            existing["deliverables"] = list(existing_deliverables | new_deliverables)
        else:
            service_dict[service_name] = service.copy()
    
    merged["offerings"]["service_details"] = list(service_dict.values())


def _merge_product_categories(merged: dict, p_dict: dict) -> None:
    """Mergeia product_categories."""
    cat_dict = {c["category_name"]: c for c in merged["offerings"].get("product_categories", [])}
    
    for cat in p_dict["offerings"].get("product_categories", []):
        cat_name = cat.get("category_name")
        if not cat_name or not isinstance(cat_name, str):
            continue
        
        if cat_name in cat_dict:
            existing_items = set(cat_dict[cat_name].get("items", []))
            new_items = set(cat.get("items", []))
            cat_dict[cat_name]["items"] = list(existing_items | new_items)
        else:
            cat_dict[cat_name] = cat.copy()
    
    merged["offerings"]["product_categories"] = list(cat_dict.values())


def _merge_reputation(merged: dict, p_dict: dict) -> None:
    """Mergeia seção reputation."""
    if "reputation" not in merged or "reputation" not in p_dict:
        return
    
    for field in ["certifications", "awards", "partnerships", "client_list"]:
        merged["reputation"][field] = list(set(
            merged["reputation"].get(field, []) + p_dict["reputation"].get(field, [])
        ))
    
    _merge_case_studies(merged, p_dict)


def _merge_case_studies(merged: dict, p_dict: dict) -> None:
    """Mergeia case_studies."""
    case_dict = {cs["title"]: cs for cs in merged["reputation"].get("case_studies", [])}
    
    for case in p_dict["reputation"].get("case_studies", []):
        case_title = case.get("title")
        if not case_title or not isinstance(case_title, str):
            continue
        
        if case_title in case_dict:
            existing = case_dict[case_title]
            for field in ["challenge", "solution", "outcome"]:
                if case.get(field):
                    existing[field] = _merge_text_fields(
                        existing.get(field), case.get(field), field
                    )
            for field in ["client_name", "industry"]:
                if case.get(field) and (not existing.get(field) or len(str(case[field])) > len(str(existing.get(field, "")))):
                    existing[field] = case[field]
        else:
            case_dict[case_title] = case.copy()
    
    merged["reputation"]["case_studies"] = list(case_dict.values())


def _merge_sources(merged: dict, p_dict: dict) -> None:
    """Mergeia sources."""
    if "sources" in merged and "sources" in p_dict:
        existing_sources = set(merged.get("sources", []))
        merged["sources"] = list(merged.get("sources", [])) + [
            s for s in p_dict.get("sources", []) if s not in existing_sources
        ]


def _clean_merged_profile(merged: dict) -> None:
    """Limpa e valida o perfil mergeado."""
    if "offerings" in merged and isinstance(merged["offerings"], dict):
        offerings = merged["offerings"]
        
        for field in ["products", "services", "engagement_models", "key_differentiators"]:
            if isinstance(offerings.get(field), list):
                offerings[field] = [item for item in offerings[field] if isinstance(item, str) and item.strip()]
        
        # Limpar categorias inválidas
        invalid_names = {"outras categorias", "outras", "marcas", "marca", "geral", "diversos", "outros", "categorias", "categoria", "produtos", "produto"}
        if isinstance(offerings.get("product_categories"), list):
            valid_cats = []
            for cat in offerings["product_categories"]:
                if not isinstance(cat, dict) or not cat.get("category_name"):
                    continue
                if cat.get("category_name", "").strip().lower() in invalid_names:
                    continue
                if not isinstance(cat.get("items"), list):
                    cat["items"] = []
                else:
                    cat["items"] = [item for item in cat["items"] if isinstance(item, str) and item.strip()]
                valid_cats.append(cat)
            offerings["product_categories"] = valid_cats
        
        if isinstance(offerings.get("service_details"), list):
            valid_services = []
            for service in offerings["service_details"]:
                if isinstance(service, dict) and service.get("name"):
                    if isinstance(service.get("deliverables"), list):
                        service["deliverables"] = [d for d in service["deliverables"] if isinstance(d, str) and d.strip()]
                    valid_services.append(service)
            offerings["service_details"] = valid_services
    
    # Limpar reputation
    if "reputation" in merged and isinstance(merged["reputation"], dict):
        reputation = merged["reputation"]
        for field in ["certifications", "awards", "partnerships", "client_list"]:
            if isinstance(reputation.get(field), list):
                reputation[field] = [item for item in reputation[field] if isinstance(item, str) and item.strip()]
        
        if isinstance(reputation.get("case_studies"), list):
            reputation["case_studies"] = [case for case in reputation["case_studies"] if isinstance(case, dict) and case.get("title")]
    
    # Limpar contact
    if "contact" in merged and isinstance(merged["contact"], dict):
        for field in ["emails", "phones", "locations"]:
            if isinstance(merged["contact"].get(field), list):
                merged["contact"][field] = [item for item in merged["contact"][field] if isinstance(item, str) and item.strip()]
    
    # Limpar sources
    if isinstance(merged.get("sources"), list):
        merged["sources"] = [s for s in merged["sources"] if isinstance(s, str) and s.strip()]

