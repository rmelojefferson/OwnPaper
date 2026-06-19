---
name: ownpaper-standard-implantação
description: Padrão obrigatório de trabalho no OwnPaper para mudanças em páginas públicas, admin, modelos, CSS, JS, runtime, Docker e implantação. Substitui processos anteriores e deve ser usado como fluxo de trabalho padrão do projeto daqui para frente.
---

# Padrão de implantação do OwnPaper

Esta é a skill padrão do projeto.

Use este processo sempre que o trabalho tocar:

- páginas públicas
- admin
- modelos
- CSS
- JS
- comportamento de runtime
- Docker, estáticos, manifests ou implantação

Esta skill substitui os fluxos anteriores de conflito e debug cirúrgico.

## Regra central

Não iterar no escuro.

Antes de editar:

1. confirmar o sintoma exato
2. mapear a trilha ativa real
3. identificar competição local ou transversal
4. aplicar o menor ajuste coerente possível
5. validar localmente
6. sincronizar só o que mudou
7. validar o runtime real

## Como trabalhar neste projeto

Trabalhe sempre por bloco fechado.

Exemplos:

- só popup de login
- só quiz
- só imagem e legenda
- só comentários
- só página de publicação

Não misture correções de blocos diferentes na mesma rodada, a menos que a causa seja comprovadamente transversal.

## Mapeamento obrigatório antes de editar

Sempre verificar:

- template ativo
- CSS ativo
- JS ativo
- includes usados pela página
- regras globais do tema
- listeners duplicados
- manifest estático
- hash servido no HTML
- processo ou serviço que precisa reload

## Como classificar o problema

### Local

É local quando a competição está no mesmo bloco, mesma página ou mesma recurso.

Nesses casos:

- corrija direto
- mantenha a mudança pequena
- remova sobreposição morta no mesmo ponto

### Transversal

É transversal quando a origem vem de:

- tema global
- componente compartilhado
- hook compartilhado
- comportamento de compilação ou Docker
- regras que podem afetar outras páginas

Nesses casos:

- explicite o risco
- amplie o escopo só se necessário

## Regras específicas do OwnPaper

### 1. Runtime e container

Neste projeto, editar o source não basta.

Quando o arquivo ativo estiver dentro do container, o fluxo padrão é:

1. editar localmente
2. sincronizar no `web` todos os arquivos tocados
3. se houver dúvida sobre divergência entre workspace e container, sincronizar o bloco inteiro relevante do projeto
4. regenerar estáticos se houver CSS/JS/imagem estática
5. rodar `manage.py check`
6. reiniciar o `web` se houver:
   - template
   - manifest stale
   - cache de processo
7. validar a URL pública real

### 1.1 Regra rígida de limpeza e implantação

Quando o usuário pedir:

- limpar
- reverter
- restaurar
- rebuildar
- não deixar nada antigo

isso significa limpar a trilha inteira, não só o repositório local.

Checklist obrigatório:

1. área de trabalho local no estado correto
2. source equivalente dentro do container no estado correto
3. `collectstatic --clear --noinput` executado quando houver estáticos
4. `web` reiniciado quando houver template, manifest, JS, CSS ou dúvida de cache
5. runtime validado por rota real

Não encerrar dizendo que limpou, reverteu ou restaurou antes de fechar os 5 itens.

### 1.2 Regra de sync no container

Não copiar um diretório de topo para um destino existente com o mesmo nome.

Exemplos proibidos:
- `docker compose cp config web:/app/config`
- `docker compose cp conteudo web:/app/conteudo`
- `docker compose cp home web:/app/home`

Esse padrão aninha o source dentro do destino e cria resíduos como:
- `/app/config/config`
- `/app/conteudo/conteudo`
- `/app/home/home`

Esses resíduos contaminam:
- imports Python
- modelos
- `collectstatic`
- runtime servido

Fluxo correto:
1. preferir copiar os arquivos tocados individualmente para o caminho final
2. se precisar copiar um bloco, copiar o conteúdo do diretório, nunca o diretório de topo para ele mesmo
3. após qualquer sync amplo, verificar explicitamente se não surgiram diretórios aninhados antes de validar a entrega

### 2. Estáticos

Se a mudança não aparecer:

Não assuma que o código está errado.

Verifique, nesta ordem:

1. o arquivo correto foi sincronizado?
2. o `collectstatic` foi refeito?
3. o hash novo está no `staticfiles.json`?
4. o HTML servido aponta para o hash novo?
5. o processo `web` ainda está com cache antigo?

### 3. CSS

Evite:

- seletor amplo demais
- regra compartilhada entre blocos diferentes
- empilhar ajuste novo sobre ajuste antigo
- corrigir via cascata sem remover a base conflituosa

Prefira:

- bloco com responsabilidade única
- regra específica por componente
- separar layout, aparência e estado

### 4. JS

Se houver sintoma de loop, comportamento duplicado ou estado preso:

assuma primeiro:

- listener duplicado
- estado antigo mantido no DOM
- hash/URL interferindo
- fluxo incompleto entre popup e página principal

### 5. HTML/template

Se a página parecer ignorar mudanças:

verifique:

- include real usado
- template real usado pelo runtime
- template cache no processo

## Anti-padrões proibidos

Não fazer:

- múltiplas hipóteses num mesmo patch
- mexer em blocos não relacionados “aproveitando a rodada”
- declarar sucesso sem validar o runtime público
- insistir em tentativa e erro quando a causa ainda não foi mapeada
- adicionar nova camada sem remover a antiga quando a antiga é a causa

## Ordem padrão de execução

1. confirmar o sintoma
2. localizar os arquivos ativos
3. localizar regras/listeners/includes concorrentes
4. decidir local ou transversal
5. fazer o menor ajuste coerente
6. remover sobreposição morta da mesma área
7. validar sintaxe local
8. validar `manage.py check`
9. sincronizar só os arquivos tocados
10. se houver suspeita de drift, sincronizar também os diretórios do bloco afetado
11. regenerar estáticos quando necessário
12. reiniciar só o serviço necessário
13. validar a URL real servida

## Validação mínima obrigatória

Antes de encerrar qualquer bloco:

1. checagem local de sintaxe quando aplicável
2. `python manage.py check`
3. confirmação de que o runtime está servindo o arquivo novo
4. confirmação do seletor, hook, string, hash, rota ou comportamento esperado

## Padrão de resposta durante o trabalho

Ao reportar progresso:

1. dizer o que estava competindo
2. dizer se era local ou transversal
3. dizer o que foi alterado
4. dizer como foi validado
5. dizer o que o usuário deve testar agora

## Padrão de colaboração com este usuário

Este projeto funciona melhor quando:

- o trabalho é feito por bloco fechado
- o sintoma é tratado de forma concreta
- a preservação do que já está bom é prioridade
- rollback do último delta é imediato se houver regressão
- ajuste visual fino só vem depois da trilha ativa estar estabilizada

## Regra final

Se algo “não mudou”:

não edite novamente antes de verificar:

- trilha ativa
- hash ativo
- manifest
- processo `web`
- URL pública real

No OwnPaper, isso é tão importante quanto o código em si.

## Regra permanente para este projeto

Esta skill deve ser tratada como fluxo de trabalho padrão obrigatório do OwnPaper.

Sempre que o trabalho tocar:

- página pública
- publicação
- admin
- template
- CSS
- JS
- estáticos
- container
- implantação

use esta skill antes de iterar.
