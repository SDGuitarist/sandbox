# Test Results -- Recipe Organizer

**STATUS: PASS**

- **Date:** 2026-04-09
- **Runner:** pytest 9.0.3, Python 3.14.3
- **Duration:** 0.22s
- **Result:** 21 passed, 0 failed

## Test Breakdown

| # | Test Class | Test | Result |
|---|-----------|------|--------|
| 1 | TestAppFactory | test_create_app | PASS |
| 2 | TestAppFactory | test_secret_key_set | PASS |
| 3 | TestHomeRedirect | test_home_redirects | PASS |
| 4 | TestRecipeCRUD | test_create_recipe | PASS |
| 5 | TestRecipeCRUD | test_read_recipe_list | PASS |
| 6 | TestRecipeCRUD | test_read_recipe_detail | PASS |
| 7 | TestRecipeCRUD | test_update_recipe | PASS |
| 8 | TestRecipeCRUD | test_delete_recipe | PASS |
| 9 | TestIngredientCRUD | test_create_ingredient | PASS |
| 10 | TestIngredientCRUD | test_read_ingredient_list | PASS |
| 11 | TestIngredientCRUD | test_delete_ingredient | PASS |
| 12 | TestIngredientCRUD | test_delete_ingredient_restrict_when_linked | PASS |
| 13 | TestRecipeIngredientLinking | test_link_ingredient_to_recipe | PASS |
| 14 | TestSearch | test_search_finds_recipe | PASS |
| 15 | TestSearch | test_search_empty_query | PASS |
| 16 | TestSearch | test_search_no_results | PASS |
| 17 | TestCSRF | test_post_without_token_returns_403 | PASS |
| 18 | TestCSRF | test_post_with_wrong_token_returns_403 | PASS |
| 19 | TestNotFound | test_missing_recipe_detail | PASS |
| 20 | TestNotFound | test_missing_recipe_edit | PASS |
| 21 | TestNotFound | test_missing_ingredient_edit | PASS |

## Coverage Areas

1. App factory creates successfully
2. Home route redirects to /recipes/
3. Recipe CRUD (create, read list, read detail, update, delete)
4. Ingredient CRUD (create, read list, delete, delete-with-restrict)
5. Recipe-ingredient linking
6. Search by ingredient (match, empty query, no results)
7. CSRF protection (missing token, wrong token both return 403)
8. 404 on missing recipe/ingredient
