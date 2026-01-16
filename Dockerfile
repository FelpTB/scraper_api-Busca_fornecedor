FROM python:3.11-slim

# Definir diretório de trabalho
WORKDIR /app

# Variáveis de ambiente para evitar arquivos .pyc e logs em buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema necessárias para build e playwright
# libpq-dev é necessário para compilar asyncpg (PostgreSQL driver)
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    musl-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
# Atualizar pip primeiro para garantir instalação correta
RUN pip install --upgrade pip setuptools wheel
# Instalar asyncpg explicitamente primeiro (requer libpq-dev que já instalamos)
RUN pip install --no-cache-dir asyncpg>=0.29.0
# Depois instalar todas as outras dependências
RUN pip install --no-cache-dir -r requirements.txt

# Instalar navegadores do Playwright (necessário para crawl4ai)
# Instalamos apenas o chromium para economizar espaço e tempo de build.
# Se precisar de outros, altere para "playwright install --with-deps"
RUN playwright install --with-deps chromium

# Copiar o restante do código
COPY . .

# Criar diretório de resultados (embora o código crie, é bom garantir permissões)
RUN mkdir -p results && chmod 777 results

# Expor a porta (Railway injeta a porta na var $PORT)
EXPOSE 8000

# Comando de inicialização usando a variável de ambiente PORT (padrão 8000 se não definida)
CMD sh -c "hypercorn app.main:app --bind [::]:${PORT:-8000}"

