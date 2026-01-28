"""
Serviço de banco de dados 100% assíncrono.
Atualizado para usar o schema busca_fornecedor.
"""
import json
import logging
from typing import List, Optional, Dict, Any
from app.core.database import get_pool
from app.schemas.profile import CompanyProfile

logger = logging.getLogger(__name__)

# Schema do banco de dados - IMPORTANTE: sempre usar explicitamente nas queries
# Usar aspas duplas para garantir que o PostgreSQL use o schema correto
SCHEMA = "busca_fornecedor"


class DatabaseService:
    """Serviço de CRUD assíncrono para todas as tabelas."""
    
    # ========== SERPER RESULTS ==========
    
    async def save_serper_results(
        self,
        cnpj_basico: str,
        results: List[dict],
        query_used: str,
        company_name: Optional[str] = None,
        razao_social: Optional[str] = None,
        nome_fantasia: Optional[str] = None,
        municipio: Optional[str] = None,
    ) -> int:
        """
        Salva resultados Serper e retorna ID.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
            results: Lista de resultados da busca (array de dicts)
            query_used: Query usada na busca
            company_name: Nome da empresa (opcional)
            razao_social: Razão social (opcional)
            nome_fantasia: Nome fantasia (opcional)
            municipio: Município (opcional)
        
        Returns:
            ID do registro criado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Garantir que estamos usando o schema correto - SEMPRE explícito
            query = f"""
                INSERT INTO "{SCHEMA}".serper_results 
                    (cnpj_basico, company_name, razao_social, nome_fantasia, 
                     municipio, results_json, results_count, query_used)
                VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8)
                RETURNING id
                """
            logger.info(f"🔍 [SCHEMA={SCHEMA}] Executando INSERT em serper_results")
            logger.debug(f"🔍 Query: {query[:150]}...")
            row = await conn.fetchrow(
                query,
                cnpj_basico,
                company_name,
                razao_social,
                nome_fantasia,
                municipio,
                json.dumps(results),  # Converter para JSON string e fazer cast para JSONB
                len(results),
                query_used
            )
            serper_id = row['id']
            logger.debug(f"✅ Serper results salvos: id={serper_id}, cnpj={cnpj_basico}, results={len(results)}")
            return serper_id
    
    async def get_serper_results(self, cnpj_basico: str) -> Optional[Dict[str, Any]]:
        """
        Busca resultados Serper mais recentes para um CNPJ.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
        
        Returns:
            Dict com os resultados ou None se não encontrado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT * FROM "{SCHEMA}".serper_results 
                WHERE cnpj_basico = $1 
                ORDER BY created_at DESC 
                LIMIT 1
                """
            logger.debug(f"🔍 [SCHEMA={SCHEMA}] SELECT serper_results")
            row = await conn.fetchrow(
                query,
                cnpj_basico
            )
            if row:
                result = dict(row)
                # Parse JSONB se for string
                if isinstance(result.get('results_json'), str):
                    result['results_json'] = json.loads(result['results_json'])
                return result
            return None
    
    # ========== WEBSITE DISCOVERY ==========
    
    async def save_discovery(
        self,
        cnpj_basico: str,
        website_url: Optional[str],
        discovery_status: str,
        serper_id: Optional[int] = None,
        confidence_score: Optional[float] = None,
        llm_reasoning: Optional[str] = None,
    ) -> int:
        """
        Salva resultado da descoberta de site.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
            website_url: URL do site encontrado (None se não encontrado)
            discovery_status: Status ('found', 'not_found', 'error')
            serper_id: ID do resultado Serper relacionado (opcional)
            confidence_score: Score de confiança (opcional)
            llm_reasoning: Raciocínio do LLM (opcional)
        
        Returns:
            ID do registro criado ou atualizado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Garantir que estamos usando o schema correto - SEMPRE explícito
            query_check = f'SELECT id FROM "{SCHEMA}".website_discovery WHERE cnpj_basico = $1'
            logger.info(f"🔍 [SCHEMA={SCHEMA}] Verificando discovery")
            # Verificar se já existe registro para este CNPJ
            existing = await conn.fetchrow(
                query_check,
                cnpj_basico
            )
            
            if existing:
                # Atualizar registro existente
                query_update = f"""
                    UPDATE "{SCHEMA}".website_discovery 
                    SET website_url = $2,
                        discovery_status = $3,
                        serper_id = $4,
                        confidence_score = $5,
                        llm_reasoning = $6,
                        updated_at = NOW()
                    WHERE cnpj_basico = $1
                    RETURNING id
                    """
                logger.info(f"🔍 [SCHEMA={SCHEMA}] UPDATE website_discovery")
                row = await conn.fetchrow(
                    query_update,
                    cnpj_basico,
                    website_url,
                    discovery_status,
                    serper_id,
                    confidence_score,
                    llm_reasoning
                )
                discovery_id = row['id']
                logger.debug(f"✅ Discovery atualizado: id={discovery_id}, cnpj={cnpj_basico}, status={discovery_status}")
            else:
                # Criar novo registro
                query_insert = f"""
                    INSERT INTO "{SCHEMA}".website_discovery 
                        (cnpj_basico, serper_id, website_url, discovery_status, 
                         confidence_score, llm_reasoning)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """
                logger.info(f"🔍 [SCHEMA={SCHEMA}] INSERT website_discovery")
                row = await conn.fetchrow(
                    query_insert,
                    cnpj_basico,
                    serper_id,
                    website_url,
                    discovery_status,
                    confidence_score,
                    llm_reasoning
                )
                discovery_id = row['id']
                logger.debug(f"✅ Discovery criado: id={discovery_id}, cnpj={cnpj_basico}, status={discovery_status}")
            
            return discovery_id
    
    async def get_discovery(self, cnpj_basico: str) -> Optional[Dict[str, Any]]:
        """
        Busca descoberta de site para um CNPJ.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
        
        Returns:
            Dict com os dados da descoberta ou None se não encontrado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT * FROM "{SCHEMA}".website_discovery 
                WHERE cnpj_basico = $1
                """
            logger.debug(f"🔍 [SCHEMA={SCHEMA}] SELECT website_discovery")
            row = await conn.fetchrow(
                query,
                cnpj_basico
            )
            if row:
                return dict(row)
            return None
    
    # ========== SCRAPED CHUNKS ==========
    
    async def save_chunks_batch(
        self,
        cnpj_basico: str,
        chunks: List[Any],  # Lista de objetos Chunk
        website_url: str,
        discovery_id: Optional[int] = None,
    ) -> int:
        """
        Salva múltiplos chunks em batch (transação única).
        
        Args:
            cnpj_basico: CNPJ básico da empresa
            chunks: Lista de objetos Chunk (com content, tokens, index, total_chunks, pages_included)
            website_url: URL do site
            discovery_id: ID da descoberta relacionada (opcional)
        
        Returns:
            Número de chunks salvos
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Transação para garantir atomicidade
            async with conn.transaction():
                # Preparar dados para batch insert
                records = []
                for chunk in chunks:
                    # Extrair page_source (primeira página ou todas concatenadas)
                    page_source = None
                    if hasattr(chunk, 'pages_included') and chunk.pages_included:
                        page_source = ','.join(chunk.pages_included[:5])  # Limitar a 5 URLs
                    
                    records.append((
                        cnpj_basico,
                        discovery_id,
                        website_url,
                        chunk.index,
                        chunk.total_chunks,
                        chunk.content,
                        chunk.tokens,
                        page_source
                    ))
                
                # Batch insert (muito mais eficiente) - SEMPRE com schema explícito
                query_chunks = f"""
                    INSERT INTO "{SCHEMA}".scraped_chunks 
                        (cnpj_basico, discovery_id, website_url, chunk_index, 
                         total_chunks, chunk_content, token_count, page_source)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """
                logger.info(f"🔍 [SCHEMA={SCHEMA}] Salvando {len(records)} chunks")
                await conn.executemany(
                    query_chunks,
                    records
                )
                
                logger.debug(f"✅ {len(records)} chunks salvos para cnpj={cnpj_basico}")
                return len(records)
    
    async def get_chunks(self, cnpj_basico: str) -> List[Dict[str, Any]]:
        """
        Busca todos os chunks para um CNPJ, ordenados por índice.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
        
        Returns:
            Lista de dicts com os dados dos chunks
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT * FROM "{SCHEMA}".scraped_chunks 
                WHERE cnpj_basico = $1 
                ORDER BY chunk_index ASC
                """
            logger.debug(f"🔍 [SCHEMA={SCHEMA}] SELECT scraped_chunks")
            rows = await conn.fetch(
                query,
                cnpj_basico
            )
            return [dict(row) for row in rows]
    
    # ========== COMPANY PROFILE ==========
    
    async def save_profile(
        self,
        cnpj_basico: str,
        profile: CompanyProfile,
        nome_empresa_override: Optional[str] = None,
    ) -> int:
        """
        Salva perfil completo da empresa no schema busca_fornecedor.
        Usa campos em português (identidade, classificacao, contato, fontes).
        Inclui salvamento nas tabelas auxiliares (locations, services, products, etc).

        Args:
            cnpj_basico: CNPJ básico da empresa
            profile: Objeto CompanyProfile (Pydantic)
            nome_empresa_override: Nome da empresa (opcional, extraído do profile se None)

        Returns:
            ID do registro criado ou atualizado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                logger.info(f"📊 Salvando perfil no schema: {SCHEMA}")
                ide = profile.identidade
                cla = profile.classificacao
                cont = profile.contato

                nome_empresa = nome_empresa_override or (ide.nome_empresa if ide else None) or ""
                cnpj = cnpj_basico
                descricao = (ide.descricao if ide else None) or None
                ano_fundacao = (ide.ano_fundacao if ide else None) or None
                faixa_funcionarios = (ide.faixa_funcionarios if ide else None) or None

                industria = (cla.industria if cla else None) or None
                modelo_negocio = (cla.modelo_negocio if cla else None) or None
                publico_alvo = (cla.publico_alvo if cla else None) or None
                cobertura_geografica = (cla.cobertura_geografica if cla else None) or None

                emails = list(cont.emails) if cont and cont.emails else []
                telefones = list(cont.telefones) if cont and cont.telefones else []
                url_linkedin = (cont.url_linkedin if cont else None) or None
                url_site = (cont.url_site if cont else None) or None
                endereco_matriz = (cont.endereco_matriz if cont else None) or None

                fontes = list(profile.fontes) if profile.fontes else []

                n_exibicoes = 0
                recebe_email = False

                profile_dict = profile.model_dump()
                profile_json = json.dumps(profile_dict, ensure_ascii=False)
                full_profile = json.dumps(profile_dict, ensure_ascii=False)

                query_check_profile = f'SELECT id FROM "{SCHEMA}".company_profile WHERE cnpj = $1'
                logger.info(f"🔍 [SCHEMA={SCHEMA}] Verificando profile existente")
                existing = await conn.fetchrow(query_check_profile, cnpj)

                if existing:
                    query_update = f"""
                        UPDATE "{SCHEMA}".company_profile
                        SET nome_empresa = $2, descricao = $3, ano_fundacao = $4, faixa_funcionarios = $5,
                            industria = $6, modelo_negocio = $7, publico_alvo = $8, cobertura_geografica = $9,
                            emails = $10, telefones = $11, url_linkedin = $12, url_site = $13,
                            endereco_matriz = $14, fontes = $15, n_exibicoes = $16, recebe_email = $17,
                            profile_json = $18::jsonb, full_profile = $19::jsonb, updated_at = NOW()
                        WHERE cnpj = $1
                        RETURNING id
                    """
                    logger.info(f"🔍 [SCHEMA={SCHEMA}] UPDATE company_profile")
                    row = await conn.fetchrow(
                        query_update,
                        cnpj,
                        nome_empresa,
                        descricao,
                        ano_fundacao,
                        faixa_funcionarios,
                        industria,
                        modelo_negocio,
                        publico_alvo,
                        cobertura_geografica,
                        emails,
                        telefones,
                        url_linkedin,
                        url_site,
                        endereco_matriz,
                        fontes,
                        n_exibicoes,
                        recebe_email,
                        profile_json,
                        full_profile,
                    )
                    company_id = row["id"]
                    logger.debug(f"✅ Profile atualizado: id={company_id}, cnpj={cnpj}")
                else:
                    query_insert_profile = f"""
                        INSERT INTO "{SCHEMA}".company_profile
                            (nome_empresa, cnpj, descricao, ano_fundacao, faixa_funcionarios,
                             industria, modelo_negocio, publico_alvo, cobertura_geografica,
                             emails, telefones, url_linkedin, url_site, endereco_matriz, fontes,
                             n_exibicoes, recebe_email, profile_json, full_profile)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18::jsonb, $19::jsonb)
                        RETURNING id
                    """
                    logger.info(f"🔍 [SCHEMA={SCHEMA}] INSERT company_profile")
                    row = await conn.fetchrow(
                        query_insert_profile,
                        nome_empresa,
                        cnpj,
                        descricao,
                        ano_fundacao,
                        faixa_funcionarios,
                        industria,
                        modelo_negocio,
                        publico_alvo,
                        cobertura_geografica,
                        emails,
                        telefones,
                        url_linkedin,
                        url_site,
                        endereco_matriz,
                        fontes,
                        n_exibicoes,
                        recebe_email,
                        profile_json,
                        full_profile,
                    )
                    company_id = row["id"]
                    logger.debug(f"✅ Profile criado: id={company_id}, cnpj={cnpj}")

                await self._save_profile_auxiliary_data(conn, company_id, profile)
                return company_id
    
    async def _save_profile_auxiliary_data(
        self,
        conn,
        company_id: int,
        profile: CompanyProfile
    ):
        """
        Salva dados nas tabelas auxiliares (locations, services, products, etc).
        Usa campos em português: contato.localizacoes, ofertas.servicos, ofertas.produtos,
        reputacao.certificacoes, premios, parcerias.
        """
        cont = profile.contato
        ofertas = profile.ofertas
        rep = profile.reputacao

        # 1. Localizações (contato.localizacoes -> company_location.localizacao)
        localizacoes = list(cont.localizacoes) if cont and cont.localizacoes else []
        if localizacoes:
            query_delete = f'DELETE FROM "{SCHEMA}".company_location WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for loc in localizacoes:
                if loc and isinstance(loc, str) and loc.strip():
                    q = f'INSERT INTO "{SCHEMA}".company_location (company_id, localizacao) VALUES ($1, $2)'
                    await conn.execute(q, company_id, loc.strip())

        # 2. Serviços (ofertas.servicos -> company_service.nome, descricao)
        servicos = list(ofertas.servicos) if ofertas and ofertas.servicos else []
        if servicos:
            query_delete = f'DELETE FROM "{SCHEMA}".company_service WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for s in servicos:
                nome = (s.nome if hasattr(s, "nome") else (s.get("nome") if isinstance(s, dict) else None)) or ""
                if not nome or not isinstance(nome, str) or not nome.strip():
                    continue
                descricao = (s.descricao if hasattr(s, "descricao") else (s.get("descricao") if isinstance(s, dict) else None)) or None
                q = f'INSERT INTO "{SCHEMA}".company_service (company_id, nome, descricao) VALUES ($1, $2, $3)'
                await conn.execute(q, company_id, nome.strip(), (descricao.strip() if descricao else None))

        # 3. Categorias de produtos (ofertas.produtos -> company_product_category.categoria, produtos)
        produtos_cats = list(ofertas.produtos) if ofertas and ofertas.produtos else []
        if produtos_cats:
            query_delete = f'DELETE FROM "{SCHEMA}".company_product_category WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for cat in produtos_cats:
                categoria = (cat.categoria if hasattr(cat, "categoria") else (cat.get("categoria") if isinstance(cat, dict) else None)) or ""
                if not categoria or not isinstance(categoria, str) or not categoria.strip():
                    continue
                prods = cat.produtos if hasattr(cat, "produtos") else (cat.get("produtos") if isinstance(cat, dict) else []) or []
                prods = [p for p in prods if isinstance(p, str) and p.strip()]
                prods_json = json.dumps(prods, ensure_ascii=False)
                q = f'INSERT INTO "{SCHEMA}".company_product_category (company_id, categoria, produtos) VALUES ($1, $2, $3::jsonb)'
                await conn.execute(q, company_id, categoria.strip(), prods_json)

        # 4. Certificações (reputacao.certificacoes)
        certs = list(rep.certificacoes) if rep and rep.certificacoes else []
        if certs:
            query_delete = f'DELETE FROM "{SCHEMA}".company_certification WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for c in certs:
                if c and isinstance(c, str) and c.strip():
                    q = f'INSERT INTO "{SCHEMA}".company_certification (company_id, nome) VALUES ($1, $2)'
                    await conn.execute(q, company_id, c.strip())

        # 5. Prêmios (reputacao.premios)
        premios = list(rep.premios) if rep and rep.premios else []
        if premios:
            query_delete = f'DELETE FROM "{SCHEMA}".company_award WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for p in premios:
                if p and isinstance(p, str) and p.strip():
                    q = f'INSERT INTO "{SCHEMA}".company_award (company_id, nome) VALUES ($1, $2)'
                    await conn.execute(q, company_id, p.strip())

        # 6. Parcerias (reputacao.parcerias)
        parcerias = list(rep.parcerias) if rep and rep.parcerias else []
        if parcerias:
            query_delete = f'DELETE FROM "{SCHEMA}".company_partnership WHERE company_id = $1'
            await conn.execute(query_delete, company_id)
            for p in parcerias:
                if p and isinstance(p, str) and p.strip():
                    q = f'INSERT INTO "{SCHEMA}".company_partnership (company_id, nome) VALUES ($1, $2)'
                    await conn.execute(q, company_id, p.strip())
    
    async def get_profile(self, cnpj_basico: str) -> Optional[Dict[str, Any]]:
        """
        Busca perfil completo da empresa.
        
        Args:
            cnpj_basico: CNPJ básico da empresa
        
        Returns:
            Dict com os dados do perfil ou None se não encontrado
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = f"""
                SELECT * FROM "{SCHEMA}".company_profile 
                WHERE cnpj = $1 OR cnpj LIKE $2
                ORDER BY updated_at DESC
                LIMIT 1
                """
            logger.debug(f"🔍 [SCHEMA={SCHEMA}] SELECT company_profile")
            row = await conn.fetchrow(
                query,
                cnpj_basico,
                f"{cnpj_basico}%"
            )
            if row:
                result = dict(row)
                # Parse JSONB se for string
                if isinstance(result.get('profile_json'), str):
                    result['profile_json'] = json.loads(result['profile_json'])
                return result
            return None


# Singleton
_db_service: Optional[DatabaseService] = None


def get_db_service() -> DatabaseService:
    """
    Retorna instância singleton do DatabaseService.
    
    Returns:
        DatabaseService: Instância do serviço de banco de dados
    """
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
