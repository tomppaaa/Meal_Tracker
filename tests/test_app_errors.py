import pytest

import db
import users
import meals
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as session:
            session['csrf_token'] = 'test-csrf-token'
        yield client


def csrf_data(client, data):
    return {**data, 'csrf_token': 'test-csrf-token'}


def test_register_error_renders_form(client):
    response = client.post(
        '/create',
        data=csrf_data(client, {'username': 'alice', 'password1': 'abc', 'password2': 'def'}),
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b'Create account' in response.data
    assert b'Passwords do not match' in response.data


def test_login_error_renders_form(client):
    response = client.post(
        '/login',
        data=csrf_data(client, {'username': 'no-such-user', 'password': 'wrong'}),
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert b'Sign in' in response.data
    assert b'Invalid username or password' in response.data


def test_csrf_token_is_required_and_rotated_after_login(client):
    with app.app_context():
        username = 'csrf-login-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        users.create_user(username, 'secret123')

    missing_token_response = client.post(
        '/login',
        data={'username': username, 'password': 'secret123'},
    )
    assert missing_token_response.status_code == 403

    with client.session_transaction() as session:
        old_token = session['csrf_token']
    response = client.post(
        '/login',
        data=csrf_data(client, {'username': username, 'password': 'secret123'}),
    )

    assert response.status_code == 302
    with client.session_transaction() as session:
        assert session['csrf_token'] != old_token

    with app.app_context():
        user = users.get_user_by_username(username)
        users.delete_user(user['id'])


def test_meal_type_search_filters_results(client):
    with app.app_context():
        username = 'search-meal-type-user'
        user = users.get_user_by_username(username)
        if user:
            users.delete_user(user['id'])


def test_diet_schema_initialization_preserves_existing_diets():
    with app.app_context():
        db.execute(
            "INSERT OR REPLACE INTO diets (id, name) VALUES (?, ?)",
            (99, 'Custom diet'),
        )

        db.ensure_meals_schema()

        diets = {diet['id']: diet['name'] for diet in db.query("SELECT id, name FROM diets")}
        assert diets[99] == 'Custom diet'
        assert diets[1] == 'Keto'
        assert diets[4] == 'High-protein'

        db.execute("DELETE FROM diets WHERE id = ?", (99,))


def test_meal_type_schema_initialization_preserves_existing_types(client):
    with app.app_context():
        db.execute(
            "INSERT OR REPLACE INTO meal_types (id, name) VALUES (?, ?)",
            (99, 'Brunch'),
        )

        db.ensure_meals_schema()

        meal_types = {item['id']: item['name'] for item in db.get_meal_types()}
        assert meal_types == {
            1: 'Breakfast',
            2: 'Lunch',
            3: 'Dinner',
            4: 'Snack',
            5: 'Evening meal',
            99: 'Brunch',
        }
        db.execute("DELETE FROM meal_types WHERE id = ?", (99,))

    add_meal_response = client.get('/meal')
    assert b'Breakfast' in add_meal_response.data
    assert b'Evening meal' in add_meal_response.data

    search_response = client.get('/')
    assert b'name="meal_types" value="Breakfast"' in search_response.data


def test_profile_meals_shows_statistics_by_type_and_diet(client):
    with app.app_context():
        username = 'profile-stats-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')
        meals.create_meal(user_id=user_id, name='Stats breakfast', meal_type='Breakfast', calories=300, price=4, diet_tags='2')
        meals.create_meal(user_id=user_id, name='Stats dinner', meal_type='Dinner', calories=700, price=8, diet_tags='1,4')

    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['user_name'] = username

    response = client.get('/profile/meals')

    assert response.status_code == 200
    assert b"By meal type" in response.data
    assert b"By diet" in response.data
    assert b"Breakfast" in response.data
    assert b"Vegan" in response.data
    assert b"2" in response.data

    with app.app_context():
        users.delete_user(user_id)

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


def test_profile_shows_overview_and_links_to_separate_account_settings(client):
    with app.app_context():
        username = 'profile-settings-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')

    with client.session_transaction() as session:
        session['user_id'] = user_id
        session['user_name'] = username

    profile_response = client.get('/profile')
    assert profile_response.status_code == 200
    assert b'Account settings' in profile_response.data
    assert b'Change username' not in profile_response.data
    assert b'Change password' not in profile_response.data
    assert b'Delete account' not in profile_response.data

    settings_response = client.get('/profile/settings')
    assert settings_response.status_code == 200
    assert b'Change username' in settings_response.data
    assert b'Change password' in settings_response.data
    assert b'Delete account' in settings_response.data

    invalid_settings_submissions = [
        (
            '/profile/change-username',
            {'new_username': 'new-profile-name', 'password': 'wrong'},
            b'Password is incorrect.',
        ),
        (
            '/profile/change-password',
            {
                'current_password': 'wrong',
                'new_password': 'new-secret',
                'confirm_password': 'new-secret',
            },
            b'Current password is incorrect.',
        ),
        (
            '/profile/delete-account',
            {'password': 'wrong'},
            b'Password is incorrect.',
        ),
    ]
    for endpoint, form_data, error_message in invalid_settings_submissions:
        response = client.post(endpoint, data=csrf_data(client, form_data))
        assert response.status_code == 200
        assert b'Account settings' in response.data
        assert error_message in response.data

    with app.app_context():
        users.delete_user(user_id)


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


def test_user_fields_reject_values_longer_than_their_limits():
    with app.app_context():
        with pytest.raises(ValueError, match='Username cannot be longer than 50 characters'):
            users.create_user('u' * 51, 'secret123')

        with pytest.raises(ValueError, match='Password cannot be longer than 128 characters'):
            users.create_user('long-password-user', 'p' * 129)


def test_create_and_update_meal_reject_long_meal_types():
    with app.app_context():
        username = 'long-meal-type-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')

        with pytest.raises(ValueError, match='Meal type cannot be longer than 50 characters'):
            meals.create_meal(user_id=user_id, name='Meal', meal_type='t' * 51)

        meal_id = meals.create_meal(user_id=user_id, name='Meal', meal_type='Dinner')
        with pytest.raises(ValueError, match='Meal type cannot be longer than 50 characters'):
            meals.update_meal(meal_id, meal_type='t' * 51)

        assert meals.get_meal_by_id(meal_id)['meal_type'] == 'Dinner'
        users.delete_user(user_id)


@pytest.mark.parametrize(
    ('field', 'value', 'expected_error'),
    [
        ('calories', '-1', 'Calories must be a valid number greater than or equal to 0.'),
        ('calories', '1.5', 'Calories must be a valid number greater than or equal to 0.'),
        ('protein', '-0.1', 'Protein must be a valid number greater than or equal to 0.'),
        ('carbs', 'not-a-number', 'Carbs must be a valid number greater than or equal to 0.'),
        ('fat', '-2', 'Fat must be a valid number greater than or equal to 0.'),
        ('price', 'NaN', 'Price must be a valid number greater than or equal to 0.'),
        ('price', '-0.01', 'Price must be a valid number greater than or equal to 0.'),
    ],
)
@pytest.mark.parametrize('route', ['add', 'edit'])
def test_meal_routes_reject_invalid_numeric_values(client, field, value, expected_error, route):
    with app.app_context():
        username = 'invalid-meal-number-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')
        meal_id = meals.create_meal(user_id=user_id, name='Existing meal', meal_type='Dinner')

    with client.session_transaction() as session:
        session['user_id'] = user_id

    form_data = {'name': 'New meal', 'meal_type': 'Dinner', field: value}
    path = '/add_meal' if route == 'add' else f'/meal/{meal_id}/edit'
    response = client.post(path, data=csrf_data(client, form_data))

    assert response.status_code == 200
    assert expected_error.encode() in response.data

    with app.app_context():
        if route == 'add':
            user_meals = meals.get_meals_by_user(user_id)
            assert len(user_meals) == 1
            assert user_meals[0]['name'] == 'Existing meal'
        else:
            assert meals.get_meal_by_id(meal_id)['name'] == 'Existing meal'
        users.delete_user(user_id)


def test_oversized_search_and_message_are_rejected(client):
    search_response = client.get('/', query_string={'query': 'q' * 1001})
    assert search_response.status_code == 400
    assert b'Search query cannot be longer than 1000 characters.' in search_response.data

    message_response = client.post(
        '/result',
        data=csrf_data(client, {'message': 'm' * 1001}),
    )
    assert message_response.status_code == 400
    assert b'Message cannot be longer than 1000 characters.' in message_response.data
    assert b'Message sent' not in message_response.data


@pytest.mark.parametrize('query_key, value', [('min_price', '-1'), ('max_price', 'not-a-number')])
def test_price_search_filters_reject_invalid_numbers(client, query_key, value):
    response = client.get('/', query_string={query_key: value})
    assert response.status_code == 400
    assert b'Price filters must be valid numbers greater than or equal to 0.' in response.data


def test_oversized_input_is_rejected_globally(client):
    response = client.get('/', query_string={'unused': 'x' * 10001})
    assert response.status_code == 400
    assert b'Input values cannot be longer than 10000 characters.' in response.data


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
        data=csrf_data(client, {'name': 'a' * 51, 'meal_type': 'Dinner'}),
    )

    assert response.status_code == 200
    assert b'Meal name cannot be longer than 50 characters.' in response.data

    with app.app_context():
        assert meals.get_meals_by_user(user_id) == []
        users.delete_user(user_id)


@pytest.mark.parametrize(
    ('name', 'error'),
    [
        (' Meal name', 'Meal name cannot start with whitespace.'),
        ('   ', 'Meal name is required.'),
    ],
)
def test_add_meal_route_rejects_invalid_names(client, name, error):
    with app.app_context():
        username = 'add-route-invalid-name-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')

    with client.session_transaction() as session:
        session['user_id'] = user_id

    response = client.post(
        '/add_meal',
        data=csrf_data(client, {'name': name, 'meal_type': 'Dinner'}),
    )

    assert response.status_code == 200
    assert error.encode() in response.data

    with app.app_context():
        assert meals.get_meals_by_user(user_id) == []
        users.delete_user(user_id)


@pytest.mark.parametrize(
    ('name', 'error'),
    [
        (' Meal name', 'Meal name cannot start with whitespace.'),
        ('   ', 'Meal name cannot be empty.'),
    ],
)
def test_edit_meal_route_rejects_invalid_names(client, name, error):
    with app.app_context():
        username = 'edit-route-invalid-name-user'
        old_user = users.get_user_by_username(username)
        if old_user:
            users.delete_user(old_user['id'])
        user_id = users.create_user(username, 'secret123')
        meal_id = meals.create_meal(user_id=user_id, name='Valid meal', meal_type='Dinner')

    with client.session_transaction() as session:
        session['user_id'] = user_id

    response = client.post(
        f'/meal/{meal_id}/edit',
        data=csrf_data(client, {'name': name, 'meal_type': 'Dinner'}),
    )

    assert response.status_code == 200
    assert error.encode() in response.data
    assert name.encode() in response.data

    with app.app_context():
        assert meals.get_meal_by_id(meal_id)['name'] == 'Valid meal'
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

    empty_response = client.post(f'/meal/{meal_id}/comments', data=csrf_data(client, {'comment': '   '}))
    assert empty_response.status_code == 200
    assert b'Comment cannot be empty.' in empty_response.data

    response = client.post(
        f'/meal/{meal_id}/comments',
        data=csrf_data(client, {'comment': 'Tasty and easy to make.'}),
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
        data=csrf_data(client, {'reply': 'Here is the recipe.'}),
    )
    assert forbidden_response.status_code == 403

    with client.session_transaction() as session:
        session['user_id'] = owner_id
        session['user_name'] = owner_name
    response = client.post(
        f'/meal/{meal_id}/comments/{comment_id}/reply',
        data=csrf_data(client, {'reply': 'Here is the recipe.'}),
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


def test_opening_comment_and_reply_messages_marks_them_read(client):
    with app.app_context():
        owner_name = 'notification-owner-user'
        commenter_name = 'notification-commenter-user'
        for username in (owner_name, commenter_name):
            old_user = users.get_user_by_username(username)
            if old_user:
                users.delete_user(old_user['id'])
        owner_id = users.create_user(owner_name, 'secret123')
        commenter_id = users.create_user(commenter_name, 'secret123')
        meal_id = meals.create_meal(user_id=owner_id, name='Notification meal', meal_type='Lunch')

    with client.session_transaction() as session:
        session['user_id'] = commenter_id
        session['user_name'] = commenter_name

    comment_response = client.post(
        f'/meal/{meal_id}/comments',
        data=csrf_data(client, {'comment': 'A new comment'}),
    )
    assert comment_response.status_code == 302

    with app.app_context():
        notifications = db.get_notifications(owner_id)
        assert len(notifications) == 1
        assert notifications[0]['notification_type'] == 'new_comment'
        assert notifications[0]['is_read'] == 0
        comment_id = notifications[0]['comment_id']

    unauthorized_open_response = client.get(
        f"/messages/{notifications[0]['id']}/open",
    )
    assert unauthorized_open_response.status_code == 404
    with app.app_context():
        assert db.get_unread_notification_count(owner_id) == 1

    with client.session_transaction() as session:
        session['user_id'] = owner_id
        session['user_name'] = owner_name

    inbox_response = client.get('/messages')
    assert inbox_response.status_code == 200
    assert b'notification-commenter-user' in inbox_response.data
    assert b'Messages (1)' in inbox_response.data
    assert b'Mark as read' not in inbox_response.data

    open_response = client.get(f"/messages/{notifications[0]['id']}/open")
    assert open_response.status_code == 302
    assert open_response.headers['Location'].endswith(f'/meal/{meal_id}#comment-{comment_id}')
    with app.app_context():
        assert db.get_unread_notification_count(owner_id) == 0

    reply_response = client.post(
        f'/meal/{meal_id}/comments/{comment_id}/reply',
        data=csrf_data(client, {'reply': 'A reply to your comment'}),
    )
    assert reply_response.status_code == 302

    with client.session_transaction() as session:
        session['user_id'] = commenter_id
        session['user_name'] = commenter_name

    reply_inbox_response = client.get('/messages')
    assert reply_inbox_response.status_code == 200
    assert b'replied to your comment' in reply_inbox_response.data
    assert b'Messages (1)' in reply_inbox_response.data
    with app.app_context():
        reply_notifications = db.get_notifications(commenter_id)
        assert len(reply_notifications) == 1
        assert reply_notifications[0]['notification_type'] == 'comment_reply'
        assert reply_notifications[0]['is_read'] == 0

    open_reply_response = client.get(f"/messages/{reply_notifications[0]['id']}/open")
    assert open_reply_response.status_code == 302
    assert open_reply_response.headers['Location'].endswith(
        f"/meal/{meal_id}#comment-{reply_notifications[0]['comment_id']}"
    )
    with app.app_context():
        assert db.get_unread_notification_count(commenter_id) == 0
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

    invalid_response = client.post(f'/meal/{meal_id}/rating', data=csrf_data(client, {'rating': '6'}))
    assert invalid_response.status_code == 200
    assert b'Choose a rating from 1 to 5 stars.' in invalid_response.data

    response = client.post(f'/meal/{meal_id}/rating', data=csrf_data(client, {'rating': '4'}), follow_redirects=True)
    assert response.status_code == 200
    assert b'4.0/5 stars (1 ratings)' in response.data
    assert b'class="rating-stars"' in response.data
    assert b'Save rating' not in response.data

    client.post(f'/meal/{meal_id}/rating', data=csrf_data(client, {'rating': '5'}))
    with app.app_context():
        rating = db.get_meal_rating_summary(meal_id, user_id)
        assert rating['average'] == 5.0
        assert rating['count'] == 1
        assert rating['user_rating'] == 5
        users.delete_user(user_id)


def test_homepage_displays_current_meal_rating_summary(client):
    with app.app_context():
        usernames = ('homepage-rating-owner', 'homepage-rating-voter-one', 'homepage-rating-voter-two')
        for username in usernames:
            old_user = users.get_user_by_username(username)
            if old_user:
                users.delete_user(old_user['id'])

        owner_id = users.create_user(usernames[0], 'secret123')
        voter_one_id = users.create_user(usernames[1], 'secret123')
        voter_two_id = users.create_user(usernames[2], 'secret123')
        rated_meal_id = meals.create_meal(
            user_id=owner_id,
            name='Homepage rated meal',
            meal_type='Dinner',
        )
        unrated_meal_id = meals.create_meal(
            user_id=owner_id,
            name='Homepage unrated meal',
            meal_type='Lunch',
        )
        db.save_meal_rating(rated_meal_id, voter_one_id, 3)
        db.save_meal_rating(rated_meal_id, voter_two_id, 5)
        added_at = meals.get_meal_by_id(rated_meal_id)['created_at']

    response = client.get('/')

    assert response.status_code == 200
    assert b'Rating:</strong> 4.0/5 (2 ratings)' in response.data
    assert b'Rating:</strong> 0/5 (0 ratings)' in response.data
    assert f'Added:</strong> {added_at}'.encode() in response.data

    with app.app_context():
        users.delete_user(owner_id)
        users.delete_user(voter_one_id)
        users.delete_user(voter_two_id)
