from decimal import Decimal

from django.db import migrations


def seed(apps, schema_editor):
    apps.get_model("commercial", "Plan").objects.get_or_create(code="sandbox-team", version=1, defaults={"name": "Team trial", "currency": "NGN", "monthly_amount": Decimal("100.00"), "active_users": 10, "registered_assets": 250, "trial_days": 14, "is_public": True, "is_sandbox": True})


class Migration(migrations.Migration):
    dependencies = [("commercial", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
