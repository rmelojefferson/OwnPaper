import json
import urllib.parse
import urllib.request
import csv
import io
import base64
from pathlib import Path

import re
import qrcode

from django.shortcuts import get_object_or_404
from wagtail.rich_text import expand_db_html
from django.utils.safestring import mark_safe
from pathlib import Path
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import TextIOWrapper, BytesIO
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.core.files.base import ContentFile
from wagtail.models import Site
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import escape, strip_tags

from .models import (
    Autor,
    Categoria,
    ConfiguracaoSite,
    ContatoPage,
    InscritoNewsletter,
    MensagemContato,
    NewsletterEvento,
    NewsletterPage,
    IndexadorPage,
    RegistroIndexador,
    RegistroIndexadorAutor,
    PublicacaoPage,
    SolicitacaoPrivacidadeNewsletter,
    TagPublicacao,
)

def robots_txt(request):
    linhas = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /django-admin/",
        "Allow: /",
        "",
        f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}",
    ]
    return HttpResponse("\n".join(linhas), content_type="text/plain")

def categorias_index(request):
    categorias = Categoria.objects.all().order_by("nome")

    return render(
        request,
        "conteudo/categorias_index.html",
        {
            "categorias": categorias,
        },
    )

def validar_turnstile(token, remoteip=None):
    if not settings.TURNSTILE_ENABLED:
        return True

    if not token:
        return False

    data = {
        "secret": settings.TURNSTILE_SECRET_KEY,
        "response": token,
    }

    if remoteip:
        data["remoteip"] = remoteip

    body = urllib.parse.urlencode(data).encode("utf-8")
    request_http = urllib.request.Request(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(request_http, timeout=10) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return bool(payload.get("success"))

def tags_index(request):
    tags = TagPublicacao.objects.annotate(
        total_publicacoes=Count("tagged_publicacoes")
    ).order_by("name")

    return render(
        request,
        "conteudo/tags_index.html",
        {
            "tags": tags,
        },
    )

def autores_index(request):
    autores = Autor.objects.all().order_by("nome_completo")

    return render(
        request,
        "conteudo/autores_index.html",
        {
            "autores": autores,
        },
    )

def busca_publicacoes(request):
    import csv

    q = request.GET.get("q", "").strip()
    categoria_slug = request.GET.get("categoria", "").strip()
    autor_username = request.GET.get("autor", "").strip()
    ordenacao = request.GET.get("ordem", "recentes").strip()
    exportar_csv = request.GET.get("export") == "csv"
    exportar_tudo = request.GET.get("export") == "csv_all"
    pagina = request.GET.get("page")

    categorias = Categoria.objects.all().order_by("nome")
    autores = Autor.objects.all().order_by("nome_completo")

    ordenacoes_disponiveis = {
        "recentes": ("-data_publicacao", "-first_published_at"),
        "antigos": ("data_publicacao", "first_published_at"),
        "titulo_az": ("title",),
        "titulo_za": ("-title",),
    }

    if ordenacao not in ordenacoes_disponiveis:
        ordenacao = "recentes"

    base_qs = PublicacaoPage.objects.live().select_related(
        "categoria_principal"
    ).prefetch_related(
        "autores_publicacao__autor",
        "tags",
    )

    resultados_qs = base_qs

    if q:
        resultados_qs = resultados_qs.filter(
            Q(title__icontains=q)
            | Q(resumo__icontains=q)
            | Q(corpo__icontains=q)
            | Q(autores_publicacao__autor__nome_completo__icontains=q)
            | Q(autores_publicacao__autor__nome_exibicao__icontains=q)
            | Q(categoria_principal__nome__icontains=q)
            | Q(tags__name__icontains=q)
        )

    if categoria_slug:
        resultados_qs = resultados_qs.filter(categoria_principal__slug=categoria_slug)

    if autor_username:
        resultados_qs = resultados_qs.filter(autores_publicacao__autor__username=autor_username)

    resultados_qs = resultados_qs.distinct().order_by(*ordenacoes_disponiveis[ordenacao])
    base_qs = base_qs.distinct().order_by(*ordenacoes_disponiveis[ordenacao])

    if exportar_tudo:
        export_qs = base_qs
        nome_arquivo = "todas_publicacoes.csv"
    elif exportar_csv:
        export_qs = resultados_qs
        nome_arquivo = "resultados_busca.csv"
    else:
        export_qs = None
        nome_arquivo = None

    if export_qs is not None:
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'

        writer = csv.writer(response)
        writer.writerow([
            "Título",
            "Data de publicação",
            "Data de atualização",
            "Categoria",
            "Autores",
            "Tags",
            "URL",
            "Resumo",
        ])

        for item in export_qs:
            autores_item = "; ".join([str(autor) for autor in item.autores_ordenados])
            tags = "; ".join([tag.name for tag in item.tags.all()])
            categoria = item.categoria_principal.nome if item.categoria_principal else ""
            url = request.build_absolute_uri(item.url) if item.url else ""
            resumo = strip_tags(item.resumo or "").strip()

            writer.writerow([
                item.title,
                item.data_publicacao.strftime("%d/%m/%Y") if item.data_publicacao else "",
                item.data_atualizacao.strftime("%d/%m/%Y") if item.data_atualizacao else "",
                categoria,
                autores_item,
                tags,
                url,
                resumo,
            ])

        return response

    paginador = Paginator(resultados_qs, 20)
    page_obj = paginador.get_page(pagina)

    return render(
        request,
        "conteudo/busca_publicacoes.html",
        {
            "q": q,
            "categoria_slug": categoria_slug,
            "autor_username": autor_username,
            "ordenacao": ordenacao,
            "categorias": categorias,
            "autores": autores,
            "resultados": page_obj.object_list,
            "page_obj": page_obj,
            "ha_filtros": bool(q or categoria_slug or autor_username),
        },
    )


def publicacoes_por_tag(request, slug):
    tag = get_object_or_404(TagPublicacao, slug=slug)
    publicacoes = PublicacaoPage.objects.live().filter(tags__slug=slug)

    return render(
        request,
        "conteudo/publicacoes_por_tag.html",
        {
            "tag": tag,
            "publicacoes": publicacoes,
        },
    )

def autor_detalhe(request, username):
    autor = get_object_or_404(Autor, username=username)
    publicacoes = PublicacaoPage.objects.live().filter(
        autores_publicacao__autor=autor
    ).distinct()

    return render(
        request,
        "conteudo/autor_detalhe.html",
        {
            "autor": autor,
            "publicacoes": publicacoes,
        },
    )

def categoria_detalhe(request, slug):
    categoria = get_object_or_404(Categoria, slug=slug)
    publicacoes = PublicacaoPage.objects.live().filter(categoria_principal=categoria)

    return render(
        request,
        "conteudo/categoria_detalhe.html",
        {
            "categoria": categoria,
            "publicacoes": publicacoes,
        },
    )

def registrar_evento_newsletter(inscrito, tipo, origem="", detalhes=""):
    NewsletterEvento.objects.create(
        inscrito=inscrito,
        email=inscrito.email,
        tipo=tipo,
        origem=origem,
        detalhes=detalhes,
    )

def gerar_token_privacidade(email, solicitacao_id, page_id, acao):
    return signing.dumps(
        {
            "email": email,
            "solicitacao_id": solicitacao_id,
            "page_id": page_id,
        },
        salt=f"privacidade.{acao}",
    )


def ler_token_privacidade(token, acao, max_age=60 * 60 * 24 * 7):
    return signing.loads(
        token,
        salt=f"privacidade.{acao}",
        max_age=max_age,
    )

def gerar_token_newsletter(email, page_id, acao):
    return signing.dumps(
        {
            "email": email,
            "page_id": page_id,
        },
        salt=f"newsletter.{acao}",
    )


def ler_token_newsletter(token, acao, max_age=60 * 60 * 24 * 7):
    return signing.loads(
        token,
        salt=f"newsletter.{acao}",
        max_age=max_age,
    )

def contato_form(request, slug):
    pagina = get_object_or_404(ContatoPage.objects.live(), slug=slug)

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        email = request.POST.get("email", "").strip()
        mensagem = request.POST.get("mensagem", "").strip()
        aceitou_privacidade = request.POST.get("aceitou_privacidade") == "on"
        website = request.POST.get("website", "").strip()
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "desconhecido")

        cache_key = f"contato_rate_limit:{ip}"
        tentativas = cache.get(cache_key, 0)

        if tentativas >= 5:
            return redirect(f"{pagina.url}?limite=1")

        if website:
            cache.set(cache_key, tentativas + 1, timeout=600)
            return redirect(f"{pagina.url}?enviado=1")

        if not nome or not email or not mensagem or not aceitou_privacidade:
            return HttpResponseBadRequest("Preencha todos os campos obrigatórios.")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            cache.set(cache_key, tentativas + 1, timeout=600)
            return redirect(f"{pagina.url}?captcha=1")

        cache.set(cache_key, tentativas + 1, timeout=600)

        MensagemContato.objects.create(
            pagina=pagina,
            nome=nome,
            email=email,
            mensagem=mensagem,
        )

        if pagina.email_destino:
            assunto = f"[Contato do site] {pagina.title} - {nome}"
            corpo = (
                f"Nome: {nome}\n"
                f"E-mail: {email}\n\n"
                f"Mensagem:\n{mensagem}\n"
            )

            try:
                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[pagina.email_destino],
                    reply_to=[email],
                )
                email_msg.send(fail_silently=False)
                return redirect(f"{pagina.url}?enviado=1")
            except Exception:
                return redirect(f"{pagina.url}?enviado=1&email_falhou=1")

        return redirect(f"{pagina.url}?enviado=1")

    return redirect(pagina.url)

def newsletter_form(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        consentimento = request.POST.get("consentimento") == "on"
        website = request.POST.get("website", "").strip()
        turnstile_token = request.POST.get("cf-turnstile-response", "").strip()

        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = request.META.get("REMOTE_ADDR", "desconhecido")

        cache_key = f"newsletter_rate_limit:{ip}"
        tentativas = cache.get(cache_key, 0)

        if tentativas >= 5:
            return redirect(f"{pagina.url}?limite=1")

        if website:
            cache.set(cache_key, tentativas + 1, timeout=600)
            return redirect(f"{pagina.url}?sucesso=1")

        if not email or not consentimento:
            return HttpResponseBadRequest("Preencha todos os campos obrigatorios.")

        if settings.TURNSTILE_ENABLED and not validar_turnstile(turnstile_token, remoteip=ip):
            cache.set(cache_key, tentativas + 1, timeout=600)
            return redirect(f"{pagina.url}?captcha=1")

        cache.set(cache_key, tentativas + 1, timeout=600)

        inscrito, criado = InscritoNewsletter.objects.get_or_create(
            email=email,
            defaults={
                "ativo": True,
                "consentimento": True,
                "origem": f"newsletter:{pagina.slug}",
                "confirmado_em": timezone.now(),
            },
        )

        if criado:
            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Cadastro direto via formulario publico, sem confirmacao por e-mail.",
            )
        else:
            inscrito.ativo = True
            inscrito.consentimento = True
            inscrito.origem = f"newsletter:{pagina.slug}"
            if not inscrito.confirmado_em:
                inscrito.confirmado_em = timezone.now()
            inscrito.save()

            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Inscricao reativada ou atualizada via formulario publico, sem confirmacao por e-mail.",
            )

        return redirect(f"{pagina.url}?sucesso=1")

    return redirect(pagina.url)

def newsletter_confirmar(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    try:
        payload = ler_token_newsletter(token, "confirmar")
    except signing.SignatureExpired:
        return redirect(f"{pagina.url}?token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{pagina.url}?token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{pagina.url}?token_invalido=1")

    inscrito = get_object_or_404(InscritoNewsletter, email=payload.get("email", "").lower())

    inscrito.ativo = True
    inscrito.consentimento = True
    inscrito.confirmado_em = timezone.now()
    inscrito.save()

    registrar_evento_newsletter(
        inscrito=inscrito,
        tipo=NewsletterEvento.TIPO_INSCRICAO_CONFIRMADA,
        origem=f"newsletter:{pagina.slug}",
        detalhes="Inscrição confirmada pelo link enviado por e-mail.",
    )

    return redirect(f"{pagina.url}?confirmado=1")


def newsletter_cancelar(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    try:
        payload = ler_token_newsletter(token, "cancelar")
    except signing.SignatureExpired:
        return redirect(f"{pagina.url}?token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{pagina.url}?token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{pagina.url}?token_invalido=1")

    inscrito = get_object_or_404(InscritoNewsletter, email=payload.get("email", "").lower())

    if inscrito:
        inscrito.ativo = False
        inscrito.consentimento = False
        inscrito.save()

        registrar_evento_newsletter(
            inscrito=inscrito,
            tipo=NewsletterEvento.TIPO_CANCELAMENTO_CONFIRMADO,
            origem=f"newsletter:{pagina.slug}",
            detalhes="Cancelamento confirmado por link enviado por e-mail.",
        )

    return redirect(f"{pagina.url}?descadastrado=1")

def newsletter_solicitar_cancelamento(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    if request.method == "POST":
        email = request.POST.get("email_cancelamento", "").strip().lower()

        if not email:
            return HttpResponseBadRequest("Informe um e-mail válido.")

        inscrito = InscritoNewsletter.objects.filter(email__iexact=email).first()

        if inscrito:
            registrar_evento_newsletter(
                inscrito=inscrito,
                tipo=NewsletterEvento.TIPO_CANCELAMENTO_SOLICITADO,
                origem=f"newsletter:{pagina.slug}",
                detalhes="Pedido de cancelamento solicitado pela página pública.",
            )

            token_cancelamento = gerar_token_newsletter(email, pagina.id, "cancelar")
            url_cancelamento = request.build_absolute_uri(
                f"/newsletter/{pagina.slug}/cancelar/{token_cancelamento}/"
            )

            assunto = f"Cancelar inscrição - {pagina.title}"
            corpo = (
                "Recebemos um pedido para cancelar sua inscrição.\n\n"
                "Para confirmar o cancelamento, clique no link abaixo:\n"
                f"{url_cancelamento}\n"
            )

            try:
                email_msg = EmailMessage(
                    subject=assunto,
                    body=corpo,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.send(fail_silently=False)
            except Exception:
                return redirect(f"{pagina.url}?cancelamento_email_falhou=1")

        return redirect(f"{pagina.url}?cancelamento_enviado=1")

    return redirect(pagina.url)

def gerar_exportacao_privacidade_newsletter(email):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["tipo", "campo_1", "campo_2", "campo_3", "campo_4", "campo_5"])

    inscrito = InscritoNewsletter.objects.filter(email__iexact=email).first()
    if inscrito:
        writer.writerow([
            "inscrito",
            inscrito.email,
            inscrito.ativo,
            inscrito.consentimento,
            inscrito.origem,
            inscrito.confirmado_em or "",
        ])

    for evento in NewsletterEvento.objects.filter(email__iexact=email).order_by("criado_em"):
        writer.writerow([
            "evento",
            evento.email,
            evento.tipo,
            evento.origem,
            evento.criado_em,
            evento.detalhes,
        ])

    for solicitacao in SolicitacaoPrivacidadeNewsletter.objects.filter(email__iexact=email).order_by("criado_em"):
        writer.writerow([
            "solicitacao_privacidade",
            solicitacao.email,
            solicitacao.tipo,
            solicitacao.status,
            solicitacao.criado_em,
            solicitacao.observacoes,
        ])

    return buffer.getvalue().encode("utf-8")

def newsletter_solicitar_privacidade(request, slug):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    if request.method == "POST":
        email = request.POST.get("email_privacidade", "").strip().lower()
        tipo = request.POST.get("tipo_privacidade", "").strip()

        if not email or tipo not in [
            SolicitacaoPrivacidadeNewsletter.TIPO_ACESSO,
            SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
        ]:
            return HttpResponseBadRequest("Dados invalidos.")

        solicitacao = SolicitacaoPrivacidadeNewsletter.objects.create(
            email=email,
            tipo=tipo,
            status=SolicitacaoPrivacidadeNewsletter.STATUS_PENDENTE,
        )

        site = Site.find_for_request(request)
        config_site = ConfiguracaoSite.for_site(site) if site else None

        email_destino_admin = settings.DEFAULT_FROM_EMAIL
        if config_site and config_site.email_contato:
            email_destino_admin = config_site.email_contato

        assunto_admin = f"Nova solicitacao de privacidade - {pagina.title}"
        corpo_admin = (
            f"E-mail: {solicitacao.email}\n"
            f"Tipo: {solicitacao.get_tipo_display()}\n"
            f"Data: {solicitacao.criado_em}\n"
        )

        try:
            email_msg = EmailMessage(
                subject=assunto_admin,
                body=corpo_admin,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email_destino_admin],
                reply_to=[email],
            )
            email_msg.send(fail_silently=False)
        except Exception:
            return redirect(f"{pagina.url}?privacidade_email_falhou=1")

        if tipo == SolicitacaoPrivacidadeNewsletter.TIPO_ACESSO:
            try:
                conteudo = solicitacao.gerar_csv_exportacao()
                nome_arquivo = solicitacao.nome_arquivo_exportacao()

                solicitacao.arquivo_exportacao.save(
                    nome_arquivo,
                    ContentFile(conteudo),
                    save=False,
                )
                solicitacao.status = SolicitacaoPrivacidadeNewsletter.STATUS_ATENDIDA
                solicitacao.atendida_em = timezone.now()
                solicitacao.executada_em = timezone.now()
                solicitacao.save()

                assunto_usuario = "Exportacao dos seus dados da newsletter"
                corpo_usuario = (
                    "O arquivo com os dados solicitados da newsletter segue em anexo.\n\n"
                    "Este arquivo será removido do servidor depois de alguns dias.\n"
                    "Se você precisar dele novamente no futuro, será necessário fazer uma nova solicitação.\n"
                )

                email_msg = EmailMessage(
                    subject=assunto_usuario,
                    body=corpo_usuario,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                )
                email_msg.attach(nome_arquivo, conteudo, "text/csv")
                email_msg.send(fail_silently=False)

                return redirect(f"{pagina.url}?privacidade=1")
            except Exception:
                return redirect(f"{pagina.url}?privacidade_email_falhou=1")

        token = gerar_token_privacidade(
            email=email,
            solicitacao_id=solicitacao.id,
            page_id=pagina.id,
            acao="confirmar_exclusao",
        )

        url_confirmacao = request.build_absolute_uri(
            f"/newsletter/{pagina.slug}/confirmar-exclusao-privacidade/{token}/"
        )

        assunto_usuario = f"Confirme a exclusao dos seus dados - {pagina.title}"
        corpo_usuario = (
            "Recebemos um pedido de exclusao dos seus dados da newsletter.\n\n"
            "Para confirmar a exclusao, clique no link abaixo:\n"
            f"{url_confirmacao}\n\n"
            "Se voce nao fez esse pedido, ignore esta mensagem.\n"
        )

        try:
            email_msg = EmailMessage(
                subject=assunto_usuario,
                body=corpo_usuario,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[email],
            )
            email_msg.send(fail_silently=False)
            return redirect(f"{pagina.url}?privacidade_confirmacao_exclusao_enviada=1")
        except Exception:
            return redirect(f"{pagina.url}?privacidade_confirmacao_exclusao_email_falhou=1")

    return redirect(pagina.url)

def newsletter_confirmar_exclusao_privacidade(request, slug, token):
    pagina = get_object_or_404(NewsletterPage.objects.live(), slug=slug)

    try:
        payload = ler_token_privacidade(token, "confirmar_exclusao")
    except signing.SignatureExpired:
        return redirect(f"{pagina.url}?privacidade_token_expirado=1")
    except signing.BadSignature:
        return redirect(f"{pagina.url}?privacidade_token_invalido=1")

    if payload.get("page_id") != pagina.id:
        return redirect(f"{pagina.url}?privacidade_token_invalido=1")

    email = (payload.get("email") or "").strip().lower()
    solicitacao_id = payload.get("solicitacao_id")

    if not email or not solicitacao_id:
        return redirect(f"{pagina.url}?privacidade_token_invalido=1")

    solicitacao = SolicitacaoPrivacidadeNewsletter.objects.filter(
        id=solicitacao_id,
        email__iexact=email,
        tipo=SolicitacaoPrivacidadeNewsletter.TIPO_EXCLUSAO,
    ).first()

    if not solicitacao:
        return redirect(f"{pagina.url}?privacidade_token_invalido=1")

    if solicitacao.executada_em:
        return redirect(f"{pagina.url}?privacidade_exclusao_confirmada=1")

    solicitacao.confirmacao_usuario_exclusao = True
    solicitacao.confirmacao_usuario_em = timezone.now()
    solicitacao.status = SolicitacaoPrivacidadeNewsletter.STATUS_ATENDIDA

    observacao_confirmacao = "Excluso confirmada pelo usuário via link enviado por e-mail."
    if solicitacao.observacoes:
        solicitacao.observacoes += f"\n{observacao_confirmacao}"
    else:
        solicitacao.observacoes = observacao_confirmacao

    solicitacao.save()

    assunto = f"Exclusao concluida - {pagina.title}"
    corpo = (
        "A exclusão dos seus dados da newsletter foi concluída com sucesso.\n\n"
        "Se desejar, você poderá se inscrever novamente.\n"
    )

    try:
        email_msg = EmailMessage(
            subject=assunto,
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        email_msg.send(fail_silently=False)
        return redirect(f"{pagina.url}?privacidade_exclusao_confirmada=1")
    except Exception:
        return redirect(f"{pagina.url}?privacidade_exclusao_confirmada_email_falhou=1")

def filtrar_registros_indexador(termo="", ano="", ordenar="recentes"):
    registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro")

    if termo:
        registros = registros.filter(
            Q(titulo__icontains=termo)
            | Q(resumo__icontains=termo)
            | Q(dados_editoriais__icontains=termo)
            | Q(palavras_chave__icontains=termo)
            | Q(doi__icontains=termo)
            | Q(autores_registro__nome__icontains=termo)
            | Q(autores_registro__orcid__icontains=termo)
        ).distinct()

    if ano:
        registros = registros.filter(ano_publicacao__icontains=ano)

    if ordenar == "titulo_az":
        registros = registros.order_by("titulo")
    elif ordenar == "titulo_za":
        registros = registros.order_by("-titulo")
    elif ordenar == "antigos":
        registros = registros.order_by("ano_publicacao", "titulo")
    else:
        registros = registros.order_by("-ano_publicacao", "titulo")

    return registros

def filtrar_registros_indexador(termo="", ano_inicial="", ano_final="", ordenar="recentes"):
    registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro")

    if termo:
        registros = registros.filter(
            Q(titulo__icontains=termo)
            | Q(resumo__icontains=termo)
            | Q(dados_editoriais__icontains=termo)
            | Q(palavras_chave__icontains=termo)
            | Q(doi__icontains=termo)
            | Q(autores_registro__nome__icontains=termo)
            | Q(autores_registro__orcid__icontains=termo)
        ).distinct()

    if ano_inicial:
        registros = registros.filter(ano_publicacao__gte=ano_inicial)

    if ano_final:
        registros = registros.filter(ano_publicacao__lte=ano_final)

    if ordenar == "titulo_az":
        registros = registros.order_by("titulo")
    elif ordenar == "titulo_za":
        registros = registros.order_by("-titulo")
    elif ordenar == "antigos":
        registros = registros.order_by("ano_publicacao", "titulo")
    else:
        registros = registros.order_by("-ano_publicacao", "titulo")

    return registros

def indexador_registro_detalhe(request, page_slug, registro_slug):
    page = get_object_or_404(IndexadorPage.objects.live(), slug=page_slug)
    registro = get_object_or_404(
        RegistroIndexador.objects.prefetch_related("autores_registro"),
        slug=registro_slug,
        ativo=True,
    )

    return render(
        request,
        "conteudo/indexador_registro_detalhe.html",
        {
            "page": page,
            "registro": registro,
        },
    )

def indexador_exportar_csv(request, page_slug):
    page = get_object_or_404(IndexadorPage.objects.live(), slug=page_slug)

    termo = request.GET.get("q", "").strip()
    ano_inicial = request.GET.get("ano_inicial", "").strip()
    ano_final = request.GET.get("ano_final", "").strip()
    ordenar = request.GET.get("ordenar", "recentes").strip()
    escopo = request.GET.get("escopo", "resultados").strip()

    if escopo == "todos":
        registros = RegistroIndexador.objects.filter(ativo=True).prefetch_related("autores_registro").order_by("titulo")
    else:
        registros = filtrar_registros_indexador(
            termo=termo,
            ano_inicial=ano_inicial,
            ano_final=ano_final,
            ordenar=ordenar,
        )

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="indexador.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "titulo",
        "ano_publicacao",
        "dados_editoriais",
        "resumo",
        "autores",
        "orcids",
        "palavras_chave",
        "doi",
        "url_acesso",
    ])

    for registro in registros:
        writer.writerow([
            registro.titulo,
            registro.ano_publicacao,
            registro.dados_editoriais,
            registro.resumo,
            registro.autores_formatados,
            registro.orcids_formatados,
            registro.palavras_chave,
            registro.doi,
            registro.url_acesso,
        ])

    return response

def richtext_para_html(valor):
    if not valor:
        return ""

    if hasattr(valor, "source"):
        return expand_db_html(valor.source)

    return str(valor)


def normalizar_html_pdf(html):
    if not html:
        return ""

    # Remove seta de retorno que costuma aparecer em notas/referências
    html = html.replace("↩", "")

    # xhtml2pdf costuma lidar melhor com div do que com figure/figcaption
    html = re.sub(r"<figure([^>]*)>", r"<div\1>", html)
    html = html.replace("</figure>", "</div>")
    html = re.sub(r"<figcaption([^>]*)>", r"<div\1>", html)
    html = html.replace("</figcaption>", "</div>")

    return html


def converter_urls_html_para_pdf(html, request=None):
    if not html:
        return ""

    media_url = settings.MEDIA_URL.rstrip("/")
    static_url = settings.STATIC_URL.rstrip("/")
    media_root = str(Path(settings.MEDIA_ROOT)).rstrip("/")
    static_root = str(Path(settings.STATIC_ROOT)).rstrip("/")

    html = html.replace(f'src="{media_url}/', f'src="file://{media_root}/')
    html = html.replace(f"src='{media_url}/", f"src='file://{media_root}/")
    html = html.replace(f'href="{media_url}/', f'href="file://{media_root}/')
    html = html.replace(f"href='{media_url}/", f"href='file://{media_root}/")

    html = html.replace(f'src="{static_url}/', f'src="file://{static_root}/')
    html = html.replace(f"src='{static_url}/", f"src='file://{static_root}/")
    html = html.replace(f'href="{static_url}/', f'href="file://{static_root}/')
    html = html.replace(f"href='{static_url}/", f"href='file://{static_root}/")

    if request:
        base_url = request.build_absolute_uri("/")
        html = re.sub(r'href="/(?!/)', f'href="{base_url}', html)
        html = re.sub(r"href='/(?!/)", f"href='{base_url}", html)

    return html


def obter_primeiro_campo_existente(obj, nomes):
    for nome in nomes:
        valor = getattr(obj, nome, "")
        if valor:
            return valor
    return ""


def pdf_link_callback(uri, rel):
    if uri.startswith("file://"):
        return uri.replace("file://", "", 1)

    if uri.startswith(settings.MEDIA_URL):
        return str(Path(settings.MEDIA_ROOT) / uri.replace(settings.MEDIA_URL, "", 1))

    if uri.startswith(settings.STATIC_URL):
        return str(Path(settings.STATIC_ROOT) / uri.replace(settings.STATIC_URL, "", 1))

    return uri


def gerar_qrcode_data_uri(valor):
    texto = (valor or "").strip()
    if not texto:
        return ""

    qr = qrcode.QRCode(
        version=1,
        box_size=6,
        border=2,
    )
    qr.add_data(texto)
    qr.make(fit=True)
    imagem = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def marcador_para_id(prefixo, marcador):
    valor = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(marcador or "").strip()).strip("-")
    if not valor:
        valor = "item"
    return f"{prefixo}-{valor}"


def formatar_referencia_pdf(ref):
    partes = []
    if ref.autores_formatados:
        partes.append(f"{ref.autores_formatados}.")

    titulo = ref.titulo_obra or ""
    if ref.subtitulo:
        titulo = f"{titulo}: {ref.subtitulo}"
    if titulo:
        partes.append(titulo + ".")

    if ref.tipo_midia:
        partes.append(f"{ref.tipo_midia}.")
    if ref.local_publicacao:
        partes.append(f"{ref.local_publicacao}:")
    if ref.editora:
        partes.append(f"{ref.editora},")
    if ref.ano:
        partes.append(f"{ref.ano}.")
    if ref.paginas:
        partes.append(f"{ref.paginas}.")

    texto = " ".join(partes).strip()
    return texto


def construir_corpo_pdf(page, request=None):
    html = richtext_para_html(getattr(page, "corpo", ""))

    notas = list(page.notas_rodape.all())
    refs = list(page.referencias.all())
    imagens = list(page.imagens_publicacao.all())
    videos = list(page.midias_embed.all())

    notas_map = {}
    for indice, nota in enumerate(notas, start=1):
        chave = (nota.marcador or str(indice)).strip()
        notas_map[chave] = chave or str(indice)

    refs_map = {}
    for indice, ref in enumerate(refs, start=1):
        chave = (ref.marcador or str(indice)).strip()
        refs_map[chave] = chave or str(indice)

    imagens_map = {}
    for item in imagens:
        chave = (item.marcador or "").strip()
        if chave:
            imagens_map[chave] = item

    videos_map = {}
    for item in videos:
        chave = (item.marcador or "").strip()
        if chave:
            videos_map[chave] = item

    imagens_usadas = set()
    videos_usados = set()

    def sub_nota(match):
        marcador = (match.group(1) or "").strip()
        indice = notas_map.get(marcador, "?")
        if indice == "?":
            return f'<sup class="indice-nota">{indice}</sup>'
        destino = marcador_para_id("nota", indice)
        origem = marcador_para_id("nota-src", indice)
        return (
            f'<a name="{origem}"></a>'
            f'<sup class="indice-nota"><a href="#{destino}">{indice}</a></sup>'
        )

    def sub_ref(match):
        marcador = (match.group(1) or "").strip()
        indice = refs_map.get(marcador, "?")
        if indice == "?":
            return f'<sup class="indice-ref">{indice}</sup>'
        destino = marcador_para_id("ref", indice)
        origem = marcador_para_id("ref-src", indice)
        return (
            f'<a name="{origem}"></a>'
            f'<sup class="indice-ref"><a href="#{destino}">{indice}</a></sup>'
        )

    def sub_imagem(match):
        marcador = (match.group(1) or "").strip()
        item = imagens_map.get(marcador)
        if not item:
            return ""

        imagens_usadas.add(item.id)
        rendition = item.imagem.get_rendition("max-700x394")
        imagem_src = converter_urls_html_para_pdf(
            f'<img src="{rendition.url}" alt="{escape(item.titulo or "")}">',
            request=request,
        )
        legenda = escape(item.legenda or "")
        titulo = escape(item.titulo or "")

        legenda_html = ""
        if titulo or legenda:
            legenda_html = (
                '<div class="pdf-legenda">'
                + (f"<strong>{titulo}</strong>" if titulo else "")
                + (f"<div>{legenda}</div>" if legenda else "")
                + "</div>"
            )

        return f'<div class="pdf-imagem"><div class="pdf-imagem-bloco">{imagem_src}{legenda_html}</div></div>'

    def sub_video(match):
        marcador = (match.group(1) or "").strip()
        item = videos_map.get(marcador)
        if not item:
            return ""

        videos_usados.add(item.id)
        qr_data_uri = gerar_qrcode_data_uri(item.url)
        titulo = escape(item.titulo or "Vídeo")
        url_video = escape(item.url or "")
        return (
            '<div class="pdf-video">'
            f'<div class="pdf-video-titulo">{titulo}</div>'
            f'<img src="{qr_data_uri}" alt="QR code do vídeo">'
            f'<div class="pdf-video-url">{url_video}</div>'
            "</div>"
        )

    html = re.sub(r"\[\[\s*n:\s*([^\]]+)\s*\]\]", sub_nota, html)
    html = re.sub(r"\[\[\s*r:\s*([^\]]+)\s*\]\]", sub_ref, html)
    html = re.sub(r"\[\[\s*i:\s*([^\]]+)\s*\]\]", sub_imagem, html)
    html = re.sub(r"\[\[\s*v:\s*([^\]]+)\s*\]\]", sub_video, html)

    corpo_html = converter_urls_html_para_pdf(normalizar_html_pdf(html), request=request)
    return mark_safe(corpo_html), imagens_usadas, videos_usados

def publicacao_pdf(request, page_id):
    page = get_object_or_404(
        PublicacaoPage.objects.live().public(),
        id=page_id,
    )

    resumo_html = converter_urls_html_para_pdf(
        normalizar_html_pdf(richtext_para_html(getattr(page, "resumo", ""))),
        request=request,
    )
    corpo_html, imagens_usadas, videos_usados = construir_corpo_pdf(page, request=request)

    referencias = page.referencias.all()
    notas_rodape = page.notas_rodape.all()
    imagens = list(page.imagens_publicacao.all())
    videos = list(page.midias_embed.all())

    imagens_adicionais = [item for item in imagens if item.id not in imagens_usadas]
    videos_adicionais = [item for item in videos if item.id not in videos_usados]

    for video in videos_adicionais:
        video.qr_data_uri = gerar_qrcode_data_uri(video.url)

    notas_formatadas = []
    for indice, nota in enumerate(notas_rodape, start=1):
        marcador_display = (nota.marcador or "").strip()
        marcador_base = marcador_display or str(indice)
        notas_formatadas.append(
            {
                "marcador_display": marcador_display,
                "anchor_id": marcador_para_id("nota", marcador_base),
                "anchor_src_id": marcador_para_id("nota-src", marcador_base),
                "conteudo_html": mark_safe(
                    converter_urls_html_para_pdf(
                        normalizar_html_pdf(richtext_para_html(nota.conteudo)),
                        request=request,
                    )
                ),
            }
        )

    referencias_formatadas = []
    for indice, ref in enumerate(referencias, start=1):
        marcador_display = (ref.marcador or "").strip()
        marcador_base = marcador_display or str(indice)
        referencias_formatadas.append(
            {
                "marcador_display": marcador_display,
                "anchor_id": marcador_para_id("ref", marcador_base),
                "anchor_src_id": marcador_para_id("ref-src", marcador_base),
                "texto": formatar_referencia_pdf(ref),
                "url": ref.url,
                "observacoes": ref.observacoes,
            }
        )

    creditos_videos = [item for item in page.midias_embed.all() if item.credito_texto or item.fonte_url]
    creditos_imagens = [item for item in page.imagens_publicacao.all() if item.credito_texto or item.fonte_url]

    html = render_to_string(
        "conteudo/publicacao_pdf.html",
        {
            "page": page,
            "url_publica": request.build_absolute_uri(page.url),
            "qr_publicacao_data_uri": gerar_qrcode_data_uri(request.build_absolute_uri(page.url)),
            "resumo_html": mark_safe(resumo_html),
            "corpo_html": corpo_html,
            "imagens_adicionais": imagens_adicionais,
            "videos_adicionais": videos_adicionais,
            "notas_rodape": notas_formatadas,
            "referencias": referencias_formatadas,
            "creditos_videos": creditos_videos,
            "creditos_imagens": creditos_imagens,
            "autores": page.autores_ordenados,
        },
        request=request,
    )

    resultado = BytesIO()
    pdf = pisa.CreatePDF(
        html,
        dest=resultado,
        link_callback=pdf_link_callback,
    )

    if pdf.err:
        return HttpResponse("Erro ao gerar PDF.", status=500)

    response = HttpResponse(
        resultado.getvalue(),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'inline; filename="publicacao-{page.id}.pdf"'
    return response
