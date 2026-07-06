from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("trainees", "0011_customfield_key_autogen"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customfield",
            name="label",
            field=models.CharField(max_length=150, verbose_name="اسم العمود"),
        ),
        migrations.AlterField(
            model_name="customfield",
            name="order",
            field=models.PositiveIntegerField(default=0, verbose_name="الترتيب"),
        ),
        migrations.AlterModelOptions(
            name="customfield",
            options={"ordering": ["program", "order", "id"]},
        ),
    ]
