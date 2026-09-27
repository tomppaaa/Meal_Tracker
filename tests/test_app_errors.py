import pytest

import db
import users
import meals
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_register_error_renders_form(client):
    response = client.post(
        '/create',
        data={'username': 'alice', 'password1': 'abc', 'password2': 'def'},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b'Create account' in response.data
    assert b'Passwords do not match' in response.data


def test_login_error_renders_form(client):
    response = client.post(
        '/login',
        data={'username': 'no-such-user', 'password': 'wrong'},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b'Sign in' in response.data
    assert b'Invalid username or password' in response.data


def test_meal_type_search_filters_results(client):
    with app.app_context():
        username = 'search-meal-type-user'
        user = users.get_user_by_username(username)
        if user:
            users.delete_user(user['id'])

        user_id = users.create_user(username, 'secret123')
        meals.create_meal(user_id=user_id, name='Breakfast search meal', meal_type='Breakfast', calories=200, protein=10, carbs=20, fat=5, price=5.0)
        meals.create_meal(user_id=user_id, name='Dinner search meal', meal_type='Dinner', calories=400, protein=20, carbs=30, fat=15, price=9.5)

    response = client.get('/?meal_types=Breakfast')

    assert response.status_code == 200
    assert b'Breakfast search meal' in response.data
    assert b'Dinner search meal' not in response.data

    with app.app_context():
        user = users.get_user_by_username(username)
        if user:
            users.delete_user(user['id'])


def test_meal_name_maximum_length_is_validated_before_insert(client):
    with app.app_context():
        username = 'meal-name-length-user'
        user = users.get_user_by_username(username)
        if user:
            users.delete_user(user['id'])

        user_id = users.create_user(username, 'secret123')
        meals.create_meal(user_id=user_id, name='a' * 50, meal_type='Dinner')

        with pytest.raises(ValueError, match='50 characters'):
            meals.create_meal(user_id=user_id, name='a' * 51, meal_type='Dinner')

        user_meals = meals.get_meals_by_user(user_id)
        assert len(user_meals) == 1
        assert len(user_meals[0]['name']) == 50

        users.delete_user(user_id)


def test_add_meal_route_rejects_name_longer_than_50_characters(client):
    with app.app_context():
        username = 'add-route-length-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')

    with client.session_transaction() as session:
        session['user_id'] = user_id

    response = client.post(
        '/add_meal',
        data={'name': 'a' * 51, 'meal_type': 'Dinner'},
    )

    assert response.status_code == 200
    assert b'Meal name cannot be longer than 50 characters.' in response.data

    with app.app_context():
        assert meals.get_meals_by_user(user_id) == []
        users.delete_user(user_id)
