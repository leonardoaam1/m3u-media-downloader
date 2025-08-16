from flask import Blueprint, render_template, jsonify, current_app, url_for
from flask_login import login_required, current_user
import json
import inspect
from datetime import datetime

docs_bp = Blueprint('docs', __name__, url_prefix='/docs')

def generate_openapi_spec():
    """Generate OpenAPI 3.0 specification for the API"""
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "MediaDown API",
            "description": "API completa para gerenciamento de downloads de mídia a partir de listas M3U",
            "version": "2.0.0",
            "contact": {
                "name": "MediaDown Support",
                "email": "support@mediadown.com"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": "/api/v1",
                "description": "API v1 - Produção"
            }
        ],
        "security": [
            {
                "ApiKeyAuth": []
            }
        ],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API Key para autenticação"
                },
                "WebhookSignature": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-Webhook-Signature",
                    "description": "Assinatura HMAC SHA256 para webhooks"
                }
            },
            "schemas": {
                "Download": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "ID único do download"},
                        "title": {"type": "string", "description": "Título do conteúdo"},
                        "content_type": {"type": "string", "enum": ["movie", "series", "novela"], "description": "Tipo de conteúdo"},
                        "quality": {"type": "string", "enum": ["480p", "720p", "1080p"], "description": "Qualidade do vídeo"},
                        "status": {"type": "string", "enum": ["pending", "downloading", "transferring", "completed", "failed", "paused", "cancelled"], "description": "Status atual"},
                        "progress_percentage": {"type": "number", "minimum": 0, "maximum": 100, "description": "Progresso em porcentagem"},
                        "url": {"type": "string", "format": "uri", "description": "URL de origem do conteúdo"},
                        "server": {"$ref": "#/components/schemas/ServerRef"},
                        "destination_path": {"type": "string", "description": "Caminho de destino no servidor"},
                        "file_size": {"type": "integer", "description": "Tamanho do arquivo em bytes"},
                        "download_speed": {"type": "string", "description": "Velocidade de download"},
                        "estimated_time": {"type": "string", "description": "Tempo estimado restante"},
                        "created_at": {"type": "string", "format": "date-time"},
                        "started_at": {"type": "string", "format": "date-time"},
                        "completed_at": {"type": "string", "format": "date-time"},
                        "tmdb_id": {"type": "integer", "description": "ID do TMDB"},
                        "season": {"type": "integer", "description": "Temporada (para séries)"},
                        "episode": {"type": "integer", "description": "Episódio (para séries)"}
                    }
                },
                "Server": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer", "description": "ID único do servidor"},
                        "name": {"type": "string", "description": "Nome do servidor"},
                        "description": {"type": "string", "description": "Descrição do servidor"},
                        "host": {"type": "string", "description": "Endereço IP ou hostname"},
                        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                        "protocol": {"type": "string", "enum": ["sftp", "nfs", "smb", "rsync"]},
                        "base_path": {"type": "string", "description": "Caminho base no servidor"},
                        "status": {"type": "string", "enum": ["online", "offline", "maintenance"]},
                        "content_types": {"type": "array", "items": {"type": "string", "enum": ["movie", "series", "novela"]}},
                        "disk_usage": {"$ref": "#/components/schemas/DiskUsage"},
                        "last_check": {"type": "string", "format": "date-time"},
                        "created_at": {"type": "string", "format": "date-time"}
                    }
                },
                "ServerRef": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "host": {"type": "string"},
                        "protocol": {"type": "string"}
                    }
                },
                "DiskUsage": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "string", "description": "Espaço total (ex: 1TB)"},
                        "used": {"type": "string", "description": "Espaço usado (ex: 500GB)"},
                        "available": {"type": "string", "description": "Espaço disponível (ex: 500GB)"},
                        "percentage": {"type": "number", "minimum": 0, "maximum": 100}
                    }
                },
                "CreateDownload": {
                    "type": "object",
                    "required": ["title", "url", "content_type", "quality"],
                    "properties": {
                        "title": {"type": "string", "description": "Título do conteúdo"},
                        "url": {"type": "string", "format": "uri", "description": "URL de origem"},
                        "content_type": {"type": "string", "enum": ["movie", "series", "novela"]},
                        "quality": {"type": "string", "enum": ["480p", "720p", "1080p"]},
                        "server_id": {"type": "integer", "description": "ID do servidor (opcional)"},
                        "destination_path": {"type": "string", "description": "Caminho de destino (opcional)"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
                        "season": {"type": "integer", "description": "Temporada (para séries)"},
                        "episode": {"type": "integer", "description": "Episódio (para séries)"},
                        "episode_title": {"type": "string", "description": "Título do episódio"},
                        "year": {"type": "integer", "description": "Ano de lançamento"},
                        "tmdb_id": {"type": "integer", "description": "ID do TMDB"}
                    }
                },
                "ControlDownload": {
                    "type": "object",
                    "required": ["action"],
                    "properties": {
                        "action": {"type": "string", "enum": ["pause", "resume", "cancel", "retry"]}
                    }
                },
                "SystemStatus": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "enum": ["healthy", "degraded", "down"]},
                        "timestamp": {"type": "string", "format": "date-time"},
                        "version": {"type": "string"},
                        "stats": {
                            "type": "object",
                            "properties": {
                                "downloads": {
                                    "type": "object",
                                    "properties": {
                                        "total": {"type": "integer"},
                                        "active": {"type": "integer"},
                                        "completed": {"type": "integer"},
                                        "failed": {"type": "integer"}
                                    }
                                },
                                "servers": {
                                    "type": "object",
                                    "properties": {
                                        "total": {"type": "integer"},
                                        "online": {"type": "integer"},
                                        "offline": {"type": "integer"}
                                    }
                                },
                                "users": {
                                    "type": "object",
                                    "properties": {
                                        "total": {"type": "integer"},
                                        "active": {"type": "integer"}
                                    }
                                }
                            }
                        }
                    }
                },
                "M3UParseRequest": {
                    "type": "object",
                    "required": ["content"],
                    "properties": {
                        "content": {"type": "string", "description": "Conteúdo do arquivo M3U"}
                    }
                },
                "Error": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string", "description": "Mensagem de erro"},
                        "code": {"type": "string", "description": "Código do erro"},
                        "details": {"type": "object", "description": "Detalhes adicionais do erro"}
                    }
                },
                "Pagination": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "minimum": 1},
                        "per_page": {"type": "integer", "minimum": 1, "maximum": 100},
                        "total": {"type": "integer"},
                        "pages": {"type": "integer"},
                        "has_prev": {"type": "boolean"},
                        "has_next": {"type": "boolean"}
                    }
                }
            },
            "responses": {
                "400": {
                    "description": "Requisição inválida",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "401": {
                    "description": "Não autorizado - API key necessária",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "403": {
                    "description": "Proibido - API key inválida",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "404": {
                    "description": "Recurso não encontrado",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "429": {
                    "description": "Muitas requisições - rate limit excedido",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                },
                "500": {
                    "description": "Erro interno do servidor",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Error"}
                        }
                    }
                }
            }
        },
        "paths": {
            "/status": {
                "get": {
                    "summary": "Status do Sistema",
                    "description": "Retorna o status geral do sistema e estatísticas básicas",
                    "tags": ["Sistema"],
                    "responses": {
                        "200": {
                            "description": "Status do sistema",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/SystemStatus"}
                                }
                            }
                        },
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/downloads": {
                "get": {
                    "summary": "Listar Downloads",
                    "description": "Lista downloads com filtros e paginação",
                    "tags": ["Downloads"],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "description": "Número da página",
                            "schema": {"type": "integer", "minimum": 1, "default": 1}
                        },
                        {
                            "name": "per_page",
                            "in": "query",
                            "description": "Itens por página",
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "description": "Filtrar por status",
                            "schema": {"type": "string", "enum": ["pending", "downloading", "transferring", "completed", "failed", "paused", "cancelled"]}
                        },
                        {
                            "name": "content_type",
                            "in": "query",
                            "description": "Filtrar por tipo de conteúdo",
                            "schema": {"type": "string", "enum": ["movie", "series", "novela"]}
                        },
                        {
                            "name": "server_id",
                            "in": "query",
                            "description": "Filtrar por servidor",
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Lista de downloads",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "downloads": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Download"}
                                            },
                                            "pagination": {"$ref": "#/components/schemas/Pagination"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/400"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                },
                "post": {
                    "summary": "Criar Download",
                    "description": "Cria um novo download na fila",
                    "tags": ["Downloads"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/CreateDownload"}
                            }
                        }
                    },
                    "responses": {
                        "201": {
                            "description": "Download criado com sucesso",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "message": {"type": "string"},
                                            "status": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/400"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/downloads/{download_id}": {
                "get": {
                    "summary": "Detalhes do Download",
                    "description": "Retorna informações detalhadas de um download específico",
                    "tags": ["Downloads"],
                    "parameters": [
                        {
                            "name": "download_id",
                            "in": "path",
                            "required": True,
                            "description": "ID do download",
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Detalhes do download",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Download"}
                                }
                            }
                        },
                        "404": {"$ref": "#/components/responses/404"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/downloads/{download_id}/control": {
                "post": {
                    "summary": "Controlar Download",
                    "description": "Executa ações de controle no download (pausar, resumir, cancelar, retry)",
                    "tags": ["Downloads"],
                    "parameters": [
                        {
                            "name": "download_id",
                            "in": "path",
                            "required": True,
                            "description": "ID do download",
                            "schema": {"type": "integer"}
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ControlDownload"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Ação executada com sucesso",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "message": {"type": "string"},
                                            "status": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/400"},
                        "404": {"$ref": "#/components/responses/404"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/servers": {
                "get": {
                    "summary": "Listar Servidores",
                    "description": "Lista todos os servidores configurados",
                    "tags": ["Servidores"],
                    "responses": {
                        "200": {
                            "description": "Lista de servidores",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "servers": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Server"}
                                            }
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/servers/{server_id}/test": {
                "get": {
                    "summary": "Testar Servidor",
                    "description": "Testa a conectividade com um servidor específico",
                    "tags": ["Servidores"],
                    "parameters": [
                        {
                            "name": "server_id",
                            "in": "path",
                            "required": True,
                            "description": "ID do servidor",
                            "schema": {"type": "integer"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Resultado do teste",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "server_id": {"type": "integer"},
                                            "connected": {"type": "boolean"},
                                            "status": {"type": "string"},
                                            "tested_at": {"type": "string", "format": "date-time"}
                                        }
                                    }
                                }
                            }
                        },
                        "404": {"$ref": "#/components/responses/404"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/m3u/parse": {
                "post": {
                    "summary": "Parse M3U",
                    "description": "Faz parse de conteúdo M3U e retorna dados estruturados",
                    "tags": ["M3U"],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/M3UParseRequest"}
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Dados do M3U parseados",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "total_items": {"type": "integer"},
                                            "filtered_items": {"type": "integer"},
                                            "accepted_qualities": {"type": "array", "items": {"type": "string"}},
                                            "items": {"type": "array", "items": {"type": "object"}}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/400"},
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/search": {
                "get": {
                    "summary": "Pesquisar Conteúdo",
                    "description": "Pesquisa conteúdo na biblioteca",
                    "tags": ["Pesquisa"],
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "description": "Termo de pesquisa",
                            "schema": {"type": "string"}
                        },
                        {
                            "name": "content_type",
                            "in": "query",
                            "description": "Filtrar por tipo",
                            "schema": {"type": "string", "enum": ["movie", "series", "novela"]}
                        },
                        {
                            "name": "server_id",
                            "in": "query",
                            "description": "Filtrar por servidor",
                            "schema": {"type": "integer"}
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "Limite de resultados",
                            "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Resultados da pesquisa",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {"type": "string"},
                                            "total_results": {"type": "integer"},
                                            "results": {"type": "array", "items": {"type": "object"}}
                                        }
                                    }
                                }
                            }
                        },
                        "401": {"$ref": "#/components/responses/401"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            },
            "/webhooks/download/progress": {
                "post": {
                    "summary": "Webhook de Progresso",
                    "description": "Recebe atualizações de progresso de sistemas externos",
                    "tags": ["Webhooks"],
                    "security": [{"WebhookSignature": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["download_id"],
                                    "properties": {
                                        "download_id": {"type": "integer"},
                                        "progress": {"type": "number", "minimum": 0, "maximum": 100},
                                        "speed": {"type": "string"},
                                        "eta": {"type": "string"}
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "200": {
                            "description": "Progresso atualizado",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "message": {"type": "string"}
                                        }
                                    }
                                }
                            }
                        },
                        "400": {"$ref": "#/components/responses/400"},
                        "401": {"$ref": "#/components/responses/401"},
                        "404": {"$ref": "#/components/responses/404"},
                        "500": {"$ref": "#/components/responses/500"}
                    }
                }
            }
        },
        "tags": [
            {
                "name": "Sistema",
                "description": "Operações relacionadas ao status e saúde do sistema"
            },
            {
                "name": "Downloads",
                "description": "Gerenciamento de downloads de mídia"
            },
            {
                "name": "Servidores",
                "description": "Gerenciamento de servidores de destino"
            },
            {
                "name": "M3U",
                "description": "Processamento de listas M3U"
            },
            {
                "name": "Pesquisa",
                "description": "Pesquisa de conteúdo na biblioteca"
            },
            {
                "name": "Webhooks",
                "description": "Endpoints para receber notificações externas"
            }
        ]
    }
    
    return spec

@docs_bp.route('/')
@login_required
def api_docs():
    """API Documentation homepage"""
    if not current_user.has_permission('view_api_docs'):
        return redirect(url_for('main.dashboard'))
    
    return render_template('docs/api.html')

@docs_bp.route('/openapi.json')
def openapi_spec():
    """Return OpenAPI specification in JSON format"""
    return jsonify(generate_openapi_spec())

@docs_bp.route('/redoc')
@login_required
def redoc():
    """ReDoc API documentation"""
    if not current_user.has_permission('view_api_docs'):
        return redirect(url_for('main.dashboard'))
    
    return render_template('docs/redoc.html')

@docs_bp.route('/swagger')
@login_required
def swagger():
    """Swagger UI API documentation"""
    if not current_user.has_permission('view_api_docs'):
        return redirect(url_for('main.dashboard'))
    
    return render_template('docs/swagger.html')

@docs_bp.route('/examples')
@login_required
def api_examples():
    """API usage examples"""
    if not current_user.has_permission('view_api_docs'):
        return redirect(url_for('main.dashboard'))
    
    examples = {
        "authentication": {
            "title": "Autenticação",
            "description": "Como autenticar com a API usando API Key",
            "examples": [
                {
                    "language": "curl",
                    "code": """curl -H "X-API-Key: sua-api-key-aqui" \\
     https://seu-dominio.com/api/v1/status"""
                },
                {
                    "language": "python",
                    "code": """import requests

headers = {
    'X-API-Key': 'sua-api-key-aqui',
    'Content-Type': 'application/json'
}

response = requests.get('https://seu-dominio.com/api/v1/status', headers=headers)
print(response.json())"""
                },
                {
                    "language": "javascript",
                    "code": """fetch('https://seu-dominio.com/api/v1/status', {
    headers: {
        'X-API-Key': 'sua-api-key-aqui',
        'Content-Type': 'application/json'
    }
})
.then(response => response.json())
.then(data => console.log(data));"""
                }
            ]
        },
        "create_download": {
            "title": "Criar Download",
            "description": "Como criar um novo download via API",
            "examples": [
                {
                    "language": "curl",
                    "code": """curl -X POST https://seu-dominio.com/api/v1/downloads \\
     -H "X-API-Key: sua-api-key-aqui" \\
     -H "Content-Type: application/json" \\
     -d '{
       "title": "Filme Exemplo (2024)",
       "url": "https://exemplo.com/video.m3u8",
       "content_type": "movie",
       "quality": "1080p",
       "year": 2024
     }'"""
                },
                {
                    "language": "python",
                    "code": """import requests

url = 'https://seu-dominio.com/api/v1/downloads'
headers = {
    'X-API-Key': 'sua-api-key-aqui',
    'Content-Type': 'application/json'
}

data = {
    'title': 'Filme Exemplo (2024)',
    'url': 'https://exemplo.com/video.m3u8',
    'content_type': 'movie',
    'quality': '1080p',
    'year': 2024
}

response = requests.post(url, headers=headers, json=data)
print(response.json())"""
                }
            ]
        },
        "list_downloads": {
            "title": "Listar Downloads",
            "description": "Como listar downloads com filtros",
            "examples": [
                {
                    "language": "curl",
                    "code": """# Listar todos os downloads
curl -H "X-API-Key: sua-api-key-aqui" \\
     "https://seu-dominio.com/api/v1/downloads"

# Listar apenas filmes completados
curl -H "X-API-Key: sua-api-key-aqui" \\
     "https://seu-dominio.com/api/v1/downloads?content_type=movie&status=completed"

# Paginação
curl -H "X-API-Key: sua-api-key-aqui" \\
     "https://seu-dominio.com/api/v1/downloads?page=2&per_page=50" """
                }
            ]
        },
        "control_download": {
            "title": "Controlar Downloads",
            "description": "Como pausar, resumir ou cancelar downloads",
            "examples": [
                {
                    "language": "curl",
                    "code": """# Pausar download
curl -X POST https://seu-dominio.com/api/v1/downloads/123/control \\
     -H "X-API-Key: sua-api-key-aqui" \\
     -H "Content-Type: application/json" \\
     -d '{"action": "pause"}'

# Resumir download
curl -X POST https://seu-dominio.com/api/v1/downloads/123/control \\
     -H "X-API-Key: sua-api-key-aqui" \\
     -H "Content-Type: application/json" \\
     -d '{"action": "resume"}'"""
                }
            ]
        },
        "webhooks": {
            "title": "Webhooks",
            "description": "Como implementar webhooks para receber notificações",
            "examples": [
                {
                    "language": "python",
                    "code": """import hmac
import hashlib
from flask import Flask, request

app = Flask(__name__)
WEBHOOK_SECRET = 'seu-webhook-secret'

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    # Verificar assinatura
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data()
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    if signature != f'sha256={expected_signature}':
        return 'Unauthorized', 401
    
    # Processar dados
    data = request.get_json()
    print(f"Download {data['download_id']} progress: {data['progress']}%")
    
    return 'OK'"""
                }
            ]
        }
    }
    
    return render_template('docs/examples.html', examples=examples)

@docs_bp.route('/sdk')
@login_required
def sdk_docs():
    """SDK documentation and downloads"""
    if not current_user.has_permission('view_api_docs'):
        return redirect(url_for('main.dashboard'))
    
    sdks = {
        "python": {
            "name": "Python SDK",
            "description": "SDK oficial para Python 3.8+",
            "version": "1.0.0",
            "install": "pip install mediadown-sdk",
            "github": "https://github.com/mediadown/python-sdk",
            "docs": "/docs/sdk/python"
        },
        "javascript": {
            "name": "JavaScript SDK",
            "description": "SDK para Node.js e navegadores",
            "version": "1.0.0",
            "install": "npm install mediadown-sdk",
            "github": "https://github.com/mediadown/js-sdk",
            "docs": "/docs/sdk/javascript"
        },
        "go": {
            "name": "Go SDK",
            "description": "SDK para aplicações Go",
            "version": "1.0.0",
            "install": "go get github.com/mediadown/go-sdk",
            "github": "https://github.com/mediadown/go-sdk",
            "docs": "/docs/sdk/go"
        }
    }
    
    return render_template('docs/sdk.html', sdks=sdks)
