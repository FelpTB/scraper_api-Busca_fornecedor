"""
Schemas Pydantic para endpoint Profile v2.
"""
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ProfileRequest(BaseModel):
    """
    Request schema para montagem de perfil da empresa.
    
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


class ProfileResponse(BaseModel):
    """
    Response schema para montagem de perfil da empresa.
    
    Campos:
        success: Indica se a operação foi bem-sucedida
        company_id: ID do registro salvo no banco de dados (tabela company_profile)
        profile_status: Status do processamento ('success', 'partial', 'error')
        chunks_processed: Número de chunks processados
        processing_time_ms: Tempo de processamento em milissegundos
    """
    success: bool = Field(..., description="Indica se a operação foi bem-sucedida")
    company_id: Optional[int] = Field(None, description="ID do registro salvo no banco de dados")
    profile_status: str = Field(..., description="Status do processamento: 'success', 'partial', ou 'error'")
    chunks_processed: int = Field(..., description="Número de chunks processados", ge=0)
    processing_time_ms: float = Field(..., description="Tempo de processamento em milissegundos", ge=0.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "company_id": 789,
                "profile_status": "success",
                "chunks_processed": 15,
                "processing_time_ms": 5432.1
            }
        }
    )

