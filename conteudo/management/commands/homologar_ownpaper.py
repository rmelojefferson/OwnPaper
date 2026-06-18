from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.test import Client


class Command(BaseCommand):
    help = "Executa validação automática do OwnPaper (check, migrações, testes e smoke de rotas)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-tests",
            action="store_true",
            help="Pula a suíte de testes do app conteudo.",
        )
        parser.add_argument(
            "--skip-smoke",
            action="store_true",
            help="Pula verificação de rotas principais.",
        )
        parser.add_argument(
            "--allow-pending-migrations",
            action="store_true",
            help="Permite continuar mesmo com migrações pendentes.",
        )
        parser.add_argument(
            "--keepdb",
            action="store_true",
            help="Reaproveita banco de teste ao rodar a suíte.",
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando homologação automática...")

        self.stdout.write("1/4 Verificando configuração Django (`check`)...")
        call_command("check")

        self.stdout.write("2/4 Verificando migrações pendentes...")
        pendentes = self._migracoes_pendentes()
        if pendentes:
            mensagem = (
                "Migrações pendentes detectadas: "
                + ", ".join(f"{app}.{name}" for app, name in pendentes)
            )
            if options["allow_pending_migrations"]:
                self.stdout.write(self.style.WARNING(mensagem))
            else:
                raise CommandError(mensagem)
        else:
            self.stdout.write(self.style.SUCCESS("Sem migrações pendentes."))

        if not options["skip_tests"]:
            self.stdout.write("3/4 Executando testes (`conteudo`)...")
            kwargs = {"verbosity": 1, "interactive": False}
            if options["keepdb"]:
                kwargs["keepdb"] = True
            call_command("test", "conteudo", **kwargs)
        else:
            self.stdout.write("3/4 Testes ignorados por opção (`--skip-tests`).")

        if not options["skip_smoke"]:
            self.stdout.write("4/4 Executando smoke de rotas públicas/admin...")
            self._validar_rotas()
        else:
            self.stdout.write("4/4 Smoke ignorado por opção (`--skip-smoke`).")

        self.stdout.write(self.style.SUCCESS("Homologação automática concluída com sucesso."))

    def _migracoes_pendentes(self):
        connection = connections["default"]
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        plan = executor.migration_plan(targets)
        return [(migration.app_label, migration.name) for migration, backward in plan if not backward]

    def _validar_rotas(self):
        host = self._host_smoke()
        cliente = Client(HTTP_HOST=host, wsgi_url_scheme="https")
        rotas = [
            ("/", {200}),
            ("/busca/", {200}),
            ("/rss.xml", {200}),
            ("/feed/", {200}),
            ("/account/login/", {200}),
            ("/admin/", {200}),
        ]
        falhas = []
        for path, esperados in rotas:
            response = cliente.get(path, follow=True)
            if response.status_code not in esperados:
                final = response.redirect_chain[-1][0] if response.redirect_chain else path
                falhas.append(
                    f"{path} -> {response.status_code} final={final} "
                    f"(esperado: {sorted(esperados)})"
                )
        if falhas:
            raise CommandError("Falhas no smoke de rotas: " + " | ".join(falhas))
        self.stdout.write(self.style.SUCCESS("Smoke de rotas validado."))

    def _host_smoke(self):
        for host in settings.ALLOWED_HOSTS:
            if host and host not in {"*", "localhost", "127.0.0.1", "[::1]"}:
                return host
        return "testserver"
