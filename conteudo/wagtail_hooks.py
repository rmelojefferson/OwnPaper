import csv
from io import TextIOWrapper

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse

from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.models import Site

from home.models import HomePage
from conteudo.models import (
    Autor,
    Categoria,
    ConfiguracaoSite,
    PublicacaoPage,
    PublicacaoPageAutor,
    PublicacoesIndexPage,
    RegistroIndexador,
    RegistroIndexadorAutor,
)


def importar_csv_indexador_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("/admin/")

    if request.method == "POST":
        arquivo_csv = request.FILES.get("arquivo_csv")

        if not arquivo_csv:
            messages.error(request, "Selecione um arquivo CSV para importar.")
            return redirect("admin_indexador_importar_csv")

        try:
            conteudo_bytes = arquivo_csv.read()

            texto_csv = None
            codificacoes_tentadas = ["utf-8-sig", "cp1252", "latin-1"]

            for codificacao in codificacoes_tentadas:
                try:
                    texto_csv = conteudo_bytes.decode(codificacao)
                    break
                except UnicodeDecodeError:
                    continue

            if texto_csv is None:
                messages.error(
                    request,
                    "Nao foi possivel ler o arquivo CSV. Salve o arquivo em UTF-8, ANSI ou Latin-1 e tente novamente.",
                )
                return redirect("admin_indexador_importar_csv")

            leitor = csv.DictReader(texto_csv.splitlines())

            colunas_esperadas = [
                "titulo",
                "ano_publicacao",
                "dados_editoriais",
                "resumo",
                "palavras_chave",
                "doi",
                "url_acesso",
                "autores",
                "orcids",
                "ativo",
            ]

            if not leitor.fieldnames:
                messages.error(request, "O arquivo CSV parece estar vazio.")
                return redirect("admin_indexador_importar_csv")

            colunas_faltando = [
                coluna for coluna in colunas_esperadas if coluna not in leitor.fieldnames
            ]
            if colunas_faltando:
                messages.error(
                    request,
                    "Faltam colunas no CSV: " + ", ".join(colunas_faltando),
                )
                return redirect("admin_indexador_importar_csv")

            total = 0
            criados = 0
            atualizados = 0
            ignorados = 0
            erros = []

            with transaction.atomic():
                for numero_linha, linha in enumerate(leitor, start=2):
                    total += 1

                    titulo = (linha.get("titulo") or "").strip()
                    ano_publicacao = (linha.get("ano_publicacao") or "").strip()
                    dados_editoriais = (linha.get("dados_editoriais") or "").strip()
                    resumo = (linha.get("resumo") or "").strip()
                    palavras_chave = (linha.get("palavras_chave") or "").strip()
                    doi = (linha.get("doi") or "").strip()
                    url_acesso = (linha.get("url_acesso") or "").strip()
                    autores_brutos = (linha.get("autores") or "").strip()
                    orcids_brutos = (linha.get("orcids") or "").strip()
                    ativo_bruto = (linha.get("ativo") or "").strip().lower()

                    if len(titulo) > 500:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: titulo com mais de 500 caracteres.")
                        continue

                    if len(ano_publicacao) > 20:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: ano_publicacao com mais de 20 caracteres.")
                        continue

                    if len(palavras_chave) > 500:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: palavras_chave com mais de 500 caracteres.")
                        continue

                    if len(doi) > 255:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: doi com mais de 255 caracteres.")
                        continue


                    # Ignora automaticamente a linha de exemplo do arquivo modelo
                    if (
                        titulo == "Titulo de exemplo"
                        and resumo == "Resumo de exemplo."
                        and autores_brutos == "Autor Um; Autor Dois"
                    ):
                        ignorados += 1
                        continue

                    if not titulo:
                        ignorados += 1
                        erros.append(f"Linha {numero_linha}: titulo obrigatorio ausente.")
                        continue

                    autores = [item.strip() for item in autores_brutos.split(";") if item.strip()]

                    if not resumo:
                        erros.append(f"Linha {numero_linha}: importado sem resumo.")

                    if not autores:
                        erros.append(f"Linha {numero_linha}: importado sem autor.")

                    autores_validos = []
                    for autor in autores:
                        if len(autor) > 1000:
                            erros.append(
                                f"Linha {numero_linha}: autor truncado para 1000 caracteres."
                            )
                            autor = autor[:1000]

                        if autor:
                            autores_validos.append(autor)

                    orcids = [item.strip() for item in orcids_brutos.split(";") if item.strip()]

                    orcids_validos = []
                    for orcid in orcids:
                        if len(orcid) > 19:
                            erros.append(
                                f"Linha {numero_linha}: ORCID truncado para 19 caracteres."
                            )
                            orcid = orcid[:19]

                        orcids_validos.append(orcid)

                    ativo = True
                    if ativo_bruto in ["0", "false", "nao", "não", "inativo"]:
                        ativo = False

                    registro = None

                    if doi:
                        registro = RegistroIndexador.objects.filter(doi__iexact=doi).first()

                    if registro is None:
                        registro = RegistroIndexador(
                            titulo=titulo,
                            ano_publicacao=ano_publicacao,
                            dados_editoriais=dados_editoriais,
                            resumo=resumo,
                            palavras_chave=palavras_chave,
                            doi=doi,
                            url_acesso=url_acesso,
                            ativo=ativo,
                        )
                        registro.save()
                        criados += 1
                    else:
                        registro.titulo = titulo
                        registro.ano_publicacao = ano_publicacao
                        registro.dados_editoriais = dados_editoriais
                        registro.resumo = resumo
                        registro.palavras_chave = palavras_chave
                        registro.doi = doi
                        registro.url_acesso = url_acesso
                        registro.ativo = ativo
                        registro.save()
                        atualizados += 1

                    registro.autores_registro.all().delete()

                    for indice, nome_autor in enumerate(autores_validos):
                        orcid = orcids_validos[indice] if indice < len(orcids_validos) else ""
                        RegistroIndexadorAutor.objects.create(
                            registro=registro,
                            nome=nome_autor,
                            orcid=orcid,
                            sort_order=indice,
                        )

            messages.success(
                request,
                f"Importacao concluida. Total de linhas: {total}. Criados: {criados}. Atualizados: {atualizados}. Ignorados: {ignorados}."
            )

            if erros:
                for erro in erros[:10]:
                    messages.warning(request, erro)

                if len(erros) > 10:
                    messages.warning(
                        request,
                        f"Ha mais {len(erros) - 10} erro(s) ou aviso(s) nao exibidos."
                    )

            return redirect("admin_indexador_importar_csv")

        except Exception as exc:
            import traceback

            messages.error(request, f"Erro ao importar CSV: {exc}")
            messages.error(request, traceback.format_exc()[:8000])
            return redirect("admin_indexador_importar_csv")

    return render(
        request,
        "conteudo/admin_indexador_importar_csv.html",
        {},
    )

def modelo_csv_indexador_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("/admin/")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="modelo_indexador.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "titulo",
        "ano_publicacao",
        "dados_editoriais",
        "resumo",
        "palavras_chave",
        "doi",
        "url_acesso",
        "autores",
        "orcids",
        "ativo",
    ])
    writer.writerow([
        "Titulo de exemplo",
        "2024",
        "Revista Exemplo, v. 1, n. 2",
        "Resumo de exemplo.",
        "palavra-chave um; palavra-chave dois",
        "10.0000/exemplo",
        "https://exemplo.com/artigo",
        "Autor Um; Autor Dois",
        "0000-0001-1111-1111; 0000-0002-2222-2222",
        "1",
    ])

    return response


def publicacoes_admin_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("/admin/")

    query = (request.GET.get("q") or "").strip()
    categoria_id = (request.GET.get("categoria") or "").strip()
    autor_id = (request.GET.get("autor") or "").strip()
    status = (request.GET.get("status") or "").strip()
    ano = (request.GET.get("ano") or "").strip()

    queryset = (
        PublicacaoPage.objects.all()
        .select_related("categoria_principal")
        .prefetch_related("autores_publicacao__autor")
        .order_by("-data_publicacao", "-latest_revision_created_at")
    )

    if not request.user.is_superuser:
        queryset = queryset.filter(
            autores_publicacao__autor__usuario_admin=request.user
        ).distinct()

    if query:
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(resumo__icontains=query)
            | Q(autores_publicacao__autor__nome_completo__icontains=query)
            | Q(autores_publicacao__autor__nome_exibicao__icontains=query)
            | Q(autores_publicacao__autor__username__icontains=query)
        ).distinct()

    if categoria_id.isdigit():
        queryset = queryset.filter(categoria_principal_id=int(categoria_id))

    if autor_id.isdigit():
        queryset = queryset.filter(autores_publicacao__autor_id=int(autor_id)).distinct()

    if status == "publicada":
        queryset = queryset.filter(live=True)
    elif status == "rascunho":
        queryset = queryset.filter(live=False)
    elif status == "com_alteracoes":
        queryset = queryset.filter(live=True, has_unpublished_changes=True)

    if ano.isdigit():
        queryset = queryset.filter(data_publicacao__year=int(ano))

    paginator = Paginator(queryset, 25)
    pagina_atual = paginator.get_page(request.GET.get("pagina"))

    querystring = request.GET.copy()
    querystring.pop("pagina", None)

    pasta_publicacoes = PublicacoesIndexPage.objects.first()
    url_nova_publicacao = ""
    if pasta_publicacoes:
        url_nova_publicacao = reverse(
            "wagtailadmin_pages:add_subpage",
            args=[pasta_publicacoes.id],
        )

    context = {
        "publicacoes": pagina_atual,
        "filtro_q": query,
        "filtro_categoria": categoria_id,
        "filtro_autor": autor_id,
        "filtro_status": status,
        "filtro_ano": ano,
        "categorias": Categoria.objects.order_by("nome"),
        "autores": Autor.objects.order_by("nome_completo"),
        "anos": (
            PublicacaoPage.objects.exclude(data_publicacao__isnull=True)
            .dates("data_publicacao", "year", order="DESC")
        ),
        "total_publicacoes": PublicacaoPage.objects.count(),
        "total_publicadas": PublicacaoPage.objects.filter(live=True).count(),
        "total_rascunhos": PublicacaoPage.objects.filter(live=False).count(),
        "total_com_alteracoes": PublicacaoPage.objects.filter(
            live=True,
            has_unpublished_changes=True,
        ).count(),
        "query_string_sem_pagina": querystring.urlencode(),
        "url_nova_publicacao": url_nova_publicacao,
        "tem_pasta_publicacoes": bool(pasta_publicacoes),
    }
    return render(request, "conteudo/admin_publicacoes_lista.html", context)


def _autor_vinculado_do_usuario(user):
    if not user.is_authenticated or user.is_superuser:
        return None

    return Autor.objects.filter(usuario_admin=user).first()


def _publicacao_pertence_ao_autor(publicacao, autor):
    if not autor:
        return False

    return publicacao.autores_publicacao.filter(autor=autor).exists()


def _autores_enviados_no_formulario(request):
    if request.method != "POST":
        return []

    autores_ids = []
    for key, value in request.POST.items():
        if key.startswith("autores_publicacao-") and key.endswith("-autor"):
            val = (value or "").strip()
            if val.isdigit():
                autores_ids.append(int(val))
    return autores_ids


def _bloquear_com_mensagem(request, mensagem):
    messages.error(request, mensagem)
    return redirect("admin_publicacoes_lista")


def configuracoes_site_admin_view(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("/admin/")

    site = Site.find_for_request(request) or Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return redirect("/admin/")

    ConfiguracaoSite.for_site(site)
    return redirect(
        reverse(
            "wagtailsettings:edit",
            args=["conteudo", "configuracaosite", site.id],
        )
    )


def configuracoes_home_admin_view(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect("/admin/")

    home = HomePage.objects.first()
    if not home:
        messages.error(request, "Pagina Home nao encontrada.")
        return redirect("/admin/")

    return redirect(
        reverse(
            "wagtailadmin_pages:edit",
            args=[home.id],
        )
    )


@hooks.register("before_create_page")
def restringir_criacao_publicacao_para_autor_vinculado(request, parent_page, page_class):
    if page_class is not PublicacaoPage:
        return None

    if request.user.is_superuser:
        return None

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuario nao possui autor vinculado. Fale com um administrador.",
        )

    autores_ids = _autores_enviados_no_formulario(request)
    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuarios nao administradores so podem publicar com seu autor vinculado.",
        )

    return None


@hooks.register("after_create_page")
def garantir_autor_vinculado_na_criacao(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    if request.user.is_superuser:
        return None

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return None

    if not page.specific.autores_publicacao.filter(autor=autor).exists():
        page.specific.autores_publicacao.all().delete()
        PublicacaoPageAutor.objects.create(page=page.specific, autor=autor, sort_order=0)
        page.specific.save_revision(user=request.user)
        messages.warning(
            request,
            "Autor ajustado automaticamente para o autor vinculado ao seu usuario.",
        )
    return None


@hooks.register("before_edit_page")
def restringir_edicao_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    if request.user.is_superuser:
        return None

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuario nao possui autor vinculado. Fale com um administrador.",
        )

    publicacao = page.specific
    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Voce so pode editar publicacoes do seu autor vinculado.",
        )

    autores_ids = _autores_enviados_no_formulario(request)
    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuarios nao administradores so podem usar seu autor vinculado.",
        )

    return None


@hooks.register("before_publish_page")
def restringir_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    if request.user.is_superuser:
        return None

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuario nao possui autor vinculado. Fale com um administrador.",
        )

    publicacao = page.specific
    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Voce so pode publicar publicacoes do seu autor vinculado.",
        )

    autores_ids = _autores_enviados_no_formulario(request)
    if autores_ids and any(aid != autor.id for aid in autores_ids):
        return _bloquear_com_mensagem(
            request,
            "Usuarios nao administradores so podem publicar com seu autor vinculado.",
        )

    return None


@hooks.register("before_delete_page")
def restringir_exclusao_publicacao_para_autor_vinculado(request, page):
    if not isinstance(page.specific, PublicacaoPage):
        return None

    if request.user.is_superuser:
        return None

    autor = _autor_vinculado_do_usuario(request.user)
    if not autor:
        return _bloquear_com_mensagem(
            request,
            "Seu usuario nao possui autor vinculado. Fale com um administrador.",
        )

    publicacao = page.specific
    if not _publicacao_pertence_ao_autor(publicacao, autor):
        return _bloquear_com_mensagem(
            request,
            "Voce so pode excluir publicacoes do seu autor vinculado.",
        )

    return None


@hooks.register("register_admin_urls")
def register_admin_urls():
    return [
        path(
            "publicacoes/",
            publicacoes_admin_view,
            name="admin_publicacoes_lista",
        ),
        path(
            "configuracoes-site/",
            configuracoes_site_admin_view,
            name="admin_configuracoes_site",
        ),
        path(
            "configuracoes-home/",
            configuracoes_home_admin_view,
            name="admin_configuracoes_home",
        ),
        path(
            "indexador/importar-csv/",
            importar_csv_indexador_view,
            name="admin_indexador_importar_csv",
        ),
        path(
            "indexador/modelo-csv/",
            modelo_csv_indexador_view,
            name="admin_indexador_modelo_csv",
        ),
    ]


@hooks.register("register_admin_menu_item")
def register_publicacoes_menu_item():
    return MenuItem(
        "Publicações",
        reverse("admin_publicacoes_lista"),
        icon_name="doc-full",
        order=820,
    )


@hooks.register("register_admin_menu_item")
def register_indexador_menu_item():
    return SubmenuMenuItem(
        "Indexador",
        Menu(
            items=[
                MenuItem(
                    "Registros do indexador",
                    reverse("wagtailsnippets_conteudo_registroindexador:list"),
                    icon_name="doc-full",
                ),
                MenuItem(
                    "Importar indexador",
                    reverse("admin_indexador_importar_csv"),
                    icon_name="download",
                ),
            ]
        ),
        icon_name="search",
        order=830,
    )


@hooks.register("register_admin_menu_item")
def register_autores_menu_item():
    return MenuItem(
        "Autores",
        reverse("wagtailsnippets_conteudo_autor:list"),
        icon_name="user",
        order=835,
    )


@hooks.register("register_admin_menu_item")
def register_categorias_tags_menu_item():
    return SubmenuMenuItem(
        "Categorias e Tags",
        Menu(
            items=[
                MenuItem(
                    "Categorias",
                    reverse("wagtailsnippets_conteudo_categoria:list"),
                    icon_name="folder-open-1",
                ),
                MenuItem(
                    "Tags",
                    reverse("wagtailsnippets_conteudo_tagpublicacao:list"),
                    icon_name="tag",
                ),
            ]
        ),
        icon_name="folder-open-1",
        order=840,
    )


@hooks.register("register_admin_menu_item")
def register_menu_principal_menu_item():
    return MenuItem(
        "Menu principal",
        reverse("wagtailsnippets_conteudo_menuprincipalgrupo:list"),
        icon_name="list-ul",
        order=842,
    )


@hooks.register("register_admin_menu_item")
def register_newsletter_menu_item():
    return SubmenuMenuItem(
        "Newsletter",
        Menu(
            items=[
                MenuItem(
                    "Inscritos",
                    reverse("wagtailsnippets_conteudo_inscritonewsletter:list"),
                    icon_name="mail",
                ),
                MenuItem(
                    "Eventos",
                    reverse("wagtailsnippets_conteudo_newsletterevento:list"),
                    icon_name="history",
                ),
                MenuItem(
                    "Solicitações de privacidade",
                    reverse("wagtailsnippets_conteudo_solicitacaoprivacidadenewsletter:list"),
                    icon_name="warning",
                ),
            ]
        ),
        icon_name="mail",
        order=845,
    )


@hooks.register("register_admin_menu_item")
def register_usuarios_menu_item():
    return MenuItem(
        "Usuários",
        reverse("wagtailusers_users:index"),
        icon_name="group",
        order=855,
    )


@hooks.register("register_admin_menu_item")
def register_configuracoes_site_menu_item():
    return MenuItem(
        "Configurações do site",
        reverse("admin_configuracoes_site"),
        icon_name="cogs",
        order=860,
    )


@hooks.register("register_admin_menu_item")
def register_configuracoes_home_menu_item():
    return MenuItem(
        "Configurações da Home",
        reverse("admin_configuracoes_home"),
        name="admin-config-home",
        icon_name="home",
        order=865,
    )


@hooks.register("construct_main_menu")
def remover_menu_fragmentos(request, menu_items):
    menu_items[:] = [
        item for item in menu_items if getattr(item, "name", "") != "snippets"
    ]
    if not request.user.is_superuser:
        menu_items[:] = [
            item for item in menu_items if getattr(item, "name", "") != "admin-config-home"
        ]
