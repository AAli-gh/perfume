from django.contrib import admin
from django.utils.html import format_html

from .models import Answer, Question, Review, ReviewPhoto


class ReviewPhotoInline(admin.TabularInline):
    model = ReviewPhoto
    extra = 0
    fields = ["image", "preview"]
    readonly_fields = ["preview"]

    @admin.display(description="پیش‌نمایش")
    def preview(self, obj):
        return format_html('<img src="{}" style="height:64px;border-radius:4px">', obj.image.url) if obj.image else "—"


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["name", "product", "rating", "is_verified", "photo_count", "is_approved", "created_at"]
    list_filter = ["is_approved", "is_verified", "rating"]
    list_editable = ["is_approved"]
    search_fields = ["name", "text", "product__name"]
    readonly_fields = ["is_verified"]
    inlines = [ReviewPhotoInline]
    actions = ["approve"]

    @admin.display(description="عکس")
    def photo_count(self, obj):
        return obj.photos.count() or "—"

    @admin.action(description="تأیید نظرات انتخاب‌شده")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)


class AnswerInline(admin.StackedInline):
    model = Answer
    extra = 1
    fields = ["text", "is_staff"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text_short", "product", "name", "answer_count", "is_approved", "created_at"]
    list_filter = ["is_approved"]
    list_editable = ["is_approved"]
    search_fields = ["text", "name", "product__name"]
    raw_id_fields = ["product", "user"]
    inlines = [AnswerInline]
    actions = ["approve"]

    @admin.display(description="پرسش")
    def text_short(self, obj):
        return obj.text[:70]

    @admin.display(description="پاسخ‌ها")
    def answer_count(self, obj):
        return obj.answers.count()

    def save_formset(self, request, form, formset, change):
        # پاسخ تازه به نام کارمند ثبت می‌شود و پرسشِ پاسخ‌داده‌شده خودکار نمایش داده می‌شود
        answers = formset.save(commit=False)
        for answer in answers:
            if answer.user_id is None:
                answer.user = request.user
            answer.save()
        for obj in formset.deleted_objects:
            obj.delete()
        if answers and not form.instance.is_approved:
            form.instance.is_approved = True
            form.instance.save(update_fields=["is_approved"])

    @admin.action(description="نمایش پرسش‌های انتخاب‌شده")
    def approve(self, request, queryset):
        queryset.update(is_approved=True)
