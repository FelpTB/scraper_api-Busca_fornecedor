"""
Schemas Pydantic para endpoint Serper v2.
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class SerperRequest(BaseModel):
    """
    Request schema para busca Serper.
    
    Campos:
        cnpj_basico: CNPJ básico da empresa (8 primeiros dígitos) - obrigatório
        razao_social: Razão social da empresa - opcional
        nome_fantasia: Nome fantasia da empresa - opcional
        municipio: Município da empresa - opcional
    """
    cnpj_basico: str = Field(..., description="CNPJ básico da empresa (8 primeiros dígitos)", min_length=8, max_length=8)
    razao_social: Optional[str] = Field(None, description="Razão social da empresa")
    nome_fantasia: Optional[str] = Field(None, description="Nome fantasia da empresa")
    municipio: Optional[str] = Field(None, description="Município da empresa")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cnpj_basico": "12345678",
                "razao_social": "Empresa Exemplo LTDA",
                "nome_fantasia": "Exemplo",
                "municipio": "São Paulo"
            }
        }
    )


class SerperResponse(BaseModel):
    """
    Response schema para busca Serper.
    
    Campos:
        success: Indica se a operação foi bem-sucedida
        serper_id: ID do registro salvo no banco de dados (tabela serper_results)
        results_count: Número de resultados retornados pela busca
        query_used: Query utilizada na busca Serper
    """
    success: bool = Field(..., description="Indica se a operação foi bem-sucedida")
    serper_id: Optional[int] = Field(None, description="ID do registro salvo no banco de dados")
    results_count: int = Field(..., description="Número de resultados retornados pela busca", ge=0)
    query_used: str = Field(..., description="Query utilizada na busca Serper")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "serper_id": 123,
                "results_count": 10,
                "query_used": "Empresa Exemplo LTDA São Paulo"
            }
        }
    )

