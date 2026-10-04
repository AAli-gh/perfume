/** @type {import('tailwindcss').Config} */
// رنگ‌ها، فونت‌ها و گردی گوشه‌ها از CSS Variables خوانده می‌شوند (apps/themes/tokens.py → <style> در base.html).
// تغییر پالت در پنل مدیریت نیازی به build دوباره CSS ندارد.
const v = (name) => `rgb(var(--color-${name}) / <alpha-value>)`;

module.exports = {
  content: [
    "./themes/*/templates/**/*.html",
    "./apps/*/templates/**/*.html",
    "./apps/*/templatetags/*.py",
    "./apps/*/forms.py",
    "./apps/pages/services.py",
    "./apps/builder/*.py",
    "./static/js/**/*.js",
  ],
  theme: {
    container: { center: true, padding: "1rem", screens: { "2xl": "1232px" } },
    extend: {
      colors: {
        // نام‌های معنایی (برای قالب‌های جدید)
        background: { DEFAULT: v("background"), 2: v("background-2") },
        surface: v("surface"),
        panel: v("panel"),
        media: v("media"),
        hero: v("hero"),
        overlay: v("overlay"),
        footer: v("footer"),
        input: v("input"),
        primary: { DEFAULT: v("primary"), dark: v("primary-dark") },
        accent: { DEFAULT: v("accent"), soft: v("accent-soft") },
        text: { DEFAULT: v("text"), strong: v("text-strong") },
        placeholder: v("placeholder"),
        price: v("price"),
        border: { DEFAULT: "rgb(var(--color-border) / 0.2)", strong: "rgb(var(--color-border) / 0.38)" },
        // نام‌های قبلی (سازگاری با قالب‌های پوسته لوکس) — همان متغیرها
        ink: { DEFAULT: v("background"), 2: v("background-2"), 3: v("surface") },
        line: { DEFAULT: "rgb(var(--color-border) / 0.2)", strong: "rgb(var(--color-border) / 0.38)" },
        copper: { DEFAULT: v("primary"), dark: v("primary-dark") },
        gold: { DEFAULT: v("accent"), soft: v("accent-soft") },
        cream: v("text-strong"),
        body: v("text"),
        muted: v("muted"),
        danger: v("danger"),
        success: v("success"),
      },
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        DEFAULT: "var(--radius)",
        lg: "var(--radius-lg)",
      },
      boxShadow: { luxe: "0 18px 40px rgb(0 0 0 / var(--shadow-alpha, .45))" },
    },
  },
  plugins: [],
};
