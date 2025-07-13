from django.core.management.base import BaseCommand
from prediction_engine.build_dataset import build_dataset
from prediction_engine.train_model import train_model
from prediction_engine.train_goals_model import train_goals_model

class Command(BaseCommand):
    help = "Build dataset and train both match result and goal prediction models."

    def handle(self, *args, **kwargs):
        self.stdout.write("Building dataset...")
        df = build_dataset()

        self.stdout.write(f"Dataset built: {df.shape[0]} rows, {df.shape[1]} columns.")

        self.stdout.write("Training match result model...")
        train_model(df=df)

        self.stdout.write("Training goal prediction model...")
        train_goals_model(df=df)

        self.stdout.write(self.style.SUCCESS("All models trained and saved successfully."))
