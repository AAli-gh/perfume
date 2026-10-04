# تصمیم‌های معماری (ADR)

هر سند یک تصمیم مهم را ثبت می‌کند: زمینه، تصمیم و پیامدها. تصمیم‌ها پاک نمی‌شوند. اگر تصمیمی عوض شد، ADR جدیدی نوشته می‌شود که به قبلی ارجاع می‌دهد و وضعیت قبلی «جایگزین‌شده» می‌شود.

| # | تصمیم | وضعیت |
|---|---|---|
| 0001 | [Modular Monolith با Django](0001-modular-monolith.md) | پذیرفته‌شده |
| 0002 | [چندفروشگاهی با کلید خارجی Store (یک دیتابیس، schema مشترک)](0002-tenant-by-store-fk.md) | پذیرفته‌شده |
| 0003 | [لایه پوسته جدا از اپ‌ها با Template Loader اختصاصی](0003-theme-layer-and-loader.md) | پذیرفته‌شده |
| 0004 | [Design Token‌ها به‌صورت CSS Variables، بدون build دوباره CSS](0004-design-tokens-css-variables.md) | پذیرفته‌شده |
| 0005 | [بخش‌های صفحه: JSON با schema فرم Django و registry](0005-sections-schema-as-django-forms.md) | پذیرفته‌شده |
| 0006 | [پیش‌نویس با ردیف‌های draft، انتشار اتمیک و Revision](0006-drafts-and-revisions.md) | پذیرفته‌شده |
| 0007 | [HTMX و Django Templates به‌جای SPA](0007-htmx-progressive-enhancement.md) | پذیرفته‌شده |
| 0008 | [ماندن روی Tailwind CSS 3](0008-stay-on-tailwind-3.md) | پذیرفته‌شده |
| 0009 | [CSP اعمال‌شده با nonce، و rate limit با پنجره لغزان در cache](0009-csp-nonce-and-rate-limit.md) | پذیرفته‌شده |
| 0010 | [لایه AI اختیاری، جدا از هسته، با تأیید انسانی](0010-optional-ai-layer.md) | پذیرفته‌شده |
| 0011 | [جستجو با PostgreSQL به‌جای Elasticsearch](0011-postgres-search.md) | پذیرفته‌شده |
| 0012 | [موجودی با دفتر و قفل ردیف، چرخه وضعیت، و درگاه‌ها با Adapter](0012-orders-inventory-payments.md) | پذیرفته‌شده |
| 0013 | [image production: lock با hash، کاربر غیر root، فایل‌سیستم فقط‌خواندنی، migrate جدا](0013-production-image.md) | پذیرفته‌شده |
