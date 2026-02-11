FROM python:3.11-slim

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

# Copiar requirements e instalar dependências em um único passo (menos camadas = menos risco de "context canceled").
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Instalar navegadores do Playwright (necessário para crawl4ai)
# Apenas chromium para economizar espaço/tempo. Build pode levar alguns minutos.
RUN playwright install --with-deps chromium

# Copiar o restante do código
COPY . .

# Criar diretório de resultados (embora o código crie, é bom garantir permissões)
RUN mkdir -p results && chmod 777 results

# Expor a porta (Railway injeta a porta na var $PORT)
EXPOSE 8000

# Script que sobe API + workers no mesmo container (já copiado em COPY . .)
RUN chmod +x /app/scripts/start_web_and_workers.sh

# Um único container: API + discovery_worker + profile_worker.
# Para rodar só a API (ex.: vários serviços no Railway), use Start Command:
#   hypercorn app.main:app --bind [::]:$PORT
CMD ["/app/scripts/start_web_and_workers.sh"]

