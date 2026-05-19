from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from documents.ruslawod.process_dataset import import_ruslawod_documents


class Command(BaseCommand):
    help = "Download, cache and import the RusLawOD dataset into RusLawODDocument."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=None)
        parser.add_argument("--cache-dir", type=str, default=None)
        parser.add_argument(
            "--force-download",
            action="store_true",
            help="Ignore local XML cache and download rows again.",
        )

    def handle(self, *args, **options):
        cache_dir = options["cache_dir"]
        if cache_dir:
            cache_dir = str(Path(cache_dir).resolve())

        try:
            stats = import_ruslawod_documents(
                cache_dir=cache_dir,
                limit=options["limit"],
                force_download=options["force_download"],
            )
        except ImportError as exc:
            raise CommandError(
                "RusLawOD import requires the 'datasets' and 'tqdm' packages."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "RusLawOD import completed: "
                f"processed={stats['processed']}, "
                f"created={stats['created']}, updated={stats['updated']}"
            )
        )
