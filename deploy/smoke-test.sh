#!/bin/sh
# آزمون دود پس از استقرار:  deploy/smoke-test.sh https://shop.example.com [--insecure]
set -eu
BASE=${1:?آدرس سایت، مثلاً https://shop.example.com}
CURL="curl -sS --max-time 15 ${2:+-k}"
fail() { echo "FAIL: $*" >&2; exit 1; }
check() { # check <path> <expected-status>
    code=$($CURL -o /dev/null -w '%{http_code}' "$BASE$1") || fail "$1 unreachable"
    [ "$code" = "$2" ] || fail "$1 returned $code (expected $2)"
    echo "ok  $code $1"
}

check /healthz 200
check /readyz 200
check / 200
check /shop/ 200
check /robots.txt 200
check /sitemap.xml 200
check /no-such-page/ 404

headers=$($CURL -D - -o /dev/null "$BASE/")
echo "$headers" | grep -qi '^content-security-policy:' || fail "CSP header missing"
echo "$headers" | grep -qi '^strict-transport-security:' || fail "HSTS header missing"
echo "$headers" | grep -qi '^x-request-id:' || fail "X-Request-ID header missing"
echo "ok  security headers"

css=$($CURL "$BASE/" | grep -o '/static/css/app\.[a-f0-9]*\.css' | head -1)
[ -n "$css" ] || fail "hashed CSS not referenced"
$CURL -D - -o /dev/null -H 'Accept-Encoding: br' "$BASE$css" | grep -qi '^content-encoding: br' || fail "brotli static missing"
echo "ok  static $css (brotli)"
echo "SMOKE TEST PASSED"
