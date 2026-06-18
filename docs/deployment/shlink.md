# Shlink no OwnPaper

O OwnPaper já integra a API do Shlink para gerar links curtos de:

- compartilhamento de publicações
- links usados em e-mails

O comportamento do site continua seguro sem Shlink:

- se a integração estiver desligada ou falhar, o site usa a URL longa
- os botões continuam funcionando

## Modos suportados

### 1. Serviço opcional empacotado

O `docker-compose.yml` do projeto agora inclui um perfil opcional:

```bash
docker compose --profile shlink up -d
```

Esse perfil sobe:

- `shlink`
- `shlink-db`

O serviço é opcional:

- o `web` não depende dele para iniciar
- você ativa só nas instalações que desejarem links curtos

### 2. Instância externa

Se a instalação já tiver uma instância própria do Shlink, basta apontar o OwnPaper para ela:

- `OWNPAPER_SHLINK_BASE_URL`
- `OWNPAPER_SHLINK_API_KEY`

## Variáveis de ambiente

### OwnPaper

```env
OWNPAPER_SHLINK_BASE_URL=http://shlink:8080/go
OWNPAPER_SHLINK_API_KEY=uma-chave-forte
```

Use `http://shlink:8080/go` quando o OwnPaper e o Shlink estiverem na mesma stack Docker do projeto e a instalação estiver expondo o encurtador em `/go/`.

### Serviço opcional empacotado

```env
SHLINK_HTTP_PORT=18081
SHLINK_DEFAULT_DOMAIN=teste.exemplo.com.br
SHLINK_BASE_PATH=/go
SHLINK_IS_HTTPS_ENABLED=true
SHLINK_GEOLITE_LICENSE_KEY=
SHLINK_SKIP_INITIAL_GEOLITE_DOWNLOAD=true
SHLINK_INITIAL_API_KEY=uma-chave-forte
SHLINK_DB_NAME=shlink
SHLINK_DB_USER=shlink
SHLINK_DB_PASSWORD=troque-esta-senha
```

## Primeira chave de API

O projeto suporta dois caminhos.

### Caminho recomendado para instalações novas

Defina a chave inicial diretamente no `.env`:

```env
SHLINK_INITIAL_API_KEY=uma-chave-forte
OWNPAPER_SHLINK_API_KEY=uma-chave-forte
```

Isso evita depender de um passo manual depois do bootstrap.

### Caminho alternativo

Se preferir gerar a chave depois que o serviço subir:

```bash
docker compose --profile shlink exec shlink shlink api-key:generate
```

Depois, copie a chave gerada para:

```env
OWNPAPER_SHLINK_API_KEY=chave-gerada
```

## Domínio curto e HTTPS

O Shlink precisa de um domínio curto público real.

Exemplos:

- subdomínio dedicado: `s.exemplo.com.br`
- mesmo domínio com base path: `teste.exemplo.com.br/go/`

Em ambos os casos, o proxy reverso precisa apontar para o serviço Shlink.  
Definir `SHLINK_DEFAULT_DOMAIN` ou `SHLINK_BASE_PATH` sozinho não publica a rota nem cria HTTPS automaticamente.

Você precisa:

1. definir o domínio público do encurtador
2. opcionalmente definir um `base path`
3. apontar o proxy reverso para o container `shlink`
4. garantir HTTPS no domínio público final

## Ativação no painel

Depois de configurar o ambiente:

1. abrir `Configuração do site`
2. ativar `Ativar encurtamento com Shlink`
3. opcionalmente preencher `Domínio padrão do Shlink`

As credenciais não devem ser colocadas no painel.

## Comportamento esperado

Com Shlink ativo e configurado:

- o OwnPaper cria ou reaproveita links curtos
- armazena os links em `LinkCurtoShlink`
- usa os links curtos nos botões de compartilhamento

Sem Shlink:

- `share_urls` cai para a URL longa
- a publicação e os compartilhamentos continuam funcionando

## Verificação rápida

1. subir a stack com perfil:

```bash
docker compose --profile shlink up -d
```

2. validar o Django:

```bash
docker compose exec web python manage.py check
```

3. abrir uma publicação pública

4. confirmar no admin:

- `Links curtos do Shlink`

5. se necessário, confirmar geração manual por shell:

```bash
docker compose exec web python manage.py shell
```

e chamar o serviço de encurtamento para uma publicação de teste.
