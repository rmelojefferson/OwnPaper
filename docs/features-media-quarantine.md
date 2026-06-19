# Mídia, quarentena e sanitização

OwnPaper trata uploads como uma superfície de risco. Por isso, imagens, documentos e vídeos passam por validação, sanitização e quarentena antes de ficarem disponíveis publicamente, inclusive quando enviados por admins.

## Tipos suportados por padrão

Imagens:

- JPG;
- PNG;
- WebP.

Documentos:

- PDF.

Vídeos:

- MP4;
- WebM;
- limite padrão de 500 MB.

SVG não é aceito por padrão, pois pode conter scripts, links e construções perigosas.

## Onde a quarentena se aplica

A quarentena deve cobrir:

- upload direto em `Mídias pendentes`;
- imagem enviada pelo editor da publicação;
- documento inserido no corpo da publicação;
- vídeo carregado no sistema;
- submissões públicas em PDF;
- CSV do indexador quando o fluxo de validação estiver ativo;
- anexos ou conteúdo externo que venha a ser aceito no futuro.

## Fluxo padrão

1. Usuário envia arquivo.
2. Sistema valida nome, extensão e tamanho.
3. Sistema identifica o tipo real do arquivo quando possível.
4. Arquivo passa por antivírus quando ClamAV está ativo.
5. Imagens são reprocessadas para remover metadados e normalizar conteúdo.
6. PDFs são verificados contra tokens perigosos e regravados quando possível.
7. Vídeos passam por validação de tipo e tamanho.
8. Arquivo fica pendente para avaliação humana.
9. Admin/revisor avalia o preview.
10. Arquivo aprovado entra na biblioteca ou no local planejado da publicação.
11. Arquivo rejeitado não é disponibilizado publicamente.

## Upload dentro da publicação

Quando o autor envia uma mídia diretamente no editor, o sistema não deve bloquear a publicação apenas porque a mídia ainda não foi aprovada.

O comportamento correto é:

- criar a mídia pendente;
- salvar a publicação;
- marcar o ponto de inserção como pendente;
- exibir aviso ao usuário;
- efetivar a mídia automaticamente após aprovação.

Isso evita burocracia e preserva segurança.

## Preview de avaliação

A página de mídias pendentes deve mostrar preview.

Para imagens:

- miniatura na listagem;
- preview ampliado em modal.

Para PDF:

- botão de visualização;
- abertura controlada para avaliação.

Para vídeo:

- preview ou link controlado quando possível.

A aprovação não deve depender apenas da sanitização técnica, pois o conteúdo visual também pode ser inadequado editorialmente.

## ClamAV

ClamAV é opcional por configuração, mas recomendado em produção.

Quando ativo:

- o arquivo é enviado para verificação local/rede;
- detecções bloqueiam o fluxo;
- erros devem ser registrados;
- o arquivo suspeito não deve ser publicado.

## Arquivos suspeitos

Se um arquivo contém script, assinatura suspeita, tipo divergente ou estrutura perigosa, o sistema deve:

- impedir publicação;
- registrar motivo técnico;
- manter trilha de auditoria;
- exibir status compreensível no painel;
- permitir rejeição administrativa.

## Metadados

Imagens devem ser reprocessadas para reduzir metadados desnecessários.

PDFs devem ser tratados com cautela. Sanitização de PDF reduz riscos, mas não substitui antivírus, validação de tipo, limitação de tamanho e política de aceitação.

## Armazenamento

Mídias aprovadas entram na biblioteca apropriada:

- imagens aprovadas em imagens;
- documentos aprovados em documentos;
- vídeos em armazenamento configurado.

Mídias pendentes permanecem separadas até decisão.

## Permissões

Autores podem enviar mídia se a política permitir, mas não devem aprovar.

Revisores/admins podem aprovar ou rejeitar conforme permissões.

Mesmo admin passa pela quarentena para evitar publicação acidental de arquivo comprometido.
