import hashlib
import json

from django.db import migrations, models
from django.utils import timezone


HASH_VERSION = "ownpaper-audit-v1"


def valor_hash(valor):
    if valor is None:
        return ""
    if hasattr(valor, "isoformat"):
        return valor.isoformat()
    return str(valor)


def calcular_hash_log(log, sequencia, hash_anterior, assinado_em):
    payload = {
        "versao": HASH_VERSION,
        "sequencia": sequencia,
        "hash_anterior": hash_anterior or "",
        "usuario_id_ref": log.usuario_id_ref or "",
        "usuario_email": log.usuario_email or "",
        "usuario_username": log.usuario_username or "",
        "acao": log.acao or "",
        "alvo_tipo": log.alvo_tipo or "",
        "alvo_id": log.alvo_id or "",
        "alvo_repr": log.alvo_repr or "",
        "ip": log.ip or "",
        "detalhes": log.detalhes or "",
        "criado_em": valor_hash(log.criado_em),
        "assinado_em": valor_hash(assinado_em),
    }
    payload_json = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def criar_cadeia_logs(apps, schema_editor):
    AuditLog = apps.get_model("conteudo", "AuditLog")
    hash_anterior = ""
    agora = timezone.now()
    for sequencia, log in enumerate(AuditLog.objects.order_by("criado_em", "id").iterator(), start=1):
        assinado_em = log.assinado_em or log.criado_em or agora
        hash_registro = calcular_hash_log(log, sequencia, hash_anterior, assinado_em)
        AuditLog.objects.filter(pk=log.pk).update(
            sequencia=sequencia,
            hash_anterior=hash_anterior,
            hash_registro=hash_registro,
            assinado_em=assinado_em,
        )
        hash_anterior = hash_registro


def criar_trigger_append_only(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION conteudo_auditlog_append_only_guard()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'AuditLog is append-only: UPDATE is blocked';
            ELSIF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'AuditLog is append-only: DELETE is blocked';
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS conteudo_auditlog_append_only_guard
        ON conteudo_auditlog;
        """
    )
    schema_editor.execute(
        """
        CREATE TRIGGER conteudo_auditlog_append_only_guard
        BEFORE UPDATE OR DELETE ON conteudo_auditlog
        FOR EACH ROW EXECUTE FUNCTION conteudo_auditlog_append_only_guard();
        """
    )


def remover_trigger_append_only(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS conteudo_auditlog_append_only_guard
        ON conteudo_auditlog;
        """
    )
    schema_editor.execute("DROP FUNCTION IF EXISTS conteudo_auditlog_append_only_guard();")


class Migration(migrations.Migration):
    dependencies = [
        ("conteudo", "0124_confirmacao_autoria_publicacao_auditlog_append_only"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="criado_em",
            field=models.DateTimeField(db_index=True, default=timezone.now, editable=False, verbose_name="Criado em"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="assinado_em",
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name="Assinado em"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="hash_anterior",
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name="Hash anterior"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="hash_registro",
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name="Hash do registro"),
        ),
        migrations.AddField(
            model_name="auditlog",
            name="sequencia",
            field=models.PositiveBigIntegerField(blank=True, db_index=True, null=True, unique=True, verbose_name="Sequência"),
        ),
        migrations.RunPython(criar_cadeia_logs, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(criar_trigger_append_only, reverse_code=remover_trigger_append_only),
    ]
