# Contribuindo para o MediaDown

Obrigado por considerar contribuir para o MediaDown! Este documento fornece diretrizes para contribuições.

## Como Contribuir

### 1. Fork e Clone

1. Faça um fork do repositório
2. Clone seu fork localmente:
   ```bash
   git clone https://github.com/seu-usuario/m3u-media-downloader.git
   cd m3u-media-downloader
   ```

### 2. Configurar Ambiente de Desenvolvimento

1. Crie um ambiente virtual:
   ```bash
   python3.12 -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate     # Windows
   ```

2. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # se existir
   ```

3. Configure as variáveis de ambiente:
   ```bash
   cp env.example .env
   # Edite o arquivo .env com suas configurações
   ```

### 3. Criar uma Branch

Crie uma branch para sua feature ou correção:
```bash
git checkout -b feature/nova-funcionalidade
# ou
git checkout -b fix/correcao-bug
```

### 4. Desenvolver

- Siga as convenções de código do projeto
- Adicione testes para novas funcionalidades
- Mantenha a documentação atualizada
- Use commits descritivos

### 5. Testar

Execute os testes antes de submeter:
```bash
# Testes unitários
python -m pytest tests/

# Verificação de estilo
flake8 app/ workers/

# Verificação de tipos (se configurado)
mypy app/ workers/
```

### 6. Commit e Push

```bash
git add .
git commit -m "feat: adiciona nova funcionalidade X"
git push origin feature/nova-funcionalidade
```

### 7. Pull Request

1. Vá para o repositório original no GitHub
2. Clique em "New Pull Request"
3. Selecione sua branch
4. Preencha o template do PR
5. Aguarde a revisão

## Convenções de Código

### Python

- Use Python 3.12+
- Siga PEP 8
- Use type hints quando possível
- Documente funções e classes
- Use docstrings para documentação

### Commits

Use o padrão Conventional Commits:
- `feat:` nova funcionalidade
- `fix:` correção de bug
- `docs:` documentação
- `style:` formatação
- `refactor:` refatoração
- `test:` testes
- `chore:` manutenção

### Estrutura de Arquivos

```
app/
├── models/          # Modelos do banco
├── routes/          # Rotas da aplicação
├── services/        # Lógica de negócio
├── templates/       # Templates HTML
└── static/          # Arquivos estáticos

workers/             # Workers Celery
tests/               # Testes
docs/                # Documentação
```

## Reportando Bugs

### Antes de Reportar

1. Verifique se o bug já foi reportado
2. Teste com a versão mais recente
3. Reproduza o bug em um ambiente limpo

### Template de Bug Report

```markdown
**Descrição do Bug**
Descrição clara e concisa do bug.

**Passos para Reproduzir**
1. Vá para '...'
2. Clique em '...'
3. Role até '...'
4. Veja o erro

**Comportamento Esperado**
O que deveria acontecer.

**Comportamento Atual**
O que realmente acontece.

**Screenshots**
Se aplicável, adicione screenshots.

**Ambiente**
- OS: [ex: Ubuntu 24.04]
- Python: [ex: 3.12.3]
- Versão: [ex: 1.0.0]

**Informações Adicionais**
Qualquer outra informação relevante.
```

## Sugerindo Funcionalidades

### Template de Feature Request

```markdown
**Problema**
Descrição clara do problema que a funcionalidade resolveria.

**Solução Proposta**
Descrição da solução desejada.

**Alternativas Consideradas**
Outras soluções que você considerou.

**Contexto Adicional**
Qualquer contexto adicional, screenshots, etc.
```

## Diretrizes de Revisão

### Para Revisores

- Seja construtivo e respeitoso
- Foque no código, não na pessoa
- Sugira melhorias específicas
- Teste as mudanças localmente

### Para Autores

- Responda a todos os comentários
- Faça as mudanças solicitadas
- Mantenha o histórico de commits limpo
- Seja paciente com o processo de revisão

## Licença

Ao contribuir, você concorda que suas contribuições serão licenciadas sob a mesma licença do projeto (MIT).

## Contato

Se você tiver dúvidas sobre como contribuir:

- Abra uma issue no GitHub
- Entre em contato via email: suporte@hubservices.host
- Consulte a documentação: https://docs.hubservices.host

---

Obrigado por contribuir para o MediaDown! 🚀
