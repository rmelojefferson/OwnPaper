# Generated manually for OwnPaper custom public code blocks.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _criar_codigo(Codigo, config, titulo, tipo, posicao, codigo, ordem, exigir_consentimento=False):
    codigo = (codigo or "").strip()
    if not codigo:
        return
    if Codigo.objects.filter(configuracao_site=config, titulo=titulo, codigo=codigo).exists():
        return
    Codigo.objects.create(
        configuracao_site=config,
        titulo=titulo,
        tipo=tipo,
        posicao=posicao,
        codigo=codigo,
        ativo=True,
        exigir_consentimento=exigir_consentimento,
        sort_order=ordem,
    )


def migrar_configuracoes_antigas(apps, schema_editor):
    ConfiguracaoSite = apps.get_model("conteudo", "ConfiguracaoSite")
    Codigo = apps.get_model("conteudo", "CodigoPersonalizadoSite")

    for config in ConfiguracaoSite.objects.all():
        ordem = 10
        google_verification = (getattr(config, "google_search_console_verification", "") or "").strip()
        if google_verification:
            _criar_codigo(
                Codigo,
                config,
                "Google Search Console - verificação",
                "html",
                "head",
                f'<meta name="google-site-verification" content="{google_verification}">',
                ordem,
            )
            ordem += 10

        meta_verification = (getattr(config, "meta_domain_verification", "") or "").strip()
        if meta_verification:
            _criar_codigo(
                Codigo,
                config,
                "Meta - verificação de domínio",
                "html",
                "head",
                f'<meta name="facebook-domain-verification" content="{meta_verification}">',
                ordem,
            )
            ordem += 10

        _criar_codigo(
            Codigo,
            config,
            "Verificação avançada no head",
            "html",
            "head",
            getattr(config, "verificacao_head_html", ""),
            ordem,
        )
        ordem += 10

        arquivo_nome = (getattr(config, "verificacao_arquivo_nome", "") or "").strip()
        arquivo_conteudo = (getattr(config, "verificacao_arquivo_conteudo", "") or "").strip()
        if arquivo_conteudo:
            _criar_codigo(
                Codigo,
                config,
                f"Arquivo HTML importado - {arquivo_nome or 'verificação'}",
                "html",
                "head",
                arquivo_conteudo,
                ordem,
            )
            ordem += 10

        gtm_id = (getattr(config, "google_tag_manager_id", "") or "").strip()
        if gtm_id:
            _criar_codigo(
                Codigo,
                config,
                "Google Tag Manager",
                "html",
                "head",
                """<script>
(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','%s');
</script>""" % gtm_id,
                ordem,
                exigir_consentimento=True,
            )
            ordem += 10

        ga_id = (getattr(config, "google_analytics_id", "") or "").strip()
        if ga_id:
            _criar_codigo(
                Codigo,
                config,
                "Google Analytics",
                "html",
                "head",
                """<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', '%s');
</script>""" % (ga_id, ga_id),
                ordem,
                exigir_consentimento=True,
            )
            ordem += 10

        meta_pixel_id = (getattr(config, "meta_pixel_id", "") or "").strip()
        if meta_pixel_id:
            _criar_codigo(
                Codigo,
                config,
                "Meta Pixel",
                "html",
                "head",
                """<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '%s');
fbq('track', 'PageView');
</script>""" % meta_pixel_id,
                ordem,
                exigir_consentimento=True,
            )
            ordem += 10

        plausible_url = (getattr(config, "plausible_script_url", "") or "").strip()
        plausible_domain = (getattr(config, "plausible_domain", "") or "").strip()
        plausible_direct = bool(getattr(config, "plausible_script_direto_ativo", False))
        plausible_no_consent = bool(getattr(config, "plausible_sem_consentimento_ativo", False))
        if plausible_url and plausible_direct:
            _criar_codigo(
                Codigo,
                config,
                "Plausible",
                "html",
                "head",
                """<script async src="%s"></script>
<script>
window.plausible = window.plausible || function(){(plausible.q = plausible.q || []).push(arguments);};
plausible.init = plausible.init || function(i){plausible.o = i || {};};
plausible.init();
</script>""" % plausible_url,
                ordem,
                exigir_consentimento=not plausible_no_consent,
            )
            ordem += 10
        elif plausible_url and plausible_domain:
            _criar_codigo(
                Codigo,
                config,
                "Plausible",
                "html",
                "head",
                f'<script defer data-domain="{plausible_domain}" src="{plausible_url}"></script>',
                ordem,
                exigir_consentimento=not plausible_no_consent,
            )
            ordem += 10

        umami_id = (getattr(config, "umami_website_id", "") or "").strip()
        umami_url = (getattr(config, "umami_script_url", "") or "").strip()
        if umami_id and umami_url:
            _criar_codigo(
                Codigo,
                config,
                "Umami",
                "html",
                "head",
                f'<script defer data-website-id="{umami_id}" src="{umami_url}"></script>',
                ordem,
                exigir_consentimento=True,
            )
            ordem += 10

        matomo_id = (getattr(config, "matomo_site_id", "") or "").strip()
        matomo_url = (getattr(config, "matomo_url", "") or "").strip()
        if matomo_id and matomo_url:
            base = matomo_url.rstrip("/") + "/"
            _criar_codigo(
                Codigo,
                config,
                "Matomo",
                "html",
                "head",
                """<script>
var _paq = window._paq = window._paq || [];
_paq.push(['trackPageView']);
_paq.push(['enableLinkTracking']);
(function() {
  var u = '%s';
  _paq.push(['setTrackerUrl', u + 'matomo.php']);
  _paq.push(['setSiteId', '%s']);
  var d=document, g=d.createElement('script'), s=d.getElementsByTagName('script')[0];
  g.async=true; g.src=u+'matomo.js'; s.parentNode.insertBefore(g,s);
})();
</script>""" % (base, matomo_id),
                ordem,
                exigir_consentimento=True,
            )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("conteudo", "0144_integracoes_verificacao_avancada"),
    ]

    operations = [
        migrations.CreateModel(
            name="CodigoPersonalizadoSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=120, verbose_name="Nome do bloco")),
                ("descricao", models.CharField(blank=True, max_length=255, verbose_name="Descrição/observação")),
                ("tipo", models.CharField(choices=[("html", "HTML"), ("js", "JavaScript"), ("css", "CSS")], default="html", max_length=10, verbose_name="Tipo")),
                ("posicao", models.CharField(choices=[("head", "Cabeçalho/head"), ("body_inicio", "Início do body"), ("body_fim", "Final do body/rodapé")], default="head", max_length=20, verbose_name="Local de inserção")),
                ("codigo", models.TextField(verbose_name="Código")),
                ("ativo", models.BooleanField(default=True, verbose_name="Ativo")),
                ("exigir_consentimento", models.BooleanField(default=False, help_text="Quando ativo, o bloco só é renderizado após o visitante aceitar cookies opcionais.", verbose_name="Exigir aceite de cookies opcionais")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Ordem")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("atualizado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Atualizado por")),
                ("configuracao_site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codigos_personalizados", to="conteudo.configuracaosite", verbose_name="Configuração do site")),
                ("criado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="Criado por")),
            ],
            options={
                "verbose_name": "Código personalizado",
                "verbose_name_plural": "Códigos personalizados",
                "ordering": ["sort_order", "titulo", "id"],
            },
        ),
        migrations.RunPython(migrar_configuracoes_antigas, migrations.RunPython.noop),
        migrations.RemoveField(model_name="configuracaosite", name="google_search_console_verification"),
        migrations.RemoveField(model_name="configuracaosite", name="meta_domain_verification"),
        migrations.RemoveField(model_name="configuracaosite", name="verificacao_head_html"),
        migrations.RemoveField(model_name="configuracaosite", name="verificacao_arquivo_nome"),
        migrations.RemoveField(model_name="configuracaosite", name="verificacao_arquivo_conteudo"),
        migrations.RemoveField(model_name="configuracaosite", name="google_analytics_id"),
        migrations.RemoveField(model_name="configuracaosite", name="google_tag_manager_id"),
        migrations.RemoveField(model_name="configuracaosite", name="meta_pixel_id"),
        migrations.RemoveField(model_name="configuracaosite", name="plausible_domain"),
        migrations.RemoveField(model_name="configuracaosite", name="plausible_script_url"),
        migrations.RemoveField(model_name="configuracaosite", name="plausible_script_direto_ativo"),
        migrations.RemoveField(model_name="configuracaosite", name="plausible_sem_consentimento_ativo"),
        migrations.RemoveField(model_name="configuracaosite", name="umami_website_id"),
        migrations.RemoveField(model_name="configuracaosite", name="umami_script_url"),
        migrations.RemoveField(model_name="configuracaosite", name="matomo_site_id"),
        migrations.RemoveField(model_name="configuracaosite", name="matomo_url"),
    ]
