# 🚀 Configuração do Projeto no GitHub

Este guia irá ajudá-lo a configurar o projeto MediaDown no GitHub.

## 📋 Pré-requisitos

- Conta no GitHub
- Git instalado no seu computador
- Acesso ao terminal/PowerShell

## 🔧 Passo a Passo

### 1. Criar o Repositório no GitHub

1. Acesse [github.com](https://github.com) e faça login
2. Clique no botão **"+"** no canto superior direito
3. Selecione **"New repository"**
4. Configure o repositório:

   **Repository name**: `m3u-media-downloader` (ou `mediadown`)
   
   **Description**: `Sistema completo em Python para automação de downloads de vídeos, filmes e séries baseado em listas M3U, com interface web, sistema de usuários e logs detalhados.`
   
   **Visibility**: 
   - ✅ **Public** (recomendado para projetos open source)
   - ⚠️ **Private** (se você quiser manter privado)
   
   **⚠️ IMPORTANTE**: 
   - ❌ **NÃO** marque "Add a README file" (já temos um)
   - ❌ **NÃO** marque "Add .gitignore" (já criamos um personalizado)
   - ❌ **NÃO** marque "Choose a license" (já temos a MIT)

5. Clique em **"Create repository"**

### 2. Executar o Script de Configuração

#### No Windows (PowerShell):
```powershell
# Navegar para o diretório do projeto
cd C:\Projetos\mediadown

# Executar o script PowerShell
.\setup-github.ps1
```

#### No Linux/Mac:
```bash
# Navegar para o diretório do projeto
cd /caminho/para/mediadown

# Dar permissão de execução
chmod +x setup-github.sh

# Executar o script
./setup-github.sh
```

### 3. Configurar GitHub Actions

Após o push inicial, configure o GitHub Actions:

1. Vá para o repositório criado no GitHub
2. Clique na aba **"Actions"**
3. Clique em **"Enable Actions"** se solicitado
4. O workflow CI/CD será executado automaticamente

### 4. Configurar Secrets (Opcional)

Para usar o CI/CD completo, configure os secrets:

1. Vá para **Settings** → **Secrets and variables** → **Actions**
2. Clique em **"New repository secret"**
3. Adicione os seguintes secrets:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/test_db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=sua-chave-secreta-aqui
TMDB_API_KEY=sua-chave-tmdb-aqui
```

## 📁 Estrutura do Repositório

Após o setup, seu repositório terá:

```
m3u-media-downloader/
├── app/                    # Código da aplicação
├── workers/                # Workers Celery
├── .github/               # GitHub Actions
├── .gitignore            # Arquivos ignorados
├── LICENSE               # Licença MIT
├── README.md             # Documentação principal
├── CONTRIBUTING.md       # Guia de contribuição
├── requirements.txt      # Dependências Python
├── requirements-dev.txt  # Dependências de desenvolvimento
├── Dockerfile           # Containerização
├── docker-compose.yml   # Orquestração local
├── setup-github.ps1     # Script Windows
├── setup-github.sh      # Script Linux/Mac
└── GITHUB_SETUP.md      # Este arquivo
```

## 🔄 Próximos Passos

### Para Desenvolvimento Local:
```bash
# Clone o repositório
git clone https://github.com/seu-usuario/m3u-media-downloader.git
cd m3u-media-downloader

# Configurar ambiente
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Configurar variáveis de ambiente
cp env.example .env
# Editar .env com suas configurações
```

### Para Produção com Docker:
```bash
# Usar Docker Compose
docker-compose up -d

# Ou construir manualmente
docker build -t mediadown .
docker run -p 5000:5000 mediadown
```

## 🛠️ Funcionalidades Configuradas

### ✅ CI/CD Pipeline
- Testes automatizados
- Verificação de qualidade de código
- Análise de segurança
- Build de Docker
- Deploy automático (configurável)

### ✅ Containerização
- Dockerfile otimizado
- Docker Compose para desenvolvimento
- Multi-stage builds
- Health checks

### ✅ Qualidade de Código
- Linting com flake8
- Formatação com black
- Verificação de tipos com mypy
- Testes com pytest
- Análise de segurança com bandit

### ✅ Documentação
- README completo
- Guia de contribuição
- Documentação técnica
- Templates para issues e PRs

## 🎯 Benefícios

1. **Visibilidade**: Projeto público no GitHub
2. **Colaboração**: Fácil para outros contribuírem
3. **CI/CD**: Deploy automatizado
4. **Qualidade**: Padrões de código mantidos
5. **Documentação**: Bem documentado
6. **Containerização**: Fácil deploy

## 🆘 Suporte

Se encontrar problemas:

1. Verifique se o Git está instalado: `git --version`
2. Verifique se está no diretório correto
3. Verifique se a URL do repositório está correta
4. Consulte a documentação do projeto
5. Abra uma issue no GitHub

---

**🎉 Parabéns! Seu projeto MediaDown está agora no GitHub e pronto para uso!**
