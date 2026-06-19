# Quiz e perguntas reutilizáveis

OwnPaper possui um catálogo de perguntas reutilizáveis e permite usar perguntas em publicações ou em área de quiz/estudo no site público.

## Catálogo de perguntas

O catálogo é a fonte única de perguntas.

Perguntas possuem:

- ID;
- enunciado;
- explicação;
- alternativas;
- resposta correta;
- status ativo/inativo;
- status de aprovação quando aplicável;
- categoria;
- tags;
- histórico de uso;
- autoria/criação;
- data de criação e atualização.

## Criação de perguntas

Perguntas novas devem ser cadastradas no painel de perguntas reutilizáveis.

Isso evita duplicação e mantém todo o acervo pesquisável.

Autores podem sugerir perguntas quando permitido, mas a validação deve seguir o fluxo editorial do projeto.

## Uso em publicações

Ao editar uma publicação, o autor seleciona perguntas existentes.

A busca deve permitir localizar por:

- ID;
- texto da pergunta;
- explicação;
- categoria;
- tag;
- status;
- uso;
- data;
- ordenação por título ou data.

O campo exclusivo para ID não é necessário quando a busca geral já pesquisa por ID.

## Perguntas ativas e inativas

Status ativo/inativo indica se a pergunta deve estar disponível para uso.

Uma pergunta inativa pode permanecer no histórico, mas não deve ser sugerida para novas publicações sem ação administrativa.

## Categorias e tags

Categorias e tags ajudam a localizar perguntas.

A relação entre pergunta e publicação deve ser tratada com cuidado para não misturar taxonomia automaticamente sem decisão editorial. Quando houver sincronização, ela precisa ser explícita e auditável.

## Quiz público

O site público pode oferecer quiz em publicação ou área de estudo.

Comportamentos esperados:

- responder perguntas;
- pular perguntas;
- finalizar sem criar contagem incorreta de pulos;
- exibir total de acertos, erros e pulos;
- calcular percentuais de forma consistente;
- evitar soma visual estranha quando há divisão não exata.

Para percentuais como 1/3, recomenda-se exibir duas casas decimais ou arredondamento controlado que não distorça o resultado.

## Acesso ao quiz

O projeto possui suporte a controle de acesso para quiz, incluindo códigos e sessão do usuário quando configurado.

O objetivo é permitir experiências públicas, restritas ou associadas a cadastro, conforme a instalação.

## Auditoria e uso

O painel deve indicar onde perguntas estão sendo usadas.

Informações úteis:

- número de publicações vinculadas;
- publicações específicas;
- categorias/tags relacionadas;
- status;
- data de atualização.
