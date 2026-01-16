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
    """
    Normaliza a seção team.
    
    Correções v2.1:
    - Filtra None e não-strings de key_roles e team_certifications
    """
    if "team" in data:
        if not isinstance(data["team"], dict):
            data["team"] = {}
        team = data["team"]
        
        # key_roles e team_certifications: filtrar valores inválidos
        for field in ["key_roles", "team_certifications"]:
            if team.get(field) is None:
                team[field] = []
            elif isinstance(team[field], list):
                # Filtrar: apenas strings não-vazias
                team[field] = [
                    item for item in team[field]
                    if isinstance(item, str) and item.strip()
                ]
            elif isinstance(team[field], str) and team[field].strip():
                team[field] = [team[field].strip()]
            else:
                team[field] = []
        
        # size_range: garantir que é string ou None
        if team.get("size_range") is not None and not isinstance(team.get("size_range"), str):
            team["size_range"] = str(team["size_range"]) if team["size_range"] else None


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
    """
    Normaliza a seção reputation.
    
    Correções v2.1:
    - Filtra dicts/None de listas (partnerships, certifications, etc.)
    - Extrai strings de objetos complexos quando possível
    """
    if "reputation" in data:
        if not isinstance(data["reputation"], dict):
            data["reputation"] = {}
        reputation = data["reputation"]
        
        for field in ["certifications", "awards", "partnerships", "client_list"]:
            if reputation.get(field) is None:
                reputation[field] = []
            elif not isinstance(reputation[field], list):
                if isinstance(reputation[field], str) and reputation[field].strip():
                    reputation[field] = [reputation[field].strip()]
                else:
                    reputation[field] = []
            else:
                # Filtrar lista: apenas strings válidas
                # Se item é dict, tenta extrair nome/title/name
                valid_items = []
                for item in reputation[field]:
                    if isinstance(item, str) and item.strip():
                        valid_items.append(item.strip())
                    elif isinstance(item, dict):
                        # Tentar extrair string de campos comuns
                        extracted = (
                            item.get("name") or 
                            item.get("title") or 
                            item.get("partner_name") or
                            item.get("company") or
                            item.get("client_name") or
                            item.get("certification") or
                            item.get("award")
                        )
                        if extracted and isinstance(extracted, str) and extracted.strip():
                            valid_items.append(extracted.strip())
                            logger.debug(f"Extraído '{extracted}' de dict em {field}")
                        else:
                            logger.warning(f"Item dict ignorado em {field}: {list(item.keys())[:3]}")
                    elif item is not None:
                        logger.warning(f"Item inválido em {field}: {type(item).__name__}")
                reputation[field] = valid_items
        
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
    """
    Normaliza a seção contact.
    
    Correções v2.1:
    - website_url: lista → primeira string válida
    - emails/phones/locations: filtra None e não-strings
    - linkedin_url: lista → primeira string válida
    """
    if "contact" in data:
        if not isinstance(data["contact"], dict):
            data["contact"] = {}
        contact = data["contact"]
        
        # Campos de lista: filtrar valores inválidos (None, não-strings, strings vazias)
        for field in ["emails", "phones", "locations"]:
            if contact.get(field) is None:
                contact[field] = []
            elif isinstance(contact[field], list):
                # Filtrar: apenas strings não-vazias
                contact[field] = [
                    item for item in contact[field]
                    if isinstance(item, str) and item.strip()
                ]
            elif isinstance(contact[field], str) and contact[field].strip():
                # String única → converter para lista
                contact[field] = [contact[field].strip()]
            else:
                contact[field] = []
        
        # website_url: deve ser string, não lista
        website = contact.get("website_url")
        if website is None:
            pass  # Manter None (campo opcional)
        elif isinstance(website, list):
            # Lista → extrair primeira URL válida
            valid_url = None
            for url in website:
                if isinstance(url, str) and url.strip() and url.startswith("http"):
                    valid_url = url.strip()
                    break
            if valid_url:
                logger.warning(f"website_url era lista, extraído: {valid_url[:50]}...")
            contact["website_url"] = valid_url
        elif isinstance(website, str) and website.strip():
            contact["website_url"] = website.strip()
        else:
            contact["website_url"] = None
        
        # linkedin_url: mesmo tratamento
        linkedin = contact.get("linkedin_url")
        if linkedin is None:
            pass
        elif isinstance(linkedin, list):
            valid_url = None
            for url in linkedin:
                if isinstance(url, str) and url.strip() and "linkedin" in url.lower():
                    valid_url = url.strip()
                    break
            if valid_url:
                logger.warning(f"linkedin_url era lista, extraído: {valid_url[:50]}...")
            contact["linkedin_url"] = valid_url
        elif isinstance(linkedin, str) and linkedin.strip():
            contact["linkedin_url"] = linkedin.strip()
        else:
            contact["linkedin_url"] = None
        
        # headquarters_address: garantir que é string
        address = contact.get("headquarters_address")
        if address is not None and not isinstance(address, str):
            if isinstance(address, list) and address:
                contact["headquarters_address"] = str(address[0]) if address[0] else None
            else:
                contact["headquarters_address"] = None


def _normalize_root_fields(data: dict) -> None:
    """Normaliza campos no nível raiz."""
    if data.get("sources") is None:
        data["sources"] = []
    
    # Garantir que seções obrigatórias são objetos válidos
    for section in ["identity", "classification", "team", "contact", "reputation", "offerings"]:
        if data.get(section) is None or not isinstance(data.get(section), dict):
            data[section] = {}

