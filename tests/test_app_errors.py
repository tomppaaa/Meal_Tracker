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


def test_meal_comments_can_be_added_and_empty_comments_are_rejected(client):
    with app.app_context():
        username = 'meal-comment-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')
        meal_id = meals.create_meal(user_id=user_id, name='Comment meal', meal_type='Lunch')

    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['user_name'] = username

    empty_response = client.post(f'/meal/{meal_id}/comments', data={'comment': '   '})
    assert empty_response.status_code == 200
    assert b'Comment cannot be empty.' in empty_response.data

    response = client.post(
        f'/meal/{meal_id}/comments',
        data={'comment': 'Tasty and easy to make.'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Tasty and easy to make.' in response.data
    assert b'meal-comment-user' in response.data

    with app.app_context():
        comments = db.get_meal_comments(meal_id)
        assert len(comments) == 1
        assert comments[0]['body'] == 'Tasty and easy to make.'
        users.delete_user(user_id)


def test_only_meal_owner_can_reply_to_comments(client):
    with app.app_context():
        owner_name = 'meal-owner-user'
        commenter_name = 'meal-commenter-user'
        for username in (owner_name, commenter_name):
            old_user = users.get_user_by_username(username)
            if old_user:
                users.delete_user(old_user['id'])
        owner_id = users.create_user(owner_name, 'secret123')
        commenter_id = users.create_user(commenter_name, 'secret123')
        meal_id = meals.create_meal(user_id=owner_id, name='Reply meal', meal_type='Lunch')
        comment_id = db.add_meal_comment(meal_id, commenter_name, 'Please share the recipe.')

    with client.session_transaction() as session:
        session['user_id'] = commenter_id
        session['user_name'] = commenter_name
    forbidden_response = client.post(
        f'/meal/{meal_id}/comments/{comment_id}/reply',
        data={'reply': 'Here is the recipe.'},
    )
    assert forbidden_response.status_code == 403

    with client.session_transaction() as session:
        session['user_id'] = owner_id
        session['user_name'] = owner_name
    response = client.post(
        f'/meal/{meal_id}/comments/{comment_id}/reply',
        data={'reply': 'Here is the recipe.'},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b'Here is the recipe.' in response.data
    assert b'<summary>Reply</summary>' in response.data

    with app.app_context():
        replies = db.query(
            "SELECT * FROM meal_comments WHERE parent_comment_id = ?",
            (comment_id,),
        )
        assert len(replies) == 1
        users.delete_user(owner_id)
        users.delete_user(commenter_id)


def test_meal_rating_can_be_saved_and_updated(client):
    with app.app_context():
        username = 'meal-rating-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')
        meal_id = meals.create_meal(user_id=user_id, name='Rated meal', meal_type='Dinner')

    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['user_name'] = username

    invalid_response = client.post(f'/meal/{meal_id}/rating', data={'rating': '6'})
    assert invalid_response.status_code == 200
    assert b'Choose a rating from 1 to 5 stars.' in invalid_response.data

    response = client.post(f'/meal/{meal_id}/rating', data={'rating': '4'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'4.0/5 stars (1 ratings)' in response.data
    assert b'class="rating-stars"' in response.data
    assert b'Save rating' not in response.data

    client.post(f'/meal/{meal_id}/rating', data={'rating': '5'})
    with app.app_context():
        rating = db.get_meal_rating_summary(meal_id, user_id)
        assert rating['average'] == 5.0
        assert rating['count'] == 1
        assert rating['user_rating'] == 5
        users.delete_user(user_id)
