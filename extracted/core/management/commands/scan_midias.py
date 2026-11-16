from django.core.management.base import BaseCommand
from core.media_pipeline.models import Inventory
from core.media_pipeline.scanner import MediaScanner
from core.media_pipeline.inventory import save_inventory
from core.media_pipeline.utils import validate_directory

class Command(BaseCommand):

    help = "Escaneia toda a biblioteca de mídias."

    def add_arguments(self, parser):

        parser.add_argument(
            "--path",
            required=True,
            help="Pasta raiz da biblioteca.",
        )

    def handle(self, *args, **options):

        pasta = validate_directory(options["path"])

        self.stdout.write("")
        self.stdout.write("=" * 50)
        self.stdout.write("FITFLIX MEDIA SCANNER")
        self.stdout.write("=" * 50)

        scanner = MediaScanner()

        inventory: Inventory = scanner.scan(pasta)

        save_inventory(
            inventory,
            "media_pipeline/inventario.json",
        )

        self.stdout.write("")
        total = len(inventory.media_files)

        self.stdout.write(
            self.style.SUCCESS(
                f"{total} arquivos encontrados."
            )
        )
