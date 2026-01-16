"""
Schemas Pydantic para endpoint Scrape v2.
"""
from pydantic import BaseModel, Field, ConfigDict, HttpUrl
from typing import Optional


class ScrapeRequest(BaseModel):
    """
    Request schema para scraping de site.
    
    Campos:
        cnpj_basico: CNPJ básico da empresa (8 primeiros dígitos) - obrigatório
        website_url: URL do site oficial para scraping - obrigatório
    """
    cnpj_basico: str = Field(..., description="CNPJ básico da empresa (8 primeiros dígitos)", min_length=8, max_length=8)
    website_url: str = Field(..., description="URL do site oficial para scraping")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cnpj_basico": "12345678",
                "website_url": "https://www.empresa.com.br"
            }
        }
    )


class ScrapeResponse(BaseModel):
    """
    Response schema para scraping de site.
    
    Campos:
        success: Indica se a operação foi bem-sucedida
        chunks_saved: Número de chunks salvos no banco de dados
        total_tokens: Total de tokens processados em todos os chunks
        pages_scraped: Número de páginas scraped com sucesso
        processing_time_ms: Tempo de processamento em milissegundos
    """
    success: bool = Field(..., description="Indica se a operação foi bem-sucedida")
    chunks_saved: int = Field(..., description="Número de chunks salvos no banco de dados", ge=0)
    total_tokens: int = Field(..., description="Total de tokens processados em todos os chunks", ge=0)
    pages_scraped: int = Field(..., description="Número de páginas scraped com sucesso", ge=0)
    processing_time_ms: float = Field(..., description="Tempo de processamento em milissegundos", ge=0.0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "chunks_saved": 15,
                "total_tokens": 125000,
                "pages_scraped": 8,
                "processing_time_ms": 3450.5
            }
        }
    )

