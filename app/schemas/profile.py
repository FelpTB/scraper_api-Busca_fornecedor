"""
Schema do Perfil de Empresa para extração B2B.

v4.0: Descriptions otimizadas para SGLang/XGrammar Structured Output
      - Field descriptions guiam o modelo na extração
      - Descriptions complementam o system prompt, não repetem
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class Identity(BaseModel):
    """Informações básicas de identificação da empresa."""
    company_name: Optional[str] = Field(None, description="Nome oficial da empresa")
    cnpj: Optional[str] = Field(None, description="CNPJ brasileiro se disponível")
    tagline: Optional[str] = Field(None, description="Slogan ou frase de efeito da empresa")
    description: Optional[str] = Field(None, description="Descrição resumida do que a empresa faz")
    founding_year: Optional[str] = Field(None, description="Ano de fundação")
    employee_count_range: Optional[str] = Field(None, description="Faixa de funcionários (ex: 10-50, 100-500)")


class Classification(BaseModel):
    """Classificação e posicionamento de mercado."""
    industry: Optional[str] = Field(None, description="Setor/indústria de atuação")
    business_model: Optional[str] = Field(None, description="Modelo: B2B, B2C, Distribuidor, Fabricante, etc.")
    target_audience: Optional[str] = Field(None, description="Público-alvo ou segmento atendido")
    geographic_coverage: Optional[str] = Field(None, description="Abrangência: Nacional, Regional, São Paulo, etc.")


class TeamProfile(BaseModel):
    """Informações sobre a equipe."""
    size_range: Optional[str] = Field(None, description="Tamanho da equipe")
    key_roles: List[str] = Field(default_factory=list, description="Principais funções/cargos na equipe")
    team_certifications: List[str] = Field(default_factory=list, description="Certificações da equipe (PMP, AWS, etc.)")


class ServiceDetail(BaseModel):
    """Detalhes de um serviço oferecido."""
    name: Optional[str] = Field(None, description="Nome do serviço")
    description: Optional[str] = Field(None, description="Descrição do serviço")
    methodology: Optional[str] = Field(None, description="Metodologia utilizada (Agile, Design Thinking, etc.)")
    deliverables: List[str] = Field(default_factory=list, description="Entregáveis do serviço")
    ideal_client_profile: Optional[str] = Field(None, description="Perfil ideal de cliente para este serviço")


class ProductCategory(BaseModel):
    """Categoria de produtos com itens específicos."""
    category_name: Optional[str] = Field(None, description="Nome da categoria de produtos")
    items: List[str] = Field(
        default_factory=list, 
        description="PRODUTOS ESPECÍFICOS: nomes, modelos, SKUs. NÃO coloque nomes de categorias ou marcas isoladas"
    )


class Offerings(BaseModel):
    """Produtos e serviços oferecidos pela empresa."""
    products: List[str] = Field(default_factory=list, description="Lista geral de produtos")
    product_categories: List[ProductCategory] = Field(
        default_factory=list, 
        description="Categorias de produtos com itens específicos"
    )
    services: List[str] = Field(default_factory=list, description="Lista geral de serviços")
    service_details: List[ServiceDetail] = Field(default_factory=list, description="Detalhes dos principais serviços")
    engagement_models: List[str] = Field(
        default_factory=list, 
        description="Modelos de contratação: Por Projeto, Mensalidade, Alocação, etc."
    )
    key_differentiators: List[str] = Field(default_factory=list, description="Diferenciais competitivos")


class CaseStudy(BaseModel):
    """Estudo de caso ou projeto de referência."""
    title: Optional[str] = Field(None, description="Título do caso de sucesso")
    client_name: Optional[str] = Field(None, description="Nome do cliente")
    industry: Optional[str] = Field(None, description="Setor do cliente")
    challenge: Optional[str] = Field(None, description="Desafio enfrentado")
    solution: Optional[str] = Field(None, description="Solução implementada")
    outcome: Optional[str] = Field(None, description="Resultado obtido")


class Reputation(BaseModel):
    """Reputação e prova social da empresa."""
    certifications: List[str] = Field(default_factory=list, description="Certificações da empresa (ISO, ANVISA, etc.)")
    awards: List[str] = Field(default_factory=list, description="Prêmios e reconhecimentos")
    partnerships: List[str] = Field(default_factory=list, description="Parcerias tecnológicas ou comerciais")
    client_list: List[str] = Field(default_factory=list, description="Clientes de referência mencionados")
    case_studies: List[CaseStudy] = Field(default_factory=list, description="Casos de sucesso detalhados")


class Contact(BaseModel):
    """Informações de contato."""
    emails: List[str] = Field(default_factory=list, description="Emails de contato")
    phones: List[str] = Field(default_factory=list, description="Telefones")
    linkedin_url: Optional[str] = Field(None, description="URL do LinkedIn")
    website_url: Optional[str] = Field(None, description="URL do site")
    headquarters_address: Optional[str] = Field(None, description="Endereço da sede")
    locations: List[str] = Field(default_factory=list, description="Filiais e outras localizações")

class CompanyProfile(BaseModel):
    identity: Identity = Identity()
    classification: Classification = Classification()
    team: TeamProfile = TeamProfile()
    offerings: Offerings = Offerings()
    reputation: Reputation = Reputation()
    contact: Contact = Contact()
    sources: List[str] = []

    def is_empty(self) -> bool:
        """
        Verifica se o perfil da empresa está vazio (sem dados preenchidos).
        Retorna True se nenhum campo relevante foi preenchido.
        """
        # Verifica se identity tem dados básicos
        identity_empty = (
            not self.identity.company_name and
            not self.identity.cnpj and
            not self.identity.tagline and
            not self.identity.description
        )

        # Verifica se classification tem dados
        classification_empty = (
            not self.classification.industry and
            not self.classification.business_model and
            not self.classification.target_audience
        )

        # Verifica se offerings tem dados
        offerings_empty = (
            not self.offerings.products and
            not self.offerings.services and
            not self.offerings.product_categories
        )

        # Verifica se contact tem dados
        contact_empty = (
            not self.contact.website_url and
            not self.contact.emails and
            not self.contact.phones
        )

        # Se pelo menos um campo principal tem dados, não está vazio
        return identity_empty and classification_empty and offerings_empty and contact_empty
