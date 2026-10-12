"""Blog (SPEC-BLOG P1): CRUD, cổng publish, public chỉ thấy published."""

LONG_TEXT = "nội dung bài viết. " * 30  # ~570 ký tự, qua cổng 300

LONG_DOC = {
    "type": "doc",
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 2},
            "content": [{"type": "text", "text": "Mẹo Part 3"}],
        },
        {"type": "paragraph", "content": [{"type": "text", "text": LONG_TEXT}]},
    ],
}

SHORT_DOC = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "quá ngắn"}]}],
}


def make_post(client, auth, **over):
    body = {
        "slug": "meo-part-3",
        "title": "Mẹo làm Part 3",
        "excerpt": "Ba mẹo nghe hội thoại ngắn hiệu quả trong Part 3.",
        "body_json": LONG_DOC,
        "body_html": f"<h2>Mẹo Part 3</h2><p>{LONG_TEXT}</p>",
        "category": "meo-lam-bai",
        "tags": ["part-3", "listening"],
    } | over
    response = client.post("/api/v1/admin/blog/posts", json=body, headers=auth("editor"))
    assert response.status_code == 201, response.text
    return response.json()


def test_create_sanitizes_html(client, auth):
    post = make_post(
        client,
        auth,
        slug="sanitize-me",
        body_html="<h1>Ăn cắp H1</h1><p>ok</p><script>alert(1)</script>",
    )
    assert "<script>" not in post["body_html"]
    assert "<h1>" not in post["body_html"]
    assert post["status"] == "draft"


def test_draft_invisible_to_public(client, auth):
    make_post(client, auth)
    assert client.get("/api/v1/blog/posts").json()["total"] == 0
    assert client.get("/api/v1/blog/posts/meo-part-3").status_code == 404


def test_publish_gate_rejects_short_body(client, auth):
    post = make_post(
        client, auth, slug="short-body", body_json=SHORT_DOC, body_html="<p>quá ngắn</p>"
    )
    response = client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("admin"))
    assert response.status_code == 422


def test_editor_cannot_publish(client, auth):
    post = make_post(client, auth)
    response = client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("editor"))
    assert response.status_code == 403


def test_publish_then_public_reads(client, auth):
    post = make_post(client, auth)
    published = client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("admin"))
    assert published.status_code == 200, published.text
    assert published.json()["published_at"] is not None

    listing = client.get("/api/v1/blog/posts").json()
    assert listing["total"] == 1
    assert listing["items"][0]["reading_minutes"] >= 1

    detail = client.get("/api/v1/blog/posts/meo-part-3").json()
    assert "Mẹo Part 3" in detail["body_html"]
    assert detail["toc"] == [{"level": 2, "text": "Mẹo Part 3", "id": "m-o-part-3"}]
    assert detail["related"] == []


def test_duplicate_slug_conflicts(client, auth):
    make_post(client, auth)
    response = client.post(
        "/api/v1/admin/blog/posts",
        json={
            "slug": "meo-part-3",
            "title": "Trùng slug",
            "excerpt": "Bài khác nhưng slug trùng với bài đã có.",
            "body_json": LONG_DOC,
            "body_html": "<p>x</p>",
            "category": "tu-vung",
        },
        headers=auth("editor"),
    )
    assert response.status_code == 409


def test_slug_locked_after_publish_and_body_pair_required(client, auth):
    post = make_post(client, auth)
    client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("admin"))

    response = client.patch(
        f"/api/v1/admin/blog/posts/{post['id']}",
        json={"slug": "doi-slug"},
        headers=auth("editor"),
    )
    assert response.status_code == 422

    response = client.patch(
        f"/api/v1/admin/blog/posts/{post['id']}",
        json={"body_html": "<p>thiếu json</p>"},
        headers=auth("editor"),
    )
    assert response.status_code == 422


def test_filters_and_search(client, auth):
    first = make_post(client, auth)
    second = make_post(
        client,
        auth,
        slug="collocation-take",
        title="Cụm với TAKE",
        excerpt="Take advantage of và bạn bè trong đề thi.",
        category="tu-vung",
        tags=["collocation"],
    )
    for post in (first, second):
        client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("admin"))

    assert client.get("/api/v1/blog/posts?category=tu-vung").json()["total"] == 1
    assert client.get("/api/v1/blog/posts?tag=part-3").json()["total"] == 1
    assert client.get("/api/v1/blog/posts?q=TAKE").json()["total"] == 1
    assert client.get("/api/v1/blog/posts?q=không-có-gì").json()["total"] == 0
    page = client.get("/api/v1/blog/posts?limit=1&offset=1").json()
    assert page["total"] == 2 and len(page["items"]) == 1


def test_unpublish_hides_again(client, auth):
    post = make_post(client, auth)
    client.post(f"/api/v1/admin/blog/posts/{post['id']}/publish", headers=auth("admin"))
    assert client.get("/api/v1/blog/posts/meo-part-3").status_code == 200
    client.post(f"/api/v1/admin/blog/posts/{post['id']}/unpublish", headers=auth("admin"))
    assert client.get("/api/v1/blog/posts/meo-part-3").status_code == 404


def test_invalid_slug_and_category_rejected(client, auth):
    base = {
        "title": "Sai",
        "excerpt": "Bài viết có trường sai định dạng cần bị từ chối.",
        "body_json": LONG_DOC,
        "body_html": "<p>x</p>",
        "category": "meo-lam-bai",
    }
    assert (
        client.post(
            "/api/v1/admin/blog/posts", json=base | {"slug": "Sai Format!"}, headers=auth("editor")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/admin/blog/posts",
            json=base | {"slug": "ok-slug", "category": "khong-co"},
            headers=auth("editor"),
        ).status_code
        == 422
    )


def test_admin_read_single_and_404(client, auth):
    post = make_post(client, auth)
    got = client.get(f"/api/v1/admin/blog/posts/{post['id']}", headers=auth("editor"))
    assert got.status_code == 200
    assert got.json()["body_json"]["type"] == "doc"
    assert (
        client.get(
            "/api/v1/admin/blog/posts/00000000-0000-0000-0000-000000000000",
            headers=auth("editor"),
        ).status_code
        == 404
    )


def test_admin_delete_post(client, auth):
    post = make_post(client, auth)
    assert (
        client.delete(f"/api/v1/admin/blog/posts/{post['id']}", headers=auth("editor")).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/admin/blog/posts/{post['id']}", headers=auth("admin")).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/admin/blog/posts/{post['id']}", headers=auth("editor")).status_code
        == 404
    )
