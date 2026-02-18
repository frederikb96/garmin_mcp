"""
Integration tests for nutrition MCP tools (17 tools).
"""

import json

import pytest
from unittest.mock import Mock, patch, MagicMock
from mcp.server.fastmcp import FastMCP

from garmin_mcp import nutrition
from garth.nutrition import (
    CustomFood,
    CustomMeal,
    DailyNutritionLog,
    FavoriteFoods,
    FoodLog,
    FoodSearch,
    MealDefinitions,
    NutritionSettings,
    QuickAdd,
)
from garth.nutrition._types import (
    DailyNutritionSummary,
    FoodMetaData,
    LoggedFood,
    MacroGoals,
    Meal,
    MealDetail,
    NutritionContent,
)
from garth.nutrition.search import RecentFoods, SearchResult, SearchResults
from garth.nutrition.favorites import FavoriteFood, FavoriteFoodList
from garth.nutrition.custom_food import CustomFoodItem, CustomFoodList
from garth.nutrition.custom_meal import (
    CustomMealDetail,
    CustomMealItem,
    CustomMealList,
    CustomMealFood,
)
from garth.utils import camel_to_snake_dict

from tests.fixtures.garmin_responses import (
    MOCK_DAILY_NUTRITION_LOG,
    MOCK_FOOD_SEARCH_RESULTS,
    MOCK_MEAL_DEFINITIONS,
    MOCK_NUTRITION_SETTINGS,
    MOCK_RECENT_FOODS,
    MOCK_FAVORITE_FOODS,
    MOCK_CUSTOM_FOODS,
    MOCK_CUSTOM_FOOD_CREATED,
    MOCK_CUSTOM_MEALS,
    MOCK_CUSTOM_MEAL_CREATED,
)


def _make_meals() -> list[Meal]:
    """Build Meal objects from mock data."""
    return [Meal(**camel_to_snake_dict(m)) for m in MOCK_MEAL_DEFINITIONS]


def _make_daily_log() -> DailyNutritionLog:
    """Build a DailyNutritionLog from mock data."""
    return DailyNutritionLog(**camel_to_snake_dict(MOCK_DAILY_NUTRITION_LOG))


def _make_settings() -> NutritionSettings:
    """Build NutritionSettings from mock data."""
    return NutritionSettings(**camel_to_snake_dict(MOCK_NUTRITION_SETTINGS))


def _make_search_results() -> SearchResults:
    """Build SearchResults from mock data."""
    return SearchResults(**camel_to_snake_dict(MOCK_FOOD_SEARCH_RESULTS))


def _make_recent_foods() -> RecentFoods:
    """Build RecentFoods from mock data."""
    return RecentFoods(**camel_to_snake_dict(MOCK_RECENT_FOODS))


def _make_favorite_list() -> FavoriteFoodList:
    """Build FavoriteFoodList from mock data."""
    items = [
        FavoriteFood(**camel_to_snake_dict(c))
        for c in MOCK_FAVORITE_FOODS["consumables"]
    ]
    return FavoriteFoodList(items=items, has_more=False)


def _make_custom_food_list() -> CustomFoodList:
    """Build CustomFoodList from mock data."""
    items = [
        CustomFoodItem(**camel_to_snake_dict(c))
        for c in MOCK_CUSTOM_FOODS["customFoods"]
    ]
    return CustomFoodList(items=items, more_data_available=False)


def _make_custom_food_item() -> CustomFoodItem:
    """Build a CustomFoodItem from mock data."""
    return CustomFoodItem(**camel_to_snake_dict(MOCK_CUSTOM_FOOD_CREATED))


def _make_custom_meal_list() -> CustomMealList:
    """Build CustomMealList from mock data."""
    items = [
        CustomMealItem(**camel_to_snake_dict(c))
        for c in MOCK_CUSTOM_MEALS["customMeals"]
    ]
    return CustomMealList(items=items, has_more=False)


def _make_custom_meal_detail() -> CustomMealDetail:
    """Build CustomMealDetail from mock data."""
    return CustomMealDetail(**camel_to_snake_dict(MOCK_CUSTOM_MEAL_CREATED))


@pytest.fixture
def mock_garth_client():
    """Create a mock garth client."""
    return Mock()


@pytest.fixture
def app_with_nutrition(mock_garmin_client):
    """Create FastMCP app with nutrition tools registered."""
    mock_garmin_client.garth = Mock()
    nutrition.configure(mock_garmin_client)
    app = FastMCP("Test Nutrition")
    app = nutrition.register_tools(app)
    return app


# ── READ TOOL TESTS ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_nutrition_log(app_with_nutrition, mock_garmin_client):
    """Test get_nutrition_log returns curated daily log."""
    with patch.object(DailyNutritionLog, "get", return_value=_make_daily_log()):
        result = await app_with_nutrition.call_tool(
            "get_nutrition_log", {"date": "2024-01-15"}
        )
    assert result is not None
    data = json.loads(result[0].text)
    assert data["date"] == "2024-01-15"
    assert "daily_goals" in data
    assert "daily_totals" in data
    assert "meals" in data
    assert len(data["meals"]) == 2
    assert data["meals"][0]["meal_name"] == "Breakfast"


@pytest.mark.asyncio
async def test_get_nutrition_summary(app_with_nutrition, mock_garmin_client):
    """Test get_nutrition_summary returns lightweight totals."""
    with patch.object(DailyNutritionLog, "get", return_value=_make_daily_log()):
        result = await app_with_nutrition.call_tool(
            "get_nutrition_summary", {"date": "2024-01-15"}
        )
    data = json.loads(result[0].text)
    assert data["date"] == "2024-01-15"
    assert "totals" in data
    assert "goals" in data
    assert data["totals"]["calories"] == 1850.0
    assert data["goals"]["calories"] == 2200.0


@pytest.mark.asyncio
async def test_get_nutrition_settings(app_with_nutrition, mock_garmin_client):
    """Test get_nutrition_settings returns goals and settings."""
    with patch.object(NutritionSettings, "get", return_value=_make_settings()):
        result = await app_with_nutrition.call_tool(
            "get_nutrition_settings", {"date": "2024-01-15"}
        )
    data = json.loads(result[0].text)
    assert data["calorie_goal"] == 2200
    assert data["region_code"] == "DE"
    assert "macro_goals" in data


@pytest.mark.asyncio
async def test_search_foods(app_with_nutrition, mock_garmin_client):
    """Test search_foods returns food results with IDs."""
    with patch.object(FoodSearch, "search", return_value=_make_search_results()):
        result = await app_with_nutrition.call_tool(
            "search_foods", {"query": "apple"}
        )
    data = json.loads(result[0].text)
    assert data["query"] == "apple"
    assert len(data["results"]) == 1
    assert data["results"][0]["food_id"] == "5367"
    assert data["results"][0]["food_name"] == "Apple"
    assert "servings" in data["results"][0]
    assert data["has_more"] is True


@pytest.mark.asyncio
async def test_get_recent_foods(app_with_nutrition, mock_garmin_client):
    """Test get_recent_foods resolves meal name and returns results."""
    with (
        patch.object(MealDefinitions, "get", return_value=_make_meals()),
        patch.object(FoodSearch, "recent", return_value=_make_recent_foods()),
    ):
        result = await app_with_nutrition.call_tool(
            "get_recent_foods", {"meal": "BREAKFAST"}
        )
    data = json.loads(result[0].text)
    assert data["meal"] == "BREAKFAST"
    assert len(data["frequent_foods"]) == 1
    assert len(data["recent_foods"]) == 1


@pytest.mark.asyncio
async def test_list_favorite_foods(app_with_nutrition, mock_garmin_client):
    """Test list_favorite_foods returns favorites."""
    with patch.object(FavoriteFoods, "list", return_value=_make_favorite_list()):
        result = await app_with_nutrition.call_tool(
            "list_favorite_foods", {}
        )
    data = json.loads(result[0].text)
    assert len(data["favorites"]) == 1
    assert data["favorites"][0]["food_name"] == "Oatmeal"
    assert data["favorites"][0]["is_favorite"] is True


@pytest.mark.asyncio
async def test_list_custom_foods(app_with_nutrition, mock_garmin_client):
    """Test list_custom_foods returns custom foods."""
    with patch.object(CustomFood, "list", return_value=_make_custom_food_list()):
        result = await app_with_nutrition.call_tool(
            "list_custom_foods", {}
        )
    data = json.loads(result[0].text)
    assert len(data["custom_foods"]) == 1
    assert data["custom_foods"][0]["food_name"] == "My Protein Shake"


# ── WRITE TOOL TESTS ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_log_food(app_with_nutrition, mock_garmin_client):
    """Test log_food resolves meal name and logs food."""
    with (
        patch.object(MealDefinitions, "get", return_value=_make_meals()),
        patch.object(FoodLog, "add", return_value=_make_daily_log()),
    ):
        result = await app_with_nutrition.call_tool(
            "log_food",
            {
                "date": "2024-01-15",
                "meal": "BREAKFAST",
                "food_id": "5367",
                "serving_id": "54047",
                "source": "FATSECRET",
                "serving_qty": 1,
            },
        )
    data = json.loads(result[0].text)
    assert data["date"] == "2024-01-15"
    assert "meals" in data


@pytest.mark.asyncio
async def test_quick_add_nutrition(app_with_nutrition, mock_garmin_client):
    """Test quick_add_nutrition with name and macros."""
    with (
        patch.object(MealDefinitions, "get", return_value=_make_meals()),
        patch.object(QuickAdd, "add", return_value=_make_daily_log()),
    ):
        result = await app_with_nutrition.call_tool(
            "quick_add_nutrition",
            {
                "date": "2024-01-15",
                "meal": "LUNCH",
                "name": "Smoothie",
                "calories": 350,
                "protein": 20,
            },
        )
    data = json.loads(result[0].text)
    assert data["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_update_food_log(app_with_nutrition, mock_garmin_client):
    """Test update_food_log updates an existing entry."""
    with (
        patch.object(MealDefinitions, "get", return_value=_make_meals()),
        patch.object(FoodLog, "update", return_value=_make_daily_log()),
    ):
        result = await app_with_nutrition.call_tool(
            "update_food_log",
            {
                "date": "2024-01-15",
                "log_id": "abc123",
                "meal": "BREAKFAST",
                "food_id": "5367",
                "serving_id": "54047",
                "source": "FATSECRET",
                "serving_qty": 2,
            },
        )
    data = json.loads(result[0].text)
    assert data["date"] == "2024-01-15"


@pytest.mark.asyncio
async def test_remove_food_log(app_with_nutrition, mock_garmin_client):
    """Test remove_food_log removes entries."""
    with patch.object(FoodLog, "remove", return_value=None):
        result = await app_with_nutrition.call_tool(
            "remove_food_log",
            {"date": "2024-01-15", "log_ids": "abc123,def456"},
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["removed_count"] == 2


@pytest.mark.asyncio
async def test_add_favorite_food(app_with_nutrition, mock_garmin_client):
    """Test add_favorite_food adds to favorites."""
    with patch.object(FavoriteFoods, "add", return_value=None):
        result = await app_with_nutrition.call_tool(
            "add_favorite_food",
            {"food_id": "5367", "serving_id": "54047", "source": "FATSECRET", "serving_qty": 1},
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"
    assert data["food_id"] == "5367"


@pytest.mark.asyncio
async def test_remove_favorite_food(app_with_nutrition, mock_garmin_client):
    """Test remove_favorite_food removes from favorites."""
    with patch.object(FavoriteFoods, "remove", return_value=None):
        result = await app_with_nutrition.call_tool(
            "remove_favorite_food", {"food_id": "5367"}
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_create_custom_food(app_with_nutrition, mock_garmin_client):
    """Test create_custom_food creates a new custom food."""
    with patch.object(CustomFood, "create", return_value=_make_custom_food_item()):
        result = await app_with_nutrition.call_tool(
            "create_custom_food",
            {
                "food_name": "Test Food",
                "serving_unit": "g",
                "number_of_units": 100,
                "calories": 250,
                "protein": 20,
            },
        )
    data = json.loads(result[0].text)
    assert data["food_id"] == "custom2"
    assert data["food_name"] == "Test Food"


@pytest.mark.asyncio
async def test_delete_custom_food(app_with_nutrition, mock_garmin_client):
    """Test delete_custom_food deletes a custom food."""
    with patch.object(CustomFood, "delete", return_value=None):
        result = await app_with_nutrition.call_tool(
            "delete_custom_food", {"food_id": "custom1"}
        )
    data = json.loads(result[0].text)
    assert data["status"] == "success"


# ── CUSTOM MEAL TESTS ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_custom_meals(app_with_nutrition, mock_garmin_client):
    """Test list_custom_meals returns meal list."""
    with patch.object(CustomMeal, "list", return_value=_make_custom_meal_list()):
        result = await app_with_nutrition.call_tool(
            "list_custom_meals", {}
        )
    data = json.loads(result[0].text)
    assert len(data["custom_meals"]) == 1
    assert data["has_more"] is False


@pytest.mark.asyncio
async def test_create_custom_meal(app_with_nutrition, mock_garmin_client):
    """Test create_custom_meal creates a new meal combo."""
    with patch.object(CustomMeal, "create", return_value=_make_custom_meal_detail()):
        result = await app_with_nutrition.call_tool(
            "create_custom_meal",
            {
                "name": "Test Meal",
                "foods_json": "[{\"foodId\": \"5367\"}]",
            },
        )
    data = json.loads(result[0].text)
    assert data["custom_meal_id"] == 12345
    assert data["name"] == "Test Meal"
    assert data["food_count"] == 1


@pytest.mark.asyncio
async def test_create_custom_meal_invalid_json(app_with_nutrition, mock_garmin_client):
    """Test create_custom_meal with invalid JSON returns error."""
    result = await app_with_nutrition.call_tool(
        "create_custom_meal",
        {"name": "Bad", "foods_json": "not json"},
    )
    assert "not valid JSON" in result[0].text


# ── ERROR HANDLING ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_nutrition_log_error(app_with_nutrition, mock_garmin_client):
    """Test error handling returns error string."""
    with patch.object(DailyNutritionLog, "get", side_effect=Exception("API down")):
        result = await app_with_nutrition.call_tool(
            "get_nutrition_log", {"date": "2024-01-15"}
        )
    assert "Error" in result[0].text
    assert "API down" in result[0].text


@pytest.mark.asyncio
async def test_log_food_bad_meal_name(app_with_nutrition, mock_garmin_client):
    """Test log_food with invalid meal name returns error."""
    with patch.object(MealDefinitions, "get", return_value=_make_meals()):
        result = await app_with_nutrition.call_tool(
            "log_food",
            {
                "date": "2024-01-15",
                "meal": "BRUNCH",
                "food_id": "5367",
                "serving_id": "54047",
                "source": "FATSECRET",
            },
        )
    assert "Error" in result[0].text
    assert "Unknown meal" in result[0].text


@pytest.mark.asyncio
async def test_remove_food_log_empty_ids(app_with_nutrition, mock_garmin_client):
    """Test remove_food_log with empty log_ids returns error."""
    result = await app_with_nutrition.call_tool(
        "remove_food_log", {"date": "2024-01-15", "log_ids": ""}
    )
    assert "no log_ids" in result[0].text
