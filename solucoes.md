# Soluções Implementadas

## Problema: Tabelas não encontradas no PostgreSQL (`relation does not exist`)

### Descrição do Problema

O sistema estava apresentando erros ao acessar tabelas no banco de dados PostgreSQL:

- **Erro 1**: `relation "scraped_chunks" does not exist` no endpoint `/v2/montagem_perfil`
- **Erro 2**: `relation "serper_results" does not exist` no endpoint `/v2/serper`

### Causa Raiz Identificada

O problema estava na configuração do `search_path` no `init_connection` do pool de conexões:

- O código estava usando aspas duplas no schema: `SET search_path TO "busca_fornecedor", public`
- O schema foi criado no PostgreSQL sem aspas: `CREATE SCHEMA busca_fornecedor`
- Isso causava inconsistência na resolução do schema pelo PostgreSQL
- As queries usavam schema explícito com aspas: `"{SCHEMA}".table_name`, mas o `search_path` não estava sendo configurado corretamente

### Solução Implementada

**Arquivo modificado**: `app/core/database.py`

**Mudanças**:
1. Removidas as aspas duplas do schema no `SET search_path`
   - **Antes**: `SET search_path TO "busca_fornecedor", public`
   - **Depois**: `SET search_path TO busca_fornecedor, public`

2. Adicionado tratamento de erro no `init_connection`
   - Se a configuração do `search_path` falhar, a conexão não será adicionada ao pool
   - Garante que apenas conexões válidas sejam reutilizadas

3. Melhorada documentação da função
   - Explicação clara do propósito e comportamento

### Impacto da Solução

- **Performance**: Zero impacto (configuração executada apenas na criação de novas conexões do pool)
- **Funcionalidade**: Resolve o problema de acesso às tabelas
- **Risco**: Baixo (correção pontual no código de inicialização)
- **Manutenibilidade**: Melhora com melhor documentação e tratamento de erros

### Observações

- As queries continuam usando schema explícito com aspas: `"{SCHEMA}".table_name` (mantém segurança)
- O `init_connection` é executado automaticamente pelo asyncpg apenas quando novas conexões são criadas no pool
- O pool tem configuração `min_size=5` e `max_size=20`, então a configuração do `search_path` acontece no máximo 20 vezes ao longo da vida da aplicação
- Não há overhead adicional em queries ou operações de banco de dados

### Data da Implementação

Janeiro 2026

