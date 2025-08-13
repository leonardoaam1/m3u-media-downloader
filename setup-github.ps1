# Script PowerShell para configurar o repositório Git para MediaDown

Write-Host "🚀 Configurando repositório Git para MediaDown..." -ForegroundColor Green

# Verificar se git está instalado
try {
    git --version | Out-Null
} catch {
    Write-Host "❌ Git não está instalado. Por favor, instale o Git primeiro." -ForegroundColor Red
    exit 1
}

# Verificar se estamos no diretório correto
if (-not (Test-Path "app.py") -or -not (Test-Path "requirements.txt")) {
    Write-Host "❌ Este script deve ser executado no diretório raiz do projeto MediaDown." -ForegroundColor Red
    exit 1
}

# Inicializar repositório Git (se não existir)
if (-not (Test-Path ".git")) {
    Write-Host "📁 Inicializando repositório Git..." -ForegroundColor Yellow
    git init
}

# Adicionar todos os arquivos
Write-Host "📝 Adicionando arquivos ao Git..." -ForegroundColor Yellow
git add .

# Fazer o primeiro commit
Write-Host "💾 Fazendo o primeiro commit..." -ForegroundColor Yellow
$commitMessage = @"
feat: initial commit - MediaDown M3U Download System

- Sistema completo de download de vídeos baseado em listas M3U
- Interface web com sistema de usuários e autenticação
- Integração com TMDB para metadados
- Suporte a múltiplos protocolos de transferência (SFTP, SMB, NFS, Rsync)
- Sistema de fila inteligente com Celery
- Logs detalhados e monitoramento
- Configuração para produção com Docker e CI/CD
"@

git commit -m $commitMessage

# Solicitar URL do repositório remoto
Write-Host ""
Write-Host "🔗 Por favor, forneça a URL do repositório GitHub criado:" -ForegroundColor Cyan
Write-Host "   Exemplo: https://github.com/seu-usuario/m3u-media-downloader.git" -ForegroundColor Gray
$repoUrl = Read-Host "URL do repositório"

# Adicionar remote e fazer push
if ($repoUrl) {
    Write-Host "🌐 Adicionando remote origin..." -ForegroundColor Yellow
    git remote add origin $repoUrl
    
    Write-Host "📤 Fazendo push para GitHub..." -ForegroundColor Yellow
    git branch -M main
    git push -u origin main
    
    Write-Host ""
    Write-Host "✅ Repositório configurado com sucesso!" -ForegroundColor Green
    Write-Host "🌍 Acesse: $repoUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📋 Próximos passos:" -ForegroundColor Yellow
    Write-Host "   1. Configure as variáveis de ambiente no GitHub Secrets" -ForegroundColor White
    Write-Host "   2. Ative o GitHub Actions no repositório" -ForegroundColor White
    Write-Host "   3. Configure o domínio personalizado (se necessário)" -ForegroundColor White
    Write-Host "   4. Adicione colaboradores (se necessário)" -ForegroundColor White
} else {
    Write-Host "⚠️  URL não fornecida. Remote não foi adicionado." -ForegroundColor Yellow
    Write-Host "   Você pode adicionar manualmente com:" -ForegroundColor Gray
    Write-Host "   git remote add origin <URL_DO_REPOSITORIO>" -ForegroundColor Gray
    Write-Host "   git push -u origin main" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🎉 Setup concluído! O projeto MediaDown está pronto para uso." -ForegroundColor Green
