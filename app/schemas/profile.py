from typing import List, Optional
from pydantic import BaseModel, Field

class Identidade(BaseModel):
    nome_empresa: Optional[str] = Field(
        None,
        description="Nome completo da empresa conforme registro na Receita Federal. Use o nome fantasia se disponível, caso contrário use a razão social. Exemplo: 'Empresa XYZ Ltda' ou 'XYZ Tecnologia'."
    )
    cnpj: Optional[str] = Field(
        None,
        description="CNPJ da empresa no formato XX.XXX.XXX/XXXX-XX ou apenas números (14 dígitos). Exemplo: '12.345.678/0001-90' ou '12345678000190'."
    )
    descricao: Optional[str] = Field(
        None,
        description="Descrição detalhada da empresa extraída do conteúdo fornecido. Deve incluir atividades principais, missão, histórico, diferenciais ou qualquer informação relevante sobre a empresa. Extraia do texto fornecido, não invente informações."
    )
    ano_fundacao: Optional[str] = Field(
        None,
        description="Ano de fundação da empresa no formato YYYY (ex: '2010', '1995'). Se apenas década for mencionada, use o ano aproximado. Se não encontrar informação específica, deixe null."
    )
    faixa_funcionarios: Optional[str] = Field(
        None,
        description="Faixa de número de funcionários no formato 'MIN-MAX' (ex: '10-50', '100-500', '1000+') ou descrição textual se números específicos não estiverem disponíveis. Extraia do texto fornecido."
    )

class Classificacao(BaseModel):
    industria: Optional[str] = Field(
        None,
        description="Setor ou indústria principal da empresa em português. Exemplos: 'Tecnologia da Informação', 'Construção Civil', 'Alimentação', 'Energia', 'Saúde'. Extraia do conteúdo fornecido."
    )
    modelo_negocio: Optional[str] = Field(
        None,
        description="Modelo de negócio da empresa. Exemplos: 'B2B' (empresa para empresa), 'B2C' (empresa para consumidor), 'Prestador de Serviços', 'Distribuidor', 'Fabricante', 'Varejista'. Extraia do conteúdo fornecido."
    )
    publico_alvo: Optional[str] = Field(
        None,
        description="Público-alvo ou segmento de mercado que a empresa atende. Exemplos: 'Grandes empresas', 'PMEs', 'Governo', 'Consumidores finais', 'Setor automotivo'. Extraia do conteúdo fornecido."
    )
    cobertura_geografica: Optional[str] = Field(
        None,
        description="Área geográfica de atuação da empresa. Exemplos: 'Nacional', 'Internacional', 'Apenas São Paulo', 'Região Sudeste', 'América Latina'. Extraia do conteúdo fornecido."
    )

class CategoriaProduto(BaseModel):
    categoria: Optional[str] = Field(
        None,
        description="Nome da categoria de produtos em português. Exemplos: 'Cabos e Fios', 'Conectores', 'Equipamentos de Automação', 'Luminárias'. Use apenas categorias específicas mencionadas no conteúdo, não crie categorias genéricas."
    )
    produtos: List[str] = Field(
        default_factory=list,
        description="Lista de produtos específicos desta categoria. Cada item deve ser um nome completo de produto, modelo, referência ou SKU mencionado explicitamente no texto (ex: 'Cabo 1KV HEPR', 'Conector RCA', 'Luminária LED 50W'). CRÍTICO: NÃO gere variações do mesmo produto (ex: se menciona 'RCA', não adicione 'Conector RCA', 'RCA macho', 'RCA fêmea', etc.). NÃO inclua nomes de categorias, marcas isoladas ou descrições genéricas. Máximo 60 produtos por categoria. PARE quando não houver mais produtos únicos no texto ou ao atingir o limite."
    )

class Servico(BaseModel):
    nome: Optional[str] = Field(
        None,
        description="Nome do serviço oferecido pela empresa em português. Exemplos: 'Consultoria em Automação Industrial', 'Desenvolvimento de Software Customizado', 'Manutenção Preventiva'. Extraia do conteúdo fornecido."
    )
    descricao: Optional[str] = Field(
        None,
        description="Descrição detalhada do serviço, explicando o que é oferecido, como é realizado ou quais são os benefícios. Baseie-se no conteúdo fornecido. Se não houver descrição disponível, deixe null."
    )

class Ofertas(BaseModel):
    produtos: List[CategoriaProduto] = Field(
        default_factory=list,
        description="Lista de categorias de produtos oferecidos pela empresa. Cada categoria contém uma lista de produtos específicos. Organize produtos por categoria quando possível. Máximo 40 categorias. Extraia apenas produtos mencionados explicitamente no texto, sem gerar variações."
    )
    servicos: List[Servico] = Field(
        default_factory=list,
        description="Lista de serviços oferecidos pela empresa. Cada serviço deve ter nome e descrição. Máximo 50 serviços. Extraia apenas serviços mencionados explicitamente no texto."
    )

class EstudoCaso(BaseModel):
    titulo: Optional[str] = Field(
        None,
        description="Título do estudo de caso ou projeto. Exemplos: 'Automação Industrial para Empresa ABC', 'Implementação de Sistema ERP'. Se não houver título explícito, crie um baseado no cliente ou desafio."
    )
    nome_cliente: Optional[str] = Field(
        None,
        description="Nome da empresa cliente mencionada no estudo de caso. Use o nome completo da empresa. Exemplo: 'Petrobras', 'Vale', 'Ambev'."
    )
    industria: Optional[str] = Field(
        None,
        description="Setor ou indústria do cliente no estudo de caso. Exemplos: 'Petróleo e Gás', 'Mineração', 'Alimentação'."
    )
    desafio: Optional[str] = Field(
        None,
        description="Desafio ou problema que o cliente enfrentava antes da solução. Extraia do conteúdo fornecido."
    )
    solucao: Optional[str] = Field(
        None,
        description="Solução oferecida pela empresa para resolver o desafio do cliente. Extraia do conteúdo fornecido."
    )
    resultado: Optional[str] = Field(
        None,
        description="Resultados alcançados, benefícios obtidos ou métricas de sucesso do projeto. Extraia do conteúdo fornecido."
    )

class Reputacao(BaseModel):
    certificacoes: List[str] = Field(
        default_factory=list,
        description="Lista de certificações da empresa. Exemplos: 'ISO 9001', 'ISO 14001', 'Certificação Anvisa', 'OHSAS 18001'. Extraia apenas certificações mencionadas explicitamente. Máximo 50 certificações. NÃO gere variações do mesmo certificado."
    )
    premios: List[str] = Field(
        default_factory=list,
        description="Lista de prêmios, reconhecimentos ou distinções recebidos pela empresa. Exemplos: 'Melhor Empresa do Ano', 'Prêmio de Inovação'. Extraia apenas prêmios mencionados explicitamente. Máximo 50 prêmios."
    )
    parcerias: List[str] = Field(
        default_factory=list,
        description="Lista de parceiros tecnológicos ou comerciais da empresa. Exemplos: 'Microsoft', 'SAP', 'Oracle', 'Parceiro Autorizado Siemens'. Use apenas nomes de empresas/entidades mencionadas. Máximo 50 parcerias. NÃO gere variações do mesmo parceiro."
    )
    lista_clientes: List[str] = Field(
        default_factory=list,
        description="Lista de clientes principais ou cases de sucesso mencionados. Use apenas nomes de empresas mencionadas explicitamente. Exemplos: 'Petrobras', 'Vale', 'Ambev'. Máximo 80 clientes. NÃO gere variações do mesmo cliente (ex: 'Petrobras' e 'Grupo Petrobras' são o mesmo - use apenas 'Petrobras')."
    )
    estudos_caso: List[EstudoCaso] = Field(
        default_factory=list,
        description="Lista de estudos de caso detalhados com informações sobre projetos realizados para clientes. Cada estudo deve incluir título, cliente, desafio, solução e resultados quando disponíveis. Máximo 30 estudos de caso."
    )

class Contato(BaseModel):
    emails: List[str] = Field(
        default_factory=list,
        description="Lista de endereços de email da empresa. Cada email deve estar no formato válido (ex: 'contato@empresa.com.br'). Extraia apenas emails mencionados explicitamente no conteúdo."
    )
    telefones: List[str] = Field(
        default_factory=list,
        description="Lista de números de telefone da empresa. Pode incluir telefones fixos e celulares. Formato preferido: '(XX) XXXX-XXXX' ou '+55 XX XXXX-XXXX'. Extraia apenas telefones mencionados explicitamente."
    )
    url_linkedin: Optional[str] = Field(
        None,
        description="URL completa do perfil da empresa no LinkedIn. Deve começar com 'https://' ou 'http://' e conter 'linkedin.com'. Exemplo: 'https://www.linkedin.com/company/empresa-xyz'."
    )
    url_site: Optional[str] = Field(
        None,
        description="URL completa do site oficial da empresa. Deve começar com 'https://' ou 'http://'. Exemplo: 'https://www.empresa.com.br'."
    )
    endereco_matriz: Optional[str] = Field(
        None,
        description="Endereço completo da matriz ou sede da empresa. Inclua rua, número, bairro, cidade, estado e CEP quando disponível. Exemplo: 'Av. Paulista, 1000, Bela Vista, São Paulo - SP, 01310-100'."
    )
    localizacoes: List[str] = Field(
        default_factory=list,
        description="Lista de localizações adicionais, filiais ou escritórios da empresa. Cada item deve ser um endereço ou cidade/estado onde a empresa possui presença. Extraia do conteúdo fornecido."
    )

class CompanyProfile(BaseModel):
    identidade: Identidade = Field(
        default_factory=Identidade,
        description="Informações de identidade da empresa: nome, CNPJ, descrição, ano de fundação e faixa de funcionários."
    )
    classificacao: Classificacao = Field(
        default_factory=Classificacao,
        description="Classificação da empresa: indústria, modelo de negócio, público-alvo e cobertura geográfica."
    )
    ofertas: Ofertas = Field(
        default_factory=Ofertas,
        description="Ofertas da empresa: produtos organizados por categoria e serviços oferecidos. Produtos são itens físicos, serviços são atividades intangíveis."
    )
    reputacao: Reputacao = Field(
        default_factory=Reputacao,
        description="Reputação e prova social da empresa: certificações, prêmios, parcerias, lista de clientes e estudos de caso."
    )
    contato: Contato = Field(
        default_factory=Contato,
        description="Informações de contato da empresa: emails, telefones, URLs (LinkedIn, site), endereço da matriz e outras localizações."
    )
    fontes: List[str] = Field(
        default_factory=list,
        description="Lista de fontes ou URLs de onde os dados foram extraídos. Útil para rastreabilidade e validação dos dados extraídos."
    )

    def is_empty(self) -> bool:
        """
        Verifica se o perfil da empresa está vazio (sem dados preenchidos).
        Retorna True se nenhum campo relevante foi preenchido.
        """
        # Verifica se identidade tem dados básicos
        identidade_vazia = (
            not self.identidade.nome_empresa and
            not self.identidade.cnpj and
            not self.identidade.descricao
        )

        # Verifica se classificacao tem dados
        classificacao_vazia = (
            not self.classificacao.industria and
            not self.classificacao.modelo_negocio and
            not self.classificacao.publico_alvo
        )

        # Verifica se ofertas tem dados
        ofertas_vazias = (
            not self.ofertas.produtos and
            not self.ofertas.servicos
        )

        # Verifica se contato tem dados
        contato_vazio = (
            not self.contato.url_site and
            not self.contato.emails and
            not self.contato.telefones
        )

        # Se pelo menos um campo principal tem dados, não está vazio
        return identidade_vazia and classificacao_vazia and ofertas_vazias and contato_vazio
