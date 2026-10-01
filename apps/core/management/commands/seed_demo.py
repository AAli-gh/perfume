"""داده‌های نمایشی فروشگاه: برندها، کالکشن‌ها، محصولات، نظرات، مقالات و کدهای تخفیف.

اجرا:  python manage.py seed_demo          (فقط موارد جدید ساخته می‌شوند)
       python manage.py seed_demo --reset  (حذف داده‌های کاتالوگ و مجله و ساخت دوباره)
"""

from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.blog.models import Category, Post
from apps.catalog.models import Brand, Collection, Product, ProductImage, ProductVariant, Review, ScentFamily
from apps.orders.models import Coupon

IMAGES = Path(settings.BASE_DIR) / "seed" / "images"

BRANDS = {"luxury": "لاکچری اسنس", "royal": "رویال عود", "eternal": "اترنال آروما", "mystic": "میستیک اورا"}
SCENTS = {"floral": "گُلی", "woody": "چوبی", "oriental": "شرقی", "fresh": "خنک و تازه", "spicy": "تند و ادویه‌ای"}

COLLECTIONS = [
    ("elegant", "کالکشن گنجینه‌های فاخر", "بطری‌های کریستالی با رایحه‌های اصیل و ماندگار", "col-elegant.jpg", False),
    ("royal", "کالکشن جوهر سلطنتی", "عصاره‌ای از شکوه دربارهای شرق", "col-royal.jpg", False),
    ("exotic", "کالکشن رویاهای اگزوتیک", "ظرافت مدرن برای روزهای خاص", "col-exotic.jpg", False),
    ("oud", "کالکشن عود جاودان", "عمیق‌ترین نت‌های عود و چوب‌های کمیاب", "col-oud.jpg", True),
    ("floral", "کالکشن سمفونی گل‌ها", "رقص گل‌های بهاری در یک بطری", "col-floral.jpg", True),
]

# slug, name, brand, scent, collection, price(50ml), featured, notes(top, mid, base), description
PRODUCTS = [
    ("arabesque", "الیکسیر عربسک", "luxury", "oriental", "royal", 3_900_000, False,
     ("برگاموت، هل", "گل رز دمشقی، زعفران", "عنبر، مشک"),
     "الیکسیر عربسک ترکیبی شرقی و گرم است که با هل تازه آغاز می‌شود و در دل خود رز دمشقی و زعفران را پنهان کرده؛ پایانی از عنبر و مشک، ردپایی باشکوه از شما به جا می‌گذارد."),
    ("golden-royale", "رویال طلایی", "royal", "oriental", "royal", 4_600_000, True,
     ("نارنگی، زعفران", "عسل، یاس", "وانیل، چوب صندل"),
     "رویال طلایی درخششی عسلی و گرم دارد؛ رایحه‌ای برای شب‌های مهمانی که با نارنگی و زعفران باز می‌شود و با وانیل و صندل آرام می‌گیرد."),
    ("mystic-oud", "عود رازآلود", "eternal", "woody", "oud", 5_200_000, True,
     ("برگاموت، زعفران، میخک", "قلب عود، یاس، رز", "عنبر، وانیل، مشک"),
     "عود رازآلود ترکیبی استادانه از بهترین مواد اولیه است؛ برای کسانی که عمق رایحه‌های شرقی را ارج می‌نهند. این عطر با برگاموت تازه، زعفران اگزوتیک و میخک تند آغاز می‌شود، سپس قلبی غنی از چوب عود کمیاب، یاس لطیف و رز عاشقانه را آشکار می‌کند و در نهایت با پایه‌ای مجلل از عنبر گرم، وانیل خامه‌ای و مشک، ردپایی ماندگار و افسون‌کننده بر جای می‌گذارد."),
    ("eclipse-noir", "کسوف سیاه", "mystic", "oriental", "oud", 4_900_000, False,
     ("فلفل صورتی، لیمو", "بخور، چرم", "عود، پچولی"),
     "کسوف سیاه رایحه‌ای مرموز و تیره است؛ بخور و چرم در قلب آن با عود و پچولی درهم می‌آمیزند تا حضوری فراموش‌نشدنی بسازند."),
    ("radiant-amber", "کهربای درخشان", "luxury", "oriental", "elegant", 3_600_000, False,
     ("پرتقال تلخ، دارچین", "کهربا، گل ارکیده", "تونکا، وانیل"),
     "کهربای درخشان گرمای غروب را در خود دارد؛ دارچین و پرتقال تلخ در آغاز و کهربای شیرین و تونکا در پایان."),
    ("serenity-blossom", "شکوفه آرامش", "luxury", "floral", "floral", 3_200_000, True,
     ("گلابی، برگ بنفشه", "بابونه، یاس سفید", "مشک سفید، خزه"),
     "شکوفه آرامش همچون قدم زدن در دشتی از بابونه‌هاست؛ سبک، لطیف و آرامش‌بخش برای استفاده روزانه."),
    ("royal-black", "سیاه سلطنتی", "royal", "spicy", "royal", 5_500_000, False,
     ("فلفل سیاه، زنجبیل", "میخک، گل شب‌بو", "عود، چرم"),
     "سیاه سلطنتی رایحه‌ای مقتدر و تند است؛ فلفل سیاه و زنجبیل در کنار چرم و عود، شخصیتی قاطع و باوقار می‌سازند."),
    ("aqua-inferno", "آکوا اینفرنو", "mystic", "fresh", "exotic", 3_400_000, False,
     ("نت‌های دریایی، لیمو", "اسطوخودوس، نعناع", "چوب سدر، عنبر"),
     "آکوا اینفرنو تضاد آب و آتش است؛ تازگی نت‌های دریایی با گرمای سدر و عنبر در یک رایحه پرانرژی."),
    ("royal-saffron", "زعفران شاهانه", "luxury", "spicy", "oud", 5_800_000, True,
     ("زعفران، هل", "رز طائفی، عود", "عنبر، چوب صندل"),
     "زعفران شاهانه ادای احترامی به طلای سرخ ایران است؛ زعفران ناب در کنار رز طائفی و عود، رایحه‌ای درباری و کم‌نظیر خلق کرده است."),
    ("amber-night", "شب کهربایی", "eternal", "oriental", "elegant", 4_200_000, False,
     ("آلو، دارچین", "کهربا، گل مریم", "وانیل، بنزوئین"),
     "شب کهربایی رایحه‌ای مخملی برای شب‌های سرد است؛ آلوی شیرین و گل مریم بر بستری از وانیل و بنزوئین."),
    ("cobalt-flame", "شعله کبالت", "mystic", "fresh", "exotic", 3_800_000, False,
     ("گریپ‌فروت، نعناع", "ژرانیوم، فلفل", "وتیور، مشک"),
     "شعله کبالت ترکیبی جسورانه از مرکبات خنک و ادویه‌های گرم است؛ مناسب روزهای پرتکاپو."),
    ("velvet-oud", "عود مخملی", "royal", "woody", "exotic", 4_400_000, False,
     ("زعفران، تمشک", "رز، عود", "مشک، چوب کشمیر"),
     "عود مخملی نسخه‌ای نرم و مدرن از عود است؛ تمشک و رز، تندی عود را لطیف کرده‌اند تا رایحه‌ای مخملی و دلنشین به دست آید."),
]
PRODUCT_IMAGES = {
    "arabesque": "p-arabesque.jpg", "golden-royale": "p-golden.jpg", "mystic-oud": "p-mystic.jpg",
    "eclipse-noir": "p-eclipse.jpg", "radiant-amber": "p-radiant.jpg", "serenity-blossom": "p-serenity.jpg",
    "royal-black": "p-royalblack.jpg", "aqua-inferno": "p-aqua.jpg", "royal-saffron": "p-saffron.jpg",
    "amber-night": "p-ambernight.jpg", "cobalt-flame": "p-cobalt.jpg", "velvet-oud": "p-velvet.jpg",
}
GALLERY = {"mystic-oud": ["product-main.jpg", "p-eclipse.jpg"]}

REVIEWS = [
    ("سارا", 5, "ماندگاری فوق‌العاده‌ای دارد و تا شب رایحه‌اش حس می‌شود."),
    ("امیر", 5, "بسته‌بندی بسیار شیک و رایحه‌ای کاملاً خاص. پیشنهاد می‌کنم."),
    ("نگار", 4, "خیلی خوش‌بوست، فقط کاش حجم بزرگ‌ترش هم تخفیف داشت."),
    ("حمید", 5, "هدیه خریدم و خیلی مورد پسند قرار گرفت."),
    ("مریم", 4, "پخش بوی خوبی دارد، برای شب عالی است."),
]

CATEGORIES = {"tips": "نکات عطرشناسی", "insights": "دانستنی‌های رایحه", "lifestyle": "سبک زندگی لوکس", "brand": "داستان برند"}

POSTS = [
    ("layering", "هنر لایه‌بندی عطر: چگونه رایحه امضای خود را بسازید", "tips", "blog-1.jpg", 0,
     "راز ترکیب عطرها برای ساختن رایحه‌ای منحصربه‌فرد که در طول روز به زیبایی تغییر می‌کند.",
     """لایه‌بندی عطر یعنی استفاده هم‌زمان از دو یا چند رایحه برای ساختن ترکیبی شخصی. این کار به شما امکان می‌دهد عطری داشته باشید که دقیقاً مثل خودتان باشد.

## از سنگین به سبک

همیشه ابتدا عطر سنگین‌تر (مثل عود یا عنبر) را بزنید و سپس عطر سبک‌تر (گلی یا مرکباتی) را روی آن اسپری کنید. این ترتیب اجازه می‌دهد هر دو رایحه دیده شوند.

## خانواده‌های هماهنگ

رایحه‌های شرقی با چوبی، و گلی با مرکباتی معمولاً هماهنگ‌اند. برای شروع، یک عطر عود مانند «عود رازآلود» را با یک رایحه گلی سبک مثل «شکوفه آرامش» امتحان کنید.

## کمتر، بیشتر است

در لایه‌بندی، از هر عطر کمتر از همیشه استفاده کنید تا ترکیب نهایی سنگین و خفه‌کننده نشود."""),
    ("history-of-perfume", "سفری در تاریخ عطر", "insights", "blog-2.jpg", 10,
     "از تمدن‌های باستان تا دوران مدرن؛ داستان عطر و نقشی که رایحه‌ها در فرهنگ‌های جهان داشته‌اند.",
     """تاریخ عطر به هزاران سال پیش بازمی‌گردد؛ زمانی که بخور و رزین‌های معطر در آیین‌ها سوزانده می‌شدند.

## ایران و گلاب

ابن‌سینا، دانشمند ایرانی، با بهبود روش تقطیر، استخراج گلاب از گل محمدی را متحول کرد و راه را برای عطرسازی مدرن هموار ساخت.

## از شرق تا غرب

جاده ابریشم عود، مشک و زعفران را به اروپا برد و عطرسازان فرانسوی قرن‌ها بعد این مواد را در شاهکارهای خود به کار گرفتند."""),
    ("perfume-for-every-occasion", "انتخاب عطر مناسب برای هر موقعیت", "tips", "blog-3.jpg", 20,
     "یاد بگیرید برای هر رویداد، از یک شب عاشقانه تا جلسه کاری یا یک روز معمولی، چه عطری انتخاب کنید.",
     """عطر بخشی از پوشش شماست و مانند لباس باید با موقعیت هماهنگ باشد.

## محیط کار

رایحه‌های سبک، تمیز و خنک مثل «آکوا اینفرنو» انتخاب بهتری برای فضای کاری هستند.

## شب و مهمانی

برای شب، عطرهای گرم و شرقی مانند «شب کهربایی» یا «رویال طلایی» جلوه بیشتری دارند.

## روزهای تعطیل

عطرهای گلی و شاداب مثل «شکوفه آرامش» حس سبکی و آرامش را منتقل می‌کنند."""),
    ("behind-the-scenes", "پشت صحنه: ساخت عطرهای لوکس", "brand", "blog-4.jpg", 28,
     "نگاهی به فرایند پیچیده خلق یک عطر لوکس؛ از تهیه مواد اولیه کمیاب تا فرمولاسیون نهایی.",
     """خلق هر عطر در عطر مجد ماه‌ها زمان می‌برد و از انتخاب دقیق مواد اولیه آغاز می‌شود.

## مواد اولیه

عود را از جنوب شرق آسیا، زعفران را از خراسان و گل محمدی را از کاشان تهیه می‌کنیم.

## فرمولاسیون

عطرساز ما ده‌ها نسخه آزمایشی می‌سازد تا توازن کامل میان نت‌های آغازین، میانی و پایه به دست آید.

## بلوغ

پس از ترکیب، عطر چند هفته در مکانی تاریک استراحت می‌کند تا رایحه‌ها به‌طور کامل با هم درآمیزند."""),
    ("oud-guide", "راهنمای کامل عود؛ طلای مایع شرق", "insights", "col-oud.jpg", 35,
     "عود چیست، چرا این‌قدر ارزشمند است و چگونه یک عطر عود باکیفیت را تشخیص دهیم؟",
     """عود از رزین درخت آگار به دست می‌آید؛ رزینی که درخت در واکنش به یک قارچ خاص تولید می‌کند و همین کمیابی، ارزش آن را بالا برده است.

## تشخیص کیفیت

عود باکیفیت رایحه‌ای لایه‌لایه دارد که در طول ساعت‌ها تغییر می‌کند؛ از دودی و چوبی تا شیرین و چرمی."""),
    ("perfume-lifestyle", "عطر و سبک زندگی لوکس", "lifestyle", "p-velvet.jpg", 48,
     "چطور عطر را به بخشی از آیین روزانه خود تبدیل کنیم و از آن بیشترین لذت را ببریم.",
     """عطر فقط یک رایحه نیست؛ لحظه‌ای برای توجه به خود است.

## نگهداری صحیح

عطر را دور از نور مستقیم و گرما، در جعبه اصلی آن نگه دارید تا سال‌ها کیفیت خود را حفظ کند.

## نقاط نبض

عطر را روی مچ، پشت گوش و گودی گردن بزنید؛ گرمای این نقاط به پخش رایحه کمک می‌کند."""),
]

COUPONS = [("MAJD10", 10, None), ("YALDA50", 50, 5_000_000)]


def attach(field, name):
    with (IMAGES / name).open("rb") as f:
        field.save(name, File(f), save=False)


class Command(BaseCommand):
    help = "ساخت داده‌های نمایشی فروشگاه عطر مجد"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="حذف داده‌های قبلی کاتالوگ و مجله")

    @transaction.atomic
    def handle(self, *args, reset=False, **opts):
        if reset:
            for model in (Review, ProductImage, ProductVariant, Product, Collection, Brand, ScentFamily, Post, Category):
                model.objects.all().delete()

        brands = {k: Brand.objects.get_or_create(slug=k, defaults={"name": v})[0] for k, v in BRANDS.items()}
        scents = {k: ScentFamily.objects.get_or_create(slug=k, defaults={"name": v})[0] for k, v in SCENTS.items()}

        collections = {}
        for order, (slug, name, tagline, img, wide) in enumerate(COLLECTIONS):
            c = Collection.objects.filter(slug=slug).first()
            if c is None:
                c = Collection(slug=slug, name=name, tagline=tagline, is_wide=wide, order=order)
                attach(c.image, img)
                c.save()
            collections[slug] = c

        created = 0
        now = timezone.now()
        for i, (slug, name, brand, scent, col, price, featured, notes, desc) in enumerate(PRODUCTS):
            if Product.objects.filter(slug=slug).exists():
                continue
            p = Product(
                slug=slug, name=name, brand=brands[brand], scent=scents[scent], collection=collections[col],
                is_featured=featured, short_description=desc.split("؛")[0] + ".", description=desc,
                notes_top=notes[0], notes_middle=notes[1], notes_base=notes[2],
            )
            attach(p.image, PRODUCT_IMAGES[slug])
            p.save()
            Product.objects.filter(pk=p.pk).update(created_at=now - timedelta(days=i))
            ProductVariant.objects.create(product=p, size_ml=50, price=price, stock=25)
            ProductVariant.objects.create(product=p, size_ml=100, price=round(price * 1.6, -4), stock=15)
            for order, img in enumerate(GALLERY.get(slug, [])):
                pi = ProductImage(product=p, order=order)
                attach(pi.image, img)
                pi.save()
            for j in range(3 + i % 3):
                name_, rating, text = REVIEWS[(i + j) % len(REVIEWS)]
                Review.objects.create(product=p, name=name_, rating=rating if (i + j) % 4 else 4, text=text, is_approved=True)
            created += 1

        cats = {k: Category.objects.get_or_create(slug=k, defaults={"name": v})[0] for k, v in CATEGORIES.items()}
        posts = 0
        for slug, title, cat, img, days_ago, excerpt, body in POSTS:
            if Post.objects.filter(slug=slug).exists():
                continue
            post = Post(slug=slug, title=title, category=cats[cat], excerpt=excerpt, body=body,
                        published_at=now - timedelta(days=days_ago))
            attach(post.cover, img)
            post.save()
            posts += 1

        for code, percent, max_discount in COUPONS:
            Coupon.objects.get_or_create(code=code, defaults={"percent": percent, "max_discount": max_discount})

        self.stdout.write(self.style.SUCCESS(f"{created} محصول و {posts} مقاله ساخته شد."))
