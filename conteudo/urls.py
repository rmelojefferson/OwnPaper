from django.urls import path

from .views import (
    autor_detalhe,
    autores_index,
    busca_publicacoes,
    categoria_detalhe,
    categorias_index,
    contato_form,
    newsletter_cancelar,
    newsletter_confirmar,
    newsletter_form,
    newsletter_solicitar_cancelamento,
    newsletter_solicitar_privacidade,
    newsletter_confirmar_exclusao_privacidade,
    indexador_exportar_csv,
    indexador_registro_detalhe,
    publicacoes_por_tag,
    publicacao_pdf,
    robots_txt,
    tags_index,
)

urlpatterns = [

    path("robots.txt", robots_txt, name="robots_txt"),
    path("contato/<slug:slug>/enviar/", contato_form, name="contato_form"),
    path("newsletter/<slug:slug>/inscrever/", newsletter_form, name="newsletter_form"),
    path("newsletter/<slug:slug>/solicitar-cancelamento/", newsletter_solicitar_cancelamento, name="newsletter_solicitar_cancelamento"),
    path("newsletter/<slug:slug>/confirmar/<str:token>/", newsletter_confirmar, name="newsletter_confirmar"),
    path("newsletter/<slug:slug>/cancelar/<str:token>/", newsletter_cancelar, name="newsletter_cancelar"),
    path(
        "newsletter/<slug:slug>/solicitar-privacidade/",
        newsletter_solicitar_privacidade,
        name="newsletter_solicitar_privacidade",
    ),
    path(
        "newsletter/<slug:slug>/confirmar-exclusao-privacidade/<str:token>/",
        newsletter_confirmar_exclusao_privacidade,
        name="newsletter_confirmar_exclusao_privacidade",
    ),
    path(
        "indexador/<slug:page_slug>/registro/<slug:registro_slug>/",
        indexador_registro_detalhe,
        name="indexador_registro_detalhe",
    ),
    path(
        "indexador/<slug:page_slug>/exportar/",
        indexador_exportar_csv,
        name="indexador_exportar_csv",
    ),
    path("busca/", busca_publicacoes, name="busca_publicacoes"),
    path(
        "publicacao/<int:page_id>/pdf/",
        publicacao_pdf,
        name="publicacao_pdf",
    ),
    path("categorias/", categorias_index, name="categorias_index"),
    path("categorias/<slug:slug>/", categoria_detalhe, name="categoria_detalhe"),
    path("autores/", autores_index, name="autores_index"),
    path("autores/<slug:username>/", autor_detalhe, name="autor_detalhe"),
    path("tags/", tags_index, name="tags_index"),
    path("tags/<slug:slug>/", publicacoes_por_tag, name="publicacoes_por_tag"),
]
