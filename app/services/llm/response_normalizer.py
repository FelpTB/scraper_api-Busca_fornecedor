"""
Normalização de respostas do LLM.
Garante que as respostas estejam no formato correto para CompanyProfile.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def normalize_llm_response(data: Any) -> dict:
    """
    Normaliza e valida a resposta do LLM para garantir compatibilidade com CompanyProfile.
    Corrige:
    - Arrays retornados ao invés de objetos
    - Campos None que deveriam ser listas vazias
    - Objetos aninhados com valores None
    """
    # Validar se é um objeto (não array)
    if isinstance(data, list):
        logger.warning("LLM retornou array ao invés de objeto. Tentando extrair primeiro item...")
        if len(data) > 0 and isinstance(data[0], dict):
            data = data[0]
            logger.info("✅ Array convertido para objeto (primeiro item extraído)")
        else:
            logger.error(f"❌ Array vazio ou inválido")
            raise ValueError("LLM retornou array vazio ou inválido")
    
    if not isinstance(data, dict):
        logger.error(f"❌ Tipo inválido recebido: {type(data)}. Esperado: dict")
        raise ValueError(f"LLM retornou tipo inválido: {type(data)}")
    
    # Normalizar seções principais
    _normalize_team(data)
    _normalize_offerings(data)
    _normalize_reputation(data)
    _normalize_contact(data)
    _normalize_root_fields(data)
    
    return data


def _normalize_team(data: dict) -> None:
    """Normaliza a seção team."""
    if "team" in data:
        if not isinstance(data["team"], dict):
            data["team"] = {}
        team = data["team"]
        if team.get("key_roles") is None:
            team["key_roles"] = []
        if team.get("team_certifications") is None:
            team["team_certifications"] = []


def _normalize_offerings(data: dict) -> None:
    """Normaliza a seção offerings."""
    if "offerings" in data:
        if not isinstance(data["offerings"], dict):
            data["offerings"] = {}
        offerings = data["offerings"]
        
        # Listas simples
        for field in ["products", "services", "engagement_models", "key_differentiators"]:
            if offerings.get(field) is None:
                offerings[field] = []
            elif not isinstance(offerings[field], list):
                offerings[field] = []
        
        # product_categories
        _normalize_product_categories(offerings)
        
        # service_details
        _normalize_service_details(offerings)


def _normalize_product_categories(offerings: dict) -> None:
    """Normaliza product_categories."""
    if offerings.get("product_categories") is None:
        offerings["product_categories"] = []
    elif not isinstance(offerings["product_categories"], list):
        offerings["product_categories"] = []
    else:
        valid_categories = []
        for cat in offerings["product_categories"]:
            if not isinstance(cat, dict):
                continue
            cat_name = cat.get("category_name")
            if not cat_name or not isinstance(cat_name, str):
                continue
            if cat.get("items") is None:
                cat["items"] = []
            elif not isinstance(cat["items"], list):
                cat["items"] = []
            else:
                cat["items"] = [item for item in cat["items"] if isinstance(item, str) and item.strip()]
            valid_categories.append(cat)
        offerings["product_categories"] = valid_categories


def _normalize_service_details(offerings: dict) -> None:
    """Normaliza service_details."""
    if offerings.get("service_details") is None:
        offerings["service_details"] = []
    elif not isinstance(offerings["service_details"], list):
        offerings["service_details"] = []
    else:
        valid_services = []
        for service in offerings["service_details"]:
            if not isinstance(service, dict):
                continue
            if not service.get("name") or not isinstance(service.get("name"), str):
                continue
            if service.get("deliverables") is None:
                service["deliverables"] = []
            elif not isinstance(service["deliverables"], list):
                service["deliverables"] = []
            else:
                service["deliverables"] = [d for d in service["deliverables"] if isinstance(d, str) and d.strip()]
            valid_services.append(service)
        offerings["service_details"] = valid_services


def _normalize_reputation(data: dict) -> None:
    """Normaliza a seção reputation."""
    if "reputation" in data:
        if not isinstance(data["reputation"], dict):
            data["reputation"] = {}
        reputation = data["reputation"]
        
        for field in ["certifications", "awards", "partnerships", "client_list"]:
            if reputation.get(field) is None:
                reputation[field] = []
            elif not isinstance(reputation[field], list):
                if isinstance(reputation[field], str):
                    reputation[field] = [reputation[field]]
                else:
                    reputation[field] = []
        
        _normalize_case_studies(reputation)


def _normalize_case_studies(reputation: dict) -> None:
    """Normaliza case_studies."""
    if reputation.get("case_studies") is None:
        reputation["case_studies"] = []
    elif not isinstance(reputation["case_studies"], list):
        reputation["case_studies"] = []
    else:
        valid_cases = []
        for case in reputation["case_studies"]:
            if not isinstance(case, dict):
                continue
            if not case.get("title"):
                if case.get("challenge"):
                    case["title"] = f"Desafio: {str(case['challenge'])[:50]}..."
                elif case.get("solution"):
                    case["title"] = f"Solução: {str(case['solution'])[:50]}..."
                elif case.get("client_name"):
                    case["title"] = f"Caso: {case['client_name']}"
                elif any(v for k, v in case.items() if v):
                    case["title"] = "Estudo de Caso (Sem Título)"
                else:
                    continue
            valid_cases.append(case)
        reputation["case_studies"] = valid_cases


def _normalize_contact(data: dict) -> None:
    """Normaliza a seção contact."""
    if "contact" in data:
        if not isinstance(data["contact"], dict):
            data["contact"] = {}
        contact = data["contact"]
        for field in ["emails", "phones", "locations"]:
            if contact.get(field) is None:
                contact[field] = []


def _normalize_root_fields(data: dict) -> None:
    """Normaliza campos no nível raiz."""
    if data.get("sources") is None:
        data["sources"] = []
    
    # Garantir que seções obrigatórias são objetos válidos
    for section in ["identity", "classification", "team", "contact", "reputation", "offerings"]:
        if data.get(section) is None or not isinstance(data.get(section), dict):
            data[section] = {}

