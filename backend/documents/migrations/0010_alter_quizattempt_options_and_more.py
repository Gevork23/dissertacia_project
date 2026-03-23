import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0009_document_current_version_document_document_key_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="quizattempt",
            options={"ordering": ["-created_at"]},
        ),
        migrations.RemoveConstraint(
            model_name="answer",
            name="uniq_attempt_question_answer",
        ),
        migrations.AlterField(
            model_name="choice",
            name="order",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="document",
            name="document_key",
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                editable=False,
                help_text="Устойчивый идентификатор документа внутри системы.",
                max_length=160,
                null=True,
                unique=True,
                verbose_name="Ключ документа",
            ),
        ),
        migrations.AlterField(
            model_name="generatedquiz",
            name="payload",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="question",
            name="order",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name="question",
            name="question_type",
            field=models.CharField(
                choices=[
                    ("single_choice", "Один вариант"),
                    ("multiple_choice", "Несколько вариантов"),
                    ("true_false", "Верно/Неверно"),
                    ("text", "Текстовый ответ"),
                ],
                default="single_choice",
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="answers",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="employee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="quiz_attempts",
                to="documents.employee",
            ),
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="participant_name",
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name="quizattempt",
            name="status",
            field=models.CharField(
                choices=[
                    ("in_progress", "В процессе"),
                    ("completed", "Завершён"),
                ],
                default="in_progress",
                max_length=16,
            ),
        ),
        migrations.AddConstraint(
            model_name="answer",
            constraint=models.UniqueConstraint(
                fields=("attempt", "question"),
                name="uniq_answer_per_attempt_question",
            ),
        ),
    ]
