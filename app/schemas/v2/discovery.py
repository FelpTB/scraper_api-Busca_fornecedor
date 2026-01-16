"""
Schemas Pydantic para endpoint Discovery v2.
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DiscoveryRequest(BaseModel):
    """
    Request schema para descoberta de site.
    
    Campos:
        cnpj_basico: CNPJ básico da empresa (8 primeiros dígitos) - obrigatório
    """
    cnpj_basico: str = Field(..., description="CNPJ básico da empresa (8 primeiros dígitos)", min_length=8, max_length=8)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cnpj_basico": "12345678"
            }
        }
    )


class DiscoveryResponse(BaseModel):
    """
    Response schema para descoberta de site.
    
    Campos:
        success: Indica se a operação foi bem-sucedida
        discovery_id: ID do registro salvo no banco de dados (tabela website_discovery)
        website_url: URL do site encontrado (None se não encontrado)
        discovery_status: Status da descoberta ('found', 'not_found', 'error')
        confidence_score: Score de confiança (0.0 a 1.0) - opcional
    """
    success: bool = Field(..., description="Indica se a operação foi bem-sucedida")
    discovery_id: Optional[int] = Field(None, description="ID do registro salvo no banco de dados")
    website_url: Optional[str] = Field(None, description="URL do site encontrado")
    discovery_status: str = Field(..., description="Status da descoberta: 'found', 'not_found', ou 'error'")
    confidence_score: Optional[float] = Field(None, description="Score de confiança (0.0 a 1.0)", ge=0.0, le=1.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "discovery_id": 456,
                "website_url": "https://www.empresa.com.br",
                "discovery_status": "found",
                "confidence_score": 0.95
            }
        }
    )

