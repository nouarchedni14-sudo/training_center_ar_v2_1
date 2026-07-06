from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="تمهين",
                    name="الرقم_التعريفي",
                    field=models.CharField(db_index=True, max_length=50, verbose_name="الرقم التعريفي"),
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterField(
            model_name="تمهين",
            name="رقم_الهاتف",
            field=models.CharField(db_index=True, max_length=30, verbose_name="رقم الهاتف"),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="حضوري_أولي",
                    name="الرقم_التعريفي",
                    field=models.CharField(db_index=True, max_length=50, verbose_name="الرقم التعريفي"),
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterField(
            model_name="حضوري_أولي",
            name="رقم_الهاتف",
            field=models.CharField(db_index=True, max_length=30, verbose_name="رقم الهاتف"),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="مسائي_ومعابر",
                    name="الرقم_التعريفي",
                    field=models.CharField(db_index=True, max_length=50, verbose_name="الرقم التعريفي"),
                ),
            ],
            database_operations=[],
        ),
        migrations.AlterField(
            model_name="مسائي_ومعابر",
            name="رقم_الهاتف",
            field=models.CharField(db_index=True, max_length=30, verbose_name="رقم الهاتف"),
        ),
    ]
