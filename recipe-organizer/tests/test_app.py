"""Test suite for the Recipe Organizer Flask app."""


# ---------------------------------------------------------------------------
# 1. App factory
# ---------------------------------------------------------------------------
class TestAppFactory:
    def test_create_app(self, app):
        """App factory creates a Flask app successfully."""
        assert app is not None
        assert app.config["TESTING"] is True

    def test_secret_key_set(self, app):
        """Secret key is generated on creation."""
        assert app.config["SECRET_KEY"]


# ---------------------------------------------------------------------------
# 2. Home route redirects to recipes
# ---------------------------------------------------------------------------
class TestHomeRedirect:
    def test_home_redirects(self, client):
        resp = client.get("/")
        assert resp.status_code == 302
        assert "/recipes/" in resp.headers["Location"]


# ---------------------------------------------------------------------------
# 3. Recipe CRUD
# ---------------------------------------------------------------------------
class TestRecipeCRUD:
    def _create_recipe(self, client, csrf_token, **overrides):
        data = {
            "title": "Pasta Bolognese",
            "description": "Classic Italian dish",
            "instructions": "Cook the pasta. Make the sauce.",
            "servings": "4",
            "prep_time_min": "10",
            "cook_time_min": "30",
            "csrf_token": csrf_token,
        }
        data.update(overrides)
        return client.post("/recipes/new", data=data, follow_redirects=True)

    def test_create_recipe(self, client, csrf_token):
        resp = self._create_recipe(client, csrf_token)
        assert resp.status_code == 200
        assert b"Pasta Bolognese" in resp.data

    def test_read_recipe_list(self, client, csrf_token):
        self._create_recipe(client, csrf_token)
        resp = client.get("/recipes/")
        assert resp.status_code == 200
        assert b"Pasta Bolognese" in resp.data

    def test_read_recipe_detail(self, client, csrf_token):
        self._create_recipe(client, csrf_token)
        resp = client.get("/recipes/1")
        assert resp.status_code == 200
        assert b"Pasta Bolognese" in resp.data

    def test_update_recipe(self, client, csrf_token):
        self._create_recipe(client, csrf_token)
        resp = client.post(
            "/recipes/1/edit",
            data={
                "title": "Updated Pasta",
                "description": "Updated desc",
                "instructions": "New instructions",
                "servings": "2",
                "prep_time_min": "5",
                "cook_time_min": "20",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Updated Pasta" in resp.data

    def test_delete_recipe(self, client, csrf_token):
        self._create_recipe(client, csrf_token)
        resp = client.post(
            "/recipes/1/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Pasta Bolognese" not in resp.data


# ---------------------------------------------------------------------------
# 4. Ingredient CRUD
# ---------------------------------------------------------------------------
class TestIngredientCRUD:
    def _create_ingredient(self, client, csrf_token, name="Garlic"):
        return client.post(
            "/ingredients/new",
            data={"name": name, "csrf_token": csrf_token},
            follow_redirects=True,
        )

    def test_create_ingredient(self, client, csrf_token):
        resp = self._create_ingredient(client, csrf_token)
        assert resp.status_code == 200
        assert b"Garlic" in resp.data

    def test_read_ingredient_list(self, client, csrf_token):
        self._create_ingredient(client, csrf_token)
        resp = client.get("/ingredients/")
        assert resp.status_code == 200
        assert b"Garlic" in resp.data

    def test_delete_ingredient(self, client, csrf_token):
        self._create_ingredient(client, csrf_token)
        resp = client.post(
            "/ingredients/1/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Garlic" not in resp.data

    def test_delete_ingredient_restrict_when_linked(self, client, csrf_token):
        """Deleting an ingredient used in a recipe should be restricted."""
        self._create_ingredient(client, csrf_token, name="Tomato")
        # Create a recipe that links to this ingredient
        client.post(
            "/recipes/new",
            data={
                "title": "Tomato Soup",
                "description": "Simple soup",
                "instructions": "Blend tomatoes.",
                "servings": "2",
                "prep_time_min": "5",
                "cook_time_min": "15",
                "ingredient_id": "1",
                "quantity": "3",
                "unit": "cups",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        # Attempt to delete the ingredient -- should be restricted
        resp = client.post(
            "/ingredients/1/delete",
            data={"csrf_token": csrf_token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Cannot delete" in resp.data


# ---------------------------------------------------------------------------
# 5. Recipe-ingredient linking
# ---------------------------------------------------------------------------
class TestRecipeIngredientLinking:
    def test_link_ingredient_to_recipe(self, client, csrf_token):
        # Create ingredient first
        client.post(
            "/ingredients/new",
            data={"name": "Olive Oil", "csrf_token": csrf_token},
        )
        # Create recipe with that ingredient
        resp = client.post(
            "/recipes/new",
            data={
                "title": "Simple Salad",
                "description": "A light salad",
                "instructions": "Toss ingredients.",
                "servings": "1",
                "prep_time_min": "5",
                "cook_time_min": "0",
                "ingredient_id": "1",
                "quantity": "2",
                "unit": "tbsp",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Olive Oil" in resp.data


# ---------------------------------------------------------------------------
# 6. Search by ingredient
# ---------------------------------------------------------------------------
class TestSearch:
    def _seed(self, client, csrf_token):
        client.post(
            "/ingredients/new",
            data={"name": "Chicken", "csrf_token": csrf_token},
        )
        client.post(
            "/recipes/new",
            data={
                "title": "Chicken Stir Fry",
                "description": "Quick dinner",
                "instructions": "Stir fry the chicken.",
                "servings": "2",
                "prep_time_min": "10",
                "cook_time_min": "15",
                "ingredient_id": "1",
                "quantity": "1",
                "unit": "lb",
                "csrf_token": csrf_token,
            },
        )

    def test_search_finds_recipe(self, client, csrf_token):
        self._seed(client, csrf_token)
        resp = client.get("/search/?q=chicken")
        assert resp.status_code == 200
        assert b"Chicken Stir Fry" in resp.data

    def test_search_empty_query(self, client, csrf_token):
        self._seed(client, csrf_token)
        resp = client.get("/search/?q=")
        assert resp.status_code == 200

    def test_search_no_results(self, client, csrf_token):
        self._seed(client, csrf_token)
        resp = client.get("/search/?q=zzzznotfound")
        assert resp.status_code == 200
        assert b"Chicken Stir Fry" not in resp.data


# ---------------------------------------------------------------------------
# 7. CSRF protection
# ---------------------------------------------------------------------------
class TestCSRF:
    def test_post_without_token_returns_403(self, client):
        # Hit a GET first to initialize session
        client.get("/recipes/")
        resp = client.post(
            "/recipes/new",
            data={
                "title": "Should Fail",
                "instructions": "No CSRF",
                "servings": "1",
            },
        )
        assert resp.status_code == 403

    def test_post_with_wrong_token_returns_403(self, client):
        client.get("/recipes/")
        resp = client.post(
            "/recipes/new",
            data={
                "title": "Should Fail",
                "instructions": "Bad CSRF",
                "servings": "1",
                "csrf_token": "totally-wrong-token",
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 8. 404 on missing recipe/ingredient
# ---------------------------------------------------------------------------
class TestNotFound:
    def test_missing_recipe_detail(self, client):
        resp = client.get("/recipes/9999")
        assert resp.status_code == 404

    def test_missing_recipe_edit(self, client):
        resp = client.get("/recipes/9999/edit")
        assert resp.status_code == 404

    def test_missing_ingredient_edit(self, client):
        resp = client.get("/ingredients/9999/edit")
        assert resp.status_code == 404
