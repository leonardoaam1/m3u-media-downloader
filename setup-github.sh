#!/bin/bash

# Script para configurar o repositório Git e fazer o primeiro push para GitHub

set -e

echo "🚀 Configurando repositório Git para MediaDown..."

# Verificar se git está instalado
if ! command -v git &> /dev/null; then
    echo "❌ Git não está instalado. Por favor, instale o Git primeiro."
    exit 1
fi

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ] || [ ! -f "requirements.txt" ]; then
    echo "❌ Este script deve ser executado no diretório raiz do projeto MediaDown."
    exit 1
fi

# Inicializar repositório Git (se não existir)
if [ ! -d ".git" ]; then
    echo "📁 Inicializando repositório Git..."
    git init
fi

# Adicionar todos os arquivos
echo "📝 Adicionando arquivos ao Git..."
git add .

# Fazer o primeiro commit
echo "💾 Fazendo o primeiro commit..."
git commit -m "feat: initial commit - MediaDown M3U Download System

- Sistema completo de download de vídeos baseado em listas M3U
- Interface web com sistema de usuários e autenticação
- Integração com TMDB para metadados
- Suporte a múltiplos protocolos de transferência (SFTP, SMB, NFS, Rsync)
- Sistema de fila inteligente com Celery
- Logs detalhados e monitoramento
- Configuração para produção com Docker e CI/CD"

# Solicitar URL do repositório remoto
echo ""
echo "🔗 Por favor, forneça a URL do repositório GitHub criado:"
echo "   Exemplo: https://github.com/seu-usuario/m3u-media-downloader.git"
read -p "URL do repositório: " repo_url

# Adicionar remote e fazer push
if [ ! -z "$repo_url" ]; then
    echo "🌐 Adicionando remote origin..."
    git remote add origin "$repo_url"
    
    echo "📤 Fazendo push para GitHub..."
    git branch -M main
    git push -u origin main
    
    echo ""
    echo "✅ Repositório configurado com sucesso!"
    echo "🌍 Acesse: $repo_url"
    echo ""
    echo "📋 Próximos passos:"
    echo "   1. Configure as variáveis de ambiente no GitHub Secrets"
    echo "   2. Ative o GitHub Actions no repositório"
    echo "   3. Configure o domínio personalizado (se necessário)"
    echo "   4. Adicione colaboradores (se necessário)"
else
    echo "⚠️  URL não fornecida. Remote não foi adicionado."
    echo "   Você pode adicionar manualmente com:"
    echo "   git remote add origin <URL_DO_REPOSITORIO>"
    echo "   git push -u origin main"
fi

echo ""
echo "🎉 Setup concluído! O projeto MediaDown está pronto para uso."
