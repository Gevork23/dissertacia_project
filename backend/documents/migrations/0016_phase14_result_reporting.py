from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0015_phase13_attempt_execution"),
    ]

    operations = [
        migrations.AddField(
            model_name="generatedquiz",
            name="llm_error_analysis",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="generatedquiz",
            name="llm_manager_summary",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="generatedquiz",
            name="llm_reporting_cache_key",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="generatedquiz",
            name="llm_reporting_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="generatedquiz",
            name="llm_reporting_model",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="quizattempt",
            name="llm_feedback",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="quizattempt",
            name="llm_feedback_cache_key",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="quizattempt",
            name="llm_feedback_generated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="quizattempt",
            name="llm_feedback_model",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
