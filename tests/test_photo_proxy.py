#!/usr/bin/env python3
"""
Checks for the representative-photo lookup in deploy/photo-proxy.py (#33):
the unit, not visitors' browsers, asks Wikipedia and Wikimedia Commons for a
photo of an aircraft type. Upstream answers are canned; nothing goes online.

Run: python3 tests/test_photo_proxy.py
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("photo_proxy", os.path.join(HERE, "..", "deploy", "photo-proxy.py"))
pp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pp)

failures = []
checks = 0


def check(label, condition):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


THUMB = "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/Cessna_172S_%28N123%29.jpg/320px-x.jpg"


def upstream(thumb=THUMB, licence="CC BY-SA 4.0", artist='<a href="//commons.wikimedia.org/wiki/User:Pat">Pat  Smith</a>', hits=True):
    asked = []

    def fetch(url):
        asked.append(url)
        if url.startswith(pp.WIKI_SEARCH):
            return {"query": {"search": [{"title": "Cessna 172"}] if hits else []}}
        if url.startswith(pp.WIKI_SUMMARY):
            return {"thumbnail": {"source": thumb}} if thumb else {}
        if url.startswith(pp.COMMONS_INFO):
            meta = {"Artist": {"value": artist}}
            if licence:
                meta["LicenseShortName"] = {"value": licence}
            return {"query": {"pages": {"1": {"imageinfo": [{"extmetadata": meta}]}}}}
        raise AssertionError(url)
    return fetch, asked


fetch, asked = upstream()
got = pp.representative_photo("Cessna 172 Skyhawk", fetch)
check("a Commons lead image is found", got and got["found"] and got["thumb"] == THUMB)
check("credited to its author, as text", got and got["artist"] == "Pat Smith")
check("with its licence", got and got["license"] == "CC BY-SA 4.0")
check("linked to its Commons file page", got and got["page"] == "https://commons.wikimedia.org/wiki/File:Cessna_172S_%28N123%29.jpg")
check("the search asks for the type", asked and asked[0].endswith("Cessna%20172%20Skyhawk"))
check("the summary asks for the article found", len(asked) > 1 and asked[1] == pp.WIKI_SUMMARY + "Cessna_172")

local = "https://upload.wikimedia.org/wikipedia/en/a/ab/Poster.jpg"
check("a file on English Wikipedia (maybe non-free) is not used",
      pp.representative_photo("x", upstream(thumb=local)[0]) == {"found": False})
check("nor one without a licence", pp.representative_photo("x", upstream(licence=None)[0]) == {"found": False})
check("nor plain http", pp.representative_photo("x", upstream(thumb=THUMB.replace("https", "http"))[0]) == {"found": False})
check("no article is no photo", pp.representative_photo("x", upstream(hits=False)[0]) == {"found": False})
check("an unknown author says so", pp.representative_photo("x", upstream(artist="")[0])["artist"] == "Unknown")


def broken(url):
    raise OSError("offline")


check("couldn't ask is not the same as no photo", pp.representative_photo("x", broken) is None)

check("the type comes from ?q=", pp.type_label("/photo/type?q=Boeing%20737-800") == "Boeing 737-800")
check("an empty one is refused", pp.type_label("/photo/type?q=") is None)
check("an overlong one is refused", pp.type_label("/photo/type?q=" + "A" * 81) is None)
check("control characters are refused", pp.type_label("/photo/type?q=a%0Ab") is None)
check("other paths aren't type lookups", pp.type_label("/photo/a1b2c3") is None and pp.type_label("/photo/typex?q=a") is None)
check("a tail photo path still matches as before", pp.HEX_RE.search("/photo/A1B2C3"))

store = {}
for i in range(pp.CACHE_MAX + 10):
    pp.bounded_put(store, i, (i, 0, b""))
check("the type cache stays bounded", len(store) <= pp.CACHE_MAX)
check("dropping the oldest first", 0 not in store and pp.CACHE_MAX + 9 in store)

print(f"{checks - len(failures)}/{checks} photo proxy checks passed")
for f in failures:
    print("  FAILED:", f)
sys.exit(1 if failures else 0)


# planespotters' answer, shaped for the page: URLs unchanged, the credit, the
# link, and a QR code of the link for the kiosk (their terms, 2026-10-09).
shaped = pp.shape_photo({"photos": [{"thumbnail": {"src": "https://cdn.planespotters.net/t.jpg"},
                                     "thumbnail_large": {"src": "https://cdn.planespotters.net/l.jpg"},
                                     "link": "https://www.planespotters.net/photo/1/x", "photographer": "Pat"}]})
check("the thumbnails are passed on unchanged", shaped["thumb"] == "https://cdn.planespotters.net/t.jpg" and shaped["thumbLarge"] == "https://cdn.planespotters.net/l.jpg")
check("the photographer and the link come with them", shaped["photographer"] == "Pat" and shaped["link"] == "https://www.planespotters.net/photo/1/x")
qr = shaped.get("qr")
check("a QR code of the link is included for the kiosk (or None without python3-qrcode here)",
      qr is None or ("<svg" in qr and "path" in qr))
if qr is None:
    print("note: python3-qrcode is not installed on this machine; the unit has it")
check("no photo, no QR", pp.shape_photo({"photos": []}) == {"found": False})
check("the User-Agent names a contact", "+https://" in pp.USER_AGENT)
