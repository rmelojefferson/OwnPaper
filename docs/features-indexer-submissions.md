# Indexador e submissões públicas

OwnPaper inclui recursos para indexação por CSV e recebimento de submissões públicas de textos/artigos.

## Indexador

O indexador permite importar dados estruturados por CSV para consulta no site público.

A página do indexador pode ser vinculada nas configurações do site e acessada no painel administrativo.

## Importação CSV

A importação deve validar o arquivo antes de processar.

Verificações recomendadas:

- aceitar apenas CSV;
- validar codificação;
- validar cabeçalho;
- rejeitar colunas extras perigosas quando a política exigir;
- impedir fórmulas maliciosas comuns em planilhas;
- sanitizar campos textuais;
- limitar tamanho;
- tratar quebras de linha inesperadas;
- processar de forma isolada;
- registrar logs.

O objetivo é evitar que um CSV malformado quebre o indexador ou injete conteúdo inseguro no banco.

## Exportação e modelo

O painel pode oferecer:

- download de modelo CSV;
- exportação dos dados cadastrados;
- histórico de importações;
- mensagens claras de erro.

## Submissões públicas

Submissões públicas permitem que pessoas externas enviem textos sem acesso ao painel.

Fluxo sugerido:

1. Visitante usa cadastro público ou formulário de submissão.
2. Sistema coleta dados essenciais.
3. Usuário envia PDF do texto proposto.
4. PDF passa por validação, sanitização e antivírus.
5. Submissão entra para avaliação no painel.
6. Admin/revisor aceita ou rejeita.
7. Se aceita, o autor completa perfil público com mini bio e redes.
8. Sistema cria vínculo de autoria.
9. Texto final é convertido em publicação ou encaminhado para edição.
10. Publicação passa pelo fluxo editorial normal.

## Cadastro público aproveitado

Quando possível, a submissão deve aproveitar a página de cadastro público.

Assim, o usuário externo já possui identidade básica e pode completar informações de autor apenas se a submissão for aceita.

## ORCID

A instalação pode exigir ORCID para submissões.

Essa exigência deve ser configurável por admin.

## Autor temporário

O autor temporário não precisa ter acesso ao painel.

Ele pode:

- enviar submissão;
- completar ficha pública;
- receber link pessoal;
- manter autoria vinculada;
- ser promovido depois a autor oficial sem perder histórico.

## Conversão em publicação

Quando uma submissão aceita vira publicação:

- autoria é vinculada;
- publicação começa como rascunho ou em revisão;
- logs registram origem;
- revisão segue fluxo padrão;
- mídia ou anexos permanecem controlados.

## Segurança

Submissões e CSVs devem seguir a mesma filosofia de segurança da mídia:

- validação antes de persistir;
- sanitização;
- antivírus quando ativo;
- logs;
- limites de tamanho;
- ausência de HTML/script arbitrário.
