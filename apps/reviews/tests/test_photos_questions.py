"""نظر با عکس، نشان «خریدار تأییدشده» و پرسش و پاسخ محصول."""

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.builder.tests.test_studio import PNG
from apps.catalog.tests.factories import VariantFactory
from apps.notifications.services import settings_for
from apps.notifications.sms import console
from apps.orders.models import Order, OrderItem
from apps.reviews.models import Answer, Question, Review

pytestmark = pytest.mark.django_db
REVIEW = {"name": "نسیم", "rating": 5, "text": "رایحه بی‌نظیری دارد"}


def png(name="a.png"):
    return SimpleUploadedFile(name, PNG, content_type="image/png")


@pytest.fixture
def variant(store):
    return VariantFactory(price=2_000_000, stock=5)


@pytest.fixture
def buyer(client):
    user = get_user_model().objects.create_user(email="b@example.com", password="x-Strong-123", first_name="نسیم",
                                                phone="09121234567")
    client.force_login(user)
    return user


def order_for(store, user, variant, status):
    order = Order.objects.create(store=store, user=user, first_name="ن", last_name="ن", phone="09121234567",
                                 province="تهران", city="تهران", address="a", postal_code="1234567890",
                                 subtotal=1, total=1, payment_method=Order.PaymentMethod.COD, status=status)
    OrderItem.objects.create(order=order, variant=variant, product_name=variant.product.name,
                             size_ml=variant.size_ml, unit_price=1, quantity=1)
    return order


def test_review_with_photos_htmx(client, store, variant):
    url = reverse("reviews:create", args=[variant.product.slug])
    r = client.post(url, {**REVIEW, "photos": [png("a.png"), png("b.png")]}, HTTP_HX_REQUEST="true")
    assert "پس از تأیید" in r.content.decode()
    review = Review.objects.get()
    assert review.photos.count() == 2 and not review.is_verified  # مهمان خریدار تأییدشده نیست


def test_review_photo_limits(client, store, variant):
    url = reverse("reviews:create", args=[variant.product.slug])
    r = client.post(url, {**REVIEW, "photos": [png(f"{i}.png") for i in range(4)]}, HTTP_HX_REQUEST="true")
    assert "حداکثر ۳" in r.content.decode() or "حداکثر 3" in r.content.decode()
    bad = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
    client.post(url, {**REVIEW, "photos": [bad]}, HTTP_HX_REQUEST="true")
    assert not Review.objects.exists()


def test_verified_badge_only_after_delivery(client, store, variant, buyer):
    url = reverse("reviews:create", args=[variant.product.slug])
    order_for(store, buyer, variant, Order.Status.SHIPPED)
    client.post(url, REVIEW)
    assert not Review.objects.get().is_verified
    order_for(store, buyer, variant, Order.Status.DELIVERED)
    client.post(url, REVIEW)
    verified = Review.objects.get(is_verified=True)
    other = VariantFactory(product__name="دیگری")
    client.post(reverse("reviews:create", args=[other.product.slug]), REVIEW)
    assert not Review.objects.get(product=other.product).is_verified

    Review.objects.update(is_approved=True)
    verified.photos.create(image=png())
    html = client.get(variant.product.get_absolute_url()).content.decode()
    assert "خریدار تأییدشده" in html and html.count("verified-badge") == 1 and "/media/reviews/" in html
    # خریدار تأییدشده اول نمایش داده می‌شود
    from apps.reviews.selectors import approved_reviews

    assert approved_reviews(variant.product)[0] == verified


def test_question_flow(client, store, variant, buyer, django_capture_on_commit_callbacks):
    conf = settings_for(store)
    conf.staff_emails = "boss@example.com"
    conf.save()
    product = variant.product
    url = reverse("reviews:ask", args=[product.slug])
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(url, {"name": "نسیم", "text": "ماندگاری روی لباس چقدر است؟"}, HTTP_HX_REQUEST="true")
    assert "پرسش شما ثبت شد" in r.content.decode()
    question = Question.objects.get()
    assert question.user == buyer and not question.is_approved
    assert mail.outbox[-1].to == ["boss@example.com"] and "ماندگاری" in mail.outbox[-1].body
    assert f"/reviews/question/{question.pk}/change/" in mail.outbox[-1].body

    page = client.get(product.get_absolute_url()).content.decode()
    assert "ماندگاری روی لباس" not in page  # بدون پاسخ نمایش داده نمی‌شود

    console.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        Answer.objects.create(question=question, text="حدود ۱۲ ساعت")
    assert any(m["to"] == "09121234567" and "#questions" in m["text"] for m in console.outbox)
    assert "حدود ۱۲ ساعت" in mail.outbox[-1].body and mail.outbox[-1].to == ["b@example.com"]
    question.is_approved = True
    question.save()
    page = client.get(product.get_absolute_url()).content.decode()
    assert "ماندگاری روی لباس" in page and "حدود ۱۲ ساعت" in page and "پرسش و پاسخ (۱)" in page


def test_question_validation_redirect_and_ratelimit(client, store, variant):
    url = reverse("reviews:ask", args=[variant.product.slug])
    r = client.post(url, {"name": "x", "text": "کوتاه"}, HTTP_HX_REQUEST="true")
    assert "خیلی کوتاه" in r.content.decode()
    r = client.post(url, {"name": "مهمان", "text": "این عطر برای تابستان مناسب است؟"}, follow=True)
    assert r.redirect_chain[-1][0].endswith("#questions") and "پرسش شما ثبت شد" in r.content.decode()
    assert Question.objects.get().user is None
    for _ in range(5):
        r = client.post(url, {"name": "مهمان", "text": "این عطر برای تابستان مناسب است؟"})
    assert r.status_code == 429


def test_admin_answer_sets_staff_user_and_publishes(admin_client, admin_user, store, variant):
    question = Question.objects.create(product=variant.product, name="ن", text="مناسب هدیه است؟")
    url = reverse("admin:reviews_question_change", args=[question.pk])
    assert admin_client.get(url).status_code == 200
    data = {"product": variant.product.pk, "name": "ن", "text": "مناسب هدیه است؟",
            "answers-TOTAL_FORMS": 1, "answers-INITIAL_FORMS": 0, "answers-0-text": "بله، بسیار", "answers-0-is_staff": "on"}
    r = admin_client.post(url, data)
    assert r.status_code == 302, r.content.decode()[:2000]
    question.refresh_from_db()
    answer = question.answers.get()
    assert question.is_approved and answer.user == admin_user and answer.is_staff
    review = Review.objects.create(product=variant.product, name="n", rating=4, text="خوب")
    review.photos.create(image=png())
    assert admin_client.get(reverse("admin:reviews_review_change", args=[review.pk])).status_code == 200
    assert admin_client.get(reverse("admin:reviews_review_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:reviews_question_changelist")).status_code == 200
