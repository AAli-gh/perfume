# WSGI نسخه نمایشی عطر مجد روی PythonAnywhere (جایگزین /var/www/<user>_pythonanywhere_com_wsgi.py).
# تنظیمات و رازها از ~/majd-data/.env (لینک‌شده به ~/majd/.env) خوانده می‌شوند، نه از این فایل.
import os
import sys

project_home = os.path.expanduser("~/majd")
if project_home not in sys.path:
    sys.path.insert(0, project_home)
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.pythonanywhere"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
