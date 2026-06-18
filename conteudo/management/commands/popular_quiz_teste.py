from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from conteudo.models import (
    Categoria,
    PerguntaQuizCatalogo,
    PublicacaoPage,
    PublicacaoPerguntaQuizCatalogo,
    QuizEstudoPage,
    QuizOpcaoPerguntaCatalogo,
    TagPublicacao,
)


PUBLICATION_QUESTIONS = [
    {
        "theme": "Geografia",
        "tag": "capitais",
        "question": "Qual é a capital da Austrália?",
        "options": [
            ("Sydney", False),
            ("Melbourne", False),
            ("Canberra", True),
            ("Perth", False),
        ],
        "explanation": "Canberra foi planejada como capital federal da Austrália.",
    },
    {
        "theme": "Ciência",
        "tag": "astronomia",
        "question": "Qual planeta é conhecido como Planeta Vermelho?",
        "options": [
            ("Vênus", False),
            ("Marte", True),
            ("Júpiter", False),
            ("Mercúrio", False),
        ],
        "explanation": "Marte recebe esse nome por causa da coloração avermelhada de sua superfície.",
    },
    {
        "theme": "História",
        "tag": "brasil",
        "question": "Em que ano ocorreu a Independência do Brasil?",
        "options": [
            ("1808", False),
            ("1822", True),
            ("1889", False),
            ("1891", False),
        ],
        "explanation": "A Independência do Brasil foi proclamada em 1822 por Dom Pedro I.",
    },
    {
        "theme": "Literatura",
        "tag": "autores",
        "question": "Quem escreveu o romance 'Dom Casmurro'?",
        "options": [
            ("José de Alencar", False),
            ("Machado de Assis", True),
            ("Clarice Lispector", False),
            ("Graciliano Ramos", False),
        ],
        "explanation": "Machado de Assis publicou 'Dom Casmurro' em 1899.",
    },
    {
        "theme": "Atualidades",
        "tag": "tecnologia",
        "question": "Qual tecnologia é usada para registrar blocos encadeados e imutáveis de transações?",
        "options": [
            ("Bluetooth", False),
            ("Blockchain", True),
            ("Wi-Fi", False),
            ("NFC", False),
        ],
        "explanation": "Blockchain mantém um registro distribuído e encadeado de transações.",
    },
]

CATALOG_QUESTIONS = [
    {
        "theme": "Geografia",
        "tag": "oceanos",
        "question": "Qual é o maior oceano da Terra?",
        "options": [
            ("Atlântico", False),
            ("Índico", False),
            ("Pacífico", True),
            ("Ártico", False),
        ],
        "explanation": "O oceano Pacífico é o maior em extensão superficial.",
    },
    {
        "theme": "Ciência",
        "tag": "biologia",
        "question": "Qual estrutura celular contém o material genético na maioria dos organismos eucariontes?",
        "options": [
            ("Mitocôndria", False),
            ("Núcleo", True),
            ("Ribossomo", False),
            ("Lisossomo", False),
        ],
        "explanation": "Nos eucariontes, o DNA fica majoritariamente armazenado no núcleo.",
    },
    {
        "theme": "História",
        "tag": "segunda_guerra",
        "question": "A Segunda Guerra Mundial terminou em que ano?",
        "options": [
            ("1942", False),
            ("1945", True),
            ("1948", False),
            ("1950", False),
        ],
        "explanation": "A guerra terminou em 1945, com a rendição do Japão.",
    },
    {
        "theme": "Literatura",
        "tag": "poesia",
        "question": "Quem escreveu 'Os Lusíadas'?",
        "options": [
            ("Fernando Pessoa", False),
            ("Camões", True),
            ("Eça de Queirós", False),
            ("Bocage", False),
        ],
        "explanation": "'Os Lusíadas' é a principal epopeia de Luís de Camões.",
    },
    {
        "theme": "Atualidades",
        "tag": "sustentabilidade",
        "question": "Qual fonte de energia utiliza diretamente a radiação do Sol?",
        "options": [
            ("Solar", True),
            ("Eólica", False),
            ("Geotérmica", False),
            ("Hidrelétrica", False),
        ],
        "explanation": "A energia solar converte a radiação do Sol em eletricidade ou calor.",
    },
]


class Command(BaseCommand):
    help = "Limpa e repovoa a base de teste do quiz com perguntas de conhecimentos gerais."

    @staticmethod
    def _categoria_editorial(theme_name):
        slug = slugify(theme_name)
        categoria, _ = Categoria.objects.get_or_create(
            slug=slug,
            defaults={"nome": theme_name},
        )
        if categoria.nome != theme_name:
            categoria.nome = theme_name
            categoria.save(update_fields=["nome"])
        return categoria

    @staticmethod
    def _tag_editorial(tag_slug):
        nome = tag_slug.replace("_", " ").replace("-", " ").title()
        tag, _ = TagPublicacao.objects.get_or_create(
            slug=tag_slug,
            defaults={"name": nome},
        )
        if tag.name != nome:
            tag.name = nome
            tag.save(update_fields=["name"])
        return tag

    def handle(self, *args, **options):
        publicacoes = list(
            PublicacaoPage.objects.live()
            .public()
            .order_by("-first_published_at", "-id")[:5]
        )
        if len(publicacoes) < 5:
            raise CommandError("São necessárias pelo menos 5 publicações públicas para popular o quiz.")

        quiz_page = QuizEstudoPage.objects.live().public().first()
        if not quiz_page:
            raise CommandError("Nenhuma página de quiz pública foi encontrada.")

        with transaction.atomic():
            PublicacaoPerguntaQuizCatalogo.objects.all().delete()
            PerguntaQuizCatalogo.objects.all().delete()

            for publication, offset in zip(publicacoes, range(len(publicacoes))):
                trio = [
                    PUBLICATION_QUESTIONS[offset % len(PUBLICATION_QUESTIONS)],
                    PUBLICATION_QUESTIONS[(offset + 1) % len(PUBLICATION_QUESTIONS)],
                    PUBLICATION_QUESTIONS[(offset + 2) % len(PUBLICATION_QUESTIONS)],
                ]
                categoria_publicacao = self._categoria_editorial(trio[0]["theme"])
                tags_publicacao = [self._tag_editorial(entry["tag"]) for entry in trio]
                PublicacaoPage.objects.filter(pk=publication.pk).update(
                    quiz_habilitado=True,
                    categoria_principal=categoria_publicacao,
                )
                publication.refresh_from_db(fields=["quiz_habilitado", "categoria_principal"])
                publication.tags.set(tags_publicacao)
                publication.save()
                for entry in trio:
                    question = PerguntaQuizCatalogo.objects.create(
                        pergunta=entry["question"],
                        explicacao=entry["explanation"],
                        exigir_todas_corretas=True,
                        ativa=True,
                        categoria_editorial=self._categoria_editorial(entry["theme"]),
                    )
                    question.tags_editoriais.set([self._tag_editorial(entry["tag"])])
                    for text, correct in entry["options"]:
                        QuizOpcaoPerguntaCatalogo.objects.create(
                            pergunta=question,
                            texto=text,
                            correta=correct,
                        )
                    PublicacaoPerguntaQuizCatalogo.objects.create(
                        publicacao=publication,
                        pergunta=question,
                    )

            for entry in CATALOG_QUESTIONS:
                question = PerguntaQuizCatalogo.objects.create(
                    pergunta=entry["question"],
                    explicacao=entry["explanation"],
                    exigir_todas_corretas=True,
                    ativa=True,
                    categoria_editorial=self._categoria_editorial(entry["theme"]),
                )
                question.tags_editoriais.set([self._tag_editorial(entry["tag"])])
                for text, correct in entry["options"]:
                    QuizOpcaoPerguntaCatalogo.objects.create(
                        pergunta=question,
                        texto=text,
                        correta=correct,
                    )

            quiz_page.itens_por_sessao = 20
            quiz_page.save(update_fields=["itens_por_sessao"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Quiz repovoado com {len(publicacoes) * 3} perguntas vinculadas às publicações e {len(CATALOG_QUESTIONS)} perguntas criadas diretamente no catálogo."
            )
        )
